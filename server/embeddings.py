"""Embedding interface for the audit band and suspicion scoring.

The interface is the seam: `get_embedder()` returns a real semantic embedder
(OpenAI) when OPENAI_API_KEY is set, and otherwise a deterministic local stub
so dev and the offline test suite run at zero API cost. The stub is stable but
NOT semantic — band thresholds only mean something with OpenAI wired in. Tests
that exercise the band/suspicion logic inject controlled vectors directly.
"""

import hashlib
import logging
import math
import os
from collections.abc import Callable, Sequence
from functools import lru_cache

logger = logging.getLogger(__name__)

Vector = Sequence[float]
EmbedFn = Callable[[str], Vector]

_DIM = 64
DEFAULT_OPENAI_EMBED_MODEL = "text-embedding-3-small"


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


# --- OpenAI semantic embedder -------------------------------------------------


@lru_cache(maxsize=1)
def _openai_client():  # pragma: no cover - needs a key + network
    from openai import OpenAI

    return OpenAI()  # reads OPENAI_API_KEY from env


@lru_cache(maxsize=8192)
def _openai_vector(text: str) -> tuple[float, ...]:  # pragma: no cover - network
    """Cached OpenAI embedding for one string. Repeated words (the secret word
    across a round) cost one call. On any API error, fall back to the stub so an
    OpenAI hiccup degrades the band check rather than crashing the game."""
    model = os.environ.get("OPENAI_EMBED_MODEL", DEFAULT_OPENAI_EMBED_MODEL)
    try:
        resp = _openai_client().embeddings.create(model=model, input=[text])
        return tuple(resp.data[0].embedding)
    except Exception:
        logger.warning("openai embed failed for %r; using stub fallback", text, exc_info=True)
        return tuple(stub_embed(text))


def openai_embed() -> EmbedFn:
    """A semantic embedder backed by OpenAI (results cached per string)."""

    def embed(text: str) -> Vector:
        return list(_openai_vector(text))

    return embed


def get_embedder() -> EmbedFn:
    """OpenAI when OPENAI_API_KEY is set, else the deterministic stub."""
    if os.environ.get("OPENAI_API_KEY"):
        return openai_embed()
    return stub_embed
