"""Persist factory output as a versioned pack and read shipped words back.

A pack is written unshipped; CI flips `shipped` only after the pack-quality
suite passes. The live game draws only from shipped entries.
"""

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from factory.packs import Candidate, PackEntry


async def next_version(session: AsyncSession) -> int:
    result = await session.execute(select(func.max(PackEntry.version)))
    current = result.scalar_one_or_none()
    return (current or 0) + 1


async def write_pack(
    session: AsyncSession, candidates: list[Candidate], version: int | None = None
) -> int:
    """Persist candidates as one pack version (unshipped). Returns the version."""
    version = version or await next_version(session)
    for c in candidates:
        session.add(
            PackEntry(
                version=version,
                category=c.category,
                secret_word=c.secret_word,
                difficulty=c.difficulty,
                category_distance=c.category_distance,
                win_rate=c.win_rate,
                plays=c.plays,
                shipped=False,
            )
        )
    await session.commit()
    return version


async def ship_pack(session: AsyncSession, version: int) -> None:
    await session.execute(
        update(PackEntry).where(PackEntry.version == version).values(shipped=True)
    )
    await session.commit()


async def shipped_words(session: AsyncSession) -> list[tuple[str, str, str]]:
    rows = await session.execute(
        select(PackEntry.category, PackEntry.secret_word, PackEntry.difficulty).where(
            PackEntry.shipped.is_(True)
        )
    )
    return [(c, w, d) for c, w, d in rows.all()]
