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
