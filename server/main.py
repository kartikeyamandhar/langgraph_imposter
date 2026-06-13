"""FastAPI entrypoint: REST for create/join, WebSocket for play.

Production wiring is Postgres for both app tables and the LangGraph
checkpointer. Without DATABASE_URL it falls back to SQLite + in-memory
checkpointer so local dev and the offline test suite need no services.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import BaseModel, Field

from server import db, rooms, telemetry
from server.engine import GameEngine
from server.ws import ConnectionManager

logger = logging.getLogger(__name__)

# Client-originated event types and the payload fields each may carry.
CLIENT_EVENTS: dict[str, tuple[str, ...]] = {
    "start": (),
    "settings": ("discussion_seconds", "win_mode", "second_imposter"),
    "add_ai": (),
    "remove_ai": ("target",),
    "clue": ("text",),
    "end_discussion": (),
    "vote": ("target",),
    "guess": ("text",),
    "continue": (),
}

AI_NAMES = ["Iris", "Otto", "Vera", "Cleo", "Hugo", "Nova", "Remy", "Zara", "Bex"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    url = db.database_url()
    app.state.db_engine = db.make_engine(url)
    app.state.sessions = db.make_sessionmaker(app.state.db_engine)

    checkpointer: BaseCheckpointSaver
    if db.is_postgres(url):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        raw = os.environ["DATABASE_URL"]
        saver_ctx = AsyncPostgresSaver.from_conn_string(raw)
        checkpointer = await saver_ctx.__aenter__()
        await checkpointer.setup()
        app.state._saver_ctx = saver_ctx
    else:
        # Dev/test fallback. Reconnect-across-restart needs Postgres.
        from langgraph.checkpoint.memory import MemorySaver

        from server.models import Base

        async with app.state.db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        checkpointer = MemorySaver()
        app.state._saver_ctx = None
        logger.warning("DATABASE_URL not set: SQLite + MemorySaver (dev mode)")

    app.state.manager = ConnectionManager()
    app.state.engine = GameEngine(checkpointer, sessions=app.state.sessions)
    app.state.engine.on_update = app.state.manager.broadcast
    app.state.checkpointer = checkpointer
    cleanup = asyncio.create_task(_cleanup_loop(app))
    try:
        yield
    finally:
        cleanup.cancel()
        await app.state.engine.close()
        if app.state._saver_ctx is not None:
            await app.state._saver_ctx.__aexit__(None, None, None)
        await app.state.db_engine.dispose()


async def _cleanup_loop(app: FastAPI) -> None:
    """Rooms expire after 24 hours of inactivity; checkpoints go with them."""
    while True:
        await asyncio.sleep(3600)
        try:
            async with app.state.sessions() as session:
                expired = await rooms.expire_stale_rooms(session)
            for code in expired:
                delete_thread = getattr(app.state.checkpointer, "adelete_thread", None)
                if delete_thread:
                    await delete_thread(code)
            if expired:
                logger.info("expired rooms: %s", ", ".join(expired))
        except Exception:
            logger.exception("room cleanup failed")


app = FastAPI(title="Blindspot", docs_url=None, redoc_url=None, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


class NameBody(BaseModel):
    name: str = Field(min_length=1, max_length=24)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/rooms", status_code=201)
async def create_room(body: NameBody):
    engine: GameEngine = app.state.engine
    async with app.state.sessions() as session:
        code = rooms.new_code()
        while await rooms.room_row(session, code) is not None:
            code = rooms.new_code()
        await rooms.insert_room(session, code)
        host, token = rooms.new_player(body.name.strip(), seat=0)
        await rooms.insert_player(session, code, host, token)
    await engine.create_room(code, host)
    return {"room": code, "player_id": host["id"], "token": token}


@app.post("/rooms/{code}/join", status_code=201)
async def join_room(code: str, body: NameBody):
    code = code.upper()
    engine: GameEngine = app.state.engine
    state = await engine.snapshot(code)
    if state is None:
        raise HTTPException(404, "Room not found. Check the code with the host.")
    if state.get("phase") != "lobby":
        raise HTTPException(409, "Game already started. Wait for the next match.")

    # Capacity counts the whole roster (humans + AI seats), which lives in
    # game state; the DB tracks only humans (for reconnect tokens).
    roster = state.get("players", [])
    if not rooms.can_join(len(roster)):
        raise HTTPException(409, "Room is full (10 players).")
    name = body.name.strip()
    async with app.state.sessions() as session:
        if await rooms.name_taken(session, code, name):
            raise HTTPException(409, "That name is taken in this room. Pick another.")
        info, token = rooms.new_player(name, seat=len(roster))
        await rooms.insert_player(session, code, info, token)

    await engine.dispatch(code, {"type": "join", "actor": info["id"], "player": info})
    return {"room": code, "player_id": info["id"], "token": token}


@app.websocket("/ws/{code}")
async def game_socket(ws: WebSocket, code: str, token: str = ""):
    code = code.upper()
    engine: GameEngine = app.state.engine
    manager: ConnectionManager = app.state.manager

    state = await engine.snapshot(code)
    async with app.state.sessions() as session:
        player = await rooms.player_by_token(session, code, token)
        if player is not None:
            await rooms.touch_room(session, code)
        await telemetry.record_reconnect(
            session, code, success=(player is not None and state is not None)
        )
    if player is None or state is None:
        await ws.close(code=4401)
        return

    await ws.accept()
    manager.connect(code, player.id, ws)
    try:
        # Reconnect path: rebuild from checkpoint, send immediately,
        # and show everyone the updated connection status.
        await manager.send_snapshot(code, state, player.id)
        await manager.broadcast(code, state)

        while True:
            frame = await ws.receive_json()
            if frame.get("type") != "action":
                await ws.send_json({"type": "error", "message": "Unknown frame type."})
                continue
            payload = frame.get("payload") or {}
            etype = payload.get("type")
            if etype not in CLIENT_EVENTS:
                await ws.send_json({"type": "error", "message": "Unknown action."})
                continue
            event = {k: payload[k] for k in CLIENT_EVENTS[etype] if k in payload}
            event["type"] = etype
            event["actor"] = player.id  # identity comes from the token, not the frame
            if etype == "add_ai":
                # The server mints the AI seat; the host only requests one.
                current = await engine.snapshot(code)
                roster = current.get("players", []) if current else []
                used = {p["name"] for p in roster}
                ai_name = next((n for n in AI_NAMES if n not in used), f"AI{len(roster)}")
                info, _ = rooms.new_player(ai_name, seat=len(roster), is_ai=True)
                event["player"] = info
            await engine.dispatch(code, event)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(code, player.id, ws)
        current = await engine.snapshot(code)
        if current is not None:
            await manager.broadcast(code, current)
