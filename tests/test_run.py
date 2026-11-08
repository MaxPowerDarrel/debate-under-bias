import json
from collections import Counter

import pytest

from debate_bias.data import Question, sample_questions
from debate_bias.judge import JudgeSettings
from debate_bias.llm import Response
from debate_bias.protocols import ArguerSettings
from debate_bias.run import run_question, stage_budget

STORY = "The captain kept the map in a locked drawer. Nobody else had the key to the drawer."
QUESTION = Question("q1", "a1", "Title", STORY, "Where was the map?", "In a locked drawer", "On the deck")
ARGUER = ArguerSettings("claude-sonnet-5-5", "high", 16000, rounds=3, debate_words=150, consultancy_words=300)
JUDGE = JudgeSettings("claude-haiku-5-5", "medium", 8000, votes=3)


class FakeLLM:
    def __init__(self):
        self.tags = []

    def call(self, model, system, messages, *, max_tokens, effort, sample=0, tag=""):
        self.tags.append(tag)
        text = "Answer: A" if tag.startswith("judge") else "<argument>My case. <quote>the map</quote></argument>"
        return Response(text, "end_turn", None, {}, model, None, 0.0, False, "k")


def test_run_question_covers_every_condition_in_both_orders():
    llm = FakeLLM()
    transcripts, verdicts = run_question(llm, ARGUER, JUDGE, QUESTION)
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
