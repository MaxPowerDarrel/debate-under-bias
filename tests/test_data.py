import pytest

from debate_bias.data import DATA_DIR, choose_distractor, filter_questions, load_questions


def validator(answer=2, answerability=1, context=2, distractor=3):
    return {
        "untimed_answer": answer,
        "untimed_eval1_answerability": answerability,
        "untimed_eval2_context": context,
        "untimed_best_distractor": distractor,
    }


def make_question(qid="q1", gold=2, writer=2, difficult=1, validation=None):
    return {
        "question_unique_id": qid,
        "question": " Why? ",
        "options": ["opt1", "opt2", "opt3", "opt4"],
        "gold_label": gold,
        "writer_label": writer,
        "difficult": difficult,
        "validation": validation if validation is not None else [validator(), validator(), validator()],
    }


def make_article(questions, source="Gutenberg", article_id="a1"):
    return {"article_id": article_id, "source": source, "title": " T ", "article": "story", "questions": questions}


def kept_ids(articles):
    questions, _ = filter_questions(articles)
    return [q.question_id for q in questions]


def test_passing_question_uses_one_indexed_labels():
    [q], counts = filter_questions([make_article([make_question()])])
    assert q.correct == "opt2"
    assert q.distractor == "opt3"
    assert q.question == "Why?" and q.title == "T"
    assert counts["all"] == counts["writer_agrees"] == 1


@pytest.mark.parametrize(
    "article",
    [
        make_article([make_question()], source="Slate"),
        make_article([make_question(difficult=0)]),
        make_article([make_question(validation=[validator(), validator(answer=1), validator()])]),
        make_article([make_question(validation=[validator(), validator(answerability=2), validator()])]),
        make_article([make_question(validation=[validator(context=1)] * 2 + [validator(context=2)])]),
        make_article([make_question(writer=1)]),
    ],
    ids=["not_gutenberg", "not_difficult", "annotator_wrong", "ambiguous", "low_context", "writer_disagrees"],
)
def test_each_filter_drops_failing_question(article):
    assert kept_ids([article]) == []


def test_context_threshold_is_inclusive():
    # Mean of (1, 2) is exactly 1.5, so it's kept.
    q = make_question(validation=[validator(context=1), validator(context=2)])
    assert kept_ids([make_article([q])]) == ["q1"]


def test_counts_are_cumulative_per_stage():
    articles = [
        make_article([make_question("keep"), make_question("easy", difficult=0)]),
        make_article([make_question("slate")], source="Slate", article_id="a2"),
    ]
    _, counts = filter_questions(articles)
    assert counts["all"] == 3
    assert counts["gutenberg"] == 2
    assert counts["difficult"] == 1
    assert counts["writer_agrees"] == 1


def test_distractor_is_most_common_vote():
    q = make_question(validation=[validator(distractor=1), validator(distractor=4), validator(distractor=4)])
    assert choose_distractor(q) == 4


def test_distractor_ignores_votes_for_gold():
    q = make_question(gold=2, validation=[validator(distractor=2), validator(distractor=2), validator(distractor=3)])
    assert choose_distractor(q) == 3


def test_distractor_tie_goes_to_lowest_option():
    q = make_question(validation=[validator(distractor=4), validator(distractor=1), validator(distractor=3)])
    assert choose_distractor(q) == 1


def test_distractor_without_votes_raises():
    q = make_question(gold=2, validation=[validator(distractor=2)])
    with pytest.raises(ValueError):
        choose_distractor(q)


@pytest.mark.skipif(not (DATA_DIR / "QuALITY.v1.0.1.htmlstripped.dev").exists(), reason="QuALITY not downloaded")
@pytest.mark.parametrize("split, expected", [("train", 461), ("dev", 350)])
def test_real_split_counts(split, expected):
    questions, _ = load_questions(split)
    assert len(questions) == expected
    assert all(q.correct != q.distractor for q in questions)
    assert len({q.question_id for q in questions}) == len(questions)
