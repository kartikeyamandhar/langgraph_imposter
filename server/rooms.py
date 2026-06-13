"""Room lifecycle: codes, create, join, expiry. Operational metadata lives in
app tables; the game roster itself enters state through the graph."""

import secrets
import uuid
from datetime import timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from server.models import Player, Room, utcnow
from server.state import MAX_PLAYERS, PlayerInfo

# No I, L, O, 0, 1 — codes get read out loud across a table.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 4
ROOM_TTL = timedelta(hours=24)


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def new_player(name: str, seat: int, is_ai: bool = False) -> tuple[PlayerInfo, str]:
    """Returns (player info for game state, secret reconnect token)."""
    info: PlayerInfo = {"id": str(uuid.uuid4()), "name": name, "seat": seat, "is_ai": is_ai}
    return info, secrets.token_urlsafe(24)


async def insert_room(session: AsyncSession, code: str) -> None:
    session.add(Room(code=code))
    await session.commit()


async def insert_player(
    session: AsyncSession, code: str, info: PlayerInfo, token: str
) -> None:
    session.add(
        Player(
            id=info["id"],
            room_code=code,
            name=info["name"],
            seat=info["seat"],
            token=token,
            is_ai=info["is_ai"],
        )
    )
    await session.execute(
        update(Room).where(Room.code == code).values(last_active_at=utcnow())
    )
    await session.commit()


async def room_row(session: AsyncSession, code: str) -> Room | None:
    return await session.get(Room, code)


async def player_count(session: AsyncSession, code: str) -> int:
    rows = await session.execute(select(Player.id).where(Player.room_code == code))
    return len(rows.scalars().all())


async def name_taken(session: AsyncSession, code: str, name: str) -> bool:
    rows = await session.execute(
        select(Player.id).where(Player.room_code == code, Player.name == name)
    )
    return rows.scalar_one_or_none() is not None


async def player_by_token(session: AsyncSession, code: str, token: str) -> Player | None:
    rows = await session.execute(
        select(Player).where(Player.room_code == code, Player.token == token)
    )
    return rows.scalar_one_or_none()


async def touch_room(session: AsyncSession, code: str) -> None:
    await session.execute(
        update(Room).where(Room.code == code).values(last_active_at=utcnow())
    )
    await session.commit()


async def expire_stale_rooms(session: AsyncSession) -> list[str]:
    """Delete rooms idle past the TTL. Returns the expired codes so the caller
    can also drop their graph checkpoints."""
    cutoff = utcnow() - ROOM_TTL
    rows = await session.execute(select(Room.code).where(Room.last_active_at < cutoff))
    codes = list(rows.scalars().all())
    if codes:
        await session.execute(delete(Player).where(Player.room_code.in_(codes)))
        await session.execute(delete(Room).where(Room.code.in_(codes)))
        await session.commit()
    return codes


def can_join(count: int) -> bool:
    return count < MAX_PLAYERS
