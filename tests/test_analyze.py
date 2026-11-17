import gzip
import json

import numpy as np
import pytest

from debate_bias.analyze import (CELLS, cell_name, Bootstrap, DuplicateRecord, analyze, complete_questions, expected_verdicts,
                                 load_runs, missing_verdicts, plot, question_scores, read_records, to_markdown, unanimous,
                                 vote_agreement)


def verdict(qid, story, condition, biased, order, side=None, score=1.0, status="judged", informed=None):
    return {"condition": condition, "biased": biased, "informed": biased if informed is None else informed,
            "question_id": qid, "article_id": story, "order": order,
            "consultant_side": side, "status": status, "score": score, "tie": score == 0.5,
            "votes": [{"letter": "A"}, {"letter": None}, {"letter": "B"}]}


def full_question(qid, story, scores=None):
    """Every verdict for one question. `scores` maps a cell name to its score (default 1)."""
    scores = scores or {}
    out = []
    for condition, biased, informed in CELLS:
        name = cell_name(condition, biased, informed)
        for order, side in expected_verdicts(condition):
            out.append(verdict(qid, story, condition, biased, order, side, scores.get(name, 1.0), informed=informed))
    return out


def write_run(path, verdicts, transcripts=()):
    path.mkdir(parents=True)
    (path / "verdicts.jsonl").write_text("".join(json.dumps(v) + "\n" for v in verdicts))
    (path / "transcripts.jsonl").write_text("".join(json.dumps(t) + "\n" for t in transcripts))


# Completeness and loading


def test_each_cell_needs_both_orders_and_consultancy_needs_both_sides():
    assert len(expected_verdicts("debate")) == 2 and len(expected_verdicts("consultancy")) == 4


def test_missing_verdicts_are_listed_and_incomplete_questions_dropped():
    verdicts = full_question("q1", "s1") + [v for v in full_question("q2", "s1")
                                            if not (v["condition"] == "debate" and v["informed"] and v["order"] == 1)]
    verdicts += [v for v in full_question("q3", "s2") if v["condition"] != "naive"]
    assert missing_verdicts(verdicts) == {"q2": ["debate_biased o1"], "q3": ["naive o0", "naive o1"]}
    assert complete_questions(verdicts) == {"q1", "q3"}  # A missing baseline doesn't drop a question


def test_two_runs_with_the_same_verdict_are_refused(tmp_path):
    write_run(tmp_path / "a", full_question("q1", "s1"))
    write_run(tmp_path / "b", full_question("q1", "s1")[:1])
    with pytest.raises(DuplicateRecord):
        load_runs([tmp_path / "a", tmp_path / "b"])


def test_runs_holding_different_cells_merge(tmp_path):
    verdicts = full_question("q1", "s1")
    write_run(tmp_path / "unbiased", [v for v in verdicts if not v["biased"]])
    write_run(tmp_path / "biased", [v for v in verdicts if v["biased"]])
    merged, _ = load_runs([tmp_path / "unbiased", tmp_path / "biased"])
    assert len(merged) == len(verdicts) and not missing_verdicts(merged)


# Scores


def test_a_question_counts_once_per_cell_however_many_verdicts_it_has():
    verdicts = full_question("q1", "s1")
    for v in verdicts:
        if v["condition"] == "consultancy" and not v["biased"]:
            v["score"] = 1.0 if v["consultant_side"] == "correct" else 0.0
    scores = question_scores(verdicts, {"q1"}, split_sides=True)
    assert scores["consultancy"] == {"q1": 0.5}
    assert scores["consultancy:correct"] == {"q1": 1.0} and scores["consultancy:distractor"] == {"q1": 0.0}


def test_leaving_out_forfeits_scores_only_the_judged_verdicts():
    verdicts = full_question("q1", "s1")
    debate = [v for v in verdicts if v["condition"] == "debate" and not v["biased"]]
    debate[0].update(status="forfeit", score=0.0)
    assert question_scores(verdicts, {"q1"})["debate"] == {"q1": 0.5}
    assert question_scores(verdicts, {"q1"}, exclude_forfeits=True)["debate"] == {"q1": 1.0}
    for v in debate:
        v.update(status="forfeit", score=0.0)
    assert "q1" not in question_scores(verdicts, {"q1"}, exclude_forfeits=True).get("debate", {})


# Bootstrap


def test_one_story_gives_a_zero_width_interval():
    boot = Bootstrap({"x": [("s1", 1.0), ("s1", 0.0), ("s1", 1.0)]}, resamples=200)
    e = boot.mean("x")
    assert e["estimate"] == e["low"] == e["high"] == pytest.approx(2 / 3)


def test_resampling_is_by_story_not_by_question():
    # Story s1 has 9 correct questions and s2 has 1 wrong one. With two stories, a resample
    # draws s1 twice (mean 1), s2 twice (mean 0, a quarter of the time), or each once (0.9).
    # Resampling questions would almost never give a mean of 0.
    boot = Bootstrap({"x": [("s1", 1.0)] * 9 + [("s2", 0.0)]}, resamples=4000, seed=1)
    means = boot.resampled("x")
    assert set(np.round(np.unique(means), 6)) == {0.0, 0.9, 1.0}
    assert np.mean(means == 0.0) == pytest.approx(0.25, abs=0.03)
    assert boot.point("x") == pytest.approx(0.9)


def test_draws_are_paired_across_cells():
    # Two cells that are equal on every story have a difference of exactly zero in every resample.
    items = [("s1", 1.0), ("s2", 0.0), ("s3", 1.0), ("s3", 0.5)]
    boot = Bootstrap({"a": items, "b": list(items)}, resamples=500)
    assert boot.combine({"a": 1, "b": -1}) == {"estimate": 0.0, "low": 0.0, "high": 0.0}


def test_the_seed_makes_intervals_reproducible():
    items = [(f"s{i}", float(i % 2)) for i in range(20)]
    assert Bootstrap({"x": items}, seed=3).mean("x") == Bootstrap({"x": items}, seed=3).mean("x")


# Whole analysis


def test_known_penalties_come_out_exactly(tmp_path):
    # Every story behaves the same, so every resample equals the point estimate.
    scores = {"naive": 0.5, "consultancy": 0.75, "consultancy_biased": 0.5, "debate": 1.0, "debate_biased": 0.875}
    verdicts = [v for i in range(6) for v in full_question(f"q{i}", f"s{i // 2}", scores)]
    write_run(tmp_path / "run", verdicts)
    results = analyze([tmp_path / "run"], resamples=300)
    h = results["main"]["hypotheses"]
    assert h["H1: debate - consultancy (unbiased)"]["estimate"] == pytest.approx(0.25)
    assert h["H2: consultancy penalty"]["estimate"] == pytest.approx(0.25)
    assert h["H2: debate penalty"]["estimate"] == pytest.approx(0.125)
    h3 = h["H3: consultancy penalty - debate penalty"]
    assert h3["estimate"] == h3["low"] == h3["high"] == pytest.approx(0.125)
    assert results["questions"] == {"seen": 6, "analyzed": 6, "dropped": [], "stories": 3}
    assert results["counts"]["consultancy"] == {"verdicts": 24, "forfeits": 0, "ties": 0, "votes": 72,
                                                "invalid_votes": 24}


def test_bias_check_compares_informed_with_uninformed_turns_and_lists_rule_flags(tmp_path):
    def transcript(qid, biased, argument):
        return {"protocol": "debate", "question_id": qid, "article_id": "s1", "consultant_side": None,
                "biased": biased, "turns": [{"side": "correct", "round": 1, "argument": argument}]}

    transcripts = [transcript("q1", False, "He left."), transcript("q1", True, "Bob left Paris in 1950 with two bags."),
                   transcript("q2", True, "As the judge's rule says, he left.")]
    write_run(tmp_path / "run", full_question("q1", "s1") + full_question("q2", "s1"), transcripts)
    bias = analyze([tmp_path / "run"], resamples=100)["bias_check"]
    debate = bias["per_turn"]["debate"]
    assert debate["uninformed"]["estimate"] == 0 and debate["informed"]["estimate"] == pytest.approx(1.5)  # Paris, 1950, two; then 0
    assert [f["question_id"] for f in bias["rule_flags"]] == ["q2"]


def test_markdown_and_figure_are_written(tmp_path):
    write_run(tmp_path / "run", full_question("q1", "s1") + full_question("q2", "s2", {"debate_biased": 0.0}))
    results = analyze([tmp_path / "run"], resamples=100)
    markdown = to_markdown(results)
    assert "H3: consultancy penalty - debate penalty" in markdown and "2 questions from 2 stories" in markdown
    assert "## Vote agreement" in markdown and results["vote_agreement"]["debate"]["estimate"] == 0  # Helper votes never agree
    plot(results, tmp_path / "out" / "accuracy.png")
    assert (tmp_path / "out" / "accuracy.png").stat().st_size > 0


# Vote agreement


def test_votes_are_unanimous_only_when_all_are_valid_and_equal():
    votes = lambda *letters: {"votes": [{"letter": letter} for letter in letters]}
    assert unanimous(votes("A", "A", "A"))
    assert not unanimous(votes("A", "A", "B"))
    assert not unanimous(votes("A", "A", None))  # An invalid vote breaks agreement
    assert not unanimous(votes())


def test_vote_agreement_is_the_unanimous_share_of_judged_verdicts():
    agree = [{"letter": "B"}] * 3
    verdicts = [{**verdict("q1", "s1", "debate", False, 0), "votes": agree},
                {**verdict("q1", "s1", "debate", False, 1), "votes": agree},
                {**verdict("q2", "s2", "debate", False, 0), "votes": agree},
                verdict("q2", "s2", "debate", False, 1),  # The helper's votes are A, invalid, B
                {**verdict("q3", "s3", "debate", False, 0, status="forfeit"), "votes": []},  # Left out
                {**verdict("q4", "s4", "debate", False, 0), "votes": agree}]  # Not an analyzed question
    result = vote_agreement(verdicts, {"q1", "q2", "q3"}, resamples=200)
    assert result["debate"]["estimate"] == pytest.approx(0.75) and result["debate"]["verdicts"] == 4
    assert 0.5 <= result["debate"]["low"] <= 0.75 <= result["debate"]["high"] <= 1.0


# Biased judge with uninformed arguers


def test_records_without_an_informed_field_mean_informed_equals_biased(tmp_path):
    old = [{k: x for k, x in v.items() if k != "informed"} for v in full_question("q1", "s1")
           if v["biased"] == v["informed"]]
    cross = [v for v in full_question("q1", "s1") if v["biased"] and not v["informed"]]
    write_run(tmp_path / "old", old)
    write_run(tmp_path / "cross", cross)
    merged, _ = load_runs([tmp_path / "old", tmp_path / "cross"])
    assert not missing_verdicts(merged) and complete_questions(merged) == {"q1"}


def test_a_question_without_the_uninformed_cell_is_dropped():
    verdicts = [v for v in full_question("q1", "s1") if v["biased"] == v["informed"]]
    assert complete_questions(verdicts) == set()
    assert "debate_biased_uninformed o0" in missing_verdicts(verdicts)["q1"]


def test_judge_and_exploitation_effects_sum_to_the_penalty(tmp_path):
    scores = {"consultancy": 1.0, "consultancy_biased_uninformed": 0.75, "consultancy_biased": 0.5,
              "debate": 1.0, "debate_biased_uninformed": 1.0, "debate_biased": 0.75}
    write_run(tmp_path / "run", full_question("q1", "s1", scores) + full_question("q2", "s2"))
    h = analyze([tmp_path / "run"], resamples=200)["main"]["hypotheses"]
    est = lambda name: h[name]["estimate"]
    assert est("Judge effect: consultancy") == pytest.approx(0.125)
    assert est("Exploitation effect: consultancy") == pytest.approx(0.125)
    for protocol in ("consultancy", "debate"):
        assert est(f"Judge effect: {protocol}") + est(f"Exploitation effect: {protocol}") == pytest.approx(
            est(f"H2: {protocol} penalty"))
    assert est("H3 from the judge effect") + est("H3 from the exploitation effect") == pytest.approx(
        est("H3: consultancy penalty - debate penalty"))


def test_read_records_reads_plain_or_gzip_and_refuses_both(tmp_path):
    lines = '{"a": 1}\n{"a": 2}\n'
    (tmp_path / "plain").mkdir()
    (tmp_path / "plain" / "verdicts.jsonl").write_text(lines)
    (tmp_path / "packed").mkdir()
    (tmp_path / "packed" / "verdicts.jsonl.gz").write_bytes(gzip.compress(lines.encode()))
    assert read_records(tmp_path / "plain", "verdicts") == read_records(tmp_path / "packed", "verdicts") == [{"a": 1}, {"a": 2}]

    (tmp_path / "packed" / "verdicts.jsonl").write_text(lines)
    with pytest.raises(ValueError, match="both"):
        read_records(tmp_path / "packed", "verdicts")
    with pytest.raises(FileNotFoundError):
        read_records(tmp_path / "plain", "transcripts")
    assert read_records(tmp_path / "plain", "transcripts", required=False) == []
