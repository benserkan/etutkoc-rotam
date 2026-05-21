"""impersonation_sessions — yapısal kimliğe-bürünme kaydı (Katman 11.B)

Revision ID: v0r7u9t0s88n
Revises: u9q6t8s9r77m
Create Date: 2026-05-15 15:00:00.000000

Mevcut akış AuditLog'a IMPERSONATE_START/END yazıyordu — bu yeterli geçmiş ama
panoda "şu an kim taklit ediyor" bakmak ve zorunlu gerekçe + 30 dk expire
uygulamak için ayrı bir oturum tablosu gerekli.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v0r7u9t0s88n"
down_revision: Union[str, None] = "u9q6t8s9r77m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "impersonation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(length=40), nullable=True),
        sa.Column(
            "ended_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ip", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_impersonation_active",
        "impersonation_sessions",
        ["ended_at"],
    )
    op.create_index(
        "ix_impersonation_actor_started",
        "impersonation_sessions",
        ["actor_user_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_impersonation_actor_started", table_name="impersonation_sessions"
    )
    op.drop_index("ix_impersonation_active", table_name="impersonation_sessions")
    op.drop_table("impersonation_sessions")
