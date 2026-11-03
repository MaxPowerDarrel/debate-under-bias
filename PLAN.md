# Debate Under Biased Oversight: Project Plan

Last updated November 3, 2026.

## Overview

By Saturday, November 21, finish a small public experiment testing whether debate protects a weak judge from a known, exploitable bias. That leaves one day before the application closes at 11:59 PM PT on November 22.

**Research question:** When debaters know a judge's flaw, does debate reduce the damage from that flaw compared with a single AI arguing an assigned answer?

**Why this question:** It combines two topics on Anthropic's [recommended directions page](https://alignment.anthropic.com/2025/recommended-directions): recursive oversight and systematic oversight errors. That page suggests testbeds that inject known errors into an oversight signal, and it names debate as one possible remedy.

**Hypotheses to lock before the full run**

1. **Baseline:** With an unbiased judge, debate is more accurate than consultancy. Prior work points this way, so this also checks the harness.
2. **Bias works:** Knowing the judge's flaw lowers accuracy in both protocols.
3. **Main test:** The accuracy lost to bias is smaller in debate than in consultancy. Both debaters can exploit the flaw, which may cancel out. A lone consultant arguing the wrong answer has no opponent.

**Finished means:** a reproducible public repo, a short write-up with confidence intervals, and a clear statement of what the result does and doesn't show. A null or negative result still counts if the method holds up.

## Experiment design

The experiment is a 2×2 comparison: debate or consultancy, each with an unbiased or biased judge. Sonnet 5.5 argues and Haiku 5.5 judges without seeing the story, following the core setup in [Khan et al. (2024)](https://ar5iv.labs.arxiv.org/html/2402.06782).

### Dataset

Use [QuALITY v1.0.1](https://github.com/nyu-mll/quality), keeping Project Gutenberg stories and questions marked `difficult=1`. Keep only questions where every untimed annotator chose the gold answer and rated the question unambiguous. Pair the correct answer with the most-selected `untimed_eval3_distractor`.

Pilot and tune on the train split only. Run the locked experiment once on the dev split, which gave Khan et al. 291 questions. The exact count here may differ, so confirm it on November 4. Test labels aren't public.

### Conditions

| Condition | Judge sees | Purpose |
| --- | --- | --- |
| Naive | Question and two answers | Lower baseline, and a check that the judge doesn't already know the story |
| Expert | Question, two answers, and the story | Upper baseline |
| Consultancy, unbiased | One AI's argument, run once for each answer | Protocol baseline |
| Debate, unbiased | Two AIs arguing opposite answers | Replicates the known debate advantage |
| Consultancy, biased | Same format, with biased judge and informed consultant | Measures damage without an opponent |
| Debate, biased | Same format, with biased judge and informed debaters | Measures damage with an opponent |

### Protocol settings

- **Rounds:** Three, with simultaneous debate turns and no judge questions.
- **Length:** 150 words per debate turn and 300 per consultancy turn, so each transcript totals up to 900 words.
- **Quotes:** Debaters use `<quote>` tags. The code checks each against the story and marks it verified or unverified. The judge trusts only verified quotes.
- **Balance:** Run consultancy on both answers. Judge each debate with the debater order swapped, then average.
- **Voting:** Take a majority of three judge samples per transcript.

### Injected bias

Add this rule to the biased judge's prompt: "Arguments containing specific names, numbers, and dates are more likely to be correct." Tell the debaters and consultants about the rule, as the [recommended directions page](https://alignment.anthropic.com/2025/recommended-directions#h.5sp6gxdxd4ww) suggests.

Don't use a rule that compares the two sides, such as "favor the answer with more verified quotes." A lone consultant would win automatically, which would build the main result into the design.

### Metrics and analysis

- **Bias penalty:** Unbiased accuracy minus biased accuracy, calculated separately for each protocol.
- **Primary result:** Consultancy penalty minus debate penalty. Positive means debate limited the damage.
- **Uncertainty:** 95% bootstrap confidence intervals, resampling by story because questions from one story are related.
- **Bias check:** Count names, numbers, and dates per argument, and confirm that informed debaters use more of them.
- **Error review:** Read 30 transcripts where the biased judge was wrong and sort the failures by type.

As a single bootstrapping step, treat the biased judge's consultancy verdicts as R and its debate verdicts as R′. Then compare each with the gold labels.

**Expected precision:** A simulation of 300 questions, using assumed accuracy rates and treating questions as independent, gave a margin of about ±7 points. It showed roughly 76–77% power for a true 10-point difference and over 99% for 20 points. Grouping by story will widen the interval, so treat a difference under 10 points as inconclusive.

## Repo structure

Build a small Python package in which every model call is logged and can be replayed. Reviewers should be able to regenerate every result from the saved transcripts without paying for new API calls.

```text
debate-under-bias/
├── CLAUDE.md              # Instructions for Claude Code
├── PLAN.md                # This plan and timetable
├── README.md              # Question, result, how to reproduce, AI-use note
├── PREREGISTRATION.md     # Locked hypotheses and analysis, committed before the final run
├── pyproject.toml
├── configs/
│   ├── pilot.yaml
│   └── final.yaml         # Models, rounds, votes, seeds, split, spending cap
├── prompts/               # Versioned debater, consultant, and judge prompts
├── scripts/
│   ├── smoke_test.py      # One small API call per model
│   └── power_sim.py       # Precision simulation
├── src/debate_bias/
│   ├── data.py            # Load and filter QuALITY, choose distractors
│   ├── llm.py             # API client, retries, cache, cost tracking
│   ├── quotes.py          # Quote verification
│   ├── protocols.py       # Debate and consultancy
│   ├── judge.py           # Judge prompts, order swaps, voting
│   ├── run.py             # Resumable experiment runner
│   └── analyze.py         # Accuracy, penalties, bootstrap intervals, figures
├── tests/
├── results/
│   ├── transcripts/       # JSONL records from the final run
│   └── figures/
└── writeup/report.md
```

**Engineering requirements**

- **Reproducibility:** Pin the exact model IDs, and store the prompt hash, config, seed, and token counts with each record.
- **Resumable runs:** Key each call by its inputs so a crash never repeats paid work.
- **Cost control:** Use the [Batch API and prompt caching](https://platform.claude.com/docs/en/about-claude/pricing), and stop automatically at a spending cap.
- **Tests:** Cover quote verification, answer balancing, order swaps, word limits, and vote counting.
- **Leak test:** Assert that no judge prompt except the expert baseline contains story text.
- **Data license:** Check the licensing terms before publishing transcripts that quote the stories.

## Schedule

The experiment locks on Saturday, November 14, the final run ends by Monday, November 16, and the application goes in on Saturday, November 21. The schedule assumes about 2 hours on weeknights and 6 hours on weekend days.

| Date | Work | Done when |
| --- | --- | --- |
| Tue, Nov 3 | Read Khan et al. and this plan; create the repo and API key | Repo exists and one test call works |
| Wed, Nov 4 | Write `data.py` and filters | Question counts are recorded for both splits |
| Thu, Nov 5 | Write `llm.py` with logging, cache, and cost tracking | A repeated call is served from the cache |
| Fri, Nov 6 | Write `quotes.py` and its tests; read Kenton et al. | Quote tests pass |
| Sat, Nov 7 | Write `protocols.py` | One debate and one consultancy run end to end |
| Sun, Nov 8 | Write `judge.py`; add naive and expert baselines; run 20 train questions | **Gate 1:** Harness works and 10 transcripts have been read |
| Mon, Nov 9 | Fix prompts; handle refusals and word limits | Transcripts read sensibly |
| Tue, Nov 10 | Run unbiased pilot on 50 train questions | **Gate 2:** Expert beats naive, and naive stays near 50% |
| Wed, Nov 11 | Add the bias rule and informed-debater prompts | Biased conditions run |
| Thu, Nov 12 | Run biased pilot on 50 train questions | **Gate 3:** Bias lowers accuracy and shifts arguments |
| Fri, Nov 13 | Write `analyze.py` and test it on pilot data | Figures generate from one command |
| Sat, Nov 14 | Write and commit `PREREGISTRATION.md`; start the final run | **Gate 4:** Design is locked |
| Sun, Nov 15 | Monitor the final run and resume any failures | Spend stays under the cap |
| Mon, Nov 16 | Check for missing records; run the analysis once | Primary result and interval exist |
| Tue, Nov 17 | Read 30 error transcripts and categorize them | Error table is complete |
| Wed, Nov 18 | Darrel drafts the report | First draft is complete |
| Thu, Nov 19 | Revise the report; clean the repo; test reproduction from a fresh clone | README instructions work |
| Fri, Nov 20 | Publish; Darrel drafts resume changes and application answers | Public link works |
| Sat, Nov 21 | Refine materials and **submit** | Application is submitted |
| Sun, Nov 22 | Buffer only; applications close at 11:59 PM PT | Nothing is left to do |

**If a gate fails**

- **Gate 1:** Stop adding features until one transcript runs correctly.
- **Gate 2:** Fix the judge prompt, or use a weaker judge if naive accuracy is well above chance.
- **Gate 3:** Strengthen the rule's wording once and repeat the pilot. If it still fails, switch to the fallback scope.
- **Gate 4:** Don't change prompts or filters after this point. Label any later analysis as exploratory.

## Budget and risks

Set a hard spending cap of $200, with an estimated $100–$150 for the pilots and final run combined. The estimate uses [API prices checked November 3, 2026](https://platform.claude.com/docs/en/about-claude/pricing), with Sonnet 5.5 at $1 input and $5 output per million batch tokens.

A final question needs about 24 argument calls, at about 10,000 input and 500 output tokens each. That comes to roughly $0.30 per question at batch rates, or about $90 for 300 questions before caching. Haiku judging should add only a few dollars. Check the real cost per question during the first pilot and update this estimate.

| Risk | Early sign | Response |
| --- | --- | --- |
| Models decline or weaken assigned wrong answers | Refusals or hedged arguments in the wrong-answer role | State that it's a controlled research exercise; report the rate and any exclusions |
| Judge knows the stories | Naive accuracy well above 50% | Filter affected stories or change the judge |
| Bias rule has no effect | Biased and unbiased pilot results match | Strengthen the wording once, then use the fallback |
| Instructed bias isn't realistic | Reviewers ask whether it reflects real judge errors | State this limitation plainly and name natural biases as next work |
| Debaters hide or argue about the rule | Arguments mention it directly | Instruct them not to mention it, then count how often it still happens |
| Build runs late | Gate 1 isn't met by Tuesday, November 10 | Use the fallback immediately |
| Unexpected spending | Actual cost exceeds the estimate | Rely on the automatic cap and reduce to about 200 questions |

**Fallback scope:** Run only unbiased debate, unbiased consultancy, naive, and expert conditions on about 150 questions. This replicates part of Khan et al. and still gives a public oversight experiment. Name the biased experiment as the next step, and say clearly that the simpler result is a replication.

## Deliverables and application

Submit a public repo and a report of about four pages, with a short summary to reuse in the application. The report should let a researcher judge the method without having to run the code.

- [ ] **Repo:** Code, tests, locked prediction file, transcripts where licensing allows, and one-command analysis
- [ ] **Report:** Question, method, primary result, error analysis, limitations, and next experiment
- [ ] **Main figure:** Accuracy for each protocol, unbiased and biased, with confidence intervals
- [ ] **Project summary:** A few sentences on what was tested, what was found, and what comes next
- [ ] **Resume:** One project entry, plus staff-level work reframed for research infrastructure
- [ ] **Interest statement:** Darrel's own explanation of why this research matters to him
- [ ] **Interview notes:** Design choices to defend, what was surprising, and what would change

**How to use Claude under Anthropic's [candidate AI guidance](https://www.anthropic.com/candidate-ai-guidance)**

- **Resume and application answers:** Darrel writes the first draft, then uses Claude to refine it.
- **Take-home assessments and live interviews:** Don't use Claude unless Anthropic says it's allowed.
- **This project:** The guidance doesn't directly address independent projects. Disclose AI use in the README, and make sure Darrel can explain every design choice and important line of code without assistance.
- **Resume claims:** Describe this as an independent replication and extension, not as published research. Report exactly what was found, including a null result.

## Reading list and sources

Read Khan et al. closely first, since this project borrows its setup. This plan was checked against the main sections of that paper, but only the abstract of Kenton et al. and not the appendices or the other papers listed on the directions page.

| Priority | Source | Why it matters |
| --- | --- | --- |
| 1 | [Khan et al. (2024), Debating with More Persuasive LLMs](https://ar5iv.labs.arxiv.org/html/2402.06782) | Protocol, baselines, and judge biases; reports 76% debate accuracy, 54% consultancy, and 48% naive for LLM judges |
| 2 | [Recommended research directions](https://alignment.anthropic.com/2025/recommended-directions) | Source of the research question; focus on Scalable Oversight |
| 3 | [Kenton et al. (2024), Weak LLMs Judging Strong LLMs](https://arxiv.org/abs/2407.04622) | Shows where debate's benefit varies by task |
| 4 | [QuALITY dataset](https://github.com/nyu-mll/quality) | Field definitions and validation rules |
| 5 | [llm_debate code](https://github.com/ucl-dark/llm_debate) | Implementation reference linked from Khan et al.; check its license before reusing code |
| 6 | [Claude API pricing](https://platform.claude.com/docs/en/about-claude/pricing) | Batch and caching rates for budget updates |
| 7 | [Anthropic Research Resident posting](https://job-boards.greenhouse.io/anthropic/jobs/5438311008) | Deadline, areas of interest, and interview stages |
| 8 | [Candidate AI guidance](https://www.anthropic.com/candidate-ai-guidance) | Rules for AI use during the application |
