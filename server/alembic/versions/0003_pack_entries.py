"""pack entries

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-12

"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pack_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("category", sa.String(48), nullable=False),
        sa.Column("secret_word", sa.String(48), nullable=False),
        sa.Column("difficulty", sa.String(8), nullable=False),
        sa.Column("category_distance", sa.Float, nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float, nullable=True),
        sa.Column("plays", sa.Integer, nullable=False, server_default="0"),
        sa.Column("shipped", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pack_entries_version", "pack_entries", ["version"])


def downgrade() -> None:
    op.drop_table("pack_entries")
