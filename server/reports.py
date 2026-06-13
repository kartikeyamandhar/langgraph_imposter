"""Cost and telemetry rollups. Reads the telemetry table — never called from
the game loop — to back a cost dashboard and difficulty calibration.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.telemetry import TelemetryEvent


@dataclass
class CostSummary:
    room: str | None
    tokens_in: int
    tokens_out: int
    cost_usd: float
    audit_retries: int
    fallback_clues: int
    ai_votes: int
    reconnect_attempts: int
    reconnect_successes: int

    @property
    def reconnect_rate(self) -> float | None:
        if self.reconnect_attempts == 0:
            return None
        return round(self.reconnect_successes / self.reconnect_attempts, 4)


async def cost_summary(session: AsyncSession, room: str | None = None) -> CostSummary:
    def scoped(stmt):
        return stmt.where(TelemetryEvent.room_code == room) if room else stmt

    totals = (
        await session.execute(
            scoped(
                select(
                    func.coalesce(func.sum(TelemetryEvent.tokens_in), 0),
                    func.coalesce(func.sum(TelemetryEvent.tokens_out), 0),
                    func.coalesce(func.sum(TelemetryEvent.cost_usd), 0.0),
                    func.coalesce(func.sum(TelemetryEvent.audit_retries), 0),
                    func.coalesce(func.sum(TelemetryEvent.fell_back), 0),
                )
            )
        )
    ).one()

    async def count(kind: str) -> int:
        return (
            await session.execute(
                scoped(
                    select(func.count()).select_from(TelemetryEvent).where(
                        TelemetryEvent.kind == kind
                    )
                )
            )
        ).scalar_one()

    reconnects = (
        await session.execute(
            scoped(select(TelemetryEvent.data).where(TelemetryEvent.kind == "reconnect"))
        )
    ).scalars().all()
    attempts = len(reconnects)
    successes = sum(1 for d in reconnects if d and d.get("success"))

    return CostSummary(
        room=room,
        tokens_in=int(totals[0]),
        tokens_out=int(totals[1]),
        cost_usd=round(float(totals[2]), 6),
        audit_retries=int(totals[3]),
        fallback_clues=int(totals[4]),
        ai_votes=await count("ai_vote"),
        reconnect_attempts=attempts,
        reconnect_successes=successes,
    )
