"""Test helpers for placing a clue at an exact cosine similarity to a secret
word, so audit band edges can be checked precisely."""

import math

from server.embeddings import stub_embed


def vector_at(base: list[float], sim: float) -> list[float]:
    """A unit-ish vector whose cosine with `base` is exactly `sim`."""
    n = math.sqrt(sum(x * x for x in base)) or 1.0
    u = [x / n for x in base]
    # An arbitrary direction, then Gram-Schmidt to make it orthogonal to u.
    r = [1.0 if i == 0 else 0.0 for i in range(len(base))]
    dot = sum(r[i] * u[i] for i in range(len(base)))
    w = [r[i] - dot * u[i] for i in range(len(base))]
    wn = math.sqrt(sum(x * x for x in w)) or 1.0
    w = [x / wn for x in w]
    k = math.sqrt(max(0.0, 1 - sim * sim))
    return [sim * u[i] + k * w[i] for i in range(len(base))]


def band_embed(secret: str, clue_word: str, sim: float):
    """Embed where `clue_word` sits at cosine `sim` to `secret`; all other
    strings fall back to the deterministic stub."""
    target = vector_at(stub_embed(secret), sim)

    def embed(text: str):
        return target if text == clue_word else stub_embed(text)

    return embed
