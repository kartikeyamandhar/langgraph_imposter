"""rooms and players

Revision ID: 0001
Revises:
Create Date: 2026-06-12

"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("code", sa.String(8), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "players",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "room_code",
            sa.String(8),
            sa.ForeignKey("rooms.code", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(24), nullable=False),
        sa.Column("seat", sa.Integer, nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("is_ai", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_players_room_code", "players", ["room_code"])
    op.create_index("ix_players_token", "players", ["token"], unique=True)


def downgrade() -> None:
    op.drop_table("players")
    op.drop_table("rooms")
