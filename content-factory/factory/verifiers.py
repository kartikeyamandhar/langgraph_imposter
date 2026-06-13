"""Deterministic pack verifiers. Pure functions over a candidate word; no LLM.
A candidate ships only if every verifier passes. These same checks back the
evals/ pack-quality gate in CI."""

import re

from factory.packs import Candidate
from server.embeddings import EmbedFn, similarity

# Words we never ship. Extend as needed; kept terse on purpose.
BLOCKLIST: set[str] = {
    "slur",  # placeholder stand-ins for an offensive-term blocklist
    "blood",
    "death",
    "kill",
}

# Words too ambiguous or too generic to anchor a round.
AMBIGUOUS: set[str] = {"thing", "stuff", "object", "item", "place", "person"}

# Embedding-distance band per difficulty: how far the word may sit from its
# category. Easy words are prototypical (close); hard words are further out.
# (min_similarity, max_similarity) to the category string.
CATEGORY_BANDS: dict[str, tuple[float, float]] = {
    "easy": (0.30, 1.00),
    "medium": (0.15, 0.60),
    "hard": (0.00, 0.35),
}


def check_blocklist(word: str) -> str | None:
    return "blocklisted word" if word.lower() in BLOCKLIST else None


def check_ambiguity(word: str) -> str | None:
    w = word.lower().strip()
    if len(w) < 3:
        return "word is too short"
    if w in AMBIGUOUS:
        return "word is too ambiguous"
    if not re.fullmatch(r"[a-z][a-z' -]*[a-z]", w):
        return "word has unexpected characters"
    return None


def check_category_distance(
    word: str, category: str, difficulty: str, embed: EmbedFn
) -> tuple[str | None, float]:
    sim = similarity(embed, word, category)
    low, high = CATEGORY_BANDS.get(difficulty, CATEGORY_BANDS["medium"])
    if sim < low or sim > high:
        return (
            f"{difficulty} word out of category band ({sim:.2f} not in [{low:.2f},{high:.2f}])",
            sim,
        )
    return None, sim


def verify(candidate: Candidate, embed: EmbedFn) -> list[str]:
    """Return the list of violations (empty means the candidate is shippable)."""
    violations: list[str] = []
    for check in (check_blocklist, check_ambiguity):
        v = check(candidate.secret_word)
        if v:
            violations.append(v)
    band_violation, sim = check_category_distance(
        candidate.secret_word, candidate.category, candidate.difficulty, embed
    )
    candidate.category_distance = sim
    if band_violation:
        violations.append(band_violation)
    return violations
