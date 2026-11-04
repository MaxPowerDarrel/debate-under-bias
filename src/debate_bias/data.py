"""Load and filter QuALITY, and choose each question's distractor.

Filters follow Khan et al. (2024) and their `llm_debate` code. A question is kept
only if it passes every stage in `FILTERS`, in order. `load_questions` returns the
kept questions and the number left after each stage, so the counts can be reported.

QuALITY labels are 1-indexed. The best-distractor field is `untimed_best_distractor`
in the data file. The QuALITY docs call it `untimed_eval3_distractor`.
"""

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
SPLITS = ("train", "dev")  # Test labels aren't public.
MIN_MEAN_CONTEXT = 1.5  # Khan et al.'s `min_context_required`


@dataclass(frozen=True)
class Question:
    question_id: str  # QuALITY `question_unique_id`
    article_id: str  # Story ID; bootstrap resampling groups by this
    title: str
    story: str
    question: str
    correct: str
    distractor: str


def _mean(values: list[int]) -> float:
    return sum(values) / len(values)


# Each stage takes (article, question) and returns True to keep the question.
# Validator counts vary (3 to 7), so the rules use "all" or a mean, not fixed counts.
FILTERS = [
    ("gutenberg", lambda a, q: a["source"] == "Gutenberg"),
    ("difficult", lambda a, q: q["difficult"] == 1),
    (
        "all_untimed_correct",
        lambda a, q: all(v["untimed_answer"] == q["gold_label"] for v in q["validation"]),
    ),
    (
        "all_unambiguous",
        lambda a, q: all(v["untimed_eval1_answerability"] == 1 for v in q["validation"]),
    ),
    (
        "needs_context",
        lambda a, q: _mean([v["untimed_eval2_context"] for v in q["validation"]]) >= MIN_MEAN_CONTEXT,
    ),
    ("writer_agrees", lambda a, q: q["writer_label"] == q["gold_label"]),
]


def choose_distractor(question: dict) -> int:
    """Return the 1-indexed option that untimed annotators most often named as the best distractor.

    Votes for the gold answer are ignored. Ties go to the lowest option number, which is
    what Khan et al.'s `max(set(votes), key=votes.count)` does for small integers.
    """
    votes = Counter(
        v["untimed_best_distractor"]
        for v in question["validation"]
        if v["untimed_best_distractor"] != question["gold_label"]
    )
    if not votes:
        raise ValueError(f"No distractor votes for {question['question_unique_id']}")
    return min(votes, key=lambda option: (-votes[option], option))


def read_split(split: str, data_dir: Path = DATA_DIR) -> list[dict]:
    """Read the raw article records for one split."""
    if split not in SPLITS:
        raise ValueError(f"Unknown split {split!r}; expected one of {SPLITS}")
    path = data_dir / f"QuALITY.v1.0.1.htmlstripped.{split}"
    with path.open() as f:
        return [json.loads(line) for line in f]


def filter_questions(articles: list[dict]) -> tuple[list[Question], dict[str, int]]:
    """Apply `FILTERS` and return kept questions plus the count left after each stage."""
    counts = Counter({"all": 0, **{name: 0 for name, _ in FILTERS}})
    kept = []
    for article in articles:
        for q in article["questions"]:
            counts["all"] += 1
            passed = True
            for name, keep in FILTERS:
                if not keep(article, q):
                    passed = False
                    break
                counts[name] += 1
            if not passed:
                continue
            options = q["options"]
            kept.append(
                Question(
                    question_id=q["question_unique_id"],
                    article_id=article["article_id"],
                    title=article["title"].strip(),
                    story=article["article"],
                    question=q["question"].strip(),
                    correct=options[q["gold_label"] - 1].strip(),
                    distractor=options[choose_distractor(q) - 1].strip(),
                )
            )
    return kept, dict(counts)


def load_questions(split: str, data_dir: Path = DATA_DIR) -> tuple[list[Question], dict[str, int]]:
    """Load one split and return its filtered questions and per-stage counts."""
    return filter_questions(read_split(split, data_dir))


if __name__ == "__main__":
    for split in SPLITS:
        questions, counts = load_questions(split)
        stories = len({q.article_id for q in questions})
        print(f"{split}: {counts} -> {len(questions)} questions from {stories} stories")
