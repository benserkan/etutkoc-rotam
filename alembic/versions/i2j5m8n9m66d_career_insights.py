"""career_insights — AI Kariyer Sentezi cache (anket sisteminin AI katmanı)

Revision ID: i2j5m8n9m66d
Revises: h1i4l7m8l55c
Create Date: 2026-06-12

Anket sonuçları (RIASEC + Beceri Seti + opsiyoneller) + gerçek akademik veri →
Gemini ile meslek/bölüm önerisi + hedef-belirleme seans gündemi. KS4 kredi
güvenliği deseni: öğrenci başına TEK cache satırı; GET ücretsiz / POST kredili;
yeni anket sonucu → is_stale. Additive, downgrade'li.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i2j5m8n9m66d"
down_revision: Union[str, None] = "h1i4l7m8l55c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "career_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False, unique=True,
        ),
        sa.Column(
            "generated_by_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("career_suggestions", sa.Text(), nullable=True),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("agenda", sa.Text(), nullable=True),
        sa.Column("watch_outs", sa.Text(), nullable=True),
        sa.Column("based_on", sa.Text(), nullable=True),
        sa.Column("is_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_career_insights_student", "career_insights", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_career_insights_student", table_name="career_insights")
    op.drop_table("career_insights")
