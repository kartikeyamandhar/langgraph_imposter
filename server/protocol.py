"""WebSocket protocol: typed JSON envelope {type, room, seq, payload}.

Mirrored by hand in web/lib/protocol.ts — change both in the same commit
and say so in the commit message. Message types fill in at M1.
"""

from typing import Any

from pydantic import BaseModel


class Envelope(BaseModel):
    type: str
    room: str
    seq: int
    payload: dict[str, Any]
