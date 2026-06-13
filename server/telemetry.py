"""Telemetry: one table the server writes and the game loop never reads.

Captures per room: tokens in/out, model, computed cost, audit retries,
fallback-clue counts, AI vote rationales, reconnect attempts/successes,
rounds played, and the one-tap post-round fun rating. Used for cost tracking
and difficulty calibration, never to drive gameplay.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from server.cost import compute_cost
from server.models import Base, utcnow


class TelemetryEvent(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_code: Mapped[str] = mapped_column(String(8), index=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    audit_retries: Mapped[int] = mapped_column(Integer, default=0)
    fell_back: Mapped[bool] = mapped_column(Integer, default=0)
    rationale: Mapped[str | None] = mapped_column(String(256), nullable=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


async def record_ai_clue(
    session: AsyncSession,
    room: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    audit_retries: int,
    fell_back: bool,
    round_no: int,
) -> None:
    session.add(
        TelemetryEvent(
            room_code=room,
            kind="ai_clue",
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=compute_cost(model, tokens_in, tokens_out),
            audit_retries=audit_retries,
            fell_back=fell_back,
            data={"round": round_no},
        )
    )
    await session.commit()


async def record_ai_vote(
    session: AsyncSession, room: str, voter_id: str, rationale: str, round_no: int
) -> None:
    session.add(
        TelemetryEvent(
            room_code=room,
            kind="ai_vote",
            rationale=rationale[:256],
            data={"voter": voter_id, "round": round_no},
        )
    )
    await session.commit()


async def record_reconnect(session: AsyncSession, room: str, success: bool) -> None:
    session.add(
        TelemetryEvent(
            room_code=room, kind="reconnect", data={"success": success}
        )
    )
    await session.commit()


async def record_fun_rating(
    session: AsyncSession, room: str, player_id: str, rating: int, round_no: int
) -> None:
    session.add(
        TelemetryEvent(
            room_code=room,
            kind="fun_rating",
            data={"player": player_id, "rating": rating, "round": round_no},
        )
    )
    await session.commit()
