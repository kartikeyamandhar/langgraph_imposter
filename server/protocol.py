"""WebSocket protocol: typed JSON envelope {type, room, seq, payload}.

Mirrored by hand in web/lib/protocol.ts — change both in the same commit
and say so in the commit message.

Server → client:
  phase_state   full public snapshot + the receiving player's private view
  error         malformed frame or rejected connection

Client → server:
  action        one game event; the server attaches the actor from the
                authenticated socket and never trusts a client-sent actor.

The phase_state builder is the privacy boundary: roles, the secret word, and
individual votes never enter the public payload. A player's role and word
travel only in the `you` section of their own socket's message.
"""

from typing import Any

from pydantic import BaseModel

from server.state import GameState


class Envelope(BaseModel):
    type: str
    room: str
    seq: int
    payload: dict[str, Any]


def public_phase_state(state: GameState, connected: set[str]) -> dict[str, Any]:
    phase = state.get("phase", "lobby")
    players = [
        {
            "id": p["id"],
            "name": p["name"],
            "seat": p["seat"],
            "is_ai": p["is_ai"],
            "connected": p["id"] in connected or p["is_ai"],
        }
        for p in state.get("players", [])
    ]
    order = state.get("speaking_order", [])
    idx = state.get("clue_index", 0)
    public: dict[str, Any] = {
        "room": state.get("room"),
        "phase": phase,
        "round_no": state.get("round_no", 0),
        "players": players,
        "host_id": state.get("host_id"),
        "settings": state.get("settings"),
        "scores": state.get("scores", {}),
        "category": state.get("category") if phase not in ("lobby", "match_end") else None,
        "clues": state.get("clues", []),
        "speaking_order": order if phase != "lobby" else [],
        "active_player": order[idx] if phase == "clue" and idx < len(order) else None,
        "discussion_deadline": state.get("discussion_deadline"),
        "guess_deadline": state.get("guess_deadline") if phase == "imposter_guess" else None,
        "locked_voters": sorted(state.get("votes", {}).keys()) if phase == "vote" else [],
        "revote": state.get("revote", False),
        "revote_candidates": state.get("revote_candidates", []) if phase == "vote" else [],
        "eliminated": state.get("eliminated") if phase in ("imposter_guess",) else None,
        "last_result": state.get("last_result") if phase in ("reveal", "match_end") else None,
        "match_winners": state.get("match_winners", []) if phase == "match_end" else [],
    }
    return public


def private_view(state: GameState, player_id: str) -> dict[str, Any]:
    phase = state.get("phase", "lobby")
    you: dict[str, Any] = {"id": player_id}

    if phase not in ("lobby", "match_end") and state.get("imposter_ids"):
        if player_id in state["imposter_ids"]:
            you["role"] = "imposter"
            # The imposter sees only the category, never the word.
        else:
            you["role"] = "civilian"
            you["word"] = state.get("secret_word")

    err = state.get("action_error")
    if err and err.get("player_id") == player_id:
        you["error"] = err["error"]

    if phase == "vote":
        you["voted"] = player_id in state.get("votes", {})
    return you


def phase_state_message(
    state: GameState, player_id: str, connected: set[str], seq: int
) -> dict[str, Any]:
    return Envelope(
        type="phase_state",
        room=state.get("room", ""),
        seq=seq,
        payload={
            "public": public_phase_state(state, connected),
            "you": private_view(state, player_id),
        },
    ).model_dump()
