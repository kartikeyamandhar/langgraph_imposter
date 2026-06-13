"""GameEngine: owns the compiled graph, per-room locks, phase timers, and the
AI runtime. The graph is the single writer to game state; everything else —
REST join, WebSocket actions, timers, AI seats — funnels through a graph
resume and then notifies the broadcast callback.

After every human-driven step the engine "drives" any AI seats whose turn it
is (clue, vote, caught-guess), each as its own graph step + broadcast, until
control returns to a human or a wait state.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from server import telemetry
from server.ai.runtime import AIRuntime
from server.graph import build_game_graph
from server.state import DEFAULT_DISCUSSION_SECONDS, GameState, PlayerInfo

logger = logging.getLogger(__name__)

OnUpdate = Callable[[str, GameState], Awaitable[None]]
_MAX_AI_STEPS = 200  # safety bound against any driving loop that won't settle


class GameEngine:
    def __init__(
        self,
        checkpointer: BaseCheckpointSaver,
        ai: AIRuntime | None = None,
        sessions: async_sessionmaker[AsyncSession] | None = None,
    ):
        self.graph = build_game_graph(checkpointer)
        self.ai = ai or AIRuntime()
        self.sessions = sessions  # for telemetry writes; None disables persistence
        self._locks: dict[str, asyncio.Lock] = {}
        self._timers: dict[str, asyncio.Task[None]] = {}
        self.on_update: OnUpdate | None = None

    def _lock(self, room: str) -> asyncio.Lock:
        return self._locks.setdefault(room, asyncio.Lock())

    def _config(self, room: str) -> dict[str, Any]:
        # thread_id equals the room code; LangSmith traces carry the room tag.
        return {"configurable": {"thread_id": room}, "tags": [f"room:{room}"]}

    async def create_room(self, room: str, host: PlayerInfo) -> GameState:
        initial: GameState = {
            "room": room,
            "host_id": host["id"],
            "phase": "lobby",
            "players": [host],
            "settings": {
                "discussion_seconds": DEFAULT_DISCUSSION_SECONDS,
                "win_mode": "points",
                "second_imposter": False,
            },
            "round_no": 0,
            "used_words": [],
            "scores": {},
            "results": [],
            "ai_private": {},
        }
        async with self._lock(room):
            await self.graph.ainvoke(initial, self._config(room))
        return await self.snapshot(room)  # type: ignore[return-value]

    async def dispatch(self, room: str, event: dict[str, Any]) -> GameState:
        """Resume the graph with one human/timer event, then drive AI seats."""
        state = await self._step(room, event)
        return await self._drive_ai(room, state)

    async def _step(self, room: str, event: dict[str, Any]) -> GameState:
        async with self._lock(room):
            await self.graph.ainvoke(Command(resume=event), self._config(room))
            state = await self.snapshot(room)
        assert state is not None
        self._on_phase(room, state)
        self._arm_timer(room, state)
        if self.on_update:
            await self.on_update(room, state)
        return state

    async def snapshot(self, room: str) -> GameState | None:
        """Current state from the checkpoint. Reconnect = snapshot + rebroadcast."""
        snap = await self.graph.aget_state(self._config(room))
        if not snap or not snap.values:
            return None
        return snap.values

    async def room_exists(self, room: str) -> bool:
        return await self.snapshot(room) is not None

    # --- AI seats -----------------------------------------------------------

    def _on_phase(self, room: str, state: GameState) -> None:
        phase = state.get("phase")
        if phase == "clue" and state.get("clue_index") == 0:
            # Round just started: fan out AI clue generation to hide latency.
            self.ai.start_precompute(room, state)
        elif phase in ("reveal", "match_end"):
            self.ai.clear_round(room, state.get("round_no", 0))

    async def _drive_ai(self, room: str, state: GameState) -> GameState:
        for _ in range(_MAX_AI_STEPS):
            action = await self._next_ai_action(room, state)
            if action is None:
                return state
            state = await self._step(room, action)
        logger.warning("AI driving hit the step bound in room %s", room)
        return state

    async def _next_ai_action(self, room: str, state: GameState) -> dict[str, Any] | None:
        phase = state.get("phase")
        ai_ids = {p["id"] for p in state.get("players", []) if p["is_ai"]}
        if not ai_ids:
            return None

        if phase == "clue":
            order = state["speaking_order"]
            idx = state["clue_index"]
            if idx < len(order) and order[idx] in ai_ids:
                active = order[idx]
                result = await self.ai.take_clue(room, state, active)
                await self._record_clue(room, result, state["round_no"])
                return {"type": "clue", "actor": active, "text": result.text}

        elif phase == "vote":
            voted = set(state.get("votes", {}))
            for p in state["players"]:
                if p["is_ai"] and p["id"] not in voted:
                    # Off the event loop: suspicion embeds every clue (OpenAI).
                    decision = await asyncio.to_thread(self.ai.vote_for, state, p["id"])
                    await self._record_vote(room, p["id"], decision.rationale, state["round_no"])
                    return {"type": "vote", "actor": p["id"], "target": decision.target}

        elif phase == "imposter_guess":
            elim = state.get("eliminated")
            if elim in ai_ids:
                word, _, _ = await self.ai.guess_for(state)
                return {"type": "guess", "actor": elim, "text": word}

        return None

    # --- telemetry ----------------------------------------------------------

    async def _record_clue(self, room: str, result: Any, round_no: int) -> None:
        if self.sessions is None:
            return
        try:
            async with self.sessions() as session:
                await telemetry.record_ai_clue(
                    session,
                    room=room,
                    model=self.ai.model,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    audit_retries=result.retries,
                    fell_back=result.fell_back,
                    round_no=round_no,
                )
        except Exception:
            logger.exception("telemetry record_ai_clue failed")

    async def _record_vote(self, room: str, voter: str, rationale: str, round_no: int) -> None:
        if self.sessions is None:
            return
        try:
            async with self.sessions() as session:
                await telemetry.record_ai_vote(session, room, voter, rationale, round_no)
        except Exception:
            logger.exception("telemetry record_ai_vote failed")

    # --- timers -------------------------------------------------------------

    def _arm_timer(self, room: str, state: GameState) -> None:
        deadline: float | None = None
        phase = state.get("phase")
        if phase == "discussion":
            deadline = state.get("discussion_deadline")
        elif phase == "imposter_guess":
            deadline = state.get("guess_deadline")

        old = self._timers.pop(room, None)
        if old and not old.done():
            old.cancel()
        if deadline is None or phase is None:
            return
        self._timers[room] = asyncio.create_task(self._fire_timer(room, phase, deadline))

    async def _fire_timer(self, room: str, phase: str, deadline: float) -> None:
        try:
            await asyncio.sleep(max(0.0, deadline - time.time()))
            # The node ignores stale timers: phase and deadline must still match.
            await self.dispatch(
                room, {"type": "timer", "actor": "server", "phase": phase, "deadline": deadline}
            )
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("timer dispatch failed for room %s", room)

    async def close(self) -> None:
        for t in self._timers.values():
            t.cancel()
        self._timers.clear()
        self.ai.cancel_all()
