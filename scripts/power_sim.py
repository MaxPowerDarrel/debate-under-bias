"""Estimate precision for the primary result using assumed accuracy rates.

Treats questions as independent, so real intervals that resample by story will
be wider. Rates are assumptions for planning, not measurements.
"""
import numpy as np

rng = np.random.default_rng(0)


def logit(p):
    return np.log(p / (1 - p))


def expit(x):
    return 1 / (1 + np.exp(-x))


def simulate(n, debate, debate_biased, consult, consult_biased, sd=0.8, reps=2000, boot=400):
    """Each consult rate is (accuracy when arguing correct, accuracy when arguing wrong)."""
    hits, margins = 0, []
    for _ in range(reps):
        ease = rng.normal(0, sd, n)
        def debate_acc(p):
            return (rng.random((n, 2)) < expit(logit(p) + ease[:, None])).mean(1)
        def consult_acc(pair):
            right = rng.random(n) < expit(logit(pair[0]) + ease)
            wrong = rng.random(n) < expit(logit(pair[1]) + ease)
            return (right.astype(float) + wrong) / 2
        effect = (consult_acc(consult) - consult_acc(consult_biased)) - (
            debate_acc(debate) - debate_acc(debate_biased)
        )
        means = effect[rng.integers(0, n, (boot, n))].mean(1)
        low, high = np.percentile(means, [2.5, 97.5])
        hits += low > 0
        margins.append((high - low) / 2)
    return hits / reps, float(np.mean(margins))


SCENARIOS = {
    "no difference": (0.75, 0.65, (0.85, 0.45), (0.80, 0.30)),
    "10 points": (0.75, 0.70, (0.85, 0.45), (0.80, 0.20)),
    "about 20 points": (0.75, 0.72, (0.85, 0.45), (0.75, 0.12)),
}

for n in (100, 200, 300):
    for name, args in SCENARIOS.items():
        share, margin = simulate(n, *args)
        print(f"n={n} {name}: interval above zero {share:.1%}, margin +/-{margin:.3f}")
