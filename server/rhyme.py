"""Deterministic rhyme check for the clue audit. Heuristic, not phonetic:
two words rhyme if they share the same rime (last vowel cluster onward) but
differ in onset. Catches the obvious leak forms (cat/hat, nation/station)."""

import re

_VOWELS = "aeiouy"


def rime(word: str) -> str:
    """The portion from the last sounded vowel to the end, lowercased.

    A silent terminal 'e' (consonant + e) is dropped first so that words like
    "lake" and "cake" rime on "ak" rather than the silent "e". "pancake" -> "ak",
    "cat" -> "at", "station" -> "on", "fog" -> "og".
    """
    w = re.sub(r"[^a-z]", "", word.lower())
    if len(w) >= 3 and w[-1] == "e" and w[-2] not in _VOWELS:
        w = w[:-1]
    last_vowel = -1
    for i, ch in enumerate(w):
        if ch in _VOWELS:
            last_vowel = i
    if last_vowel == -1:
        return w
    return w[last_vowel:]


def rhymes(a: str, b: str) -> bool:
    a = re.sub(r"[^a-z]", "", a.lower())
    b = re.sub(r"[^a-z]", "", b.lower())
    if not a or not b or a == b:
        return False
    ra, rb = rime(a), rime(b)
    # Require a rime of length >= 2 so "a"/"the" don't spuriously rhyme.
    if len(ra) < 2 or ra != rb:
        return False
    # Different onset: the leading consonants before the rime must differ.
    return a[: len(a) - len(ra)] != b[: len(b) - len(rb)]
