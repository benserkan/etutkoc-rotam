"""at_risk_mutes — risk panelinde 7 günlük yanlış alarm sustur

Revision ID: t2o8s1q2r11l
Revises: s1n7r0p1q00k
Create Date: 2026-05-09 16:00:00.000000

Stage 1 — risk paneli:
- (teacher_id, student_id) unique
- expires_at: 7 gün sonra otomatik aktif olmaktan çıkar
- reason: opsiyonel açıklama
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t2o8s1q2r11l"
down_revision: Union[str, None] = "s1n7r0p1q00k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "at_risk_mutes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["teacher_id"], ["users.id"], ondelete="CASCADE",
            name="fk_at_risk_mute_teacher",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], ondelete="CASCADE",
            name="fk_at_risk_mute_student",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("teacher_id", "student_id", name="uq_at_risk_mute_pair"),
    )
    with op.batch_alter_table("at_risk_mutes") as batch:
        batch.create_index("ix_at_risk_mutes_teacher_id", ["teacher_id"])
        batch.create_index("ix_at_risk_mutes_student_id", ["student_id"])


def downgrade() -> None:
    op.drop_table("at_risk_mutes")
