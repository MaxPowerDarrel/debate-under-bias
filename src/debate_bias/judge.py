"""Judge prompts, answer-order swaps, and majority voting.

There are four judge conditions, all using the prompts in `prompts/judge_v1/`:

- **naive:** the question and two answers only.
- **expert:** the question, two answers, and the story. This is the only judge that sees
  the story. `build_prompt` refuses a story for any other condition, and
  `tests/test_judge.py` checks that story text never reaches the others.
- **consultancy:** one consultant's transcript.
- **debate:** both debaters' transcript.

**Order swap:** every condition is judged in both orders. In order 0 the correct answer
is A, and in order 1 it is B. In debate, Debater A always argues answer A and is printed
first in each round, so swapping the order also swaps which debater is A. The arguers
call each other "my opponent", so their text never names a letter that could go stale.

**Votes:** each (transcript, order) gets `votes` independent samples, told apart in the
cache by `sample`. A vote is the last "Answer: A" or "Answer: B" in the reply. A refusal
or a reply with no answer is an invalid vote and is not retried.

**Scoring:** an order scores 1 if most valid votes pick the correct answer, 0 if most pick
the distractor, and 0.5 if the valid votes tie or none are valid. A tie is scored as a
coin flip so it favors neither protocol, and ties are counted so they can be reported.
"""

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from string import Template

from .data import Question
from .llm import LLM
from .protocols import SIDES, Transcript

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
JUDGE_PROMPTS = "judge_v1"
CONDITIONS = ("naive", "expert", "consultancy", "debate")
ORDERS = (0, 1)  # Order 0 shows the correct answer as A

_ANSWER = re.compile(r"answer\s*:\s*\**\s*\(?([AB])\b", re.IGNORECASE)


@dataclass(frozen=True)
class JudgeSettings:
    model: str
    effort: str
    max_tokens: int
    votes: int

    @classmethod
    def from_config(cls, config: dict) -> "JudgeSettings":
        return cls(
            model=config["models"]["judge"],
            effort=config["effort"]["judge"],
            max_tokens=config["max_tokens"]["judge"],
            votes=config["protocol"]["judge_votes"],
        )


@dataclass
class Vote:
    sample: int
    letter: str | None  # "A", "B", or None for an invalid vote
    side: str | None  # The side that letter stands for: "correct", "distractor", or None
    stop_reason: str
    text: str
    cache_key: str


@dataclass
class Verdict:
    """All votes for one condition, one transcript (or none), and one order."""

    condition: str
    question_id: str
    article_id: str
    order: int
    consultant_side: str | None  # Set only for consultancy
    status: str  # "judged", or "excluded" when the transcript didn't complete
    prompts: str = JUDGE_PROMPTS
    votes: list[Vote] = field(default_factory=list)

    @property
    def tie(self) -> bool:
        return self.status == "judged" and score_votes(self.votes) == 0.5

    @property
    def score(self) -> float | None:
        return score_votes(self.votes) if self.status == "judged" else None

    def to_dict(self) -> dict:
        return {**asdict(self), "score": self.score, "tie": self.tie}


def letters(order: int) -> dict[str, str]:
    """Map each side to its answer letter in this order."""
    first, second = SIDES if order == 0 else SIDES[::-1]
    return {first: "A", second: "B"}


def parse_answer(text: str) -> str | None:
    """Return the letter in the last "Answer: X" line, or None if there isn't one."""
    matches = _ANSWER.findall(text)
    return matches[-1].upper() if matches else None


def score_votes(votes: list[Vote]) -> float:
    correct = sum(v.side == "correct" for v in votes)
    wrong = sum(v.side == "distractor" for v in votes)
    return 1.0 if correct > wrong else 0.0 if wrong > correct else 0.5


def render_transcript(transcript: Transcript, order: int) -> str:
    """Show the transcript as the judge sees it, with sides named by this order's letters."""
    sides = letters(order)
    rounds: dict[int, list] = {}
    for turn in transcript.turns:
        rounds.setdefault(turn.round, []).append(turn)
    parts = []
    for number in sorted(rounds):
        parts.append(f"Round {number}:")
        for turn in sorted(rounds[number], key=lambda t: sides[t.side]):
            name = f"Debater {sides[turn.side]}" if transcript.protocol == "debate" else "Consultant"
            parts.append(f'{name}: """{turn.argument}"""')
    return "\n\n".join(parts)


def load_prompts() -> dict[str, Template]:
    return {p.stem: Template(p.read_text().strip()) for p in (PROMPTS_DIR / JUDGE_PROMPTS).glob("*.md")}


def build_prompt(
    condition: str,
    question: str,
    answers: dict[str, str],
    order: int,
    transcript: Transcript | None = None,
    story: str | None = None,
) -> tuple[str, str]:
    """Return the (system, user) prompt. Only the expert condition may be given the story."""
    if (story is not None) != (condition == "expert"):
        raise ValueError(f"The {condition} judge {'needs' if story is None else 'must not see'} the story")
    if (transcript is not None) != (condition in ("consultancy", "debate")):
        raise ValueError(f"Wrong transcript input for the {condition} judge")
    if transcript is not None and transcript.protocol != condition:
        raise ValueError(f"A {transcript.protocol} transcript can't be judged as {condition}")
    sides = letters(order)
    by_letter = {letter: answers[side] for side, letter in sides.items()}
    values = {"question": question, "answer_a": by_letter["A"], "answer_b": by_letter["B"]}
    if story is not None:
        values["story"] = story
    if transcript is not None:
        values["transcript"] = render_transcript(transcript, order)
        if transcript.consultant_side:
            values["consultant_letter"] = sides[transcript.consultant_side]
    prompts = load_prompts()
    return prompts["system"].substitute(), prompts[condition].substitute(values)


def judge(
    llm: LLM,
    settings: JudgeSettings,
    condition: str,
    question: Question,
    order: int,
    transcript: Transcript | None = None,
) -> Verdict:
    """Collect the votes for one condition and order. Incomplete transcripts are excluded."""
    verdict = Verdict(condition, question.question_id, question.article_id, order,
                      transcript.consultant_side if transcript else None,
                      "judged" if transcript is None or transcript.status == "complete" else "excluded")
    if verdict.status == "excluded":
        return verdict
    answers = {"correct": question.correct, "distractor": question.distractor}
    story = question.story if condition == "expert" else None
    system, user = build_prompt(condition, question.question, answers, order, transcript, story)
    side_of = {letter: side for side, letter in letters(order).items()}
    who = f":{verdict.consultant_side}" if verdict.consultant_side else ""
    for sample in range(settings.votes):
        response = llm.call(
            settings.model,
            system,
            [{"role": "user", "content": user}],
            max_tokens=settings.max_tokens,
            effort=settings.effort,
            sample=sample,
            tag=f"judge:{condition}{who}:{question.question_id}:o{order}",
        )
        letter = None if response.stop_reason == "refusal" else parse_answer(response.text)
        verdict.votes.append(Vote(sample, letter, side_of.get(letter), response.stop_reason,
                                  response.text, response.cache_key))
    return verdict
