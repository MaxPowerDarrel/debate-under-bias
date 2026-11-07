"""Check quoted text against the story and mark it verified or unverified.

Arguers wrap quotes in `<quote>` tags. `verify` re-tags each one as `<v_quote>` if it
appears in the story and `<u_quote>` if it doesn't. The judge is told to trust only
`<v_quote>` text.

This follows Khan et al.'s strict check: normalize both texts, then require the
quote to appear as one contiguous run of the story. There is no fuzzy matching, so a
quote that skips words with "..." is unverified. Three departures:

- Punctuation becomes a space instead of being deleted, and dashes and the ellipsis
  character count as punctuation. With deletion, a story's "word—word" becomes
  "wordword" while a quote written as "word - word" becomes "word word", so a
  correct quote fails.
- A quote that normalizes to nothing (empty, or only punctuation) is unverified.
  An empty string is a substring of every story, so it would otherwise pass.
- A quote must start and end on word boundaries. Khan's plain substring check
  lets "he ran" match inside "she ranked".
"""

import re
import string
from dataclasses import dataclass

_STRAIGHTEN = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
_PUNCTUATION = string.punctuation + "–—…"
_TO_SPACE = str.maketrans({c: " " for c in _PUNCTUATION})

# Arguers may write `v_quote`/`u_quote` tags themselves. Resetting them to `quote`
# before checking means only this module can mark a quote verified.
_EXISTING_TAG = re.compile(r"<(/?)[uv]_quote>")
_QUOTE = re.compile(r"<quote>(.*?)</quote>", re.DOTALL)


def normalize(text: str) -> str:
    """Straighten quotes, turn punctuation into spaces, lowercase, and collapse spaces."""
    text = text.translate(_STRAIGHTEN).translate(_TO_SPACE).lower()
    return " ".join(text.split())


def is_in_story(quote: str, normalized_story: str) -> bool:
    quote = normalize(quote)
    if not quote:
        return False
    # Pad with spaces so a quote must start and end on word boundaries:
    # "he ran" should not match inside "she ranked".
    return f" {quote} " in f" {normalized_story} "


def reset_tags(text: str) -> str:
    """Turn any `v_quote`/`u_quote` tags an arguer wrote back into `quote`, so it can't self-verify."""
    return _EXISTING_TAG.sub(r"<\1quote>", text)


@dataclass(frozen=True)
class Verified:
    text: str  # The argument with every complete quote re-tagged as v_quote or u_quote
    verified: list[str]
    unverified: list[str]


def verify(argument: str, story: str) -> Verified:
    """Re-tag each `<quote>` in `argument` by whether it appears in `story`.

    An unclosed `<quote>` isn't matched, so it stays as plain text and is never verified.
    """
    normalized_story = normalize(story)
    verified, unverified = [], []

    def retag(match: re.Match) -> str:
        quote = match.group(1)
        if is_in_story(quote, normalized_story):
            verified.append(quote)
            return f"<v_quote>{quote}</v_quote>"
        unverified.append(quote)
        return f"<u_quote>{quote}</u_quote>"

    text = _QUOTE.sub(retag, reset_tags(argument))
    return Verified(text, verified, unverified)
