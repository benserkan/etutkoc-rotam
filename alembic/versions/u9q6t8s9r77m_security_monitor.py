"""security_monitor — aktif oturumlar + şüpheli IP'ler (Katman 11.A)

Revision ID: u9q6t8s9r77m
Revises: t8p5s7r8q66l
Create Date: 2026-05-15 14:00:00.000000

Süper admin güvenlik kamerası altyapısı:
  1) active_sessions — başarılı login = bir satır; uzaktan revoke desteği
  2) suspicious_ips — başarısız login üreten IP'lerin upsert sayacı,
     eşik aşılırsa otomatik blok (blocked_until set edilir)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u9q6t8s9r77m"
down_revision: Union[str, None] = "t8p5s7r8q66l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "active_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_token", sa.String(length=64), nullable=False, unique=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("login_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "terminated_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("termination_reason", sa.String(length=40), nullable=True),
    )
    op.create_index(
        "ix_active_sessions_session_token",
        "active_sessions",
        ["session_token"],
    )
    op.create_index(
        "ix_active_sessions_user_login",
        "active_sessions",
        ["user_id", "login_at"],
    )
    op.create_index(
        "ix_active_sessions_terminated",
        "active_sessions",
        ["terminated_at"],
    )

    op.create_table(
        "suspicious_ips",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip", sa.String(length=64), nullable=False, unique=True),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "distinct_email_count", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("distinct_emails_json", sa.Text(), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("block_reason", sa.String(length=40), nullable=True),
        sa.Column(
            "blocked_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("block_note", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_suspicious_ips_ip", "suspicious_ips", ["ip"])
    op.create_index(
        "ix_suspicious_ips_blocked_until", "suspicious_ips", ["blocked_until"]
    )


def downgrade() -> None:
    op.drop_index("ix_suspicious_ips_blocked_until", table_name="suspicious_ips")
    op.drop_index("ix_suspicious_ips_ip", table_name="suspicious_ips")
    op.drop_table("suspicious_ips")
    op.drop_index("ix_active_sessions_terminated", table_name="active_sessions")
    op.drop_index("ix_active_sessions_user_login", table_name="active_sessions")
    op.drop_index("ix_active_sessions_session_token", table_name="active_sessions")
    op.drop_table("active_sessions")
