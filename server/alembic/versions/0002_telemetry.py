"""telemetry events

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-12

"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telemetry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("room_code", sa.String(8), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("audit_retries", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fell_back", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rationale", sa.String(256), nullable=True),
        sa.Column("data", sa.JSON, nullable=True),
    )
    op.create_index("ix_telemetry_room_code", "telemetry", ["room_code"])
    op.create_index("ix_telemetry_kind", "telemetry", ["kind"])


def downgrade() -> None:
    op.drop_table("telemetry")
