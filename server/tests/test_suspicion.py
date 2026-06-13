"""Deterministic suspicion scoring and AI vote selection."""

from server.ai.suspicion import choose_vote, suspicion_scores
from server.embeddings import stub_embed


def clustered_clues():
    """Three civilians give related clues; the imposter (p3) gives an outlier."""
    return {
        "p0": "breakfast morning meal",
        "p1": "morning breakfast food",
        "p2": "meal morning breakfast",
        "p3": "automobile engine wheel",
    }


class TestSuspicion:
    def test_outlier_scores_highest(self):
        scores = suspicion_scores(clustered_clues(), stub_embed)
        assert max(scores, key=lambda k: scores[k]) == "p3"

    def test_deterministic(self):
        a = suspicion_scores(clustered_clues(), stub_embed)
        b = suspicion_scores(clustered_clues(), stub_embed)
        assert a == b

    def test_single_clue_is_neutral(self):
        scores = suspicion_scores({"p0": "lonely"}, stub_embed)
        assert scores == {"p0": 0.0}


class TestChooseVote:
    def test_votes_for_outlier(self):
        d = choose_vote("p0", clustered_clues(), ["p0", "p1", "p2", "p3"], stub_embed)
        assert d.target == "p3"
        assert "p3" in d.rationale

    def test_never_votes_self(self):
        clues = clustered_clues()
        # Even if the voter is the outlier, it must pick someone else.
        d = choose_vote("p3", clues, ["p0", "p1", "p2", "p3"], stub_embed)
        assert d.target != "p3"

    def test_revote_restricts_to_candidates(self):
        d = choose_vote("p0", clustered_clues(), ["p1", "p2"], stub_embed)
        assert d.target in ("p1", "p2")

    def test_tie_break_is_deterministic(self):
        # Two identical clues -> equal suspicion -> lowest id wins.
        clues = {"p0": "same clue", "p1": "same clue", "p2": "same clue"}
        d = choose_vote("p2", clues, ["p0", "p1", "p2"], stub_embed)
        assert d.target == "p0"
