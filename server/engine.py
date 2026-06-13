"""GameEngine: owns the compiled graph, per-room locks, and phase timers.

The graph is the single writer to game state. Everything else — REST join,
WebSocket actions, timers — funnels through dispatch(), which resumes the
graph with Command(resume=event) under the room's lock and then notifies
the broadcast callback.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command

from server.graph import build_game_graph
from server.state import DEFAULT_DISCUSSION_SECONDS, GameState, PlayerInfo

logger = logging.getLogger(__name__)

OnUpdate = Callable[[str, GameState], Awaitable[None]]


class GameEngine:
    def __init__(self, checkpointer: BaseCheckpointSaver):
        self.graph = build_game_graph(checkpointer)
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
        """Resume the room's graph with one event; broadcast and re-arm timers."""
        async with self._lock(room):
            await self.graph.ainvoke(Command(resume=event), self._config(room))
            state = await self.snapshot(room)
        assert state is not None
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

    # --- timers --------------------------------------------------------------

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
