"""Resumable experiment runner with a spending cap.

For each question, `run_question` makes the debate and both consultancy transcripts, then
judges every condition in both answer orders. `--conditions` picks which conditions run:
`unbiased` (naive, expert, and both protocols with the unbiased judge), `biased` (both
protocols with informed arguers and the biased judge), `cross` (the uninformed transcripts
judged by the biased judge, see `judge.py`), or `all` (the default). It writes two files under
`results/<stage>/<run>/`, where `<stage>` is the config name (`pilot` or `final`):

- `transcripts.jsonl`: one line per debate or consultancy transcript.
- `verdicts.jsonl`: one line per (condition, transcript, order), with every vote.

**Resuming:** every model call goes through the response cache, so rerunning the same
command replays finished calls for free and pays only for calls not yet made. The output
files are rewritten from the start on each run.

**Batch mode:** `--batch` sends the calls through the Message Batches API at half price
(see `batch.py`). The run replays in passes, submitting one batch per pass, and writes the
output files in a final pass once every call is cached. Batch IDs are saved in
`batches.json` in the run folder, so a restarted run collects them instead of paying
again.

**Saved transcripts:** `--transcripts-from <run>` loads the transcripts another run in the
same stage saved, instead of calling the arguers, and judges that run's questions. A new
judge then reads exactly the transcripts the earlier judge read, even if the arguer
requests have changed since (the first unbiased pilot ran before prompt caching, so its
requests no longer match the response cache). Loaded transcripts aren't written again, so
the two runs can be merged in `analyze.py` without duplicates.

**Spending:** the config's cap covers the whole stage, so the cap check counts spend from
every run's `calls.jsonl` under `results/<stage>/`, not just this run's. `--cap` can set a
smaller cap for this run on top of that.

    uv run python -m debate_bias.run --config configs/pilot.yaml --run day6 --num 20 --cap 10
"""

import argparse
import json
from pathlib import Path

import yaml

from .data import Question, load_questions, sample_questions
from .batch import BatchRunner
from .judge import ORDERS, JudgeSettings, Verdict, judge
from .llm import LLM, Budget, Pending, logged_spend
from .protocols import SIDES, ArguerSettings, Transcript, run_consultancy, run_debate

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"


# Each choice lists its cells as (arguers informed, judge biased).
CONDITION_SETS = {
    "unbiased": ((False, False),),
    "biased": ((True, True),),
    "cross": ((False, True),),
    "all": ((False, False), (False, True), (True, True)),
}
Saved = dict[tuple, Transcript]  # (question ID, protocol, consultant side, informed) -> transcript


def load_saved(path: Path) -> Saved:
    """Read a run's `transcripts.jsonl` for `--transcripts-from`."""
    saved = {}
    for line in path.read_text().splitlines():
        t = Transcript.from_dict(json.loads(line))
        saved[t.question_id, t.protocol, t.consultant_side, t.biased] = t
    return saved


def run_question(
    llm: LLM, arguer: ArguerSettings, judge_settings: JudgeSettings, question: Question,
    conditions: str = "all", saved: Saved | None = None,
) -> tuple[list[Transcript], list[Verdict]]:
    """Make every transcript for one question, then judge every condition in both orders.

    Each transcript and each verdict is a separate unit. In batch mode a unit whose next
    call isn't cached raises `Pending`. The other units still run, so one pass collects
    every call that is ready, and the question raises `Pending` at the end.

    With `saved`, transcripts come from an earlier run's file and no arguer is called. A
    saved transcript made with a different prompt version from the config's is an error.
    """
    pending = False

    def attempt(make):
        nonlocal pending
        try:
            return make()
        except Pending:
            pending = True
            return None

    def load(protocol: str, side: str | None, informed: bool) -> Transcript:
        key = (question.question_id, protocol, side, informed)
        if key not in saved:
            raise KeyError(f"No saved transcript for {key}")
        wanted = arguer.prompts_for(protocol, informed)
        if saved[key].prompts != wanted:
            raise ValueError(f"Saved transcript {key} used {saved[key].prompts}, but the config says {wanted}")
        return saved[key]

    cells = CONDITION_SETS[conditions]
    transcripts = []
    for informed in dict.fromkeys(informed for informed, _ in cells):  # Each kind of transcript once, in order
        if saved is not None:
            transcripts += [load("debate", None, informed)] + [load("consultancy", s, informed) for s in SIDES]
            continue
        transcripts.append(attempt(lambda: run_debate(llm, arguer, question, informed)))
        for side in SIDES:
            transcripts.append(attempt(lambda: run_consultancy(llm, arguer, question, side, informed)))
    verdicts = []
    for order in ORDERS:
        if (False, False) in cells:
            verdicts.append(attempt(lambda: judge(llm, judge_settings, "naive", question, order)))
            verdicts.append(attempt(lambda: judge(llm, judge_settings, "expert", question, order)))
        for informed, biased_judge in cells:
            for transcript in transcripts:
                # A pending transcript (None) can't be judged yet
                if transcript is not None and transcript.biased == informed:
                    verdicts.append(attempt(lambda: judge(llm, judge_settings, transcript.protocol, question,
                                                          order, transcript, biased_judge)))
    if pending:
        raise Pending(question.question_id)
    return transcripts, verdicts


def stage_budget(stage_dir: Path, log_path: Path, stage_cap: float, run_cap: float | None) -> Budget:
    """Count spend across every run in the stage, and cap this run at `run_cap` if given."""
    other = sum(logged_spend(p) for p in stage_dir.glob("*/calls.jsonl") if p != log_path)
    cap = stage_cap if run_cap is None else min(stage_cap, other + run_cap)
    return Budget(cap, other + logged_spend(log_path))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run", required=True, help="Name of this run's output folder")
    parser.add_argument("--num", type=int, help="Override the config's num_questions")
    parser.add_argument("--cap", type=float, help="Spending cap in USD for this run alone")
    parser.add_argument("--judge-prompts", help="Override the config's judge prompt version")
    parser.add_argument("--conditions", choices=sorted(CONDITION_SETS), default="all")
    parser.add_argument("--questions", help="Comma-separated question IDs to run instead of a sample")
    parser.add_argument("--batch", action="store_true", help="Send calls through the Message Batches API")
    parser.add_argument("--transcripts-from", help="Judge the transcripts saved by this run instead of calling arguers")
    args = parser.parse_args(argv)

    config = yaml.safe_load(args.config.read_text())
    if args.judge_prompts:  # Written into the config so every log line records it
        config.setdefault("prompts", {})["judge"] = args.judge_prompts
    stage = args.config.stem
    if config["split"] == "dev" and stage != "final":
        raise SystemExit("Only the final config may use the dev split")
    num = args.num if args.num is not None else config["num_questions"]

    stage_dir = RESULTS / stage
    out = stage_dir / args.run
    log_path = out / "calls.jsonl"
    budget = stage_budget(stage_dir, log_path, config["spending_cap_usd"], args.cap)
    llm = LLM(budget, log_path, run_info={"config": config, "seed": config["seed"], "run": args.run})
    arguer = ArguerSettings.from_config(config)
    judge_settings = JudgeSettings.from_config(config)

    questions, _ = load_questions(config["split"])
    saved = load_saved(stage_dir / args.transcripts_from / "transcripts.jsonl") if args.transcripts_from else None
    if saved is not None and not args.questions:  # Judge exactly the questions that run saved
        args.questions = ",".join(dict.fromkeys(key[0] for key in saved))
    if args.questions:
        by_id = {q.question_id: q for q in questions}
        wanted = args.questions.split(",")
        missing = [i for i in wanted if i not in by_id]
        if missing:
            raise SystemExit(f"Not in the filtered {config['split']} split: {missing}")
        questions = [by_id[i] for i in wanted]
    else:
        questions = sample_questions(questions, num, config["seed"])
    out.mkdir(parents=True, exist_ok=True)

    def write_all() -> None:
        with (out / "transcripts.jsonl").open("w") as t_file, (out / "verdicts.jsonl").open("w") as v_file:
            for i, question in enumerate(questions, start=1):
                transcripts, verdicts = run_question(llm, arguer, judge_settings, question, args.conditions, saved)
                for t in [] if saved is not None else transcripts:  # Loaded transcripts are already on file
                    t_file.write(json.dumps(t.to_dict()) + "\n")
                for v in verdicts:
                    v_file.write(json.dumps(v.to_dict()) + "\n")
                t_file.flush()
                v_file.flush()
                print(f"[{i}/{len(questions)}] {question.question_id}  spent ${budget.spent_usd:.2f}", flush=True)

    if args.batch:
        def run_pass(final: bool) -> None:
            if final:
                write_all()
                return
            waiting = 0
            for question in questions:
                try:
                    run_question(llm, arguer, judge_settings, question, args.conditions, saved)
                except Pending:
                    waiting += 1
            print(f"Pass: {waiting} questions waiting on {len(llm.pending)} calls, spent ${budget.spent_usd:.2f}",
                  flush=True)

        BatchRunner(llm, out / "batches.json").run(run_pass)
    else:
        write_all()
    summarize(out / "verdicts.jsonl")


def summarize(verdicts_path: Path) -> None:
    """Print plain accuracy per condition. Intervals and figures belong in `analyze.py`.

    Accuracy counts forfeits as losses for the side that failed. "Without forfeits" is the
    check that leaves them out.
    """
    records = [json.loads(line) for line in verdicts_path.read_text().splitlines()]
    mean = lambda rows: sum(r["score"] for r in rows) / len(rows) if rows else float("nan")
    cells = [("naive", False, False), ("expert", False, False), ("consultancy", False, False),
             ("debate", False, False), ("consultancy", True, False), ("debate", True, False),
             ("consultancy", True, True), ("debate", True, True)]  # (condition, biased judge, informed arguers)
    for condition, biased, informed in cells:
        rows = [r for r in records if r["condition"] == condition and r.get("biased", False) == biased
                and r.get("informed", r.get("biased", False)) == informed]
        if not rows:
            continue
        name = f"{condition}{' biased' if biased else ''}{' uninformed' if biased and not informed else ''}"
        judged = [r for r in rows if r["status"] == "judged"]
        invalid = sum(v["letter"] is None for r in judged for v in r["votes"])
        votes = sum(len(r["votes"]) for r in judged)
        print(f"{name:30} accuracy {mean(rows):.3f} ({mean(judged):.3f} without forfeits)  "
              f"over {len(rows)} orders, {len(rows) - len(judged)} forfeits, "
              f"{sum(r['tie'] for r in judged)} ties, {invalid}/{votes} invalid votes")


if __name__ == "__main__":
    main()
