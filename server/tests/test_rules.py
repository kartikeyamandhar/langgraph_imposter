from server import rules
from server.state import GameState, PlayerInfo


def players(n: int) -> list[PlayerInfo]:
    return [{"id": f"p{i}", "name": f"P{i}", "seat": i, "is_ai": False} for i in range(n)]


class TestTally:
    def test_single_leader(self):
        votes = {"p0": "p2", "p1": "p2", "p2": "p0", "p3": "p2"}
        leaders, counts = rules.tally_votes(votes)
        assert leaders == ["p2"]
        assert counts["p2"] == 3

    def test_tie(self):
        votes = {"p0": "p1", "p1": "p0", "p2": "p1", "p3": "p0"}
        leaders, _ = rules.tally_votes(votes)
        assert sorted(leaders) == ["p0", "p1"]


class TestScoring:
    def test_imposter_win(self):
        delta = rules.imposter_round_scores(players(5), ["p3"])
        assert delta == {"p3": 3}

    def test_civilian_win_with_correct_voters(self):
        ps = players(4)
        # p3 is the imposter; p0 and p1 voted for the imposter, p2 missed.
        votes = {"p0": "p3", "p1": "p3", "p2": "p0", "p3": "p0"}
        delta = rules.civilian_round_scores(ps, ["p3"], votes)
        assert delta == {"p0": 2, "p1": 2, "p2": 1}
        assert "p3" not in delta

    def test_imposter_vote_for_imposter_gets_nothing(self):
        ps = players(4)
        votes = {"p0": "p3", "p1": "p3", "p2": "p3", "p3": "p3"}
        delta = rules.civilian_round_scores(ps, ["p3"], votes)
        assert delta == {"p0": 2, "p1": 2, "p2": 2}


class TestMatchEnd:
    def _state(self, scores, mode, round_no) -> GameState:
        return {
            "scores": scores,
            "settings": {"discussion_seconds": 90, "win_mode": mode, "second_imposter": False},
            "round_no": round_no,
        }

    def test_points_mode_continues_below_seven(self):
        assert rules.match_winners(self._state({"a": 6, "b": 3}, "points", 3)) == []

    def test_points_mode_ends_at_seven(self):
        assert rules.match_winners(self._state({"a": 7, "b": 3}, "points", 3)) == ["a"]

    def test_rounds_mode_ends_after_five(self):
        assert rules.match_winners(self._state({"a": 4, "b": 6}, "rounds", 5)) == ["b"]

    def test_rounds_mode_shared_win_on_tie(self):
        winners = rules.match_winners(self._state({"a": 6, "b": 6}, "rounds", 5))
        assert sorted(winners) == ["a", "b"]
