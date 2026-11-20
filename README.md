# Debate Under Biased Oversight

**Status: the final run and the preregistered analysis are complete. The report is a
draft under revision, and the error review is still in draft.**

When debaters know a judge's flaw, does debate reduce the damage from that flaw
compared with a single AI arguing an assigned answer?

This is an independent replication and extension of
[Khan et al. (2024)](https://arxiv.org/abs/2402.06782), using the systematic-error
testbed idea from Anthropic's
[recommended research directions](https://alignment.anthropic.com/2025/recommended-directions).
It is not published research.

## Where to find things

| What | Where |
| --- | --- |
| Report (draft) | [`writeup/report.md`](writeup/report.md) |
| Locked preregistration | [`PREREGISTRATION.md`](PREREGISTRATION.md), commit tagged `prereg-lock` |
| Preregistered analysis output | [`results/final/analysis/results.md`](results/final/analysis/results.md) and `results.json` |
| Main figure | [`results/final/analysis/accuracy.png`](results/final/analysis/accuracy.png) |
| Final-run transcripts and judge verdicts | `results/transcripts/final/*.jsonl.gz` |
| Final-run console log | [`results/final/run_log.txt`](results/final/run_log.txt) |
| Error-review draw (30 transcripts) | [`results/final/error_review/error_review.json`](results/final/error_review/error_review.json) |
| Error-review codes (Claude draft, not yet reviewed by Darrel) | [`results/final/error_review/codes_draft.md`](results/final/error_review/codes_draft.md) |
| Original plan and timetable | [`PLAN.md`](PLAN.md) |
| Record of who did what | [`AI_USE_LOG.md`](AI_USE_LOG.md) |

## Result in brief

The final run used 350 QuALITY dev questions from 83 stories, run once after the
preregistration was locked on November 13, 2026. Claude Sonnet 5.5 argued, and Claude
Haiku 5.5 judged without seeing the story. Intervals are 95% story-bootstrap intervals.

| Estimate | Points (95% CI) | Verdict under the locked rule |
| --- | --- | --- |
| H1: debate minus consultancy, unbiased judge | +5.6 (3.2 to 8.1) | Supported, small |
| H2: bias penalty in consultancy | +4.1 (1.7 to 6.4) | Supported, small |
| H2: bias penalty in debate | −1.6 (−3.6 to 0.5) | Inconclusive (null) |
| H3: consultancy penalty minus debate penalty | +5.6 (2.6 to 8.5) | Supported, small |

What these numbers do and don't show:

- Debate held at about 91–92% accuracy under every judge. Consultancy fell from 85.1%
  to 81.0% with the biased judge.
- Almost all of the consultancy penalty comes from the judge's rule itself. Informed
  consultants used more names, numbers, and dates, but gained nothing from it (0.0
  points, −2.3 to 2.3). By the preregistered criterion, the arguers did not exploit the
  flaw in either protocol.
- Every supported effect is under 10 points. Under the original rule in `PLAN.md`
  (at least 10 points and an interval excluding zero), all four estimates would be
  inconclusive. The rule was changed before the lock (see Deviations).
- The bias is a rule written into the judge's prompt, not a flaw the judge picked up on
  its own. The report's limitations section lists the rest.

## Design

A 2x2 comparison on [QuALITY](https://github.com/nyu-mll/quality), plus naive and
expert baselines.

| | Unbiased judge | Biased judge, informed arguers |
| --- | --- | --- |
| **Consultancy** | Protocol baseline | Damage without an opponent |
| **Debate** | Known debate advantage | Damage with an opponent |

Two more cells, added before the lock, have the biased judge re-read the unbiased
transcripts. They split each bias penalty into the judge's part and the arguers' part.
The primary result is the consultancy bias penalty minus the debate bias penalty.

## Reproduce the analysis

Every result regenerates from the saved records without new API calls:

```bash
uv sync
uv run python -m debate_bias.analyze --runs results/transcripts/final --out results/final/analysis
uv run python scripts/sample_errors.py --runs results/transcripts/final --out results/final/error_review
```

The exploratory untagged-quote count also needs the QuALITY data (see Setup):

```bash
uv run python scripts/count_untagged_quotes.py results/transcripts/final
```

## Setup for new runs

```bash
uv sync
cp .env.example .env        # then add your API key
uv run python scripts/smoke_test.py
uv run pytest
```

Download [QuALITY v1.0.1](https://github.com/nyu-mll/quality/blob/main/data/v1.0.1/QuALITY.v1.0.1.zip)
and unzip it into `data/`, which git ignores. New runs make paid API calls and stop at
the spending caps in `configs/`.

## Deviations from the plan

### Before the lock

These were decided during piloting on the train split and are recorded in Section 8 of
the preregistration:

- The judge prompt gained a warning against choosing an answer by its wording
  (`judge_v1` to `judge_v2`).
- The first bias wording failed Gate 3 on the pilot. It was strengthened once, and the
  same 50 pilot questions then passed it. This means the final wording was chosen on
  the pilot.
- Naive accuracy in the pilot was 62%, above the planned "near 50%". It is reported as
  a limitation.
- Word targets (100 per debate turn, 200 per consultancy turn) were added, with the
  planned 150 and 300 kept as hard limits.
- A retry-and-forfeit rule, the Batch API, and the biased-judge, uninformed-arguer
  cells were added.
- The support rule changed from "at least 10 points and an interval excluding zero" to
  "an interval excluding zero", with 10 points kept as a size label. A simulation from
  the pilot showed the final run would be precise enough to detect smaller effects.
- H2 was reworded so the penalty is not credited entirely to the arguers' knowledge.
- The lock and the final run came on November 13, one day early.

### After the lock

- **Error review.** The preregistration says one reader codes the 30 error transcripts.
  Instead, three Claude subagents drafted codes, and Claude checked a few by hand. The
  draft codes, with the method and notes on codebook gaps, are in
  `results/final/error_review/codes_draft.md`. Darrel has not yet reviewed them, so the
  report labels this section exploratory.
- **Exploratory checks.** Two checks that were not preregistered are in the report and
  labelled exploratory: how often the judge calls verified quotes "unverified", and how
  often arguers quote the story without tags. The untagged-quote script is in
  `scripts/`. The mislabel check is not yet in the repo.
- **Doubtful gold labels.** The preregistration asks for their share. It has not been
  measured on the final run.
- **File reading.** After the run, `analyze.py` was changed to read the compressed
  records directly. No analysis code or numbers changed.

### Division of work

The original plan was for Claude to help build the harness while Darrel wrote the
first drafts of the preregistration and the report and coded the error review himself.
In practice Claude did much more of the writing and drafting than planned. This was
partly because of time pressure before the application deadline, and partly because
Darrel is still learning what good research looks like. Specifically:

- **Preregistration.** Claude outlined it, reviewed Darrel's drafts of the early
  sections, and wrote much of the final text, including the analysis rules, the
  precision simulation, the error-review method, and most of the limitations. Darrel
  wrote the original background paragraph and four limitations, chose the support rule
  and the failure types, and locked it.
- **Report.** Claude drafted `writeup/report.md` from the results files and the
  preregistration. Darrel wrote the original section headings and the next-experiment
  section, and is revising the draft.
- **Error review.** Claude subagents drafted the codes, as above.
- **Interpretation.** Claude explained the statistical results to Darrel before the
  report was drafted.

## AI use

Claude (through Claude Code and the Claude app) wrote the project plan, the scaffold, nearly all
of the code and tests, the prompts (adapted from Khan et al.'s), the pilot analyses, and
most of the preregistration and report text, as described above. It ran the approved
paid pilots and the final run.

Darrel chose the data filters, approved the design choices and every paid run, made
the gate decisions during piloting, ran the tests and checked the work as each stage
was built, and decided what to publish. He is reviewing the report and the error-review
codes.

[`AI_USE_LOG.md`](AI_USE_LOG.md) records each task with dated entries. Where Darrel's
part was not confirmed at the time, the log says "not recorded" rather than guessing.

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
| `results/transcripts/final/` | Final-run transcripts and verdicts, gzip-compressed |
| `results/final/` | Analysis output, figure, run log, error-review draw, and draft codes |
| `writeup/report.md` | The report |
| `scripts/` | Smoke test, precision simulations, error-review draw, untagged-quote count |
