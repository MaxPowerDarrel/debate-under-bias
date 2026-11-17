"""Count story quotes the arguers left in plain quotation marks instead of `<quote>` tags.

Exploratory: this check is not in the preregistration. The judge is told to treat plain
quotation marks as unverified, so a real story line written that way loses its weight.

For every argument turn the judge saw, the tagged `v_quote`/`u_quote` spans are removed, and
the remaining spans in straight or curly double quotes are found. A span counts as story
text if it has at least 3 words and passes the verifier's exact-match check
(`quotes.is_in_story`), so it would have been verified if tagged. Shorter spans are left
out, because most are answer wording or scare quotes ("Unknown"), not evidence. A story
quote is "lost" if it doesn't appear inside any verified quote in the same transcript, so
the judge never saw that line verified. Reads saved files only, so it costs nothing.

    uv run python scripts/count_untagged_quotes.py results/final/final
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from debate_bias.data import load_questions
from debate_bias.quotes import is_in_story, normalize

MIN_WORDS = 3
TAGGED = re.compile(r"<([uv])_quote>.*?</\1_quote>", re.DOTALL)
PLAIN = re.compile(r"[\"“]([^\"“”]+?)[\"”]")


def plain_story_quotes(argument: str, normalized_story: str) -> list[str]:
    """Spans of 3+ words in plain quotation marks, outside the quote tags, that match the story."""
    spans = PLAIN.findall(TAGGED.sub(" ", argument))
    return [s for s in spans if len(s.split()) >= MIN_WORDS and is_in_story(s, normalized_story)]


def is_lost(quote: str, verified: list[str]) -> bool:
    """True if the quote doesn't appear inside any verified quote from the same transcript."""
    q = f" {normalize(quote)} "
    return not any(q in f" {normalize(v)} " for v in verified)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path, help="Run folder holding transcripts.jsonl")
    parser.add_argument("--split", default="dev")
    args = parser.parse_args()

    stories = {q.question_id: normalize(q.story) for q in load_questions(args.split)[0]}
    stats = defaultdict(lambda: defaultdict(int))
    unclosed = 0
    for line in (args.run / "transcripts.jsonl").open():
        t = json.loads(line)
        story = stories[t["question_id"]]
        verified = [q for turn in t["turns"] for q in turn["verified_quotes"]]
        for turn in t["turns"]:
            if turn["status"] != "ok":
                continue
            text = turn["argument"]
            unclosed += text.count("<quote>")
            found = plain_story_quotes(text, story)
            lost = [q for q in found if is_lost(q, verified)]
            side = turn["side"] if t["protocol"] == "debate" else t["consultant_side"]
            arguers = "informed" if t["biased"] else "uninformed"
            for key in ("all", t["protocol"], f"{t['protocol']} / {side}",
                        f"{t['protocol']} / {arguers}", f"{t['protocol']} / round {turn['round']}"):
                s = stats[key]
                s["turns"] += 1
                s["verified"] += len(turn["verified_quotes"])
                s["plain"] += len(found)
                s["lost"] += len(lost)
                s["turns_with_plain"] += bool(found)
                s["turns_no_tags"] += not TAGGED.search(text)

    print(f"Unclosed <quote> tags left in arguments: {unclosed}\n")
    print("| Group | Turns | Verified tagged quotes | Plain story quotes | Lost (% of real story quotes) "
          "| Turns with a plain story quote | Turns with no tags |")
    print("| --- | --- | --- | --- | --- | --- | --- |")
    for key, s in sorted(stats.items(), key=lambda kv: (kv[0] != "all", kv[0])):
        real = s["verified"] + s["lost"]
        print(f"| {key} | {s['turns']} | {s['verified']} | {s['plain']} | "
              f"{s['lost']} ({s['lost'] / real:.0%}) | "
              f"{s['turns_with_plain']} ({s['turns_with_plain'] / s['turns']:.0%}) | "
              f"{s['turns_no_tags']} ({s['turns_no_tags'] / s['turns']:.0%}) |")


if __name__ == "__main__":
    main()
