"""error_events + slow_request_logs — sistem hata izleme (Katman 11.E)

Revision ID: x2t9w1v2u00p
Revises: w1s8v0u1t99o
Create Date: 2026-05-15 17:00:00.000000

Sentry-tarzı: aynı signature'a sahip hatalar tek satırda gruplanır (count += 1).
Slow request append-only — sebep analizi için.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x2t9w1v2u00p"
down_revision: Union[str, None] = "w1s8v0u1t99o"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "error_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("signature", sa.String(length=40), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("exception_type", sa.String(length=100), nullable=True),
        sa.Column("exception_message", sa.String(length=500), nullable=True),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "last_actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_ip", sa.String(length=64), nullable=True),
        sa.Column("last_user_agent", sa.String(length=255), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "resolved_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolution_note", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_error_signature", "error_events", ["signature"], unique=True)
    op.create_index(
        "ix_error_resolved_last", "error_events", ["resolved_at", "last_seen_at"]
    )
    op.create_index("ix_error_endpoint", "error_events", ["endpoint"])

    op.create_table(
        "slow_request_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_slow_request_recorded", "slow_request_logs", ["recorded_at"]
    )
    op.create_index(
        "ix_slow_request_endpoint", "slow_request_logs", ["endpoint"]
    )


def downgrade() -> None:
    op.drop_index("ix_slow_request_endpoint", table_name="slow_request_logs")
    op.drop_index("ix_slow_request_recorded", table_name="slow_request_logs")
    op.drop_table("slow_request_logs")
    op.drop_index("ix_error_endpoint", table_name="error_events")
    op.drop_index("ix_error_resolved_last", table_name="error_events")
    op.drop_index("ix_error_signature", table_name="error_events")
    op.drop_table("error_events")
