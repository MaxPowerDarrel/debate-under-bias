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

## Day 5 (Sat, Nov 7, started Nov 6): `protocols.py`

Done when one debate and one consultancy run end to end.

### Reference: Khan et al.'s debater and consultant (`core/config/experiment/debaters/v1.yaml`, `consultants/v1.yaml`, `core/agents/debater_quality.py`, MIT)
- The system prompt gives the role, the word limit, the quote system (`<quote>` tags are checked and shown as `v_quote` or `u_quote` in later rounds), and the judging criteria. The user message gives the question, both answers, the story, the transcript so far, and the request for this turn.
- Output is `<thinking>…</thinking><argument>…</argument>`, and only `<argument>` goes into the transcript.
- Word limits: the prompt asks for 100 (debate) or 200 (consultancy) words. An argument counts as valid at 70–150 or 140–300 words and must contain a quote. Khan draws extra candidates until one is valid, then cuts to `max_words` and closes any quote the cut splits.
- Consultancy rounds after the first answer judge questions. We have no judge questions.

### Plan
- [x] **Prompts as files:** `prompts/debater_v1.md` and `prompts/consultant_v1.md`, adapted from Khan's wording, using `$placeholders` (`string.Template`, since stories can contain `{}`). The story comes first in the system prompt so a shared prefix can be prompt-cached later.
- [x] **No `<thinking>` tags:** Sonnet 5.5 always thinks before answering, so we ask only for `<argument>` tags. Thinking tokens are billed as output either way.
- [x] **Store by side, render per reader:** the transcript stores turns keyed by `correct` or `distractor`. Each debater sees "Your argument" and "Your opponent's argument". The `Debater A/B` labels and the order swap are added when the judge reads it (Day 6). Debaters are told to say "my opponent", never a letter, so swapping the order never contradicts the text.
- [x] **Simultaneous debate:** in round r, both debaters see only rounds 1 to r−1. A test checks that neither prompt contains the other's round-r argument.
- [x] **Consultancy:** three 300-word turns from one consultant, each building on its earlier turns. `run_consultancy` takes the side, and a helper runs both sides, so the pair always stays balanced.
- [x] **Each turn:** take the text inside `<argument>`, apply the word limit, then run `quotes.verify`. Store the raw model text, the final argument, its word count, a `truncated` flag, the verified and unverified quotes, the stop reason, and the cache key.
- [x] **Word limit:** count words with tags removed. If an argument is over the limit, cut it at the limit. If the cut lands inside a quote, cut before that `<quote>` instead of closing it like Khan does, so no shortened quote ever reaches the judge. Add a "[truncated]" marker. No minimum length and no resampling, which keeps every turn as one cached call. Day 9 revisits this once we see real lengths.
- [x] **Missing `<argument>` tag or a refusal:** record it and stop that transcript with `status` set to `format_error` or `refused`. No retries today. Day 9 decides how to handle these.
- [x] **Config:** add `max_tokens.arguer` to both configs. Output is billed by use, so a generous ceiling only stops thinking from being cut off.
- [x] **Tests with a fake LLM and no API calls:** simultaneous turns, consultancy runs on both answers, word limit, no cut quote, argument extraction, faked `v_quote` tags are reset, refusal and format-error status, story present in arguer prompts, and the transcript serializes to JSON.
- [x] **Real check (needs approval):** one train question, one debate (6 Sonnet calls) and both consultancies (6 calls). Estimate: 12 calls at about 8–10K input and 1–3K output tokens at standard rates, about $0.30–$0.70, with a $2 cap for this check. Then we read both transcripts.
- [x] Add an entry to `AI_USE_LOG.md`.

### Not in scope today
- Judge prompts, A/B labels, and order swaps (`judge.py`, Day 6).
- The bias rule and informed-arguer prompts (Day 11).
- Prompt-cache breakpoints and the Batch API (runner work). Prompts are ordered now so they can be added without rewriting them.

### Review
- `uv run pytest`: 78 passed, including 21 new tests in `tests/test_protocols.py` that use a fake LLM and make no API calls.
- `quotes.py` now exposes `reset_tags`, and `verify` uses it. Truncation runs after the tag reset, so a faked `v_quote` can't dodge the rule against cutting through a quote.
- **Real check:** train question `52995_I3M5VUMM_3` (index 0), with one debate and both consultancies. All three transcripts completed with 12 Sonnet calls, no refusals, and no format errors. Cost was **$0.346** at standard rates, under the $2 cap. Output is in `results/pilot/one_question/` (gitignored), and `scripts/run_one_question.py` replays it from the cache for free.
- **Cost:** each call used about 11–12K input and 300–1,200 output tokens, roughly $0.029 at standard rates. Input is about 75% of that, so prompt caching the story prefix should help more than anything else. At batch rates, 24 calls per question comes to about $0.35, close to the plan's $0.30.
- **Thinking:** only 3 of 12 calls used any thinking (481–600 tokens). At `high` effort, Sonnet usually answers these prompts without thinking.

### Found in the transcripts, for Day 9 (handle refusals and word limits)
- **Truncation is common:** 9 of 18 turns went over the limit, by 4–36 words. Khan's prompts ask for fewer words than the hard limit (100 for 150, 200 for 300). Doing the same is probably the fix.
- **Missing quote tags:** the correct-side consultant used plain quotation marks in rounds 1 and 2, so none of its quotes went through verification. The judge will see them as untagged text.
- **Elided quotes:** "the Economic Planning Board... will terminate" was correctly marked unverified under the strict rule, and the opposing debater pointed that out in round 2. The strict rule changes how arguers behave, which is worth a line in the report.
- **No sign of sandbagging:** the distractor arguers argued just as forcefully. One example isn't enough to rule it out.
- Prompt choice to confirm: the consultant prompt keeps Khan's line, "winning the game is the main objective, not absolute honesty." The debater prompt doesn't have it, which also matches Khan.

## Day 6 (Sun, Nov 8, started Nov 7): `judge.py`, naive and expert baselines, 20-question pilot

Done when **Gate 1** passes: the harness works and 10 transcripts have been read.

### Reference: Khan et al.'s judges (`core/config/experiment/judge/`, `core/agents/judge_quality.py`, MIT)
- **Debate and consultancy judges** (`debate/default.yaml`, `consultancy/default.yaml`): told they haven't read the story, told how `v_quote`/`u_quote` work and that plain quotation marks count as unverified, shown the question, answers A and B, and the transcript. Asked to reason inside `<thinking>` and end with `Answer: <A|B>`.
- **Naive** (`baselines/blind.yaml`): question and two answers only; "always choose an answer even if you are not sure".
- **Expert** (`baselines/oracle.yaml`): story, question, two answers; answer only.
- **Order swap:** Khan judges every transcript twice, swapping which answer is A, for all methods. In debate the debater names swap too, so Debater A always argues answer A and speaks first. In consultancy only the answer letters swap.

### Plan
- [x] **Prompts as files:** `prompts/judge_v1/` with `debate.md`, `consultancy.md`, `naive.md`, `expert.md`, adapted from Khan's wording. Only `expert.md` has a `$story` placeholder.
- [x] **Reasoning:** every judge writes a short explanation, then a final line `Answer: A` or `Answer: B`. Haiku 5.5 thinks on its own, but thinking isn't stored, and the Day 17 error review needs the judge's stated reasons. This also covers naive and expert, where Khan asks for the answer only.
- [x] **Render per order:** `render(transcript, order)` builds what the judge sees. In order 0 the correct answer is A; in order 1 it's B. In debate, Debater A argues answer A and its turn is printed first in each round. The arguers never use letters, so the text needs no edits.
- [x] **Balance:** every condition is judged in both orders: debate (1 transcript), consultancy (2 transcripts, one per side), naive and expert (no transcript). A test checks that each answer is A exactly once per transcript.
- [x] **Votes:** 3 samples per (transcript, order), using `sample=0,1,2` so each gets its own cache key. Parse the last `Answer: A|B` line. A refusal or missing answer is an invalid vote and is not retried.
- [x] **Scoring (Darrel chose 0.5 for ties):** majority of valid votes per order. If the valid votes tie or none are valid, that order scores 0.5, the expected value of a coin flip, and the count of such cases is reported. Transcript score = mean of its two orders. Question score per condition = mean over its transcripts (consultancy averages both sides). This follows `PLAN.md`: majority within an order, then average across orders.
- [x] **Leak test:** non-expert prompt builders never receive the story (they take the question, answers, and transcript only). A test uses a story with sentinel sentences that no argument quotes and checks that none of them appear in any naive, debate, or consultancy prompt, and that they do appear in the expert prompt.
- [x] **Config:** add `max_tokens.judge` to both configs. Set to 8000, not the planned 4000: Haiku's thinking counts toward it, and a reply cut off before its answer would become an invalid vote. Output is billed by use, so the higher ceiling costs nothing.
- [x] **`run.py` (minimal):** for each question, run debate and both consultancies, judge all four conditions, and write `transcripts.jsonl` and `verdicts.jsonl`. Resuming relies on the response cache, so a rerun pays only for calls not yet made. Batch API and prompt caching stay for later.
- [x] **Pilot spending across runs:** each pilot run's cap check also adds the spend in every other `results/pilot/**/calls.jsonl`, so the $50 pilot cap holds across all pilots, not per run. A run can also set a smaller cap for itself.
- [x] **Question sample:** 20 train questions from 20 different stories, chosen with seed 0. The first 20 filtered questions come from only about 5 stories.
- [x] **Tests with a fake LLM:** answer parsing (last match wins, lowercase, missing answer), order swap and letters, vote majority and ties, invalid votes, scoring, leak test, and `run.py` writing one record per condition.
- [x] **Real run (needs approval):** 20 train questions, all four conditions unbiased. Estimate about $7 for Sonnet arguers at standard rates (about $0.35 per question, from Day 5) plus under $0.50 for Haiku judging (30 judge calls per question). Run cap **$10**.
- [x] **Read transcripts:** a script prints a transcript as the judge saw it, with the votes. Claude reads 10 and writes notes. Darrel reads at least 10 for Gate 1.
- [x] Add an entry to `AI_USE_LOG.md`.

### Not in scope today
- Fixing the arguer prompts (word limits, missing quote tags): Day 9.
- Bias rule and informed-arguer prompts: Day 11.
- Bootstrap intervals and figures: Day 13. Today's script prints plain accuracy per condition only, which is not a Gate 2 check (that's Day 10, 50 questions).

### Review
- `uv run pytest`: 114 passed. New: `tests/test_judge.py` (answer parsing, order swaps, debater order, consultant letter, leak test, vote scoring, invalid votes, exclusions) and `tests/test_run.py` (every condition in both orders, one question per story, cross-run spending). Also added `Transcript.from_dict` with a round-trip test.
- Added after approval: `build_prompt` raises an error if a non-expert judge is given the story, or if a transcript doesn't match its condition. `scripts/show_transcript.py` prints a saved transcript as the judge saw it, with the votes, at no cost.
- **Real run** `results/pilot/day6_unbiased_20/` (gitignored): 20 train questions from 20 stories. 60 transcripts all completed. 840 calls with no refusals, no invalid votes, no ties, and no exclusions. Cost **$7.55** ($7.14 Sonnet arguers, $0.41 Haiku judges), under the $10 cap. Total pilot spend so far is $7.90 of $50.
- **Cost per question:** $0.36 at standard rates, matching Day 5. Judges add about $0.02 per question.
- Haiku used some thinking on all 600 judge calls.

| Condition | Accuracy (20 questions) | Order 0 / order 1 |
| --- | --- | --- |
| Naive | 0.775 | 0.75 / 0.80 |
| Expert | 0.950 | 0.95 / 0.95 |
| Consultancy | 0.812 (correct side 1.00, distractor side 0.625) | 0.80 / 0.825 |
| Debate | 0.850 | 0.85 / 0.85 |

With 20 questions, each of these has a margin of roughly ±15–20 points, so the protocol differences mean nothing yet. The naive result is the exception, because it's far enough above 50% to matter.

### Gate 1
- Harness: works end to end on 20 questions. Order effects are small.
- Reading: Claude read 8 full transcripts (debates on Q7, Q9, Q10, and Q15; distractor consultancies on Q1, Q6, Q10, and Q14), the expert judge's votes on Q7, and the naive judge's reasons on 8 questions. Darrel read the transcripts and ran the tests on November 7. **Gate 1 passed.** Suggested: `uv run python scripts/show_transcript.py day6_unbiased_20 <n> debate`, with n = 7, 9, 10, and 15, then the consultancies above with `--side distractor`.

### Findings from reading, for Day 9 and Gate 2
1. **The naive judge is at 77.5%, not near 50%. This affects Gate 2.** Its reasons show it isn't recalling the stories. It guesses from how the answers are worded: "specific, less conventional answers often reflect what a story actually says", "Option B is a more generic reason… reads more like a plausible distractor". In this data, the correct answer is often the more specific one. Khan et al. report 48% naive with their judges. The same shortcut shows up in consultancy: on Q1 the judge rejected the distractor consultant because "Answer B is generic". Because of this, consultancy and debate both start well above chance, which leaves less room to measure a difference. Darrel needs to choose a response before the Day 10 pilot (options are listed below).
2. **Missing quote tags, mostly in round 1:** 48 of 240 turns have no quote tags at all. That's 16/40 consultancy and 11/40 debate turns in round 1, falling to 7/40 and 1/40 by round 3. These arguers quote with plain quotation marks. Judges sometimes notice ("none of the consultant's quotations are shown as verified"), but on Q6 a distractor consultant with no tagged quotes still won both orders.
3. **Truncation is now the norm:** 166 of 240 turns went over the limit, by a median of 11 words and at most 45. Judges mention the cut ("I cannot verify the truncated passages", "the final argument is incomplete"), so truncation may cost a side votes. The planned fix stands: ask for fewer words than the hard limit, as Khan does.
4. **One question is ambiguous despite the filters:** on Q7 ("what didn't William decide to do"), even the expert judge picked the distractor in 5 of 6 votes. Questions phrased as negations (Q7, Q14) seem easiest for the distractor side to argue.
5. **The judge made up a claim:** on Q15 the judge said "the quotes from Debater B's side are partly unverified" when every quote was verified. The error review should watch for this.
6. **Debate rescued the judge on Q10:** the distractor consultant won both orders, but in debate the correct side argued against the same quotes and won both orders. This is the debate advantage the experiment is designed to measure.
7. Q15 looks like a fair debate loss. The distractor debater's argument (Rocsates said the same things and wasn't arrested) was clever and supported by verified quotes.
8. **No sign of sandbagging:** distractor arguers argued as hard as correct ones in every transcript read.

### Options for the naive-accuracy problem (Darrel to decide by Day 10)
- **Keep and report.** Measure every protocol against the naive score, and state the answer-wording shortcut as a limitation.
- **Drop questions where naive is right.** This measures oversight only where the judge has no shortcut, but it selects on a judge outcome and shrinks the dataset. It would have to be done on train-derived rules only, or as a separate dev naive pass before the lock.
- **Change the judge prompt** to warn against guessing from answer wording (the Gate 2 response in `PLAN.md`). This may not help, since the shortcut works.
- `PLAN.md`'s other Gate 2 response, a weaker judge, doesn't address this, because the problem isn't story knowledge.
