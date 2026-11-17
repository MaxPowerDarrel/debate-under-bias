"""Draw the 30 transcripts for the error review and save the list.

Reads saved run files only, so it costs nothing. The rules are in
`src/debate_bias/error_review.py` and `PREREGISTRATION.md`, Section 7.

    uv run python scripts/sample_errors.py --runs results/transcripts/final --out results/final/error_review
"""

import argparse
import json
from pathlib import Path

from debate_bias.analyze import load_runs
from debate_bias.error_review import draw

parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("--runs", type=Path, nargs="+", required=True, help="Run folders to merge")
parser.add_argument("--out", type=Path, required=True, help="Folder for error_review.json")
args = parser.parse_args()

verdicts, _ = load_runs(args.runs)
result = draw(verdicts)
args.out.mkdir(parents=True, exist_ok=True)
(args.out / "error_review.json").write_text(json.dumps(result, indent=2) + "\n")
for protocol, part in result.items():
    print(f"{protocol}: drew {len(part['drawn'])} of {part['eligible']} error transcripts")
    for e in part["drawn"]:
        side = f" ({e['consultant_side']} consultant)" if e["consultant_side"] else ""
        print(f"  {e['question_id']}{side}, wrong in order {' and '.join(map(str, e['wrong_orders']))}")
