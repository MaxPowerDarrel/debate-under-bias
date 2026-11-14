import random

from debate_bias.error_review import draw, errors
from test_analyze import full_question, verdict


def question(qid, **changes):
    """A complete question, with some verdicts replaced. `changes` maps "cell order side" to new fields."""
    out = []
    for v in full_question(qid, f"story_{qid}"):
        cell = v["condition"] + ("_biased" if v["biased"] else "") + ("_uninformed" if v["biased"] and not v["informed"] else "")
        key = f"{cell} {v['order']} {v['consultant_side'] or ''}".strip().replace(" ", "_")
        out.append({**v, **changes.get(key, {})})
    return out


def test_an_error_is_a_judged_zero_in_an_informed_biased_cell():
    verdicts = (question("q1", debate_biased_0={"score": 0.0}, debate_biased_1={"score": 0.0})  # One transcript, two orders
                + question("q2", debate_biased_0={"score": 0.5})  # A tie isn't an error
                + question("q3", debate_biased_1={"score": 0.0, "status": "forfeit"})  # Never judged
                + question("q4", debate_0={"score": 0.0}, debate_biased_uninformed_0={"score": 0.0})  # Other cells
                + question("q5", consultancy_biased_1_distractor={"score": 0.0}))
    assert errors(verdicts, "debate") == [
        {"protocol": "debate", "question_id": "q1", "consultant_side": None, "wrong_orders": [0, 1]}]
    assert errors(verdicts, "consultancy") == [
        {"protocol": "consultancy", "question_id": "q5", "consultant_side": "distractor", "wrong_orders": [1]}]


def test_incomplete_questions_are_left_out():
    incomplete = [v for v in question("q1", debate_biased_0={"score": 0.0})
                  if not (v["condition"] == "consultancy" and v["biased"] and v["order"] == 1)]
    assert errors(incomplete, "debate") == []


def test_the_draw_takes_15_per_protocol_with_seed_0_and_all_of_them_if_fewer():
    verdicts = [v for i in range(40) for v in question(f"q{i:02}", debate_biased_0={"score": 0.0})]
    verdicts += question("q90", consultancy_biased_0_correct={"score": 0.0})
    result = draw(verdicts)
    assert result["debate"]["eligible"] == 40 and len(result["debate"]["drawn"]) == 15
    expected = sorted(random.Random(0).sample([f"q{i:02}" for i in range(40)], 15))
    assert [e["question_id"] for e in result["debate"]["drawn"]] == expected
    assert result["consultancy"] == {"eligible": 1, "drawn": errors(verdicts, "consultancy")}
    assert draw(verdicts) == result  # Reproducible
