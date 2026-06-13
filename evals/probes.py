"""Adversarial clue-leak probe set. Each leaking probe MUST be rejected by the
audit. The gate is zero leaks: a single accepted leaking clue fails CI.

Embedding-similarity probes are produced with the test vector helper so they
have a precise, controllable similarity regardless of the embedder wired in.
"""

from dataclasses import dataclass


@dataclass
class LeakProbe:
    secret: str
    clue: str
    why: str  # which leak channel this exercises


# Leaks that the deterministic checks must catch with any embedder.
DETERMINISTIC_LEAKS: list[LeakProbe] = [
    LeakProbe("pancake", "pancake please", "contains the word"),
    LeakProbe("pancake", "PANCAKE", "contains, case-insensitive"),
    LeakProbe("pancake", "pancakes", "plural form"),
    LeakProbe("camping", "camp", "stem match"),
    LeakProbe("camping", "camper", "stem match"),
    LeakProbe("pancake", "lake", "rhyme"),
    LeakProbe("nation", "station", "rhyme"),
    LeakProbe("cat", "hat", "rhyme"),
    LeakProbe("octopus", "an octopus swims", "contains + too many words"),
]

# Clues that are clean and should be accepted (guards against over-blocking).
CLEAN_CLUES: list[LeakProbe] = [
    LeakProbe("pancake", "breakfast", "related, distinct"),
    LeakProbe("camping", "tent", "related, distinct"),
    LeakProbe("octopus", "eight arms", "descriptive"),
]
