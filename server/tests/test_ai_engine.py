"""AI seats driven through the real engine: clues auto-fill in turn order,
AI votes are cast, and a full round resolves with humans + AIs mixed."""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from server.ai.clue_agent import ClueProposal
from server.ai.runtime import AIRuntime
from server.embeddings import stub_embed
from server.engine import GameEngine
from server.state import PlayerInfo

ROOM = "AITEST"


def human(i: int) -> PlayerInfo:
    return {"id": f"h{i}", "name": f"Human{i}", "seat": i, "is_ai": False}


async def fixed_propose(system: str, user: str) -> ClueProposal:
    return ClueProposal(text="some hint", tokens_in=5, tokens_out=2)


@pytest.fixture
async def engine():
    # Offline runtime: deterministic propose + stub embeddings, no DB telemetry.
    ai = AIRuntime(embed=stub_embed, propose_factory=lambda model: fixed_propose)
    e = GameEngine(MemorySaver(), ai=ai)
    yield e
    await e.close()


async def lobby_with_ai(engine: GameEngine, humans: int = 2, ais: int = 2):
    await engine.create_room(ROOM, human(0))
    for i in range(1, humans):
        await engine.dispatch(ROOM, {"type": "join", "actor": f"h{i}", "player": human(i)})
    for k in range(ais):
        ai_player: PlayerInfo = {
            "id": f"ai{k}",
            "name": f"AI{k}",
            "seat": humans + k,
            "is_ai": True,
        }
        await engine.dispatch(ROOM, {"type": "add_ai", "actor": "h0", "player": ai_player})
    return await engine.snapshot(ROOM)


async def resolve_round(engine: GameEngine, state, human_ids):
    """Drive a started round to a terminal phase: submit pending human clues,
    end discussion, then vote pending humans through any re-vote until the vote
    resolves, and answer an AI guess. Robust against AI-vote ties."""
    while state["phase"] == "clue":
        active = state["speaking_order"][state["clue_index"]]
        if active in human_ids:
            state = await engine.dispatch(ROOM, {"type": "clue", "actor": active, "text": "a hint"})
    if state["phase"] == "discussion":
        state = await engine.dispatch(ROOM, {"type": "end_discussion", "actor": human_ids[0]})

    while state["phase"] == "vote":
        if state["revote"]:
            target = state["revote_candidates"][0]
        else:
            target = next(p["id"] for p in state["players"])
        pending = [h for h in human_ids if h not in state["votes"]]
        if not pending:
            break
        voter = pending[0]
        choice = target if target != voter else state["players"][-1]["id"]
        state = await engine.dispatch(ROOM, {"type": "vote", "actor": voter, "target": choice})

    if state["phase"] == "imposter_guess":
        state = await engine.dispatch(
            ROOM, {"type": "guess", "actor": state["eliminated"], "text": "x"}
        )
    return state


class TestAISeats:
    async def test_host_adds_ai_seats(self, engine):
        state = await lobby_with_ai(engine)
        ais = [p for p in state["players"] if p["is_ai"]]
        assert len(ais) == 2

    async def test_non_host_cannot_add_ai(self, engine):
        await engine.create_room(ROOM, human(0))
        await engine.dispatch(ROOM, {"type": "join", "actor": "h1", "player": human(1)})
        before = await engine.snapshot(ROOM)
        ai_player: PlayerInfo = {"id": "x", "name": "X", "seat": 2, "is_ai": True}
        state = await engine.dispatch(ROOM, {"type": "add_ai", "actor": "h1", "player": ai_player})
        assert len(state["players"]) == len(before["players"])

    async def test_ai_clues_autofill_in_order(self, engine):
        await lobby_with_ai(engine, humans=2, ais=2)
        state = await engine.dispatch(ROOM, {"type": "start", "actor": "h0"})
        # The graph should auto-advance through AI turns and stop at a human,
        # or reach discussion if humans happen to be last.
        ai_ids = {"ai0", "ai1"}
        clued = {c["player_id"] for c in state["clues"]}
        # Every AI that came before the first pending human has already clued.
        order = state["speaking_order"]
        if state["phase"] == "clue":
            active = order[state["clue_index"]]
            assert active not in ai_ids  # never waits on an AI
            for pid in order[: state["clue_index"]]:
                assert pid in clued
        else:
            assert state["phase"] == "discussion"
            assert ai_ids <= clued

    async def test_full_round_with_ai_votes(self, engine):
        await lobby_with_ai(engine, humans=2, ais=2)
        state = await engine.dispatch(ROOM, {"type": "start", "actor": "h0"})

        # Submit pending human clues until discussion (AIs auto-fill theirs).
        while state["phase"] == "clue":
            active = state["speaking_order"][state["clue_index"]]
            state = await engine.dispatch(
                ROOM, {"type": "clue", "actor": active, "text": "guess hint"}
            )
        assert state["phase"] == "discussion"
        assert len(state["clues"]) == 4

        state = await engine.dispatch(ROOM, {"type": "end_discussion", "actor": "h0"})
        assert state["phase"] == "vote"
        # AIs vote automatically; only humans remain pending.
        assert {"ai0", "ai1"} <= set(state["votes"].keys())

        state = await resolve_round(engine, state, ["h0", "h1"])
        assert state["phase"] in ("reveal", "match_end")

    async def test_precompute_registry_clears_on_reveal(self, engine):
        await lobby_with_ai(engine, humans=2, ais=2)
        state = await engine.dispatch(ROOM, {"type": "start", "actor": "h0"})
        round_no = state["round_no"]
        assert (ROOM, round_no) in engine.ai._precomputed
        state = await resolve_round(engine, state, ["h0", "h1"])
        assert state["phase"] in ("reveal", "match_end")
        assert (ROOM, round_no) not in engine.ai._precomputed
