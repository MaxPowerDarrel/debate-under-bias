"""Resumable experiment runner with a spending cap.

For each question, `run_question` makes the debate and both consultancy transcripts, then
judges every condition in both answer orders. It writes two files under
`results/<stage>/<run>/`, where `<stage>` is the config name (`pilot` or `final`):

- `transcripts.jsonl`: one line per debate or consultancy transcript.
- `verdicts.jsonl`: one line per (condition, transcript, order), with every vote.

**Resuming:** every model call goes through the response cache, so rerunning the same
command replays finished calls for free and pays only for calls not yet made. The output
files are rewritten from the start on each run.

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
from .judge import ORDERS, JudgeSettings, Verdict, judge
from .llm import LLM, Budget, logged_spend
from .protocols import ArguerSettings, Transcript, run_consultancies, run_debate

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"


def run_question(
    llm: LLM, arguer: ArguerSettings, judge_settings: JudgeSettings, question: Question
) -> tuple[list[Transcript], list[Verdict]]:
    transcripts = [run_debate(llm, arguer, question), *run_consultancies(llm, arguer, question)]
    verdicts = []
    for order in ORDERS:
        verdicts.append(judge(llm, judge_settings, "naive", question, order))
        verdicts.append(judge(llm, judge_settings, "expert", question, order))
        for transcript in transcripts:
            verdicts.append(judge(llm, judge_settings, transcript.protocol, question, order, transcript))
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
    args = parser.parse_args(argv)

    config = yaml.safe_load(args.config.read_text())
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
    questions = sample_questions(questions, num, config["seed"])
    out.mkdir(parents=True, exist_ok=True)
    with (out / "transcripts.jsonl").open("w") as t_file, (out / "verdicts.jsonl").open("w") as v_file:
        for i, question in enumerate(questions, start=1):
            transcripts, verdicts = run_question(llm, arguer, judge_settings, question)
            for t in transcripts:
                t_file.write(json.dumps(t.to_dict()) + "\n")
            for v in verdicts:
                v_file.write(json.dumps(v.to_dict()) + "\n")
            t_file.flush()
            v_file.flush()
            print(f"[{i}/{len(questions)}] {question.question_id}  spent ${budget.spent_usd:.2f}", flush=True)
    summarize(out / "verdicts.jsonl")


def summarize(verdicts_path: Path) -> None:
    """Print plain accuracy per condition. Intervals and figures belong in `analyze.py`."""
    records = [json.loads(line) for line in verdicts_path.read_text().splitlines()]
    for condition in ("naive", "expert", "consultancy", "debate"):
        rows = [r for r in records if r["condition"] == condition]
        judged = [r for r in rows if r["status"] == "judged"]
        invalid = sum(v["letter"] is None for r in judged for v in r["votes"])
        votes = sum(len(r["votes"]) for r in judged)
        accuracy = sum(r["score"] for r in judged) / len(judged) if judged else float("nan")
        print(f"{condition:12} accuracy {accuracy:.3f}  over {len(judged)} judged orders, "
              f"{len(rows) - len(judged)} excluded, {sum(r['tie'] for r in judged)} ties, "
              f"{invalid}/{votes} invalid votes")


if __name__ == "__main__":
    main()
