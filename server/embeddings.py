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
