"""The fail-closed AI clue audit (ADR 001). Deterministic, pure, offline.

An AI clue enters game state only if it passes every check:
  1. does not contain the secret word,
  2. does not stem-match the secret word,
  3. does not rhyme with the secret word,
  4. its embedding similarity to the secret word sits inside the calibrated
     band for the pack's difficulty (too close = leak; too far = off-topic).

There is no force-pass path. On FAIL the caller loops back to the clue agent
with the specific violations, then falls back to a safe template clue.
"""

from dataclasses import dataclass, field

from server.embeddings import EmbedFn, similarity
from server.rhyme import rhymes
from server.validators import _tokens, simple_stem

# (low, high) inclusive similarity band per difficulty. Calibrated against
# telemetry in M3; these are conservative starting values. The upper bound is
# the leak guard and is the one that must never be widened to pass a test.
DIFFICULTY_BANDS: dict[str, tuple[float, float]] = {
    "easy": (0.10, 0.60),
    "medium": (0.08, 0.55),
    "hard": (0.05, 0.50),
}
DEFAULT_BAND = (0.08, 0.55)


@dataclass
class AuditReport:
    passed: bool
    similarity: float
    band: tuple[float, float]
    violations: list[str] = field(default_factory=list)

    def feedback(self) -> str:
        return "; ".join(self.violations)


def audit_clue(
    clue: str,
    secret_word: str,
    difficulty: str,
    embed: EmbedFn,
    bands: dict[str, tuple[float, float]] | None = None,
) -> AuditReport:
    bands = bands or DIFFICULTY_BANDS
    low, high = bands.get(difficulty, DEFAULT_BAND)
    violations: list[str] = []

    secret = secret_word.lower()
    tokens = _tokens(clue)
    secret_stem = simple_stem(secret)

    if not tokens:
        violations.append("clue is empty")
    if len(tokens) > 3:
        violations.append(f"clue has {len(tokens)} words, max 3")
    if secret in clue.lower():
        violations.append("clue contains the secret word")
    if any(simple_stem(t) == secret_stem for t in tokens):
        violations.append("clue is a grammatical form of the secret word")
    if any(rhymes(t, secret) for t in tokens):
        violations.append("clue rhymes with the secret word")

    sim = similarity(embed, clue, secret_word) if tokens else 0.0
    if sim > high:
        violations.append(f"clue is too close to the secret word ({sim:.2f} > {high:.2f})")
    elif tokens and sim < low:
        violations.append(f"clue is too far from the category ({sim:.2f} < {low:.2f})")

    return AuditReport(
        passed=not violations, similarity=sim, band=(low, high), violations=violations
    )
