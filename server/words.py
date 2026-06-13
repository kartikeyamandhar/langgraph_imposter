"""Word source for the live game.

M1 ships a small built-in dev pack so rounds are playable before the content
factory (M3) starts producing versioned packs in Postgres. The draw interface
stays the same when the source switches.
"""

import random

# (category, word, difficulty)
DEV_PACK: list[tuple[str, str, str]] = [
    ("Food", "pancake", "easy"),
    ("Food", "sushi", "easy"),
    ("Food", "burrito", "easy"),
    ("Animals", "penguin", "easy"),
    ("Animals", "octopus", "easy"),
    ("Animals", "kangaroo", "easy"),
    ("Places", "airport", "medium"),
    ("Places", "library", "medium"),
    ("Places", "lighthouse", "medium"),
    ("Objects", "umbrella", "medium"),
    ("Objects", "telescope", "medium"),
    ("Objects", "hammock", "medium"),
    ("Activities", "karaoke", "medium"),
    ("Activities", "camping", "easy"),
    ("Activities", "yoga", "easy"),
    ("Movies", "western", "hard"),
    ("Music", "jazz", "hard"),
    ("Weather", "fog", "hard"),
]


def draw_word(used_words: list[str], rng: random.Random | None = None) -> tuple[str, str, str]:
    """Draw (category, word, difficulty), avoiding words already used this match."""
    rng = rng or random.Random()
    pool = [entry for entry in DEV_PACK if entry[1] not in used_words]
    if not pool:
        pool = list(DEV_PACK)
    return rng.choice(pool)
