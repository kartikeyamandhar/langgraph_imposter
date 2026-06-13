"""Pure game rules from the spec. No I/O, no LLM, fully unit-testable.

Scoring: imposter round win is +3 to the imposter. Civilian round win is +1 to
every civilian plus +1 extra to each player who voted for the imposter in the
deciding vote. Match end: first to 7 points, or 5 rounds, host's choice.
"""

from collections import Counter

from server.state import MAX_ROUNDS, POINTS_TO_WIN, GameState, PlayerInfo


def tally_votes(votes: dict[str, str]) -> tuple[list[str], Counter[str]]:
    """Return (leaders, counts). Leaders are all targets tied for most votes."""
    counts: Counter[str] = Counter(votes.values())
    if not counts:
        return [], counts
    top = max(counts.values())
    leaders = [target for target, n in counts.items() if n == top]
    return leaders, counts


def imposter_round_scores(
    players: list[PlayerInfo], imposter_ids: list[str]
) -> dict[str, int]:
    return {pid: 3 for pid in imposter_ids}


def civilian_round_scores(
    players: list[PlayerInfo], imposter_ids: list[str], deciding_votes: dict[str, str]
) -> dict[str, int]:
    scores: dict[str, int] = {}
    for p in players:
        if p["id"] in imposter_ids:
            continue
        scores[p["id"]] = 1
    for voter, target in deciding_votes.items():
        if target in imposter_ids and voter not in imposter_ids:
            scores[voter] = scores.get(voter, 0) + 1
    return scores


def match_winners(state: GameState) -> list[str]:
    """Empty list means the match continues. Ties at match end share the win."""
    scores = state.get("scores", {})
    mode = state["settings"]["win_mode"]
    over = False
    if mode == "points":
        over = any(s >= POINTS_TO_WIN for s in scores.values())
    else:
        over = state.get("round_no", 0) >= MAX_ROUNDS
    if not over:
        return []
    if not scores:
        return []
    top = max(scores.values())
    return [pid for pid, s in scores.items() if s == top]
