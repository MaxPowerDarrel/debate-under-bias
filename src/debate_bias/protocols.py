"""Debate and consultancy transcript generation.

Both protocols have the arguer model argue for an assigned answer over several rounds.
Each turn goes through the same steps:

1. Build the prompt from the versioned files in `prompts/<version>/`. The versions come
   from the config's `prompts.debater` and `prompts.consultant` settings. The story comes
   first in the system prompt, and the transcript so far is in the user message.
2. Make the call through `LLM.call`, so the turn is cached, logged, and counted against
   the budget.
3. Keep only the text inside `<argument>` tags. Reset any `v_quote`/`u_quote` tags the
   arguer wrote, apply the word limit, then verify quotes against the story.

**Debate:** the turns are simultaneous. In round r both debaters see only rounds 1 to
r-1, so neither one sees the other's current argument.

**Consultancy:** one consultant argues alone for all rounds. `run_consultancies` runs it
on both answers so the condition stays balanced.

**Informed arguers:** with `biased=True`, both protocols use the informed prompt versions
(`prompts.debater_informed` and `prompts.consultant_informed`). These are the v2 prompts plus
one section that tells the arguer the biased judge's rule. The transcript is marked
`biased`, so `judge.py` judges it with the biased judge.

Transcripts store turns by side (`correct` or `distractor`), not by debater letter. Each
arguer reads the transcript as "your argument" and "your opponent's argument". The
judge's Debater A/B labels and the order swap are added in `judge.py`.

**Word limit:** there are two numbers, as in Khan et al. The prompt asks for the target
(`*_target_words`, such as 100), and the code enforces the hard limit
(`*_words_per_turn`, such as 150), which the prompt doesn't state. Words are
whitespace-separated tokens, with quote tags not counted. An argument over the hard limit
is cut at the limit. If the cut falls inside a quote, the whole quote is dropped, so the
judge never sees a shortened quote. There is no minimum length and no resampling for
length.

**Refusals and format errors:** a refusal, or a reply with no `<argument>…</argument>`,
is retried once with `sample=1`, which gives the retry its own cache key and log line.
The failed first attempt is kept in `Turn.attempts`. If the retry also fails, the turn
keeps its `refused` or `format_error` status and the transcript ends as a forfeit by that
side. `judge.py` scores a forfeit as a loss for the side that failed, without judging it.
"""

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from string import Template

from .data import Question
from .llm import LLM
from .quotes import reset_tags, verify

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
DEFAULT_DEBATER_PROMPTS = "debater_v1"
DEFAULT_CONSULTANT_PROMPTS = "consultant_v1"
REQUEST_FILES = ("opening", "second", "later")  # Consultants have no `second`, so use `later`
RETRIES = 1
SIDES = ("correct", "distractor")
TRUNCATED_MARK = "[truncated]"

_ARGUMENT = re.compile(r"<argument>(.*?)</argument>", re.DOTALL)
_TOKEN = re.compile(r"\S+")
_QUOTE_TAG = re.compile(r"</?quote>")


@dataclass(frozen=True)
class ArguerSettings:
    model: str
    effort: str
    max_tokens: int
    rounds: int
    debate_words: int  # Hard limits, enforced by truncation
    consultancy_words: int
    debate_target_words: int | None = None  # What the prompt asks for; None means the hard limit
    consultancy_target_words: int | None = None
    debater_prompts: str = DEFAULT_DEBATER_PROMPTS
    consultant_prompts: str = DEFAULT_CONSULTANT_PROMPTS
    debater_informed_prompts: str | None = None  # Used when the judge is biased
    consultant_informed_prompts: str | None = None

    def prompts_for(self, protocol: str, biased: bool) -> str:
        version = {
            ("debate", False): self.debater_prompts,
            ("consultancy", False): self.consultant_prompts,
            ("debate", True): self.debater_informed_prompts,
            ("consultancy", True): self.consultant_informed_prompts,
        }[protocol, biased]
        if version is None:
            raise ValueError("Biased conditions need prompts.debater_informed and prompts.consultant_informed")
        return version

    @classmethod
    def from_config(cls, config: dict) -> "ArguerSettings":
        protocol = config["protocol"]
        prompts = config.get("prompts", {})
        return cls(
            model=config["models"]["arguer"],
            effort=config["effort"]["arguer"],
            max_tokens=config["max_tokens"]["arguer"],
            rounds=protocol["rounds"],
            debate_words=protocol["debate_words_per_turn"],
            consultancy_words=protocol["consultancy_words_per_turn"],
            debate_target_words=protocol.get("debate_target_words"),
            consultancy_target_words=protocol.get("consultancy_target_words"),
            debater_prompts=prompts.get("debater", DEFAULT_DEBATER_PROMPTS),
            consultant_prompts=prompts.get("consultant", DEFAULT_CONSULTANT_PROMPTS),
            debater_informed_prompts=prompts.get("debater_informed"),
            consultant_informed_prompts=prompts.get("consultant_informed"),
        )


@dataclass
class Turn:
    round: int
    side: str
    status: str  # "ok", or "refused" or "format_error" if the retry also failed
    argument: str  # What the judge sees: word-limited, quotes tagged v_quote or u_quote
    word_count: int  # Before truncation
    truncated: bool
    verified_quotes: list[str]
    unverified_quotes: list[str]
    raw: str  # The model's full text reply
    stop_reason: str
    cache_key: str
    attempts: list[dict] = field(default_factory=list)  # Failed earlier attempts, if retried


@dataclass
class Transcript:
    protocol: str  # "debate" or "consultancy"
    question_id: str
    article_id: str
    answers: dict[str, str]  # side -> answer text
    consultant_side: str | None  # Which side the consultant argued; None for debate
    prompts: str  # Prompt version, such as "debater_v1"
    turns: list[Turn] = field(default_factory=list)
    biased: bool = False  # Informed arguers, to be judged by the biased judge

    @property
    def forfeits(self) -> dict[str, str]:
        """Each side whose turn still failed after the retry, with the reason."""
        return {t.side: t.status for t in self.turns if t.status != "ok"}

    @property
    def status(self) -> str:
        return "forfeit" if self.forfeits else "complete"

    def to_dict(self) -> dict:
        return {**asdict(self), "status": self.status, "forfeits": self.forfeits}

    @classmethod
    def from_dict(cls, record: dict) -> "Transcript":
        fields = {k: v for k, v in record.items() if k not in ("status", "forfeits", "turns")}
        return cls(**fields, turns=[Turn(**t) for t in record["turns"]])


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
    target_words: int | None,
    tag: str,
) -> Turn:
    prompts = load_prompts(version)
    requests = [name for name in REQUEST_FILES if name in prompts]
    round_number = len(rounds) + 1
    values = {
        "story": question.story,
        "question": question.question,
        "your_answer": answers[side],
        "other_answer": answers[_other(side)],
        "word_limit": word_limit,  # Used by v1 prompts, which state the hard limit
        "target_words": target_words or word_limit,
    }
    request = prompts[requests[min(round_number, len(requests)) - 1]].substitute(values)
    user = prompts["user"].substitute(values, transcript=render_history(rounds, side), request=request)
    failures = []
    for attempt in range(RETRIES + 1):
        response = llm.call(
            settings.model,
            prompts["system"].substitute(values),
            [{"role": "user", "content": user}],
            max_tokens=settings.max_tokens,
            effort=settings.effort,
            sample=attempt,
            tag=f"{tag}:{side}:r{round_number}",
        )
        match = None if response.stop_reason == "refusal" else _ARGUMENT.search(response.text)
        if match:
            break
        failures.append({"status": "refused" if response.stop_reason == "refusal" else "format_error",
                         "raw": response.text, "stop_reason": response.stop_reason,
                         "cache_key": response.cache_key})
    else:  # Every attempt failed: the last one becomes the turn, and earlier ones are kept
        last = failures.pop()
        return Turn(round_number, side, last["status"], "", 0, False, [], [], last["raw"],
                    last["stop_reason"], last["cache_key"], failures)
    limited, word_count, truncated = apply_word_limit(reset_tags(match.group(1).strip()), word_limit)
    checked = verify(limited, question.story)
    return Turn(round_number, side, "ok", checked.text, word_count, truncated, checked.verified,
                checked.unverified, response.text, response.stop_reason, response.cache_key, failures)


def _answers(question: Question) -> dict[str, str]:
    return {"correct": question.correct, "distractor": question.distractor}


def _tag(protocol: str, biased: bool, question: Question) -> str:
    return f"{protocol}{'_biased' if biased else ''}:{question.question_id}"


def run_debate(llm: LLM, settings: ArguerSettings, question: Question, biased: bool = False) -> Transcript:
    version = settings.prompts_for("debate", biased)
    transcript = Transcript("debate", question.question_id, question.article_id,
                            _answers(question), None, version, biased=biased)
    rounds: list[dict[str, Turn]] = []
    for _ in range(settings.rounds):
        # Both turns are built from the same earlier rounds, so they are simultaneous.
        new = {
            side: take_turn(llm, settings, version, question, transcript.answers,
                            side, rounds, settings.debate_words, settings.debate_target_words,
                            _tag("debate", biased, question))
            for side in SIDES
        }
        rounds.append(new)
        transcript.turns.extend(new.values())
        if transcript.status != "complete":
            break
    return transcript


def run_consultancy(
    llm: LLM, settings: ArguerSettings, question: Question, side: str, biased: bool = False
) -> Transcript:
    version = settings.prompts_for("consultancy", biased)
    transcript = Transcript("consultancy", question.question_id, question.article_id,
                            _answers(question), side, version, biased=biased)
    rounds: list[dict[str, Turn]] = []
    for _ in range(settings.rounds):
        turn = take_turn(llm, settings, version, question, transcript.answers,
                         side, rounds, settings.consultancy_words, settings.consultancy_target_words,
                         _tag("consultancy", biased, question))
        rounds.append({side: turn})
        transcript.turns.append(turn)
        if turn.status != "ok":
            break
    return transcript


def run_consultancies(
    llm: LLM, settings: ArguerSettings, question: Question, biased: bool = False
) -> list[Transcript]:
    """Run consultancy once for each answer, so the condition is balanced."""
    return [run_consultancy(llm, settings, question, side, biased) for side in SIDES]
