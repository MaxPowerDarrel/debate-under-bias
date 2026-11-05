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

## Day 3 (Thu, Nov 5): `llm.py` with logging, cache, and cost tracking

Done when a repeated call is served from the cache.

### API facts that shape the design (from the current Claude API reference)
- **No sampling controls.** Sonnet 5.5 and Haiku 5.5 reject non-default `temperature`, `top_p`, and `top_k`, and the API has no seed. Judge votes therefore can't be made deterministic. The three votes are three independent samples, and each one gets its own cache key through a `sample` index.
- **Thinking is always adaptive** on both models and can't be turned off; Sonnet 5.5 only accepts `between_tools`. Thinking tokens are billed as output, so the plan's 500 output tokens per call may be too low. The Day 8 pilot will measure it. `effort` sets thinking depth, and the defaults differ by model (Sonnet `high`, Haiku `medium`). We'll pin it in the config so it's recorded and doesn't silently depend on a default.
- **Refusals** come back as `stop_reason: "refusal"` with HTTP 200. We record them as data and never retry them, because `CLAUDE.md` requires reporting refusals.
- **No refusal fallbacks.** The API can rerun a refused request on another model, which would silently swap the model mid-experiment. We leave it off.
- **Prices (standard rate):** Sonnet 5.5 costs $2 per million input tokens and $10 per million output. Haiku 5.5 costs $0.10 input and $0.50 output for prompts up to 100K tokens. Batch is half price.

### Plan
- [x] `call(model, system, messages, *, max_tokens, effort, sample=0, tag)` returns a `Response` with the text, stop reason, usage, cost, a `cached` flag, and the cache key.
- [x] **Cache:** the key is the SHA-256 of the canonical JSON of every request field plus `sample`. Each entry is one JSON file under `.cache/llm/` (gitignored), written to a temp file and then renamed so a crash can't leave a half-written entry. A cache hit costs $0 and makes no API call.
- [x] **Log:** every call, including cache hits, appends one JSONL line to the run's log. The line holds the timestamp, model ID, prompt hash, cache key, sample, effort, `tag` (condition or question ID), token counts, cost, stop reason, request ID, and `cached`. The runner adds the config and seed to each record when it opens the log.
- [x] **Spending cap:** a `Budget(cap_usd)` adds up real spend and raises `BudgetExceeded` before any new paid call once spend reaches the cap. Cache hits always go through, so resuming a run never hits the cap on work already paid for. With sequential calls, the most it can go over is the cost of one call.
- [x] **Retries:** use the SDK's built-in retries for 429, 5xx, and connection errors (`max_retries` set to 5). Errors like a 400 fail loudly.
- [x] **Prompt hash:** SHA-256 of the system text plus messages, logged so runs can be grouped by prompt version.
- [x] Add `effort` per role to both configs.
- [x] Tests with a fake client and no API calls: the same request is served from the cache with no second API call, a different `sample` gets a different key, cost math, the cap blocks paid calls but allows cache hits, refusals are recorded and not retried, and every call writes a log line.
- [x] Real check: one tiny Haiku call made twice, with the second served from the cache (under $0.001).
- [x] Add an entry to `AI_USE_LOG.md`.

### Not in scope today
- **Batch API.** Batches return in any order after a delay, so they belong in the runner (`run.py`) rather than here. The cache key and record format will be the same, so batch results can go into the same cache later. Calls are synchronous until then.

### Review
- `uv run pytest`: 36 passed, including 12 new tests in `tests/test_llm.py` that use a fake client and make no API calls.
- Real check: the same Haiku 5.5 call was made twice. The first was a paid API call ($0.0000046). The second was served from the cache with no API call, and the log shows `cached: true`, a cost of $0, and the original request ID.
- Usage data reports `output_tokens_details.thinking_tokens`, so the Day 8 pilot can measure thinking cost per role directly.
- Effort is now pinned in both configs (arguer `high`, judge `medium`), and a test checks that pilot and final match.

## Day 4 (Fri, Nov 6, started Nov 5): `quotes.py` and its tests

Done when the quote tests pass. Darrel also reads Kenton et al.

### Reference: Khan et al.'s strict verification (`web/backend/services/parser.py`, MIT)
- Normalize both the quote and the story: curly quotes become straight, all ASCII punctuation is removed, text is lowercased, and runs of whitespace become one space.
- A quote is verified only if its normalized text appears as a contiguous substring of the normalized story.
- Verified quotes are re-tagged `<v_quote>` and unverified ones `<u_quote>`. Any `v_quote` or `u_quote` tags already in the text are first turned back into `<quote>`, so a debater can't mark its own quote as verified.

### Plan
- [x] `normalize(text)`: Khan's rule, plus en and em dashes and the ellipsis character treated as punctuation. Punctuation becomes a space instead of being deleted, so "word—word" and "word - word" normalize the same way. Those are non-ASCII, so Khan's rule leaves them in and a correct quote fails if the model writes "-" or "...".
- [x] `verify(argument, story) -> Verified(text, verified, unverified)`: strip any debater-written `v_quote`/`u_quote` tags, then check each `<quote>…</quote>`, including quotes that span lines.
- [x] Keep Khan's strict rule with no fuzzy matching. A quote that skips text with "..." counts as unverified. No minimum length, matching Khan.
- [x] Leave an unclosed `<quote>` as plain text. It's never verified.
- [x] Return counts so the analysis can report verified and unverified quotes per role (needed for the Gate 3 bias check).
- [x] Tests: exact match, changes in case, punctuation, whitespace, and curly quotes, dashes, a quote that isn't in the story, an elided quote, faked `v_quote` tags, multi-line quotes, multiple quotes, unclosed tags, an empty quote, and one real QuALITY story.
- [x] Added during the build and not in the approved plan: quotes must match whole words, so "he ran" can't match inside "she ranked". Khan's plain substring check allows that.
- [x] Add an entry to `AI_USE_LOG.md`.

### Left for `protocols.py` (Day 5)
- Word limits must never cut a quote in half. Khan closes a cut-off quote tag. Decide when truncation is built.

### Review
- `uv run pytest`: 57 passed, including 21 new tests in `tests/test_quotes.py`. One of them checks 20 sentences from a real train story; all of them verify.
- Three departures from Khan, each explained in the `quotes.py` docstring: punctuation becomes a space, an empty quote is unverified, and quotes must match whole words.
