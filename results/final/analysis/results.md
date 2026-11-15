# Results

Runs: results/final/final. 350 questions from 83 stories analyzed; 0 dropped for missing protocol verdicts. 95% intervals from 10,000 story-bootstrap resamples (seed 0).

## Main (forfeits scored as losses)

| Cell | Accuracy (95% CI) | Questions |
| --- | --- | --- |
| consultancy | 0.851 (0.828 to 0.873) | 350 |
| consultancy:correct | 0.957 (0.936 to 0.976) | 350 |
| consultancy:distractor | 0.744 (0.702 to 0.785) | 350 |
| consultancy_biased | 0.810 (0.785 to 0.835) | 350 |
| consultancy_biased:correct | 0.983 (0.970 to 0.994) | 350 |
| consultancy_biased:distractor | 0.637 (0.589 to 0.685) | 350 |
| consultancy_biased_uninformed | 0.810 (0.784 to 0.836) | 350 |
| consultancy_biased_uninformed:correct | 0.964 (0.946 to 0.981) | 350 |
| consultancy_biased_uninformed:distractor | 0.656 (0.610 to 0.701) | 350 |
| debate | 0.907 (0.882 to 0.931) | 350 |
| debate_biased | 0.923 (0.898 to 0.946) | 350 |
| debate_biased_uninformed | 0.913 (0.888 to 0.937) | 350 |
| expert | 0.964 (0.943 to 0.982) | 350 |
| naive | 0.584 (0.539 to 0.626) | 350 |

| Estimate | Value (95% CI) |
| --- | --- |
| H1: debate - consultancy (unbiased) | 0.056 (0.032 to 0.081) |
| H2: consultancy penalty | 0.041 (0.017 to 0.064) |
| H2: debate penalty | -0.016 (-0.036 to 0.005) |
| H3: consultancy penalty - debate penalty | 0.056 (0.026 to 0.085) |
| Judge effect: consultancy | 0.041 (0.024 to 0.057) |
| Judge effect: debate | -0.006 (-0.020 to 0.009) |
| Exploitation effect: consultancy | 0.000 (-0.023 to 0.023) |
| Exploitation effect: debate | -0.010 (-0.031 to 0.012) |
| H3 from the judge effect | 0.046 (0.024 to 0.069) |
| H3 from the exploitation effect | 0.010 (-0.020 to 0.039) |

## Check: forfeits left out

| Cell | Accuracy (95% CI) | Questions |
| --- | --- | --- |
| consultancy | 0.851 (0.828 to 0.873) | 350 |
| consultancy:correct | 0.957 (0.936 to 0.976) | 350 |
| consultancy:distractor | 0.744 (0.702 to 0.785) | 350 |
| consultancy_biased | 0.810 (0.785 to 0.835) | 350 |
| consultancy_biased:correct | 0.983 (0.970 to 0.994) | 350 |
| consultancy_biased:distractor | 0.637 (0.589 to 0.685) | 350 |
| consultancy_biased_uninformed | 0.810 (0.784 to 0.836) | 350 |
| consultancy_biased_uninformed:correct | 0.964 (0.946 to 0.981) | 350 |
| consultancy_biased_uninformed:distractor | 0.656 (0.610 to 0.701) | 350 |
| debate | 0.907 (0.882 to 0.931) | 350 |
| debate_biased | 0.923 (0.898 to 0.946) | 350 |
| debate_biased_uninformed | 0.913 (0.888 to 0.937) | 350 |
| expert | 0.964 (0.943 to 0.982) | 350 |
| naive | 0.584 (0.539 to 0.626) | 350 |

| Estimate | Value (95% CI) |
| --- | --- |
| H1: debate - consultancy (unbiased) | 0.056 (0.032 to 0.081) |
| H2: consultancy penalty | 0.041 (0.017 to 0.064) |
| H2: debate penalty | -0.016 (-0.036 to 0.005) |
| H3: consultancy penalty - debate penalty | 0.056 (0.026 to 0.085) |
| Judge effect: consultancy | 0.041 (0.024 to 0.057) |
| Judge effect: debate | -0.006 (-0.020 to 0.009) |
| Exploitation effect: consultancy | 0.000 (-0.023 to 0.023) |
| Exploitation effect: debate | -0.010 (-0.031 to 0.012) |
| H3 from the judge effect | 0.046 (0.024 to 0.069) |
| H3 from the exploitation effect | 0.010 (-0.020 to 0.039) |

## Counts

| Cell | Verdicts | Forfeits | Ties | Invalid votes |
| --- | --- | --- | --- | --- |
| consultancy | 1400 | 0 | 0 | 0/4200 |
| consultancy_biased | 1400 | 0 | 0 | 0/4200 |
| consultancy_biased_uninformed | 1400 | 0 | 0 | 0/4200 |
| debate | 700 | 0 | 0 | 0/2100 |
| debate_biased | 700 | 0 | 0 | 0/2100 |
| debate_biased_uninformed | 700 | 0 | 0 | 0/2100 |
| expert | 700 | 0 | 0 | 0/2100 |
| naive | 700 | 0 | 0 | 0/2100 |

## Vote agreement (diagnostic): share of judged verdicts with unanimous votes

| Cell | Agreement (95% CI) | Judged verdicts |
| --- | --- | --- |
| consultancy | 0.874 (0.854 to 0.894) | 1400 |
| consultancy_biased | 0.869 (0.851 to 0.887) | 1400 |
| consultancy_biased_uninformed | 0.861 (0.840 to 0.880) | 1400 |
| debate | 0.903 (0.877 to 0.925) | 700 |
| debate_biased | 0.896 (0.874 to 0.917) | 700 |
| debate_biased_uninformed | 0.909 (0.884 to 0.930) | 700 |
| expert | 0.956 (0.929 to 0.976) | 700 |
| naive | 0.787 (0.754 to 0.819) | 700 |

## Bias check: names, numbers, and dates per turn

| Protocol | Uninformed | Informed | Difference (95% CI) |
| --- | --- | --- | --- |
| consultancy | 11.00 | 12.06 | 1.06 (0.89 to 1.24) |
| debate | 6.15 | 6.56 | 0.41 (0.28 to 0.53) |

| Protocol | Side | Round | Uninformed | Informed |
| --- | --- | --- | --- | --- |
| consultancy | correct | 1 | 14.08 | 15.42 |
| consultancy | correct | 2 | 9.99 | 11.01 |
| consultancy | correct | 3 | 9.83 | 10.55 |
| consultancy | distractor | 1 | 12.32 | 14.37 |
| consultancy | distractor | 2 | 10.10 | 10.69 |
| consultancy | distractor | 3 | 9.69 | 10.35 |
| debate | correct | 1 | 7.42 | 7.96 |
| debate | correct | 2 | 5.56 | 6.00 |
| debate | correct | 3 | 5.64 | 6.10 |
| debate | distractor | 1 | 6.75 | 7.35 |
| debate | distractor | 2 | 5.69 | 6.01 |
| debate | distractor | 3 | 5.83 | 5.91 |

0 informed turns flagged as possibly mentioning the rule; read them in `results.json` before reporting a rate.
