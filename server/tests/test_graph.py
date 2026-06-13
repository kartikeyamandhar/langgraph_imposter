"""Full-graph round trips with an in-memory checkpointer. No LLM, no network."""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from server.engine import GameEngine
from server.state import GameState, PlayerInfo, RoundResult

ROOM = "TEST"


def result(state: GameState) -> RoundResult:
    r = state["last_result"]
    assert r is not None
    return r


def player(i: int) -> PlayerInfo:
    return {"id": f"p{i}", "name": f"Player{i}", "seat": i, "is_ai": False}


@pytest.fixture
async def engine():
    e = GameEngine(MemorySaver())
    yield e
    await e.close()


async def start_match(engine: GameEngine, n: int = 4) -> GameState:
    await engine.create_room(ROOM, player(0))
    for i in range(1, n):
        await engine.dispatch(ROOM, {"type": "join", "actor": f"p{i}", "player": player(i)})
    return await engine.dispatch(ROOM, {"type": "start", "actor": "p0"})


async def submit_all_clues(engine: GameEngine, state: GameState) -> GameState:
    for i, pid in enumerate(state["speaking_order"]):
        state = await engine.dispatch(
            ROOM, {"type": "clue", "actor": pid, "text": f"hint number{i}"}
        )
    return state


async def play_to_vote(engine: GameEngine, n: int = 4) -> GameState:
    state = await start_match(engine, n)
    state = await submit_all_clues(engine, state)
    assert state["phase"] == "discussion"
    return await engine.dispatch(ROOM, {"type": "end_discussion", "actor": "p0"})


class TestLobby:
    async def test_create_and_join(self, engine):
        await engine.create_room(ROOM, player(0))
        state = await engine.dispatch(
            ROOM, {"type": "join", "actor": "p1", "player": player(1)}
        )
        assert state["phase"] == "lobby"
        assert [p["id"] for p in state["players"]] == ["p0", "p1"]

    async def test_start_needs_four(self, engine):
        await engine.create_room(ROOM, player(0))
        state = await engine.dispatch(ROOM, {"type": "start", "actor": "p0"})
        assert state["phase"] == "lobby"
        assert "Need 4 players" in state["action_error"]["error"]

    async def test_only_host_starts(self, engine):
        await engine.create_room(ROOM, player(0))
        for i in range(1, 4):
            await engine.dispatch(ROOM, {"type": "join", "actor": f"p{i}", "player": player(i)})
        state = await engine.dispatch(ROOM, {"type": "start", "actor": "p1"})
        assert state["phase"] == "lobby"

    async def test_settings_clamped(self, engine):
        await engine.create_room(ROOM, player(0))
        state = await engine.dispatch(
            ROOM, {"type": "settings", "actor": "p0", "discussion_seconds": 999}
        )
        assert state["settings"]["discussion_seconds"] == 180

    async def test_duplicate_join_ignored(self, engine):
        await engine.create_room(ROOM, player(0))
        state = await engine.dispatch(
            ROOM, {"type": "join", "actor": "p0", "player": player(0)}
        )
        assert len(state["players"]) == 1


class TestClueRound:
    async def test_roles_dealt(self, engine):
        state = await start_match(engine)
        assert state["phase"] == "clue"
        assert state["round_no"] == 1
        assert len(state["imposter_ids"]) == 1
        assert state["secret_word"]
        assert sorted(state["speaking_order"]) == ["p0", "p1", "p2", "p3"]

    async def test_clue_leak_rejected_and_retry(self, engine):
        state = await start_match(engine)
        active = state["speaking_order"][0]
        secret = state["secret_word"]
        state = await engine.dispatch(ROOM, {"type": "clue", "actor": active, "text": secret})
        assert state["clue_index"] == 0
        assert state["action_error"]["player_id"] == active
        state = await engine.dispatch(ROOM, {"type": "clue", "actor": active, "text": "safe"})
        assert state["clue_index"] == 1
        assert state["clues"][0] == {"player_id": active, "clue": "safe"}

    async def test_out_of_turn_rejected(self, engine):
        state = await start_match(engine)
        wrong = state["speaking_order"][1]
        state = await engine.dispatch(ROOM, {"type": "clue", "actor": wrong, "text": "early"})
        assert state["clue_index"] == 0
        assert "Not your turn" in state["action_error"]["error"]

    async def test_all_clues_move_to_discussion(self, engine):
        state = await start_match(engine)
        state = await submit_all_clues(engine, state)
        assert state["phase"] == "discussion"
        assert state["discussion_deadline"] is not None
        assert len(state["clues"]) == 4


class TestVoteAndResolve:
    async def test_imposter_caught_wrong_guess_civilians_win(self, engine):
        state = await play_to_vote(engine)
        imposter = state["imposter_ids"][0]
        for pid in ["p0", "p1", "p2", "p3"]:
            state = await engine.dispatch(ROOM, {"type": "vote", "actor": pid, "target": imposter})
        assert state["phase"] == "imposter_guess"
        state = await engine.dispatch(
            ROOM, {"type": "guess", "actor": imposter, "text": "definitelywrong"}
        )
        assert state["phase"] == "reveal"
        assert result(state)["winner"] == "civilians"
        assert result(state)["imposter_caught"] is True
        for pid in ["p0", "p1", "p2", "p3"]:
            if pid == imposter:
                assert pid not in state["scores"]
            else:
                assert state["scores"][pid] == 2  # +1 civilian win, +1 voted imposter

    async def test_imposter_caught_correct_guess_steals_round(self, engine):
        state = await play_to_vote(engine)
        imposter = state["imposter_ids"][0]
        secret = state["secret_word"]
        for pid in ["p0", "p1", "p2", "p3"]:
            state = await engine.dispatch(ROOM, {"type": "vote", "actor": pid, "target": imposter})
        state = await engine.dispatch(ROOM, {"type": "guess", "actor": imposter, "text": secret})
        assert result(state)["winner"] == "imposter"
        assert state["scores"][imposter] == 3

    async def test_civilian_eliminated_imposter_wins(self, engine):
        state = await play_to_vote(engine)
        imposter = state["imposter_ids"][0]
        civilian = next(p for p in ["p0", "p1", "p2", "p3"] if p != imposter)
        for pid in ["p0", "p1", "p2", "p3"]:
            state = await engine.dispatch(ROOM, {"type": "vote", "actor": pid, "target": civilian})
        assert state["phase"] == "reveal"
        assert result(state)["winner"] == "imposter"
        assert state["scores"][imposter] == 3

    async def test_tie_triggers_single_revote_then_no_elimination(self, engine):
        state = await play_to_vote(engine)
        # Engineer a 2-2 tie: p0/p1 vote p2, p2/p3 vote p0.
        await engine.dispatch(ROOM, {"type": "vote", "actor": "p0", "target": "p2"})
        await engine.dispatch(ROOM, {"type": "vote", "actor": "p1", "target": "p2"})
        await engine.dispatch(ROOM, {"type": "vote", "actor": "p2", "target": "p0"})
        state = await engine.dispatch(ROOM, {"type": "vote", "actor": "p3", "target": "p0"})
        assert state["phase"] == "vote"
        assert state["revote"] is True
        assert sorted(state["revote_candidates"]) == ["p0", "p2"]
        assert state["votes"] == {}

        # Re-vote restricted to tied players: a vote outside is rejected.
        state = await engine.dispatch(ROOM, {"type": "vote", "actor": "p0", "target": "p3"})
        assert "restricted" in state["action_error"]["error"]

        # Second tie: no elimination, imposter takes the round.
        await engine.dispatch(ROOM, {"type": "vote", "actor": "p0", "target": "p2"})
        await engine.dispatch(ROOM, {"type": "vote", "actor": "p1", "target": "p2"})
        await engine.dispatch(ROOM, {"type": "vote", "actor": "p2", "target": "p0"})
        state = await engine.dispatch(ROOM, {"type": "vote", "actor": "p3", "target": "p0"})
        assert state["phase"] == "reveal"
        assert result(state)["eliminated"] is None
        assert result(state)["winner"] == "imposter"

    async def test_double_vote_rejected(self, engine):
        state = await play_to_vote(engine)
        await engine.dispatch(ROOM, {"type": "vote", "actor": "p0", "target": "p1"})
        state = await engine.dispatch(ROOM, {"type": "vote", "actor": "p0", "target": "p2"})
        assert state["votes"]["p0"] == "p1"
        assert "already locked" in state["action_error"]["error"].lower()


class TestMatchFlow:
    async def test_next_round_after_reveal(self, engine):
        state = await play_to_vote(engine)
        imposter = state["imposter_ids"][0]
        civilian = next(p for p in ["p0", "p1", "p2", "p3"] if p != imposter)
        for pid in ["p0", "p1", "p2", "p3"]:
            state = await engine.dispatch(ROOM, {"type": "vote", "actor": pid, "target": civilian})
        first_word = state["secret_word"]
        state = await engine.dispatch(ROOM, {"type": "continue", "actor": "p0"})
        assert state["phase"] == "clue"
        assert state["round_no"] == 2
        assert state["secret_word"] != first_word  # no repeats within a match

    async def test_snapshot_survives_for_reconnect(self, engine):
        state = await play_to_vote(engine)
        snap = await engine.snapshot(ROOM)
        assert snap["phase"] == "vote"
        assert snap["round_no"] == state["round_no"]
