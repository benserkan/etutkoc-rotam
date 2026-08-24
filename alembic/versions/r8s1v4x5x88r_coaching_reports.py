"""Haftalık koç raporu — coaching_reports + coaching_sessions.report_id/agenda_items

Revision ID: r8s1v4x5x88r
Revises: q7r0u3w4w77q
Create Date: 2026-08-19 00:00:00.000000

"Haftalık rapor oluştur" butonu: programın işlendiği son güne kadar 7 günlük
pencerenin tüm analizleri (data_json) + kural motoru gündemi (agenda_json) +
KS4 AI gündemi (ai_agenda_json, kredili) saklanır; HTML her seferinde aynı
formatla üretilir. Seans bu rapordan açıldıysa report_id + seçilen gündem
maddeleri (agenda_items). Additive, downgrade'li.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r8s1v4x5x88r"
down_revision: Union[str, None] = "q7r0u3w4w77q"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coaching_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("data_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("agenda_json", sa.Text(), nullable=True),
        sa.Column("ai_agenda_json", sa.Text(), nullable=True),
        sa.Column("ai_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_coaching_reports_student_id", "coaching_reports", ["student_id"])
    op.create_index("ix_coaching_reports_coach_id", "coaching_reports", ["coach_id"])
    op.create_index("ix_coaching_report_student_week", "coaching_reports", ["student_id", "week_start"])

    with op.batch_alter_table("coaching_sessions") as batch:
        batch.add_column(sa.Column(
            "report_id", sa.Integer(),
            sa.ForeignKey("coaching_reports.id", ondelete="SET NULL", name="fk_session_report"),
            nullable=True,
        ))
        batch.add_column(sa.Column("agenda_items", sa.Text(), nullable=True))
    op.create_index("ix_coaching_sessions_report_id", "coaching_sessions", ["report_id"])


def downgrade() -> None:
    op.drop_index("ix_coaching_sessions_report_id", table_name="coaching_sessions")
    with op.batch_alter_table("coaching_sessions") as batch:
        batch.drop_column("agenda_items")
        batch.drop_column("report_id")
    op.drop_index("ix_coaching_report_student_week", table_name="coaching_reports")
    op.drop_index("ix_coaching_reports_coach_id", table_name="coaching_reports")
    op.drop_index("ix_coaching_reports_student_id", table_name="coaching_reports")
    op.drop_table("coaching_reports")
