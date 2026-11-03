# Debate Under Biased Oversight

Research question: when debaters know a judge's flaw, does debate reduce the damage from that flaw compared with a single AI arguing an assigned answer?

This is Darrel's independent project for his Anthropic Research Resident application. Applications close November 22, 2026 at 11:59 PM PT, and the target submission date is November 21.

@PLAN.md

`PLAN.md` is this project's constitution. It covers the goals, scope, assumptions, definition of done, risks, and timetable. Use its schedule to find the current task, and raise any change to scope or dates before making it.

## Commands

```bash
uv sync                                 # Install dependencies
uv run pytest                           # Run tests
uv run python scripts/smoke_test.py     # Make two small paid API calls
uv run python scripts/power_sim.py      # Rerun the precision simulation
```

## Experiment rules

These protect the validity of the result:

- **Keep the dev split untouched.** Use train for all development, prompt tuning, and pilots. Use dev only for the locked final run.
- **Respect the lock.** Once `PREREGISTRATION.md` is committed as final, don't change prompts, filters, or the planned analysis. Label anything added later as exploratory.
- **Run the final experiment once.** Resume interrupted work, but don't rerun it to get a better result.
- **Keep the story from judges.** Only the expert baseline may see story text, and a test must enforce this.
- **Don't compare the two sides in the bias rule.** A rule like "favor the answer with more verified quotes" makes a lone consultant win automatically.
- **Balance every condition.** Run consultancy on both answers, and judge each debate with the debater order swapped.
- **Resample by story.** Confidence intervals must bootstrap stories, not individual questions.
- **Report results as they are.** Never invent or adjust results, and include null results, negative results, refusals, and exclusions.

## Spending and secrets

- **Ask before paid runs.** Get Darrel's approval before any API run beyond a small test, and state the expected cost first.
- **Enforce the caps.** The pilot cap is $50 and the final cap is $150, as set in `configs/`. Runs must stop automatically at the cap.
- **Reuse work.** Cache calls by their inputs, and make runs resumable so a crash never repeats paid work.
- **Protect secrets.** Never read, print, or commit `.env` or an API key.

## Code

- Keep each module focused on the job described in its docstring.
- Log the model ID, prompt hash, config, seed, and token counts with every call.
- Keep prompts as versioned files in `prompts/`, not inline in code.
- Add tests for quote verification, answer balancing, order swaps, word limits, and vote counting as those features are built.
- Don't commit `data/` or pilot output. Check the licensing terms before publishing transcripts that quote the stories.

## Working with Darrel

- Explain design choices and non-obvious code. He needs to be able to explain every design choice and important line without assistance in a research discussion.
- Darrel writes the first drafts of the report, resume changes, and application answers himself. Claude may review and refine them, but shouldn't write them from scratch. This follows [Anthropic's candidate AI guidance](https://www.anthropic.com/candidate-ai-guidance) for the application materials.
- Don't help with Anthropic take-home assessments or live interviews unless Anthropic explicitly allows it.
- Keep the README's AI-use section accurate as the work progresses.
- Describe this project as an independent replication and extension, not as published research.
