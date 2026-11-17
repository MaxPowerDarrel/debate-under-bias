import importlib.util
from pathlib import Path

from debate_bias.quotes import normalize

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "count_untagged_quotes.py"
_spec = importlib.util.spec_from_file_location("count_untagged_quotes", _PATH)
cu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cu)

STORY = normalize("The ship landed at dawn. “We are home,” said the captain, and nobody answered.")


def test_finds_plain_story_quote_with_straight_or_curly_marks():
    assert cu.plain_story_quotes('He says "The ship landed at dawn."', STORY) == ["The ship landed at dawn."]
    assert cu.plain_story_quotes("He says “nobody answered at all”", STORY) == []  # not in story
    assert cu.plain_story_quotes("He says “and nobody answered”", STORY) == ["and nobody answered"]


def test_ignores_tagged_quotes_short_spans_and_non_story_text():
    text = ('<v_quote>"We are home," said the captain</v_quote> and the answer is "Unknown". '
            'The opponent claims "the ship never landed".')
    assert cu.plain_story_quotes(text, STORY) == []


def test_lost_unless_inside_a_verified_quote():
    verified = ["The ship landed at dawn"]
    assert not cu.is_lost("landed at dawn", verified)
    assert cu.is_lost("nobody answered", verified)
    assert cu.is_lost("ship land", verified)  # word boundaries, not substrings
