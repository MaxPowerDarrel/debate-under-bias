import pytest

from debate_bias.data import DATA_DIR, load_questions
from debate_bias.quotes import normalize, verify

STORY = (
    "Captain Hale didn’t look back. “We leave at dawn,” she said—quietly, firmly.\n"
    "The ship had 42 crewmen, and every one of them was ranked by seniority."
)


def tags(argument):
    result = verify(argument, STORY)
    return result, len(result.verified), len(result.unverified)


def test_normalize():
    assert normalize("  “Hello,”  World—it’s\nME… ") == "hello world it s me"


@pytest.mark.parametrize(
    "quote",
    [
        "We leave at dawn",  # Exact
        "we LEAVE at dawn",  # Case
        '"We leave at dawn," she said',  # Straight quotes and punctuation
        "Captain Hale didn't look back",  # Straight apostrophe against a curly one
        "she said - quietly, firmly",  # Hyphen against an em dash
        "she said quietly firmly",  # Dropped punctuation
        "firmly. The ship",  # Across a line break
        "The ship had 42\n   crewmen",  # Extra whitespace inside the quote
    ],
)
def test_matching_quotes_are_verified(quote):
    result, n_verified, n_unverified = tags(f"Look: <quote>{quote}</quote>.")
    assert (n_verified, n_unverified) == (1, 0)
    assert result.text == f"Look: <v_quote>{quote}</v_quote>."


@pytest.mark.parametrize(
    "quote",
    [
        "We leave at midnight",  # Not in the story
        "The ship had 43 crewmen",  # Wrong number
        "Captain Hale ... look back",  # Elided words
        "he ran",  # Only inside "she ... ranked"; must match whole words
        "",  # Empty
        "...!",  # Only punctuation
    ],
)
def test_non_matching_quotes_are_unverified(quote):
    result, n_verified, n_unverified = tags(f"<quote>{quote}</quote>")
    assert (n_verified, n_unverified) == (0, 1)
    assert result.text == f"<u_quote>{quote}</u_quote>"


def test_arguer_cannot_fake_verification():
    result, n_verified, n_unverified = tags("<v_quote>We leave at midnight</v_quote>")
    assert (n_verified, n_unverified) == (0, 1)
    assert result.text == "<u_quote>We leave at midnight</u_quote>"


def test_arguer_written_u_quote_is_rechecked():
    result, n_verified, _ = tags("<u_quote>We leave at dawn</u_quote>")
    assert n_verified == 1
    assert result.text == "<v_quote>We leave at dawn</v_quote>"


def test_multiple_quotes_are_checked_separately():
    result, n_verified, n_unverified = tags(
        "<quote>We leave at dawn</quote> but <quote>We stay</quote> and <quote>42 crewmen</quote>"
    )
    assert (n_verified, n_unverified) == (2, 1)
    assert result.verified == ["We leave at dawn", "42 crewmen"]
    assert result.unverified == ["We stay"]


def test_unclosed_quote_stays_plain_text():
    argument = "He wrote <quote>We leave at dawn and never closed it"
    result, n_verified, n_unverified = tags(argument)
    assert (n_verified, n_unverified) == (0, 0)
    assert result.text == argument


def test_text_without_quotes_is_unchanged():
    assert verify("No quotes here.", STORY).text == "No quotes here."


@pytest.mark.skipif(not (DATA_DIR / "QuALITY.v1.0.1.htmlstripped.train").exists(), reason="QuALITY not downloaded")
def test_real_story_sentences_verify():
    question = load_questions("train")[0][0]
    sentences = [s.strip() for s in question.story.split(".") if len(s.split()) >= 8][:20]
    assert sentences
    argument = " ".join(f"<quote>{s}</quote>" for s in sentences)
    result = verify(argument, question.story)
    assert len(result.verified) == len(sentences)
    assert not verify("<quote>this sentence is not in the story at all</quote>", question.story).verified
