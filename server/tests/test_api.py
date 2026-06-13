"""REST + WebSocket flow against the real app with SQLite + MemorySaver.
Covers create, join via code, playing over sockets, and reconnect."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/test.db")
    with TestClient(app) as c:
        yield c


def make_room(client) -> tuple[str, list[dict]]:
    host = client.post("/rooms", json={"name": "Host"}).json()
    code = host["room"]
    seats = [host]
    for name in ("Ana", "Ben", "Cam"):
        r = client.post(f"/rooms/{code}/join", json={"name": name})
        assert r.status_code == 201
        seats.append(r.json())
    return code, seats


def recv_until(ws, predicate, limit=50):
    for _ in range(limit):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError("expected message not received")


class TestRest:
    def test_create_room(self, client):
        r = client.post("/rooms", json={"name": "Host"})
        assert r.status_code == 201
        body = r.json()
        assert len(body["room"]) == 4 and body["token"]

    def test_join_unknown_room_404(self, client):
        r = client.post("/rooms/XXXX/join", json={"name": "Ana"})
        assert r.status_code == 404

    def test_duplicate_name_409(self, client):
        code, _ = make_room(client)
        r = client.post(f"/rooms/{code}/join", json={"name": "Ana"})
        assert r.status_code == 409

    def test_join_after_start_409(self, client):
        code, seats = make_room(client)
        with client.websocket_connect(f"/ws/{code}?token={seats[0]['token']}") as ws:
            ws.send_json({"type": "action", "payload": {"type": "start"}})
            recv_until(ws, lambda m: m["payload"]["public"]["phase"] == "clue")
        r = client.post(f"/rooms/{code}/join", json={"name": "Late"})
        assert r.status_code == 409


class TestSocket:
    def test_bad_token_rejected(self, client):
        code, _ = make_room(client)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/ws/{code}?token=nope") as ws:
                ws.receive_json()

    def test_snapshot_on_connect(self, client):
        code, seats = make_room(client)
        with client.websocket_connect(f"/ws/{code}?token={seats[1]['token']}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "phase_state"
            assert msg["payload"]["public"]["phase"] == "lobby"
            names = [p["name"] for p in msg["payload"]["public"]["players"]]
            assert names == ["Host", "Ana", "Ben", "Cam"]

    def test_start_broadcasts_roles_privately(self, client):
        code, seats = make_room(client)
        with client.websocket_connect(
            f"/ws/{code}?token={seats[0]['token']}"
        ) as host_ws, client.websocket_connect(f"/ws/{code}?token={seats[1]['token']}") as ana_ws:
            host_ws.send_json({"type": "action", "payload": {"type": "start"}})
            host_msg = recv_until(host_ws, lambda m: m["payload"]["public"]["phase"] == "clue")
            ana_msg = recv_until(ana_ws, lambda m: m["payload"]["public"]["phase"] == "clue")

            roles = {host_msg["payload"]["you"]["role"], ana_msg["payload"]["you"]["role"]}
            assert roles <= {"imposter", "civilian"}
            for msg in (host_msg, ana_msg):
                public_str = str(msg["payload"]["public"])
                if msg["payload"]["you"].get("word"):
                    assert msg["payload"]["you"]["word"] not in public_str

    def test_reconnect_gets_current_phase(self, client):
        code, seats = make_room(client)
        with client.websocket_connect(f"/ws/{code}?token={seats[0]['token']}") as ws:
            ws.send_json({"type": "action", "payload": {"type": "start"}})
            recv_until(ws, lambda m: m["payload"]["public"]["phase"] == "clue")
        # Socket dropped mid-game. Reconnect with the same token.
        with client.websocket_connect(f"/ws/{code}?token={seats[0]['token']}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "phase_state"
            assert msg["payload"]["public"]["phase"] == "clue"
            assert msg["payload"]["you"].get("role") in ("imposter", "civilian")
