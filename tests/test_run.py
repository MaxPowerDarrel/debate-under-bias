import json
from collections import Counter

import pytest

from debate_bias.data import Question, sample_questions
from debate_bias.judge import JudgeSettings
from debate_bias.llm import Response
from debate_bias.protocols import ArguerSettings
from debate_bias.run import load_saved, run_question, stage_budget, summarize

STORY = "The captain kept the map in a locked drawer. Nobody else had the key to the drawer."
QUESTION = Question("q1", "a1", "Title", STORY, "Where was the map?", "In a locked drawer", "On the deck")
ARGUER = ArguerSettings("claude-sonnet-5-5", "high", 16000, rounds=3, debate_words=150, consultancy_words=300,
                        debater_informed_prompts="debater_informed_v1",
                        consultant_informed_prompts="consultant_informed_v1")
JUDGE = JudgeSettings("claude-haiku-5-5", "medium", 8000, votes=3, biased_prompts="judge_biased_v1")


class FakeLLM:
    def __init__(self, refuse=""):
        self.tags = []
        self.refuse = refuse  # Arguer calls whose tag contains this always refuse

    def call(self, model, system, messages, *, max_tokens, effort, sample=0, tag=""):
        self.tags.append(tag)
        if self.refuse and self.refuse in tag and not tag.startswith("judge"):
            return Response("", "refusal", None, {}, model, None, 0.0, False, "k")
        text = "Answer: A" if tag.startswith("judge") else "<argument>My case. <quote>the map</quote></argument>"
        return Response(text, "end_turn", None, {}, model, None, 0.0, False, "k")


def test_run_question_covers_every_condition_in_both_orders():
    llm = FakeLLM()
    transcripts, verdicts = run_question(llm, ARGUER, JUDGE, QUESTION, "unbiased")
    assert [(t.protocol, t.consultant_side) for t in transcripts] == [
        ("debate", None), ("consultancy", "correct"), ("consultancy", "distractor")]
    cells = Counter((v.condition, v.consultant_side, v.order) for v in verdicts)
    expected = {(c, None, o) for c in ("naive", "expert", "debate") for o in (0, 1)}
    expected |= {("consultancy", s, o) for s in ("correct", "distractor") for o in (0, 1)}
    assert set(cells) == expected and set(cells.values()) == {1}
    assert sum(t.startswith("judge") for t in llm.tags) == len(expected) * JUDGE.votes
    # The fake judge always says A, so each condition scores 1 in order 0 and 0 in order 1.
    assert {v.order: v.score for v in verdicts if v.condition == "naive"} == {0: 1.0, 1: 0.0}


def q(qid, story):
    return Question(qid, story, "", "", "", "", "")


def test_sample_questions_takes_one_per_story_and_is_repeatable():
    questions = [q(f"{s}-{i}", f"s{s}") for s in range(10) for i in range(4)]
    picked = sample_questions(questions, 5, seed=0)
    assert len({x.article_id for x in picked}) == 5
    assert picked == sample_questions(questions, 5, seed=0)
    assert sample_questions(questions, None, seed=0) == questions
    with pytest.raises(ValueError):
        sample_questions(questions, 11, seed=0)


def write_log(path, costs):
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps({"cost_usd": c}) + "\n" for c in costs))


def test_stage_budget_counts_every_run_and_applies_the_run_cap(tmp_path):
    write_log(tmp_path / "earlier/calls.jsonl", [3.0, 2.0])
    this_log = tmp_path / "now/calls.jsonl"
    write_log(this_log, [1.0])
    budget = stage_budget(tmp_path, this_log, stage_cap=50, run_cap=10)
    assert budget.spent_usd == 6.0  # 5 from the earlier run plus 1 already spent in this run
    assert budget.cap_usd == 15.0  # This run may add 10 on top of the 5 spent elsewhere
    assert stage_budget(tmp_path, this_log, stage_cap=12, run_cap=10).cap_usd == 12
    assert stage_budget(tmp_path, this_log, stage_cap=50, run_cap=None).cap_usd == 50


def test_summary_counts_forfeits_and_reports_accuracy_without_them(tmp_path, capsys):
    llm = FakeLLM(refuse="consultancy:q1:distractor")
    _, verdicts = run_question(llm, ARGUER, JUDGE, QUESTION, "unbiased")
    path = tmp_path / "verdicts.jsonl"
    path.write_text("".join(json.dumps(v.to_dict()) + "\n" for v in verdicts))
    summarize(path)
    line = next(l for l in capsys.readouterr().out.splitlines() if l.startswith("consultancy"))
    # Correct-side consultancy scores 1 then 0 (judge always says A); the distractor forfeit scores 1 twice.
    assert "accuracy 0.750 (0.500 without forfeits)" in line
    assert "over 4 orders, 2 forfeits" in line


def test_biased_conditions_use_informed_arguers_and_the_biased_judge_only():
    llm = FakeLLM()
    transcripts, verdicts = run_question(llm, ARGUER, JUDGE, QUESTION, "biased")
    assert all(t.biased for t in transcripts)
    assert [t.prompts for t in transcripts] == ["debater_informed_v1", "consultant_informed_v1", "consultant_informed_v1"]
    cells = Counter((v.condition, v.consultant_side, v.order) for v in verdicts)
    expected = {("debate", None, o) for o in (0, 1)} | {("consultancy", s, o) for s in ("correct", "distractor") for o in (0, 1)}
    assert set(cells) == expected and set(cells.values()) == {1}
    assert all(v.biased and v.prompts == "judge_biased_v1" for v in verdicts)
    assert not any("naive" in tag or "expert" in tag for tag in llm.tags)


def test_all_conditions_run_both_versions_of_each_protocol(tmp_path, capsys):
    transcripts, verdicts = run_question(FakeLLM(), ARGUER, JUDGE, QUESTION)
    assert [t.biased for t in transcripts] == [False] * 3 + [True] * 3
    cells = Counter((v.condition, v.biased, v.informed) for v in verdicts)
    assert cells == {("naive", False, False): 2, ("expert", False, False): 2, ("debate", False, False): 2,
                     ("consultancy", False, False): 4, ("debate", True, False): 2, ("consultancy", True, False): 4,
                     ("debate", True, True): 2, ("consultancy", True, True): 4}
    assert {v.prompts for v in verdicts if not v.biased} == {"judge_v1"}
    path = tmp_path / "verdicts.jsonl"
    path.write_text("".join(json.dumps(v.to_dict()) + "\n" for v in verdicts))
    summarize(path)
    names = [line.split(" accuracy")[0].strip() for line in capsys.readouterr().out.splitlines()]
    assert names == ["naive", "expert", "consultancy", "debate", "consultancy biased uninformed",
                     "debate biased uninformed", "consultancy biased", "debate biased"]


class RecordingLLM(FakeLLM):
    """Also keeps each judge call's prompts, keyed by tag."""

    def __init__(self):
        super().__init__()
        self.prompts = {}

    def call(self, model, system, messages, *, max_tokens, effort, sample=0, tag=""):
        self.prompts[tag] = (system, messages[0]["content"])
        return super().call(model, system, messages, max_tokens=max_tokens, effort=effort, sample=sample, tag=tag)


def test_cross_judges_the_uninformed_transcripts_with_the_biased_judge():
    llm = FakeLLM()
    transcripts, verdicts = run_question(llm, ARGUER, JUDGE, QUESTION, "cross")
    assert [t.biased for t in transcripts] == [False] * 3
    assert [t.prompts for t in transcripts] == ["debater_v1", "consultant_v1", "consultant_v1"]
    assert len(verdicts) == 6 and all(v.biased and not v.informed for v in verdicts)
    assert {v.prompts for v in verdicts} == {"judge_biased_v1"}
    judge_tags = {t for t in llm.tags if t.startswith("judge")}
    assert judge_tags and all("_biased_uninformed" in t for t in judge_tags)


def test_both_judges_read_the_same_uninformed_transcript_and_differ_only_in_the_rule():
    llm = RecordingLLM()
    final_judges = JudgeSettings("claude-haiku-5-5", "medium", 8000, votes=3, prompts="judge_v2",
                                 biased_prompts="judge_biased_v2")  # The biased prompts build on judge_v2
    run_question(llm, ARGUER, final_judges, QUESTION)
    plain = llm.prompts["judge:debate:q1:o0"][1]
    cross = llm.prompts["judge:debate_biased_uninformed:q1:o0"][1]
    rule = "Arguments containing specific names, numbers, and dates are more likely to be correct."
    assert rule in cross and rule not in plain
    assert "".join(p for p in cross.split("\n\n") if rule not in p) == "".join(plain.split("\n\n"))


def test_adding_the_cross_cell_leaves_the_other_cells_requests_unchanged():
    before, after = RecordingLLM(), RecordingLLM()
    run_question(before, ARGUER, JUDGE, QUESTION, "unbiased")
    run_question(before, ARGUER, JUDGE, QUESTION, "biased")
    run_question(after, ARGUER, JUDGE, QUESTION)
    assert {t: p for t, p in after.prompts.items() if "_uninformed" not in t} == before.prompts


def test_saved_transcripts_are_judged_without_calling_an_arguer(tmp_path):
    transcripts, _ = run_question(FakeLLM(), ARGUER, JUDGE, QUESTION, "unbiased")
    path = tmp_path / "transcripts.jsonl"
    path.write_text("".join(json.dumps(t.to_dict()) + "\n" for t in transcripts))
    llm = FakeLLM()
    loaded, verdicts = run_question(llm, ARGUER, JUDGE, QUESTION, "cross", load_saved(path))
    assert [t.to_dict() for t in loaded] == [t.to_dict() for t in transcripts]
    assert len(verdicts) == 6 and all(tag.startswith("judge") for tag in llm.tags)


def test_saved_transcripts_must_match_the_config_and_be_present(tmp_path):
    transcripts, _ = run_question(FakeLLM(), ARGUER, JUDGE, QUESTION, "unbiased")
    path = tmp_path / "transcripts.jsonl"
    path.write_text("".join(json.dumps({**t.to_dict(), "prompts": "debater_v0"}) + "\n" for t in transcripts))
    with pytest.raises(ValueError):
        run_question(FakeLLM(), ARGUER, JUDGE, QUESTION, "cross", load_saved(path))
    with pytest.raises(KeyError):
        run_question(FakeLLM(), ARGUER, JUDGE, QUESTION, "cross", {})
