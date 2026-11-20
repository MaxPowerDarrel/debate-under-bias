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

## 2026-11-08: Run the 50-question unbiased pilot (Day 8, two days early)
- **Claude:** Wrote the plan, ran the approved 50-question train pilot ($17.23), computed accuracy with bootstrap intervals, compared turn statistics with Day 6, read the expert votes on two shared failures, two lost debates, the untagged turns, and naive reasons, and wrote findings and a Gate 2 recommendation in `tasks/todo.md`.
- **Darrel:** Approved the paid run. Passed Gate 2, accepting naive at 62% as a stated limitation, and approved the commit.

## 2026-11-08: Add the bias rule and informed-arguer prompts (Day 9, three days early)
- **Claude:** Proposed the design and wording: the biased judge as `judge_v2` plus the `PLAN.md` rule, informed arguers as v2 plus a section that quotes the rule and forbids mentioning it, arguers informed but not told to exploit it, and debaters not told their opponent knows. Flagged the tension with `judge_v2`'s wording line. Wrote `prompts/judge_biased_v1/`, `prompts/debater_informed_v1/`, `prompts/consultant_informed_v1/`, the `biased` flag in `protocols.py` and `judge.py`, `--conditions` and `--questions` in `run.py`, `specifics.py` (names, numbers, and dates counter, and a rule-mention check), and tests. Ran the approved one-question check ($0.31), found and fixed a bug in the name counter, and compared specifics with the Day 8 transcripts of the same question.
- **Darrel:** Chose the order (bias prompts, then Batch API, then the biased pilot). Approved the prompt wording, both "don't tell" choices, and the paid check.

## 2026-11-08: Add the Batch API and prompt caching
- **Claude:** Read the current Batch API and prompt-caching documentation. Designed and wrote batch mode as replay passes over the existing code: collect mode and `Pending` in `llm.py`, `batch.py` (submit, poll, collect, resume from `batches.json`, cost estimate before each batch), unit-level pausing in `protocols.py`, `judge.py`, and `run.py`, and `--batch`. Added batch and 1-hour cache-write pricing, story prompt caching (`prompt_cache_ttl: 1h` in both configs), and `tests/test_batch.py`. Ran the approved 2-question batch check ($0.18), confirmed 4 batches, cache reads, matching records, and a free replay, and checked the cost estimate against actual cost.
- **Darrel:** Asked when the Batch API work made most sense, chose to build it after the bias prompts and before the biased pilot, and approved the paid check.

## 2026-11-09: Run the biased pilot (Gate 3)
- **Claude:** Committed the Batch API work. Ran the approved 50-question biased pilot through the Batch API ($3.94). Compared it with Day 8's unbiased pilot: accuracy by protocol and side, story-bootstrap intervals for the penalties, specifics per turn, and rule mentions. Recorded the results in `tasks/todo.md`.
- **Darrel:** Approved the commit and the paid run. Gate 3 decision: not recorded yet.

## 2026-11-09: Strengthen the bias wording after Gate 3 failed
- **Claude:** Proposed strengthening both the judge rule and the arguer prompts, and wrote `judge_biased_v2`, `debater_informed_v2`, `consultant_informed_v2`, the config changes, tests, and the README section.
- **Darrel:** Failed Gate 3 and chose to strengthen both prompts, including inviting arguers to use the rule.

## 2026-11-09: Run the biased pilot with the v2 wording (Gate 3 retry)
- **Claude:** Committed the v2 prompts and ran the approved 50-question biased pilot through the Batch API ($3.22). Compared it with the unbiased and v1 biased pilots, read the two arguments flagged as mentioning the rule (both false positives), and recorded the results in `tasks/todo.md`.
- **Darrel:** Approved the commit and the paid run. Passed Gate 3.

## 2026-11-09: Write `analyze.py` (Day 13, two days early)
- **Claude:** Proposed the analysis plan (per-question scores, a paired story bootstrap with 10,000 resamples, only questions complete in all four protocol cells, H1–H3 from `PLAN.md`, the forfeit check, the bias check with rule flags listed for hand reading, and one command writing JSON, Markdown, and the main figure). Wrote `analyze.py` and `tests/test_analyze.py`, ran it on the pilot data, checked the numbers against the Gate 3 script, and fixed the figure's label placement.
- **Darrel:** Approved the plan.

## 2026-11-09: Explain the extra batch and narrow the rule-mention check
- **Claude:** Traced the first biased run's 5th batch to one retried debater turn (a reply that closed with the wrong tag), and corrected the earlier count of retried turns, which my own check had gotten wrong. Narrowed `mentions_rule`, added tests, and searched both biased pilots by hand for any mention of the rule (none).
- **Darrel:** Asked for both follow-ups.

## 2026-11-09: Outline the preregistration
- **Claude:** Proposed an outline and saved it as a skeleton in `PREREGISTRATION.md`, keeping the scaffold draft's text unchanged under the new headings and adding comments on what each section needs, decisions still open (⚑), and two scaffold lines that are out of date (the data filters and the distractor field).
- **Darrel:** Asked for the outline and the skeleton. He writes the draft.

## 2026-11-10: Adversarial review of the experiment before the lock
- **Claude:** Read the code, prompts, configs, plan, and preregistration skeleton, and probed the two 50-question pilot runs offline (no API calls, no dev data beyond the existing question counts). Reported design, analysis, and code weaknesses in the session, with the main one being that the biased-judge effect and the informed-arguer effect aren't separated. Changed no code, prompts, or analysis.
- **Darrel:** Asked for the review. Decisions on the findings: not recorded.

## 2026-11-10: Add the biased-judge, uninformed-arguer cell and pilot it
- **Claude:** Planned the cell and its cost in `tasks/todo.md`. Changed `judge.py`, `run.py` (new `cross` condition and `--transcripts-from`), and `analyze.py` (two new cells, judge and exploitation effects, six-cell completeness), added 8 tests, and added the cell to `PLAN.md`'s condition table and the preregistration skeleton's comments. Ran the 50-question pilot (900 Haiku calls, $0.28) and the merged analysis. Chose the six-cell completeness rule and the H3 split without a separate decision from Darrel.
- **Darrel:** Asked for the plan and cost, then approved the build and the pilot run. Review of the code and result: not recorded.

## 2026-11-13: Read the pilot data against the hypotheses
- **Claude:** Reran `analyze.py` on the three pilot runs (output matches `analysis_pilot_v3` exactly). Wrote a scratch script (not committed) for per-question breakdowns: direction counts and sign tests per estimate, penalty concentration, consultant side, debate order, and vote agreement. Wrote the H1–H3 reading and cautions in `tasks/todo.md`. No API calls, and no changes to code, prompts, or `PREREGISTRATION.md`.
- **Darrel:** Asked for the analysis. Review of the reading: not recorded.

## 2026-11-13: Review and draft PREREGISTRATION.md sections 1–3
- **Claude:** Reviewed sections 1–3 against `tasks/todo.md` and checked each pilot number against `analysis_pilot_v3`. Found a missing lock statement, a sequential description of the design, a pilot mean described as an average, unlabeled consultancy numbers, the debate H2 null left out, and an unresolved H3 decision rule that conflicts with itself. Drafted replacement text for sections 1–3 (saved to the session scratchpad), then applied it to `PREREGISTRATION.md`. Left ⚑ placeholders for the Section 2 background paragraph and the H1/H2 support rules, and kept the H3 conflict open for Section 6. No changes to prompts, configs, code, or analysis, and no dev runs.
- **Darrel:** Asked for the review, the draft, and then for the edits to be applied. Decisions on the ⚑ items and the Section 2 background: not recorded. Wording of the applied text: not recorded.

## 2026-11-13: Review the full PREREGISTRATION.md draft
- **Claude:** Reviewed the whole draft for completeness, accuracy, form, style, and tone. Checked the embedded prompts against `prompts/*_v2/` by script, the pilot numbers against `analysis_pilot_v3/results.md`, the filters against `data.py`, the settings against `configs/final.yaml`, and the scoring, retry, and bootstrap rules against `judge.py`, `protocols.py`, and `analyze.py`. Reported findings in the session. No changes to `PREREGISTRATION.md`, prompts, configs, code, or analysis, and no API calls.
- **Darrel:** Asked for the review. Decisions on the findings: not recorded.

## 2026-11-13: Apply mechanical and accuracy fixes to PREREGISTRATION.md
- **Claude:** Applied the fixes from the review by script. Moved the prompt text to an appendix rebuilt from `prompts/*_v2/` (now all 18 distinct prompt texts, adding the biased consultancy judge and the debater user message; checked verbatim by script). Corrected the retry, invalid-vote, tie, and forfeit rules to match `judge.py` and `protocols.py`, the seed and reproducibility statement, the quote-matching rule, the prompt-hash statement, the cost estimate (about $68), the Gate 3 history, and the list of changes from `PLAN.md`. Registered the forfeits-excluded check that `analyze.py` already runs. Left five ⚑ markers for open decisions. Did not change the hypotheses, the H2/H3 decision rules, the precision figure, the Section 2 background, or Section 10. No changes to prompts, configs, code, or analysis, and no API calls.
- **Darrel:** Asked for the fixes to be applied. Review of the applied text and decisions on the ⚑ items: not recorded.

## 2026-11-13: Add vote agreement to analyze.py
- **Claude:** Added `unanimous` and `vote_agreement` to `analyze.py`: per cell, the share of judged verdicts where every vote is valid and all agree, with a story-bootstrap interval, written to `results.json` and `results.md`. Chose the definition (an invalid vote breaks agreement; forfeits are left out). Added 2 tests and one assertion (186 pass). Reran the pilot analysis to the session scratchpad: agreement matches the scratch-script figures (consultancy 0.905 → 0.830, debate 0.93 to 0.97) and every other number is identical to `analysis_pilot_v3`. Replaced the ⚑ on the diagnostic in `PREREGISTRATION.md` with the definition. No API calls.
- **Darrel:** Asked for the addition. Review of the code and the definition: not recorded.

## 2026-11-13: Resolve the four open flags in PREREGISTRATION.md and add the error-review draw
- **Claude:** Recommended wording for the four ⚑ items, then applied it: the criterion for claiming exploitation (Section 7), the H3 split as secondary with no support rule, the error-review definition, draw, and five failure types, and the rule for a harness bug during the run (Section 9). Wrote `src/debate_bias/error_review.py` (the draw), `scripts/sample_errors.py` (the command), and 3 tests (189 pass). Chose that ties and forfeits are not errors, that only questions in the primary analysis count, and that each protocol gets a fresh seeded generator. Tried the script on the pilot runs with output to the session scratchpad (7 debate and 25 consultancy error transcripts). No API calls.
- **Darrel:** Asked for the recommendations, then for all four to be applied and the script written. Review of the wording, the failure types, and the code: not recorded.

## 2026-11-13: Change the support rule to the interval rule with a size label
- **Claude:** Recommended fixes for the three open review items (the H3 decision-rule labels, the 0.10 bars against the pilot, and the stale precision figure), with a back-of-envelope precision estimate scaled from the pilot interval (about ±3 to ±4 points on H3 at 350 questions; the within-story correlation of 0.1 to 0.3 is an assumption). Applied the chosen version to `PREREGISTRATION.md`: one three-way interval rule for H1 to H3 (Sections 3 and 6), 0.10 kept as a size label with the original-rule verdict also reported, the new precision statement (Section 5), and a disclosure in Section 8 that the pilot's H3 and consultancy penalty pass the new rule and not the old. `PLAN.md` is unchanged. No changes to prompts, configs, or code, and no API calls.
- **Darrel:** Chose the interval rule with the size label and disclosure over keeping 0.10 as the bar, and asked for it to be applied. Review of the applied wording: not recorded.

## 2026-11-13: Replace the precision estimate with a simulation from the pilot
- **Claude:** Wrote `scripts/precision_from_pilot.py`: it resamples the pilot's per-question scores (cells kept paired) into simulated final runs of 350 questions from 83 stories, with story sizes drawn from the train split, and applies the story bootstrap to each (2,000 runs, 2,000 resamples, seed 0). Chose the model for related questions (a story "theme" copied with probability sqrt(icc)) and the assumed correlations (0, 0.1, 0.3). Ran it (no API calls, dev not read) and replaced the Section 5 precision statement in `PREREGISTRATION.md` with its numbers: H3 half-width ±0.028 to ±0.042, and power at the pilot's effect sizes. No tests added for the script.
- **Darrel:** Asked for the back-of-envelope figure to be replaced with a proper resampling. Review of the simulation's assumptions and the new wording: not recorded.

## 2026-11-13: Reword H2 and record the failure-type confirmation
- **Claude:** Reworded H2 in `PREREGISTRATION.md` Section 3 so it describes the comparison the penalty measures (biased judge with informed arguers against unbiased judge with uninformed arguers) and noted the change from `PLAN.md` in Section 8. The estimate and `PLAN.md` are unchanged. Recommended changes to the Section 2 background and Section 10 in the session without editing them.
- **Darrel:** Asked for the H2 correction and the recommendations. Confirmed the five error-review failure types. The bug-rerun clause in Section 9: not recorded.

## 2026-11-13: Apply the background and Section 10 changes to PREREGISTRATION.md
- **Claude:** Replaced the Section 2 background paragraph with the refined version recommended in the session, and rewrote Section 10: corrected two of Darrel's bullets, kept his answer-wording bullet unchanged, removed the "single consultant" bullet, and added eight limitations (ceiling, pilot-chosen wording, partial knowledge, prompt asymmetry, one dataset with doubtful labels, no human judges, reproducibility, error review). The wording of the new text is Claude's.
- **Darrel:** Wrote the original background paragraph and the original four limitations, and asked for the recommended changes to be applied. Review of the applied wording: not recorded.

## 2026-11-13: Update PLAN.md and commit the preregistration draft
- **Claude:** Updated `PLAN.md` to match the preregistration: the reworded H2, and a dated revision under "Expected precision" with the new precision estimate and the interval support rule. Committed the day's work. `PREREGISTRATION.md` is still marked DRAFT and is not locked.
- **Darrel:** Confirmed the bug-rerun clause in Section 9, and asked for the `PLAN.md` update and the commit.

## 2026-11-13: Lock the preregistration
- **Claude:** Checked before the lock that no draft markers remain, that every v2 prompt file appears verbatim in the appendix, and that the tests pass (189). Updated the status header and the lock date in Section 1, committed `PREREGISTRATION.md` as final, and tagged the commit `prereg-lock`. No dev model calls have been made, and the final run has not started.
- **Darrel:** Changed the status from DRAFT to FINAL himself and asked for the lock. His final read of the locked text: not recorded.

## 2026-11-13: Start the locked final run
- **Claude:** Before starting, checked that the tests pass (189), that nothing had changed since the `prereg-lock` tag, and that no final-run output existed. Stated the expected cost (about $68, with a $150 cap). Then started the run once on the dev split with all conditions through the Batch API: `uv run python -m debate_bias.run --config configs/final.yaml --run final --batch`. Output goes to `results/final/final/`, and the console log goes to `results/final/run_log.txt`. The first pass sent 7,000 calls for 350 questions.
- **Darrel:** Approved the cost and asked for the run to start on November 13, one day ahead of the schedule.

## 2026-11-14: Final run finished and checked for completeness
- **Claude:** The final run finished in 5 batch passes with no errors, at a cost of $50.75 against the $150 cap. Checked the records: 2,100 transcripts (350 questions × 3 protocol transcripts × informed and uninformed arguers) and 7,700 verdicts (22 per question), covering all 350 questions, with 0 forfeits, 0 ties, and 0 invalid votes. The preregistered analysis has not been run.
- **Darrel:** not recorded.

## 2026-11-14: Run the preregistered analysis on the final run
- **Claude:** Ran the preregistered command once: `uv run python -m debate_bias.analyze --runs results/final/final --out results/final/analysis` (10,000 story-bootstrap resamples, seed 0). Output: `results.json`, `results.md`, and `accuracy.png`. All 350 questions from 83 stories were analyzed, none were dropped, and there were 0 forfeits, ties, invalid votes, and flagged rule mentions. Applied the Section 6 and Section 7 rules in the session summary. No code, prompts, or configs changed, and no API calls.
- **Darrel:** Asked for the analysis to be run. Interpretation of the results: not recorded.

## 2026-11-14: Run the error-review draw on the final run
- **Claude:** Ran the preregistered draw: `uv run python scripts/sample_errors.py --runs results/final/final --out results/final/error_review`. It drew 15 debate and 15 consultancy error transcripts (consultancy from 166 error transcripts) and wrote `error_review.json`. No transcripts were read or coded, no code changed, and no API calls.
- **Darrel:** Asked for the draw. The coding: not started.

## 2026-11-15: Commit the final-run results
- **Claude:** Committed the final run's console log, the analysis output (`results.md`, `results.json`, `accuracy.png`), the error-review draw, and this log. Left the raw run records (`calls.jsonl`, `transcripts.jsonl`, `verdicts.jsonl`, `batches.json`) out of git: they quote the stories, whose licensing hasn't been checked, and `calls.jsonl` is about 100 MB.
- **Darrel:** Asked for the final-run results to be committed. Decision on committing the raw records: not recorded.

## 2026-11-15: Ignore the raw final-run records
- **Claude:** Added `results/final/final/` to `.gitignore` so the raw run records can't be committed by accident, and committed the change.
- **Darrel:** Asked for the folder to be ignored. Decision on publishing the transcripts: not recorded.

## 2026-11-15: Draft codes for the 30 error-review transcripts
- **Claude:** Wrote a scratch script that produced one reading file per drawn transcript (story, question, transcript as the judge saw it, and every biased-judge vote). Three subagents drafted codes with the Section 7 codebook, 10 items each. Claude checked some items by hand: item 16 in full, the rule-reliance evidence on items 01 and 26, the judge-misreads-tags claim on items 03, 13, and 22, and the wrong-order column against `error_review.json` (one fix). Collected everything in `results/final/error_review/codes_draft.md`, marked DRAFT, with notes on codebook gaps. No code, prompts, or configs changed, and no API calls.
- **Darrel:** Asked for draft codes. His review of the codes: not recorded.

## 2026-11-16: Count untagged story quotes across the final run (exploratory)
- **Claude:** Wrote a scratch script (in the session scratchpad, not the repo) that finds quotes of 3+ words in plain quotation marks in every argument turn and checks them against the story with the verifier's own exact-match check. Result: 5,460 real story quotes were left untagged, against 26,085 verified tagged quotes. 3,799 of those 5,460 never appear verified elsewhere in their transcript. The rate is about the same on both sides in each protocol and highest in round 1. 4 turns had an unclosed `<quote>` tag. Checked a random sample of 12 matches by eye. No code, prompts, or configs changed, and no API calls.
- **Darrel:** Asked for the count. Whether to report it, and whether to add the script to the repo: not recorded.

## 2026-11-16: Move the untagged-quote count into scripts/
- **Claude:** Moved the scratch script into `scripts/count_untagged_quotes.py`. It now takes the run folder as an argument and reports "lost" quotes (never verified elsewhere in the transcript) in place of all plain quotes, plus per-protocol rows. Added `tests/test_count_untagged_quotes.py` with 3 tests (192 pass). Reran it on the final run, and the totals match the earlier count. New: lost quotes are 15% of real story quotes in consultancy and 8% in debate. Committed the script, the test, and this log.
- **Darrel:** Asked for the script to be moved into `scripts/` and committed.

## 2026-11-17: Check licensing and commit the final-run records
- **Claude:** Looked up the licensing terms. QuALITY is CC BY 4.0 (project homepage). All 197 stories used (83 dev, 114 train) are Project Gutenberg texts with the standard Gutenberg license field, and nearly all carry the note that no US copyright renewal was found. Found that the saved records hold short quotes only, never the full story, which corrects an earlier claim in this session. Compressed `transcripts.jsonl` and `verdicts.jsonl` with `gzip -9 -n` into `results/transcripts/final/`, checked that both decompress to identical files, and confirmed that `analyze.py` run on the decompressed copies reproduces `results.md` and `results.json` exactly, apart from the run path. Committed them. `calls.jsonl` and `batches.json` stay local. The README attribution has not been written yet.
- **Darrel:** Asked for the licensing lookup, then decided to publish the transcripts and verdicts compressed.

## 2026-11-17: Make analyze.py read the gzip records directly
- **Claude:** Added `read_records` to `analyze.py`. It reads `<name>.jsonl` or `<name>.jsonl.gz`, and refuses a folder that holds both. `load_runs` now uses it, so `scripts/sample_errors.py` reads gzip records too, and `scripts/count_untagged_quotes.py` was switched to it. Updated the example commands to `results/transcripts/final`. Added 1 test (193 pass). Running from `results/transcripts/final` reproduces `results.md`, `results.json`, `accuracy.png`, and `error_review.json` exactly (the run path aside), plus the untagged-quote totals. This changes how `analyze.py` reads files after the lock, but no analysis code and no numbers. Committed.
- **Darrel:** Asked for `analyze.py` to read the `.gz` files directly.

## 2026-11-17: Add data attribution to the README
- **Claude:** Added a "Data and licensing" section to `README.md`. It credits QuALITY (Pang et al., 2022) under CC BY 4.0, lists the changes made to the questions (filters, two options), and states that the stories are US public-domain Project Gutenberg texts that appear only as short excerpts, with a note for readers outside the US and a no-affiliation line. The wording is Claude's. Committed and pushed.
- **Darrel:** Asked for the attribution. Review of the wording: not recorded.

## 2026-11-20: Update the README for the finished run
- **Claude:** Rewrote `README.md`: new status line, a table of where the report, preregistration, results, figure, transcripts, and error-review files are, the headline results with what they do and don't show, commands to reproduce the analysis from the saved records, and a "Deviations from the plan" section (before the lock, after the lock, and the division of work). Rewrote the AI-use section from this log. The wording is Claude's.
- **Darrel:** Asked for the update, and stated that Claude did more of the writing and drafting than planned because of time constraints and because he is still learning what good research looks like. Review of the wording: not recorded.

## 2026-11-20: Add the draft error-review codes to the repo
- **Claude:** Staged `results/final/error_review/codes_draft.md` (drafted on 2026-11-15) so it can be committed. Linked it from the README's "Where to find things" table and its "After the lock" deviations, both marked as a Claude draft that Darrel has not reviewed, and updated the layout table.
- **Darrel:** Asked for the draft codes to be added to the repo and the README updated. His review of the codes: not recorded.

## 2026-11-20: Commit the report draft
- **Claude:** Committed `writeup/report.md` as it stood in the working tree, without editing it. The draft's own "Deviations and AI use" section says Claude (Claude Opus 5.5, in the Claude app) drafted it from the results files and the locked preregistration. That drafting session has no earlier entry in this log.
- **Darrel:** Asked for the draft to be committed and pushed. His revisions to the draft: not recorded.
