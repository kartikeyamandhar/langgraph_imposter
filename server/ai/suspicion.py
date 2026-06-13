"""Deterministic suspicion scoring for AI votes.

Civilians' clues cluster around the secret word; the imposter, not knowing the
word, tends to give a clue that is an outlier. Suspicion(player) is how
dissimilar their clue is from everyone else's. An AI votes for the most
suspicious player other than itself. The rationale is logged to telemetry.

Pure and deterministic: same clues + same embed function => same vote.
"""

from dataclasses import dataclass

from server.embeddings import EmbedFn, cosine


@dataclass
class VoteDecision:
    target: str
    rationale: str
    scores: dict[str, float]


def suspicion_scores(clues: dict[str, str], embed: EmbedFn) -> dict[str, float]:
    """Map player_id -> suspicion in [0, 1]; higher = more likely imposter."""
    ids = list(clues)
    if len(ids) < 2:
        return {pid: 0.0 for pid in ids}

    vectors = {pid: embed(text) for pid, text in clues.items()}
    scores: dict[str, float] = {}
    for pid in ids:
        others = [vectors[o] for o in ids if o != pid]
        avg_sim = sum(cosine(vectors[pid], o) for o in others) / len(others)
        # Map cosine [-1, 1] to suspicion [0, 1]: less similar => more suspicious.
        scores[pid] = max(0.0, min(1.0, (1.0 - avg_sim) / 2.0))
    return scores


def choose_vote(
    voter_id: str,
    clues: dict[str, str],
    candidates: list[str],
    embed: EmbedFn,
) -> VoteDecision:
    """Pick the most suspicious eligible target (never the voter).

    `candidates` restricts the choice (e.g. tied players in a re-vote).
    Ties broken by player id for determinism.
    """
    scores = suspicion_scores(clues, embed)
    eligible = [c for c in candidates if c != voter_id]
    if not eligible:
        eligible = [c for c in candidates] or [voter_id]

    target = max(eligible, key=lambda pid: (scores.get(pid, 0.0), _neg_id(pid)))
    sim_note = scores.get(target, 0.0)
    rationale = (
        f"voted {target}: most out-of-place clue "
        f"(suspicion {sim_note:.2f} of {len(clues)} clues)"
    )
    return VoteDecision(target=target, rationale=rationale, scores=scores)


def _neg_id(pid: str) -> tuple[int, ...]:
    # Lexicographically smaller id wins ties: negate codepoints for max().
    return tuple(-ord(c) for c in pid)
