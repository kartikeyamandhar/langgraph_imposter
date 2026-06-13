"""Deterministic validators. Anything entering game state passes through here,
for humans and AI alike. Pure functions, unit-tested offline."""

import re

from server.state import MAX_CLUE_WORDS

# Verb/adjective inflections, applied after plurals are normalized.
_INFLECTIONS = ("ingly", "edly", "ing", "ed", "est", "er", "ly")


def simple_stem(word: str) -> str:
    """Cheap deterministic stemmer: lowercase, normalize plurals, strip
    common inflections. Two forms of the same root collapse to one string.

    Not linguistically perfect; tuned to catch obvious leak forms
    (pancakes/pancake, camping/camp/camper). Same-spelling-different-meaning
    is out of scope — containment catches the rest.
    """
    w = word.lower()

    # Plurals, sibilant-aware: "boxes" -> "box" but "cakes" -> "cake".
    if w.endswith("ies") and len(w) >= 5:
        w = w[:-3] + "y"
    elif w.endswith(("ses", "xes", "zes", "ches", "shes")) and len(w) >= 5:
        w = w[:-2]
    elif w.endswith("s") and not w.endswith("ss") and len(w) >= 4:
        w = w[:-1]

    for suffix in _INFLECTIONS:
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            return w[: -len(suffix)]
    return w


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def validate_clue(clue: str, secret_word: str) -> str | None:
    """Return None if the clue is acceptable, else a player-facing error.

    Rejects any clue that contains or stem-matches the secret word.
    Errors state what happened and what to do — never apologize.
    """
    words = _tokens(clue)
    if not words:
        return "Clue is empty. Enter up to 3 words."
    if len(words) > MAX_CLUE_WORDS:
        return f"Clue has {len(words)} words. Use {MAX_CLUE_WORDS} or fewer."

    secret = secret_word.lower()
    secret_stem = simple_stem(secret)
    if secret in clue.lower():
        return "Clue contains the secret word. Pick a different clue."
    for w in words:
        if simple_stem(w) == secret_stem:
            return "Clue is a form of the secret word. Pick a different clue."
    return None


def normalize_guess(text: str) -> str:
    return simple_stem(text.strip().lower())


def guess_matches(guess: str, secret_word: str) -> bool:
    """Imposter's word guess: exact or stem-equal after normalization."""
    g = _tokens(guess)
    if len(g) != 1:
        return False
    return g[0] == secret_word.lower() or simple_stem(g[0]) == simple_stem(secret_word)
