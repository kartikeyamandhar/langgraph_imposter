"""WebSocket layer. Handlers only resume the graph — never mutate state.

Reconnect contract: connect with your token, get the current phase_state
rebuilt from the checkpoint immediately, keep playing.
"""

import logging
from typing import Any

from fastapi import WebSocket

from server.protocol import phase_state_message
from server.state import GameState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks live sockets per room and the per-room broadcast sequence."""

    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, WebSocket]] = {}
        self._seq: dict[str, int] = {}

    def connect(self, room: str, player_id: str, ws: WebSocket) -> None:
        self._rooms.setdefault(room, {})[player_id] = ws

    def disconnect(self, room: str, player_id: str, ws: WebSocket) -> None:
        sockets = self._rooms.get(room, {})
        if sockets.get(player_id) is ws:
            sockets.pop(player_id, None)

    def connected_ids(self, room: str) -> set[str]:
        return set(self._rooms.get(room, {}).keys())

    def next_seq(self, room: str) -> int:
        self._seq[room] = self._seq.get(room, 0) + 1
        return self._seq[room]

    async def send_snapshot(self, room: str, state: GameState, player_id: str) -> None:
        """Send the current phase_state to one player (connect/reconnect path)."""
        ws = self._rooms.get(room, {}).get(player_id)
        if ws is None:
            return
        msg = phase_state_message(state, player_id, self.connected_ids(room), self.next_seq(room))
        await self._safe_send(ws, msg, room, player_id)

    async def broadcast(self, room: str, state: GameState) -> None:
        """Full phase_state after every graph step; private fields per socket."""
        sockets = dict(self._rooms.get(room, {}))
        if not sockets:
            return
        seq = self.next_seq(room)
        connected = set(sockets.keys())
        for player_id, ws in sockets.items():
            msg = phase_state_message(state, player_id, connected, seq)
            await self._safe_send(ws, msg, room, player_id)

    async def _safe_send(
        self, ws: WebSocket, msg: dict[str, Any], room: str, player_id: str
    ) -> None:
        try:
            await ws.send_json(msg)
        except Exception:
            logger.info("drop dead socket room=%s player=%s", room, player_id)
            self.disconnect(room, player_id, ws)
