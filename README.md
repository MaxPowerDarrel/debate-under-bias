# Debate Under Biased Oversight

**Status: in progress. Nothing here is a result yet.**

When debaters know a judge's flaw, does debate reduce the damage from that flaw
compared with a single AI arguing an assigned answer?

This project extends the setup in [Khan et al. (2024)](https://arxiv.org/abs/2402.06782)
using the systematic-error testbed idea from Anthropic's
[recommended research directions](https://alignment.anthropic.com/2025/recommended-directions).

## Design

A 2x2 comparison on [QuALITY](https://github.com/nyu-mll/quality), plus naive and
expert baselines. Sonnet 5.5 argues and Haiku 5.5 judges without seeing the story.

| | Unbiased judge | Biased judge, informed arguers |
| --- | --- | --- |
| **Consultancy** | Protocol baseline | Damage without an opponent |
| **Debate** | Known debate advantage | Damage with an opponent |

The primary result is the consultancy bias penalty minus the debate bias penalty.
See [PREREGISTRATION.md](PREREGISTRATION.md).

## Setup

```bash
uv sync
cp .env.example .env        # then add your API key
uv run python scripts/smoke_test.py
uv run pytest
```

Download [QuALITY v1.0.1](https://github.com/nyu-mll/quality/blob/main/data/v1.0.1/QuALITY.v1.0.1.zip)
and unzip it into `data/`, which git ignores.

## Layout

| Path | Purpose |
| --- | --- |
| `configs/` | Models, protocol settings, seeds, and spending caps |
| `prompts/` | Versioned debater, consultant, and judge prompts |
| `src/debate_bias/` | Data, API client, quotes, protocols, judging, runner, analysis |
| `tests/` | Harness tests, including the story-leak test |
| `results/` | Final-run transcripts and figures |
| `writeup/report.md` | The report |
| `scripts/power_sim.py` | Simulation behind the precision estimate |

## AI use

Claude created the project plan and the initial scaffold. Complete this section
before publishing, stating what Claude and Claude Code did and what the author did.
