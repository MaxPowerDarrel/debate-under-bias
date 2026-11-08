# AI Use Log

A dated record of what Claude did and what Darrel did, used to write the README's AI-use section and the report's contribution statement. Add new entries at the bottom and don't rewrite earlier ones. Darrel may correct any entry.

Entry format:

```markdown
## YYYY-MM-DD: <task>
- **Claude:** <what Claude did>
- **Darrel:** <decisions, drafts, code, and review he did, or "not recorded">
```

## 2026-11-04: Add the contribution-log rule
- **Claude:** Wrote the `CLAUDE.md` rule requiring this log and created this file.
- **Darrel:** Asked for a log that separates Claude's work from his own so it can be condensed for the final report.

## 2026-11-04: Write `data.py` and the QuALITY filters (Day 2)
- **Claude:** Downloaded QuALITY v1.0.1. Found that the distractor field is named `untimed_best_distractor`. Read the filter code in Khan et al.'s `llm_debate` repo and counted how each candidate filter changes both splits. Wrote `data.py` and `tests/test_data.py`, and updated the dataset section and counts in `PLAN.md`.
- **Darrel:** Chose the filter set: the plan's filters plus Khan's context-rating and writer-label filters, giving 350 dev questions.

## 2026-11-04: Verify Days 1 and 2
- **Claude:** Recorded Darrel's verification.
- **Darrel:** Confirmed that the Day 1 smoke test (`scripts/smoke_test.py`) ran and passed on November 3. Ran `uv run pytest` on November 4 and checked the results for the Day 2 data work.

## 2026-11-05: Write `llm.py` with cache, logging, and cost tracking (Day 3)
- **Claude:** Checked the current Claude API reference for Sonnet 5.5 and Haiku 5.5. Neither accepts temperature or a seed, and thinking is always on. Wrote the Day 3 plan, `llm.py` (cache keyed by request plus sample index, JSONL call log, cost calculation, spending cap that still allows cache hits, refusals recorded without retry, refusal fallbacks off), and `tests/test_llm.py`. Pinned effort in both configs. Ran one approved Haiku call twice to confirm the second came from the cache (cost $0.0000046).
- **Darrel:** Approved the Day 3 plan and the tiny paid check.

## 2026-11-05: Verify Day 3
- **Claude:** Recorded Darrel's verification.
- **Darrel:** Ran the test suite and checked the results for the Day 3 `llm.py` work.

## 2026-11-05: Write `quotes.py` and its tests (Day 4)
- **Claude:** Read Khan et al.'s strict quote check (`llm_debate`, MIT) and wrote the Day 4 plan. Wrote `quotes.py`, which follows Khan's normalize-then-match rule with three changes: punctuation becomes a space and dashes count as punctuation, an empty quote is unverified, and quotes must match whole words. The whole-word rule was added during the build, beyond the approved plan. Wrote `tests/test_quotes.py`.
- **Darrel:** Approved the Day 4 plan. Reading Kenton et al.: not recorded.

## 2026-11-05: Verify Day 4
- **Claude:** Recorded Darrel's verification.
- **Darrel:** Ran the test suite and checked the results for the Day 4 `quotes.py` work, and approved committing it with the whole-word rule.

## 2026-11-05: Report draft, next-experiment section
- **Claude:** Committed the draft at Darrel's request. Did not write or edit it.
- **Darrel:** Wrote the report's section headings and a first draft of the "Next experiment" section: rejecting both answers and synthesizing an answer, with how to score each and how hard it is.

## 2026-11-06: Verify Day 4 reading
- **Claude:** Recorded Darrel's confirmation.
- **Darrel:** Confirmed that he finished the Day 4 reading of Kenton et al.

## 2026-11-06: Write `protocols.py` and the arguer prompts (Day 5)
- **Claude:** Read Khan et al.'s debater and consultant prompts and code (`llm_debate`, MIT) and wrote the Day 5 plan. Wrote `prompts/debater_v1/` and `prompts/consultant_v1/`, adapted from Khan's wording. Wrote `protocols.py`: simultaneous debate, consultancy on both answers, transcripts stored by side, and a word limit that never cuts through a quote. Added `reset_tags` to `quotes.py`, `max_tokens.arguer` to both configs, `tests/test_protocols.py`, and `scripts/run_one_question.py`. Ran the approved paid check on one train question ($0.35), read the transcripts, and wrote down issues for Day 9.
- **Darrel:** Approved the Day 5 plan, including its five design choices and the paid check.

## 2026-11-06: Verify Day 5
- **Claude:** Recorded Darrel's verification and committed the Day 5 work.
- **Darrel:** Ran the test suite, read the transcripts from the one-question check, and approved the commit.

## 2026-11-07: Write `judge.py`, the baselines, and the runner, and run the 20-question pilot (Day 6)
- **Claude:** Read Khan et al.'s judge prompts and order-swap code (`llm_debate`, MIT) and wrote the Day 6 plan. Wrote `prompts/judge_v1/` (adapted from Khan's wording), `judge.py` (answer-order swaps, three votes, last-answer parsing, 0.5 for ties, and a check that only the expert judge gets the story), a minimal `run.py` with a spending cap shared across pilot runs, `sample_questions` in `data.py`, `scripts/show_transcript.py`, and tests including the leak test. Ran the approved 20-question train pilot ($7.55). Read 8 transcripts plus the expert and naive judge outputs, and wrote findings in `tasks/todo.md`. The main one is that the naive judge scores 77.5% by guessing from answer wording.
- **Darrel:** Approved the Day 6 plan and the paid pilot, and chose to score tied or invalid votes as 0.5. Reading transcripts for Gate 1: not recorded.

## 2026-11-07: Verify Day 6
- **Claude:** Recorded Darrel's verification and committed the Day 6 work.
- **Darrel:** Read the pilot transcripts for Gate 1, ran the test suite, and approved the commit.

## 2026-11-07: Test a judge prompt that warns against guessing from answer wording
- **Claude:** Suggested the test and its cost. Made the judge prompt version a config setting with a `run.py` override, wrote `prompts/judge_v2/` (one added line in all four judge prompts), and added a test. Re-judged the 20 pilot questions from cached transcripts ($0.42), compared the results with `judge_v1`, and read the new naive reasoning.
- **Darrel:** Asked whether a prompt change was worth testing, approved the run with a $1 cap, chose to switch both configs to `judge_v2`, and approved the commit.

## 2026-11-08: Fix the arguer prompts, refusals, and word limits (Day 7, a day early)
- **Claude:** Listed the open Day 9 questions from `tasks/todo.md` and recommended options, including the quote-tag wording. Wrote the plan, `prompts/debater_v2/` and `prompts/consultant_v2/` (word target, quote-tag rule, "..." rule), the retry and forfeit logic in `protocols.py`, forfeit scoring in `judge.py`, the forfeit lines in the `run.py` summary, config settings for arguer prompt versions and word targets, retry display in `scripts/show_transcript.py`, and tests. No API calls.
- **Darrel:** Chose one retry and then scoring as a loss for the failing side, with annotation. Chose Khan's word targets, kept the consultant honesty line to match Khan, and asked for it to be noted in the report. Approved the recommended quote wording including the "..." line, chose to report accuracy without forfeits as a check, and chose to fold the v2 check into the Day 10 pilot.
