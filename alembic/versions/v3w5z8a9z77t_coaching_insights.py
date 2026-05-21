"""coaching_insights: AI koçluk içgörüsü cache (KS4 kredi güvenliği)

Revision ID: v3w5z8a9z77t
Revises: u2v4y7z8y66s
Create Date: 2026-05-21 16:00:00.000000

Additive — yalnız yeni tablo. Mevcut veriyi ETKİLEMEZ. Downgrade'li.

KREDİ GÜVENLİĞİ: İçgörü bir kez (pahalı Claude çağrısı) üretilir + burada
saklanır; sonraki görüntülemeler DB'den okunur (ücretsiz). Yeni/değişen seans
`is_stale=True` yapar (AI çağrısı yok). Öğrenci başına TEK kayıt (unique).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "v3w5z8a9z77t"
down_revision: Union[str, None] = "u2v4y7z8y66s"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coaching_insights",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("generated_by_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("agenda_suggestions", sa.Text(), nullable=True),
        sa.Column("psychological_tips", sa.Text(), nullable=True),
        sa.Column("watch_outs", sa.Text(), nullable=True),
        sa.Column("based_on_sessions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_stale", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_coaching_insights_student_id", "coaching_insights", ["student_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_coaching_insights_student_id", table_name="coaching_insights")
    op.drop_table("coaching_insights")
