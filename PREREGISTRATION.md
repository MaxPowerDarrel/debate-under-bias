# Preregistration

**Status: DRAFT. Commit the final version before the final run (planned Nov 14, 2026).**
Changes to prompts, filters, or analysis after that commit count as exploratory.

## Question

When debaters know a judge's flaw, does debate reduce the damage from that flaw
compared with consultancy?

## Hypotheses

1. **Baseline:** With an unbiased judge, debate is more accurate than consultancy.
2. **Bias works:** Knowing the judge's flaw lowers accuracy in both protocols.
3. **Main test:** The accuracy lost to bias is smaller in debate than in consultancy.

## Data

- QuALITY v1.0.1, Project Gutenberg stories, `difficult=1`.
- Every untimed annotator chose the gold answer and rated the question unambiguous.
- Distractor: the most-selected `untimed_eval3_distractor`.
- Pilot on train. Run the final experiment once on dev.
- Final question count: TBD

## Bias rule

> Arguments containing specific names, numbers, and dates are more likely to be correct.

Final wording: TBD after the pilot.

## Analysis

- **Bias penalty:** unbiased accuracy minus biased accuracy, per protocol.
- **Primary result:** consultancy penalty minus debate penalty.
- **Uncertainty:** 95% bootstrap confidence intervals, resampling by story.
- **Decision rule:** Hypothesis 3 is supported if the interval excludes zero and
  the estimate is positive. A difference under 10 points is treated as inconclusive.
- **Exclusions:** TBD. Report refusals and every excluded question.

## Commit hash of locked prompts and config

TBD
