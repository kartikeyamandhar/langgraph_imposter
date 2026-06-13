"""Candidate proposal + the offline embedder.

The LLM seam is injectable; the offline default returns a deterministic seed
list so the factory and its tests run without a key. The seed carries an
intended category similarity per word, and `seed_embed` places each word at
that similarity so the offline pipeline is deterministic while the category
band stays enforced. Production swaps in a real semantic embedder.
"""

from collections.abc import Awaitable, Callable

from factory.packs import Candidate
from server.embeddings import EmbedFn, stub_embed, vector_at

# (category, difficulty) -> proposer that yields candidate words.
ProposeFn = Callable[[str, str, int], Awaitable[list[Candidate]]]

# (word, difficulty, intended category similarity). Similarities sit inside the
# verifier's CATEGORY_BANDS for the stated difficulty.
SEED: dict[str, list[tuple[str, str, float]]] = {
    "Food": [
        ("pancake", "easy", 0.50),
        ("sushi", "easy", 0.45),
        ("risotto", "medium", 0.40),
    ],
    "Animals": [
        ("penguin", "easy", 0.55),
        ("octopus", "medium", 0.35),
        ("axolotl", "hard", 0.20),
    ],
    "Places": [
        ("library", "medium", 0.40),
        ("lighthouse", "medium", 0.30),
        ("tundra", "hard", 0.18),
    ],
}


def seed_embed() -> EmbedFn:
    """Offline embedder: places each seed word at its intended similarity to
    its category; everything else falls back to the deterministic stub."""
    placed: dict[str, list[float]] = {}
    for category, entries in SEED.items():
        base = stub_embed(category)
        for word, _difficulty, sim in entries:
            placed[word] = vector_at(base, sim)

    def embed(text: str) -> list[float]:
        return placed.get(text, list(stub_embed(text)))

    return embed


async def offline_propose(category: str, difficulty: str, n: int) -> list[Candidate]:
    words = [w for w, d, _ in SEED.get(category, []) if d == difficulty][:n]
    return [Candidate(category=category, secret_word=w, difficulty=difficulty) for w in words]


def default_propose() -> ProposeFn:
    return offline_propose
