"""Expected precision of the final run, simulated from the pilot's per-question scores.

`power_sim.py` was the planning simulation: assumed accuracy rates, independent questions,
unpaired cells. This one uses what the pilot measured. It keeps the pairing (each
simulated question carries one pilot question's scores in all six protocol cells), uses
the final run's size (350 questions from 83 stories), and analyzes each simulated run the
way `analyze.py` does, with a story bootstrap.

Reads saved pilot files and the train split only. It makes no API calls and never reads dev.

    uv run python scripts/precision_from_pilot.py

**Story sizes.** Dev's 350 questions and 83 stories are known counts (`PLAN.md`), but its
sizes per story are not read. Sizes are drawn from the train split's stories, redrawing
until 83 stories hold exactly 350 questions.

**Questions from one story are related.** The pilot has one question per story, so it
can't say how strongly. The simulation takes that as an assumption, `icc`: each story
picks one pilot question as its "theme", and each of its questions copies the theme with
probability sqrt(icc) or else draws a pilot question at random. Two questions from one
story then have identical scores with probability icc, which makes icc the within-story
correlation of every cell and every estimate.

**Outputs, per estimate and icc.** The mean half-width of the 95% story-bootstrap
interval, and the share of simulated runs whose interval excludes zero. That share is the
power if the pilot's effect sizes were the truth; the pilot chose the bias wording, so its
effects are probably optimistic and so is the power. The half-width depends much less on
the effect size.
"""

from collections import Counter
from pathlib import Path

import numpy as np

from debate_bias.analyze import HYPOTHESES, complete_questions, load_runs, question_scores
from debate_bias.data import load_questions

ROOT = Path(__file__).resolve().parents[1]
PILOT_RUNS = ("day10_unbiased_50", "day11b_biased_v2_50", "day14_biased_judge_uninformed_50")
ESTIMATES = [name for name in HYPOTHESES if name.startswith("H")][:4]  # H1, the two H2 penalties, and H3
QUESTIONS, STORIES = 350, 83  # Dev counts from PLAN.md
ICCS = (0.0, 0.1, 0.3)
SIMS, RESAMPLES, SEED = 2000, 2000, 0


def pilot_contrasts() -> np.ndarray:
    """One row per pilot question and one column per estimate: that question's own value of the estimate."""
    verdicts, _ = load_runs([ROOT / "results" / "pilot" / run for run in PILOT_RUNS])
    questions = sorted(complete_questions(verdicts))
    scores = question_scores(verdicts, set(questions))
    return np.array([[sum(w * scores[cell][q] for cell, w in HYPOTHESES[name].items()) for name in ESTIMATES]
                     for q in questions])


def story_sizes(rng: np.random.Generator, train_sizes: np.ndarray) -> np.ndarray:
    while True:
        sizes = rng.choice(train_sizes, STORIES)
        if sizes.sum() == QUESTIONS:
            return sizes


def simulate(contrasts: np.ndarray, train_sizes: np.ndarray, icc: float, rng: np.random.Generator):
    """Return the interval half-widths and whether each interval excludes zero, one row per simulated run."""
    n_pilot = len(contrasts)
    half_widths, excludes_zero = [], []
    for _ in range(SIMS):
        sizes = story_sizes(rng, train_sizes)
        story = np.repeat(np.arange(STORIES), sizes)
        theme = rng.integers(0, n_pilot, STORIES)[story]
        picks = np.where(rng.random(QUESTIONS) < np.sqrt(icc), theme, rng.integers(0, n_pilot, QUESTIONS))
        sums = np.zeros((STORIES, len(ESTIMATES)))
        np.add.at(sums, story, contrasts[picks])
        # Story bootstrap, as in analyze.py: weights[r, s] is how often story s is drawn in resample r.
        weights = rng.multinomial(STORIES, np.full(STORIES, 1 / STORIES), size=RESAMPLES)
        resampled = (weights @ sums) / (weights @ sizes)[:, None]
        low, high = np.percentile(resampled, [2.5, 97.5], axis=0)
        half_widths.append((high - low) / 2)
        excludes_zero.append((low > 0) | (high < 0))
    return np.array(half_widths), np.array(excludes_zero)


if __name__ == "__main__":
    contrasts = pilot_contrasts()
    train, _ = load_questions("train")
    train_sizes = np.array(list(Counter(q.article_id for q in train).values()))
    print(f"{len(contrasts)} pilot questions; {QUESTIONS} questions from {STORIES} stories per simulated run; "
          f"{SIMS} runs, {RESAMPLES} resamples each, seed {SEED}\n")
    print("Pilot estimates: " + ", ".join(f"{name.split(':')[0]} {'(debate) ' if 'debate penalty' in name and name.startswith('H2') else ''}"
                                          f"{value:+.3f}" for name, value in zip(ESTIMATES, contrasts.mean(axis=0))))
    for icc in ICCS:
        half_widths, excludes_zero = simulate(contrasts, train_sizes, icc, np.random.default_rng(SEED))
        print(f"\nicc = {icc}")
        for i, name in enumerate(ESTIMATES):
            print(f"  {name:42} half-width ±{half_widths[:, i].mean():.3f}   "
                  f"interval excludes zero in {excludes_zero[:, i].mean():.0%} of runs")
