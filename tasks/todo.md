# Todo

## Day 2 (Wed, Nov 4): `data.py` and filters

Done when question counts are recorded for both splits.

### Findings before building
- QuALITY v1.0.1 is downloaded to `data/`. Use the `htmlstripped` files so quote checks run against plain text.
- The distractor field is `untimed_best_distractor`. The QuALITY docs call it `untimed_eval3_distractor`, but the data file doesn't. `PLAN.md` uses the docs name and needs fixing.
- Labels are 1-indexed. Some questions have 3 to 7 untimed validators.
- A story is an `article_id`. Several question sets (`set_unique_id`) share one story, so the bootstrap must group by `article_id`.
- Khan et al.'s code (`ucl-dark/llm_debate`, MIT license) also filters on average `untimed_eval2_context` ≥ 1.5 and on `writer_label == gold_label`. Its default keeps one question per story and pools train with dev.

| Filter stage | Train | Dev |
| --- | --- | --- |
| Gutenberg | 2000 | 1552 |
| + `difficult == 1` | 1056 | 873 |
| + all untimed annotators correct | 715 | 531 |
| + all rated unambiguous (current plan) | 603 | 438 |
| + mean context ≥ 1.5 | 497 | 354 |
| + writer label = gold | 461 | 350 |
| One per story | 114 | 83 |

### Plan
- [x] Decide which filters to use: Darrel chose the plan's filters plus Khan's context and writer-label filters (350 dev questions)
- [x] `data.py`: load a split, apply the filters, choose the distractor, and return `Question` records (`question_id`, `article_id`, title, story, question, correct answer, distractor)
- [x] Distractor rule: the option most often chosen by untimed annotators as best distractor, excluding gold. Break ties by lowest option index, which matches what Khan's `max(set(...))` does in practice.
- [x] Record per-stage filter counts so they can be written down
- [x] Tests on small synthetic records: each filter, distractor choice and ties, distractor never equal to gold, 1-indexing
- [x] Record the counts for both splits in `PLAN.md`, and fix the field name there
- [x] Add an entry to `AI_USE_LOG.md`

### Review
- `uv run pytest`: 23 passed. Real-data tests check the counts for both splits, unique IDs, and that the distractor never equals the correct answer.
- `uv run python -m debate_bias.data` prints the per-stage counts. Train: 461 questions from 114 stories. Dev: 350 questions from 83 stories.
- Dev was used only to count questions. No prompts or model calls touched it.
- Darrel ran `uv run pytest` on November 4 and checked the results. He also confirmed that the Day 1 smoke test passed on November 3.
