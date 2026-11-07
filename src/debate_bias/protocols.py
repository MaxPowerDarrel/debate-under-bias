"""Debate and consultancy transcript generation.

Both protocols have the arguer model argue for an assigned answer over several rounds.
Each turn goes through the same steps:

1. Build the prompt from the versioned files in `prompts/<role>_v1/`. The story comes
   first in the system prompt, and the transcript so far is in the user message.
2. Make one call through `LLM.call`, so the turn is cached, logged, and counted against
   the budget.
3. Keep only the text inside `<argument>` tags. Reset any `v_quote`/`u_quote` tags the
   arguer wrote, apply the word limit, then verify quotes against the story.

**Debate:** the turns are simultaneous. In round r both debaters see only rounds 1 to
r-1, so neither one sees the other's current argument.

**Consultancy:** one consultant argues alone for all rounds. `run_consultancies` runs it
on both answers so the condition stays balanced.

Transcripts store turns by side (`correct` or `distractor`), not by debater letter. Each
arguer reads the transcript as "your argument" and "your opponent's argument". The
judge's Debater A/B labels and the order swap are added in `judge.py`.

**Word limit:** words are whitespace-separated tokens, with quote tags not counted. An
argument over the limit is cut at the limit. If the cut falls inside a quote, the whole
quote is dropped, so the judge never sees a shortened quote. There is no minimum length
and no resampling, so each turn is exactly one cached call.

**Refusals and format errors:** a refusal, or a reply with no `<argument>…</argument>`,
is recorded on the turn and ends the transcript. Nothing is retried.
"""

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from string import Template

from .data import Question
from .llm import LLM
from .quotes import reset_tags, verify

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
DEBATER_PROMPTS = "debater_v1"
CONSULTANT_PROMPTS = "consultant_v1"
SIDES = ("correct", "distractor")
TRUNCATED_MARK = "[truncated]"

# Round 1 uses the first request file, round 2 the second, and so on; the last repeats.
_REQUESTS = {DEBATER_PROMPTS: ("opening", "second", "later"), CONSULTANT_PROMPTS: ("opening", "later")}
_ARGUMENT = re.compile(r"<argument>(.*?)</argument>", re.DOTALL)
_TOKEN = re.compile(r"\S+")
_QUOTE_TAG = re.compile(r"</?quote>")


@dataclass(frozen=True)
class ArguerSettings:
    model: str
    effort: str
    max_tokens: int
    rounds: int
    debate_words: int
    consultancy_words: int

    @classmethod
    def from_config(cls, config: dict) -> "ArguerSettings":
        protocol = config["protocol"]
        return cls(
            model=config["models"]["arguer"],
            effort=config["effort"]["arguer"],
            max_tokens=config["max_tokens"]["arguer"],
            rounds=protocol["rounds"],
            debate_words=protocol["debate_words_per_turn"],
            consultancy_words=protocol["consultancy_words_per_turn"],
        )


@dataclass
class Turn:
    round: int
    side: str
    status: str  # "ok", "refused", or "format_error"
    argument: str  # What the judge sees: word-limited, quotes tagged v_quote or u_quote
    word_count: int  # Before truncation
    truncated: bool
    verified_quotes: list[str]
    unverified_quotes: list[str]
    raw: str  # The model's full text reply
    stop_reason: str
    cache_key: str


@dataclass
class Transcript:
    protocol: str  # "debate" or "consultancy"
    question_id: str
    article_id: str
    answers: dict[str, str]  # side -> answer text
    consultant_side: str | None  # Which side the consultant argued; None for debate
    prompts: str  # Prompt version, such as "debater_v1"
    turns: list[Turn] = field(default_factory=list)

    @property
    def status(self) -> str:
        return next((t.status for t in self.turns if t.status != "ok"), "complete")

    def to_dict(self) -> dict:
        return {**asdict(self), "status": self.status}


def count_words(text: str) -> int:
    return sum(1 for token in _TOKEN.findall(text) if _QUOTE_TAG.sub("", token))


def apply_word_limit(text: str, limit: int) -> tuple[str, int, bool]:
    """Return the text cut to `limit` words, its original word count, and whether it was cut."""
    total = count_words(text)
    if total <= limit:
        return text, total, False
    count, cut = 0, 0
    for match in _TOKEN.finditer(text):
        if _QUOTE_TAG.sub("", match.group()):
            if count == limit:
                break
            count += 1
        cut = match.end()  # Tag-only tokens after the last word are kept, such as a lone </quote>
    kept = text[:cut]
    opened = kept.rfind("<quote>")
    if opened > kept.rfind("</quote>"):
        kept = kept[:opened]  # The cut fell inside a quote, so drop the whole quote
    return f"{kept.rstrip()} {TRUNCATED_MARK}", total, True


def load_prompts(version: str) -> dict[str, Template]:
    return {p.stem: Template(p.read_text().strip()) for p in (PROMPTS_DIR / version).glob("*.md")}


def render_history(rounds: list[dict[str, Turn]], viewer: str) -> str:
    """Show earlier rounds from `viewer`'s point of view, with their own argument first."""
    if not rounds:
        return ""
    parts = []
    for number, round_turns in enumerate(rounds, start=1):
        parts.append(f"Round {number}")
        for side in sorted(round_turns, key=lambda s: s != viewer):
            label = "Your argument" if side == viewer else "Your opponent's argument"
            parts.append(f"{label}:\n{round_turns[side].argument}")
    body = "\n\n".join(parts)
    return f"Here is the transcript so far:\n\n<transcript>\n{body}\n</transcript>\n\n"


def _other(side: str) -> str:
    return SIDES[1 - SIDES.index(side)]


def take_turn(
    llm: LLM,
    settings: ArguerSettings,
    version: str,
    question: Question,
    answers: dict[str, str],
    side: str,
    rounds: list[dict[str, Turn]],
    word_limit: int,
    tag: str,
) -> Turn:
    prompts = load_prompts(version)
    requests = _REQUESTS[version]
    round_number = len(rounds) + 1
    values = {
        "story": question.story,
        "question": question.question,
        "your_answer": answers[side],
        "other_answer": answers[_other(side)],
        "word_limit": word_limit,
    }
    request = prompts[requests[min(round_number, len(requests)) - 1]].substitute(values)
    user = prompts["user"].substitute(values, transcript=render_history(rounds, side), request=request)
    response = llm.call(
        settings.model,
        prompts["system"].substitute(values),
        [{"role": "user", "content": user}],
        max_tokens=settings.max_tokens,
        effort=settings.effort,
        tag=f"{tag}:{side}:r{round_number}",
    )

    def failed(status: str) -> Turn:
        return Turn(round_number, side, status, "", 0, False, [], [], response.text,
                    response.stop_reason, response.cache_key)

    if response.stop_reason == "refusal":
        return failed("refused")
    match = _ARGUMENT.search(response.text)
    if not match:
        return failed("format_error")
    limited, word_count, truncated = apply_word_limit(reset_tags(match.group(1).strip()), word_limit)
    checked = verify(limited, question.story)
    return Turn(round_number, side, "ok", checked.text, word_count, truncated, checked.verified,
                checked.unverified, response.text, response.stop_reason, response.cache_key)


def _answers(question: Question) -> dict[str, str]:
    return {"correct": question.correct, "distractor": question.distractor}


def run_debate(llm: LLM, settings: ArguerSettings, question: Question) -> Transcript:
    transcript = Transcript("debate", question.question_id, question.article_id,
                            _answers(question), None, DEBATER_PROMPTS)
    rounds: list[dict[str, Turn]] = []
    for _ in range(settings.rounds):
        # Both turns are built from the same earlier rounds, so they are simultaneous.
        new = {
            side: take_turn(llm, settings, DEBATER_PROMPTS, question, transcript.answers, side,
                            rounds, settings.debate_words, f"debate:{question.question_id}")
            for side in SIDES
        }
        rounds.append(new)
        transcript.turns.extend(new.values())
        if transcript.status != "complete":
            break
    return transcript


def run_consultancy(llm: LLM, settings: ArguerSettings, question: Question, side: str) -> Transcript:
    transcript = Transcript("consultancy", question.question_id, question.article_id,
                            _answers(question), side, CONSULTANT_PROMPTS)
    rounds: list[dict[str, Turn]] = []
    for _ in range(settings.rounds):
        turn = take_turn(llm, settings, CONSULTANT_PROMPTS, question, transcript.answers, side,
                         rounds, settings.consultancy_words, f"consultancy:{question.question_id}")
        rounds.append({side: turn})
        transcript.turns.append(turn)
        if turn.status != "ok":
            break
    return transcript


def run_consultancies(llm: LLM, settings: ArguerSettings, question: Question) -> list[Transcript]:
    """Run consultancy once for each answer, so the condition is balanced."""
    return [run_consultancy(llm, settings, question, side) for side in SIDES]
