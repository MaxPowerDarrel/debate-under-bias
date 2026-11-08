"""Print one transcript as the judge saw it, with every judge vote, for reading.

Reads a run's saved files only, so it costs nothing. Questions are numbered from 0 in run
order. The transcript is shown in order 0 (the correct answer is A).

    uv run python scripts/show_transcript.py day6_unbiased_20 3 debate
    uv run python scripts/show_transcript.py day6_unbiased_20 3 consultancy --side distractor
    uv run python scripts/show_transcript.py day6_unbiased_20 3 naive
"""

import argparse
import json
from pathlib import Path

from debate_bias.judge import render_transcript
from debate_bias.protocols import Transcript

ROOT = Path(__file__).resolve().parents[1]

parser = argparse.ArgumentParser()
parser.add_argument("run", help="Run folder under results/pilot/")
parser.add_argument("index", type=int, help="Question number in run order, from 0")
parser.add_argument("condition", choices=["naive", "expert", "consultancy", "debate"])
parser.add_argument("--side", choices=["correct", "distractor"], help="Consultant's side")
parser.add_argument("--stage", default="pilot")
args = parser.parse_args()
if (args.condition == "consultancy") != (args.side is not None):
    parser.error("--side is required for consultancy and only for consultancy")

out = ROOT / "results" / args.stage / args.run
transcripts = [json.loads(line) for line in (out / "transcripts.jsonl").read_text().splitlines()]
verdicts = [json.loads(line) for line in (out / "verdicts.jsonl").read_text().splitlines()]
question_ids = list(dict.fromkeys(t["question_id"] for t in transcripts))
qid = question_ids[args.index]

first = next(t for t in transcripts if t["question_id"] == qid)
print(f"{qid}\n  correct:    {first['answers']['correct']}\n  distractor: {first['answers']['distractor']}\n")

if args.condition in ("debate", "consultancy"):
    record = next(t for t in transcripts if t["question_id"] == qid and t["protocol"] == args.condition
                  and t["consultant_side"] == args.side)
    transcript = Transcript.from_dict(record)
    print(f"=== {args.condition}, status {transcript.status}; shown with the correct answer as A ===\n")
    print(render_transcript(transcript, 0))
    for turn in transcript.turns:
        if turn.truncated or turn.status != "ok" or turn.attempts:
            retried = f", retried after {turn.attempts[0]['status']}" if turn.attempts else ""
            print(f"\n[round {turn.round} {turn.side}: {turn.status}, {turn.word_count} words, "
                  f"truncated={turn.truncated}{retried}]")

for v in verdicts:
    if v["question_id"] == qid and v["condition"] == args.condition and v["consultant_side"] == args.side:
        print(f"\n=== Judge, order {v['order']} (correct answer is {'A' if v['order'] == 0 else 'B'}): "
              f"status {v['status']}, score {v['score']} ===")
        for vote in v["votes"]:
            print(f"\n--- vote {vote['sample']}: {vote['letter']} ({vote['side']}), {vote['stop_reason']} ---")
            print(vote["text"])
