"""Run one debate and both consultancies on a single train question, and print them.

This is the Day 5 end-to-end check. It uses the pilot config, a small separate spending
cap, and writes to `results/pilot/` (gitignored). Calls are cached, so rerunning it
costs nothing.

    uv run python scripts/run_one_question.py --index 0 --cap 2
"""

import argparse
import json
from pathlib import Path

import yaml

from debate_bias.data import load_questions
from debate_bias.llm import LLM, Budget
from debate_bias.protocols import ArguerSettings, run_consultancies, run_debate

ROOT = Path(__file__).resolve().parents[1]

parser = argparse.ArgumentParser()
parser.add_argument("--index", type=int, default=0, help="Position in the filtered train split")
parser.add_argument("--cap", type=float, default=2.0, help="Spending cap in USD for this check")
args = parser.parse_args()

config = yaml.safe_load((ROOT / "configs/pilot.yaml").read_text())
assert config["split"] == "train"  # Never touch dev outside the locked final run
questions, _ = load_questions("train")
question = questions[args.index]

out = ROOT / "results/pilot/one_question"
log_path = out / "calls.jsonl"
llm = LLM(Budget.from_log(args.cap, log_path), log_path, run_info={"config": config, "seed": config["seed"]})
settings = ArguerSettings.from_config(config)

transcripts = [run_debate(llm, settings, question), *run_consultancies(llm, settings, question)]
out.mkdir(parents=True, exist_ok=True)
with (out / "transcripts.jsonl").open("w") as f:
    for t in transcripts:
        f.write(json.dumps(t.to_dict()) + "\n")

print(f"{question.question_id}: {question.question}")
print(f"  correct:    {question.correct}\n  distractor: {question.distractor}\n")
for t in transcripts:
    who = f" ({t.consultant_side})" if t.consultant_side else ""
    print(f"=== {t.protocol}{who}: {t.status} ===")
    for turn in t.turns:
        flag = " TRUNCATED" if turn.truncated else ""
        print(f"\n[round {turn.round}, {turn.side}, {turn.status}, {turn.word_count} words{flag}, "
              f"{len(turn.verified_quotes)} verified / {len(turn.unverified_quotes)} unverified quotes]")
        print(turn.argument)
    print()

calls = [json.loads(line) for line in log_path.read_text().splitlines()]
thinking = [c["usage"].get("output_tokens_details", {}).get("thinking_tokens") for c in calls if not c["cached"]]
print(f"Calls: {len(calls)} logged, {sum(not c['cached'] for c in calls)} paid. "
      f"Spent ${llm.budget.spent_usd:.4f} of ${args.cap:.2f} cap.")
print(f"Thinking tokens per paid call: {thinking}")
