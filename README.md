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

## Data and licensing

This project uses the QuALITY dataset from
[Pang et al. (2022), "QuALITY: Question Answering with Long Input Texts, Yes!"](https://aclanthology.org/2022.naacl-main.391),
which is distributed under a
[CC BY 4.0 License](https://creativecommons.org/licenses/by/4.0/). The dataset itself is
not redistributed here. The published run records in `results/transcripts/` contain QuALITY
questions and answer options, with these changes:

- Only Project Gutenberg stories and questions marked `difficult` are kept, and further
  filters keep questions that annotators found unambiguous (`src/debate_bias/data.py` and
  `PREREGISTRATION.md`).
- Each question is reduced to two options: the gold answer and the distractor that the
  annotators most often named as best.

The stories come from [Project Gutenberg](https://www.gutenberg.org). The run records
include short excerpts quoted by the models, never full stories. These texts are in the
public domain in the United States: nearly all carry Project Gutenberg's note that no
renewal of their US copyright was found. If you are outside the United States, check
your country's copyright law before reusing them. This project is not affiliated with or
endorsed by Project Gutenberg.

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
