"""The broadcast builder is the privacy boundary. These tests enumerate what
must never leak into the public payload or the wrong player's private view."""

from server.protocol import private_view, public_phase_state
from server.state import GameState


def mid_vote_state() -> GameState:
    return {
        "room": "ABCD",
        "host_id": "p0",
        "phase": "vote",
        "players": [
            {"id": f"p{i}", "name": f"P{i}", "seat": i, "is_ai": False} for i in range(4)
        ],
        "settings": {"discussion_seconds": 90, "win_mode": "points", "second_imposter": False},
        "round_no": 1,
        "imposter_ids": ["p2"],
        "category": "Food",
        "secret_word": "pancake",
        "difficulty": "easy",
        "speaking_order": ["p1", "p0", "p3", "p2"],
        "clue_index": 4,
        "clues": [{"player_id": "p1", "clue": "syrup"}],
        "votes": {"p0": "p2", "p1": "p3"},
        "revote": False,
        "revote_candidates": [],
        "eliminated": None,
        "action_error": {"player_id": "p3", "error": "Pick a player to vote for."},
        "scores": {},
        "results": [],
        "last_result": None,
    }


class TestPublicPayload:
    def test_no_secret_fields_anywhere(self):
        public = public_phase_state(mid_vote_state(), connected=set())
        flat = str(public)
        assert "pancake" not in flat
        assert "imposter_ids" not in public
        assert "secret_word" not in public

    def test_votes_stay_secret_only_locks_show(self):
        public = public_phase_state(mid_vote_state(), connected=set())
        assert public["locked_voters"] == ["p0", "p1"]
        assert "votes" not in public

    def test_result_hidden_until_reveal(self):
        state = mid_vote_state()
        state["last_result"] = {"secret_word": "pancake"}  # type: ignore[typeddict-item]
        public = public_phase_state(state, connected=set())
        assert public["last_result"] is None

    def test_result_visible_at_reveal(self):
        state = mid_vote_state()
        state["phase"] = "reveal"
        state["last_result"] = {"secret_word": "pancake", "winner": "civilians"}  # type: ignore[typeddict-item]
        public = public_phase_state(state, connected=set())
        assert public["last_result"]["winner"] == "civilians"


class TestPrivateView:
    def test_civilian_sees_word(self):
        you = private_view(mid_vote_state(), "p0")
        assert you["role"] == "civilian"
        assert you["word"] == "pancake"

    def test_imposter_sees_no_word(self):
        you = private_view(mid_vote_state(), "p2")
        assert you["role"] == "imposter"
        assert "word" not in you

    def test_error_only_to_its_player(self):
        assert "error" in private_view(mid_vote_state(), "p3")
        assert "error" not in private_view(mid_vote_state(), "p0")

    def test_no_role_in_lobby(self):
        state = mid_vote_state()
        state["phase"] = "lobby"
        you = private_view(state, "p0")
        assert "role" not in you and "word" not in you
