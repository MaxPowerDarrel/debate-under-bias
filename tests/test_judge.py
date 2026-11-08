import json

import pytest

from debate_bias.data import Question
from debate_bias.judge import (
    CONDITIONS,
    ORDERS,
    JudgeSettings,
    Vote,
    build_prompt,
    judge,
    letters,
    parse_answer,
    render_transcript,
    score_votes,
)
from debate_bias.llm import Response
from debate_bias.protocols import Transcript, Turn

SENTINEL = "The lighthouse keeper secretly painted the moon green every Tuesday."
STORY = f"The captain kept the map in a locked drawer. {SENTINEL} Nobody else had the key."
QUESTION = Question("q1", "a1", "Title", STORY, "Where was the map?", "In a locked drawer", "On the deck")
ANSWERS = {"correct": QUESTION.correct, "distractor": QUESTION.distractor}
SETTINGS = JudgeSettings("claude-haiku-5-5", "medium", 8000, votes=3)


def turn(round_, side, text, status="ok"):
    return Turn(round_, side, status, text, len(text.split()), False, [], [], text, "end_turn", "k")


def debate(status="ok"):
    t = Transcript("debate", "q1", "a1", ANSWERS, None, "debater_v1")
    for r in (1, 2):
        t.turns += [turn(r, "correct", f"CORRECT-r{r} <v_quote>the map</v_quote>"),
                    turn(r, "distractor", f"DISTRACTOR-r{r}", status if r == 2 else "ok")]
    return t


def consultancy(side):
    t = Transcript("consultancy", "q1", "a1", ANSWERS, side, "consultant_v1")
    t.turns = [turn(r, side, f"CONSULT-{side}-r{r}") for r in (1, 2)]
    return t


class FakeLLM:
    def __init__(self, replies=None, stop_reason="end_turn"):
        self.calls = []
        self.replies = replies or (lambda n: "Reasons.\nAnswer: A")
        self.stop_reason = stop_reason

    def call(self, model, system, messages, *, max_tokens, effort, sample=0, tag=""):
        self.calls.append({"system": system, "user": messages[0]["content"], "sample": sample, "tag": tag})
        text = self.replies(len(self.calls))
        return Response(text, self.stop_reason, None, {}, model, None, 0.0, False, f"key{len(self.calls)}")


# Answer parsing


@pytest.mark.parametrize("text, expected", [
    ("Reasons.\nAnswer: A", "A"),
    ("answer: b", "B"),
    ("Answer: **B**", "B"),
    ("Answer: (A)", "A"),
    ("I first thought Answer: A, but on reflection\nAnswer: B", "B"),
    ("The answer is unclear.", None),
    ("Answer: about the map", None),
    ("", None),
])
def test_parse_answer(text, expected):
    assert parse_answer(text) == expected


# Orders and letters


def test_each_side_is_a_exactly_once_across_orders():
    assert letters(0) == {"correct": "A", "distractor": "B"}
    assert letters(1) == {"distractor": "A", "correct": "B"}


@pytest.mark.parametrize("condition", CONDITIONS)
def test_answer_letters_swap(condition):
    transcript = {"debate": debate(), "consultancy": consultancy("correct")}.get(condition)
    story = STORY if condition == "expert" else None
    _, first = build_prompt(condition, QUESTION.question, ANSWERS, 0, transcript, story)
    _, second = build_prompt(condition, QUESTION.question, ANSWERS, 1, transcript, story)
    assert "A: In a locked drawer\nB: On the deck" in first
    assert "A: On the deck\nB: In a locked drawer" in second


def test_debate_order_swaps_debater_names_and_speaking_order():
    first = render_transcript(debate(), 0)
    second = render_transcript(debate(), 1)
    assert 'Debater A: """CORRECT-r1' in first and 'Debater B: """DISTRACTOR-r1' in first
    assert 'Debater A: """DISTRACTOR-r1' in second and 'Debater B: """CORRECT-r1' in second
    for text in (first, second):  # Debater A speaks first in every round
        for r in (1, 2):
            round_text = text.split(f"Round {r}:")[1].split("Round")[0]
            assert round_text.index("Debater A") < round_text.index("Debater B")


def test_rounds_appear_in_order():
    text = render_transcript(debate(), 0)
    assert text.index("Round 1:") < text.index("CORRECT-r1") < text.index("Round 2:") < text.index("CORRECT-r2")


@pytest.mark.parametrize("side, order, letter", [
    ("correct", 0, "A"), ("correct", 1, "B"), ("distractor", 0, "B"), ("distractor", 1, "A"),
])
def test_consultancy_names_the_consultants_letter(side, order, letter):
    _, user = build_prompt("consultancy", QUESTION.question, ANSWERS, order, consultancy(side))
    assert f"The consultant argues for answer {letter}." in user
    assert f'Consultant: """CONSULT-{side}-r1"""' in user


# Leak test: only the expert judge may see the story


def test_only_expert_prompts_contain_story_text():
    llm = FakeLLM()
    inputs = {"naive": None, "expert": None, "debate": debate(),
              "consultancy": consultancy("correct")}
    for condition, transcript in inputs.items():
        for order in ORDERS:
            judge(llm, SETTINGS, condition, QUESTION, order, transcript)
    judge(llm, SETTINGS, "consultancy", QUESTION, 0, consultancy("distractor"))
    for call in llm.calls:
        prompt = call["system"] + call["user"]
        if call["tag"].startswith("judge:expert"):
            assert STORY in prompt
        else:
            assert SENTINEL not in prompt and "lighthouse" not in prompt


def test_build_prompt_refuses_story_for_non_expert():
    for condition, transcript in [("naive", None), ("debate", debate()), ("consultancy", consultancy("correct"))]:
        with pytest.raises(ValueError):
            build_prompt(condition, QUESTION.question, ANSWERS, 0, transcript, STORY)
    with pytest.raises(ValueError):
        build_prompt("expert", QUESTION.question, ANSWERS, 0)


def test_build_prompt_checks_transcript_matches_condition():
    with pytest.raises(ValueError):
        build_prompt("debate", QUESTION.question, ANSWERS, 0, consultancy("correct"))
    with pytest.raises(ValueError):
        build_prompt("naive", QUESTION.question, ANSWERS, 0, debate())
    with pytest.raises(ValueError):
        build_prompt("debate", QUESTION.question, ANSWERS, 0)


# Votes and scoring


def vote(side):
    return Vote(0, None, side, "end_turn", "", "k")


@pytest.mark.parametrize("sides, score", [
    (["correct"] * 3, 1.0),
    (["correct", "correct", "distractor"], 1.0),
    (["correct", "distractor", "distractor"], 0.0),
    (["correct", "distractor", None], 0.5),  # Tie among valid votes
    ([None, None, None], 0.5),  # No valid votes
    (["distractor", None, None], 0.0),
])
def test_score_votes(sides, score):
    assert score_votes([vote(s) for s in sides]) == score


def test_votes_use_separate_samples_and_map_letters_to_sides():
    llm = FakeLLM(replies=lambda n: ["Answer: A", "Answer: B", "Answer: A"][(n - 1) % 3])
    first = judge(llm, SETTINGS, "naive", QUESTION, 0)
    second = judge(llm, SETTINGS, "naive", QUESTION, 1)
    assert [c["sample"] for c in llm.calls] == [0, 1, 2, 0, 1, 2]
    assert [v.side for v in first.votes] == ["correct", "distractor", "correct"]
    assert [v.side for v in second.votes] == ["distractor", "correct", "distractor"]
    assert (first.score, second.score) == (1.0, 0.0)


def test_refusals_and_missing_answers_are_invalid_votes():
    refused = judge(FakeLLM(replies=lambda n: "Answer: A", stop_reason="refusal"), SETTINGS, "naive", QUESTION, 0)
    assert [v.letter for v in refused.votes] == [None] * 3
    assert refused.score == 0.5 and refused.tie
    rambling = judge(FakeLLM(replies=lambda n: "I can't tell."), SETTINGS, "naive", QUESTION, 0)
    assert rambling.score == 0.5 and all(v.side is None for v in rambling.votes)


def test_incomplete_transcript_is_excluded_without_calls():
    llm = FakeLLM()
    verdict = judge(llm, SETTINGS, "debate", QUESTION, 0, debate(status="refused"))
    assert verdict.status == "excluded" and verdict.score is None and not verdict.tie
    assert llm.calls == []


def test_verdict_serializes_to_json():
    verdict = judge(FakeLLM(), SETTINGS, "consultancy", QUESTION, 1, consultancy("distractor"))
    record = json.loads(json.dumps(verdict.to_dict()))
    assert record["consultant_side"] == "distractor" and record["score"] == 0.0
    assert record["prompts"] == "judge_v1" and len(record["votes"]) == 3
