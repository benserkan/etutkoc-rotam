"""parent_insights — AI veli içgörüsü cache (P2b)

Revision ID: f9g2j5k6j33a
Revises: e8f1i4j5i22z
Create Date: 2026-06-06

Veli "çocuğum için analiz oluştur" → Gemini ücretli key ile konu performansı +
deneme sonuçlarından veliye yönelik analiz. Kredi öğrencinin koçunun havuzundan
düşer; cache ile tekrar görüntülemede kredi yanmaz (bayatlık hesaplanır). Additive,
downgrade'li — mevcut veriyi etkilemez.
"""
from alembic import op
import sqlalchemy as sa

revision = "f9g2j5k6j33a"
down_revision = "e8f1i4j5i22z"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parent_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("generated_by_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("strengths", sa.Text(), nullable=True),
        sa.Column("focus_areas", sa.Text(), nullable=True),
        sa.Column("parent_tips", sa.Text(), nullable=True),
        sa.Column("based_on_exams", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("based_on_solved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("parent_insights")
