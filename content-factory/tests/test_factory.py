"""Unit tests for the content factory: verifiers, calibration, and the graph."""

from factory.calibrate import calibrate
from factory.graph import build_factory_graph
from factory.packs import Candidate
from factory.propose import seed_embed
from factory.verifiers import check_ambiguity, check_blocklist, verify

from server.tests.helpers import band_embed


class TestVerifiers:
    def test_blocklist(self):
        assert check_blocklist("blood") is not None
        assert check_blocklist("pancake") is None

    def test_ambiguity(self):
        assert check_ambiguity("thing") is not None
        assert check_ambiguity("ox") is not None  # too short
        assert check_ambiguity("pancake") is None

    def test_category_band_sets_distance(self):
        cand = Candidate("Food", "pancake", "easy")
        embed = band_embed("Food", "pancake", sim=0.5)
        verify(cand, embed)
        assert cand.category_distance == 0.5


class TestCalibrate:
    def test_low_plays_keeps_difficulty(self):
        cand = Candidate("Food", "pancake", "medium", win_rate=0.99, plays=2)
        assert calibrate(cand).difficulty == "medium"

    def test_civilians_win_too_much_bumps_harder(self):
        cand = Candidate("Food", "pancake", "medium", win_rate=0.95, plays=20)
        assert calibrate(cand).difficulty == "hard"

    def test_imposter_wins_too_much_eases(self):
        cand = Candidate("Food", "pancake", "medium", win_rate=0.10, plays=20)
        assert calibrate(cand).difficulty == "easy"

    def test_in_band_unchanged(self):
        cand = Candidate("Food", "pancake", "medium", win_rate=0.55, plays=20)
        assert calibrate(cand).difficulty == "medium"

    def test_hard_does_not_overflow(self):
        cand = Candidate("Food", "x", "hard", win_rate=0.99, plays=20)
        assert calibrate(cand).difficulty == "hard"


class TestGraph:
    async def test_pipeline_accepts_clean_and_rejects_dirty(self):
        graph = build_factory_graph()
        result = await graph.ainvoke({"requests": [("Food", "easy", 5)]})
        embed = seed_embed()
        assert result["accepted"]
        assert all(verify(c, embed) == [] for c in result["accepted"])
