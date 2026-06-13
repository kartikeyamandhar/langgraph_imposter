"""Embedding interface for the audit band and suspicion scoring.

The interface is the seam: production injects a real semantic embedding model;
dev and the offline test suite use a deterministic local stub so the suite runs
at zero API cost. The stub is stable but NOT semantic — band thresholds only
mean something with a real model wired in (see calibration in M3). Tests that
exercise the band/suspicion logic inject controlled vectors directly.
"""

import hashlib
import math
from collections.abc import Callable, Sequence

Vector = Sequence[float]
EmbedFn = Callable[[str], Vector]

_DIM = 64


def stub_embed(text: str) -> list[float]:
    """Deterministic per-token bag-of-words vector. Stable across runs."""
    vec = [0.0] * _DIM
    for token in text.lower().split():
        h = hashlib.sha256(token.encode()).digest()
        for i in range(_DIM):
            vec[i] += (h[i % len(h)] / 255.0) - 0.5
    return vec


def cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def similarity(embed: EmbedFn, a: str, b: str) -> float:
    """Cosine similarity in [-1, 1] between two strings under `embed`."""
    return cosine(embed(a), embed(b))


def vector_at(base: Vector, sim: float) -> list[float]:
    """A vector whose cosine similarity with `base` is exactly `sim`. Used to
    place a word/clue at a controlled similarity for the offline embedder and
    for band-edge tests."""
    n = math.sqrt(sum(x * x for x in base)) or 1.0
    u = [x / n for x in base]
    # An arbitrary direction, then Gram-Schmidt to make it orthogonal to u.
    r = [1.0 if i == 0 else 0.0 for i in range(len(u))]
    dot = sum(r[i] * u[i] for i in range(len(u)))
    w = [r[i] - dot * u[i] for i in range(len(u))]
    wn = math.sqrt(sum(x * x for x in w)) or 1.0
    w = [x / wn for x in w]
    k = math.sqrt(max(0.0, 1 - sim * sim))
    return [sim * u[i] + k * w[i] for i in range(len(u))]
