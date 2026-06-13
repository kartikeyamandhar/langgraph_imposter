"""Difficulty calibration from historical telemetry. Deterministic.

A word's difficulty is how hard it is for civilians to expose the imposter.
If civilians win far more often than expected, the word leaks the concept too
easily -> bump it harder. If the imposter wins far more often, the word is too
obscure -> ease it. Words without enough plays keep their proposed difficulty.
"""

from factory.packs import Candidate

MIN_PLAYS = 5  # below this, history is noise — leave difficulty as proposed
ORDER = ["easy", "medium", "hard"]

# Civilian win-rate bands considered "well calibrated" per difficulty.
TARGET_BANDS: dict[str, tuple[float, float]] = {
    "easy": (0.55, 0.85),
    "medium": (0.40, 0.70),
    "hard": (0.25, 0.55),
}


def _shift(difficulty: str, steps: int) -> str:
    idx = max(0, min(len(ORDER) - 1, ORDER.index(difficulty) + steps))
    return ORDER[idx]


def calibrate(candidate: Candidate) -> Candidate:
    if candidate.plays < MIN_PLAYS or candidate.win_rate is None:
        return candidate
    low, high = TARGET_BANDS.get(candidate.difficulty, TARGET_BANDS["medium"])
    if candidate.win_rate > high:
        # Civilians win too easily -> make it harder.
        candidate.difficulty = _shift(candidate.difficulty, +1)
    elif candidate.win_rate < low:
        # Imposter wins too easily -> make it easier.
        candidate.difficulty = _shift(candidate.difficulty, -1)
    return candidate
