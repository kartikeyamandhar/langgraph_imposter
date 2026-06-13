"""Telemetry writers + cost rollup. Uses an in-memory SQLite session."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from server import telemetry
from server.models import Base
from server.reports import cost_summary


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


class TestCostSummary:
    async def test_aggregates_tokens_and_cost(self, session):
        await telemetry.record_ai_clue(
            session, "ROOM", "claude-haiku-4-5-20251001", 1000, 200, 1, False, 1
        )
        await telemetry.record_ai_clue(
            session, "ROOM", "claude-haiku-4-5-20251001", 500, 100, 0, True, 1
        )
        summary = await cost_summary(session, "ROOM")
        assert summary.tokens_in == 1500
        assert summary.tokens_out == 300
        assert summary.audit_retries == 1
        assert summary.fallback_clues == 1
        assert summary.cost_usd > 0

    async def test_vote_and_reconnect_counts(self, session):
        await telemetry.record_ai_vote(session, "ROOM", "ai0", "voted ai1: outlier", 1)
        await telemetry.record_reconnect(session, "ROOM", success=True)
        await telemetry.record_reconnect(session, "ROOM", success=True)
        await telemetry.record_reconnect(session, "ROOM", success=False)
        summary = await cost_summary(session, "ROOM")
        assert summary.ai_votes == 1
        assert summary.reconnect_attempts == 3
        assert summary.reconnect_successes == 2
        assert summary.reconnect_rate == pytest.approx(2 / 3, abs=1e-3)

    async def test_room_scoping(self, session):
        await telemetry.record_ai_clue(session, "AAAA", "m", 100, 0, 0, False, 1)
        await telemetry.record_ai_clue(session, "BBBB", "m", 999, 0, 0, False, 1)
        only_a = await cost_summary(session, "AAAA")
        assert only_a.tokens_in == 100
        everything = await cost_summary(session, None)
        assert everything.tokens_in == 1099
