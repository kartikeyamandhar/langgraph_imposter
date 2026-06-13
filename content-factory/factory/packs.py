"""Versioned word packs. Each row is one (category, word, difficulty) entry
tagged with a pack version; a "pack" is all rows sharing a version. A pack
ships only after the evals/ pack-quality suite passes in CI."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from server.models import Base, utcnow


class PackEntry(Base):
    __tablename__ = "pack_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[str] = mapped_column(String(48))
    secret_word: Mapped[str] = mapped_column(String(48))
    difficulty: Mapped[str] = mapped_column(String(8))
    category_distance: Mapped[float] = mapped_column(Float, default=0.0)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    plays: Mapped[int] = mapped_column(Integer, default=0)
    shipped: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


@dataclass
class Candidate:
    """A proposed word before it is persisted."""

    category: str
    secret_word: str
    difficulty: str
    category_distance: float = 0.0
    win_rate: float | None = None
    plays: int = 0
