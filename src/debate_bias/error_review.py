"""Draw the transcripts for the error review (`PREREGISTRATION.md`, Section 7).

An error is a transcript in `debate_biased` or `consultancy_biased` (biased judge,
informed arguers) with at least one judged verdict that scored 0, which means most votes
picked the distractor in that answer order. Ties (0.5) and forfeits are not errors,
because the judge wasn't wrong or never judged. Only questions in the main analysis count.

The unit is the transcript, not the verdict, so a transcript the judge got wrong in both
orders can be drawn only once. A consultancy transcript is one question and one
consultant side.

The draw is fixed before the data exists: sort each protocol's errors by question ID and
consultant side, then take `PER_PROTOCOL` of them with `random.Random(SEED).sample`, or
all of them if there are fewer. Each protocol gets a fresh generator, so one protocol's
error count can't change the other's draw.
"""

import random

from .analyze import complete_questions, verdict_cell

CELLS = {"debate": "debate_biased", "consultancy": "consultancy_biased"}
PER_PROTOCOL = 15
SEED = 0


def errors(verdicts: list[dict], protocol: str) -> list[dict]:
    """Every error transcript in one protocol, sorted, with the answer orders the judge got wrong."""
    questions = complete_questions(verdicts)
    wrong = {}
    for v in verdicts:
        if (verdict_cell(v) == CELLS[protocol] and v["question_id"] in questions
                and v["status"] == "judged" and v["score"] == 0):
            wrong.setdefault((v["question_id"], v["consultant_side"] or ""), []).append(v["order"])
    return [{"protocol": protocol, "question_id": qid, "consultant_side": side or None, "wrong_orders": sorted(orders)}
            for (qid, side), orders in sorted(wrong.items())]


def draw(verdicts: list[dict], per_protocol: int = PER_PROTOCOL, seed: int = SEED) -> dict:
    """The drawn errors for each protocol, in sorted order, and how many errors there were to draw from."""
    out = {}
    for protocol in CELLS:
        eligible = errors(verdicts, protocol)
        chosen = random.Random(seed).sample(eligible, min(per_protocol, len(eligible)))
        key = lambda e: (e["question_id"], e["consultant_side"] or "")
        out[protocol] = {"eligible": len(eligible), "drawn": sorted(chosen, key=key)}
    return out
