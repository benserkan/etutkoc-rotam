"""Haftalık İskelet — kalıptan program (F1)

Revision ID: b3c6f9g0f44b
Revises: a2b5e8f9e33a
Create Date: 2026-09-25

3 yeni tablo, mevcut veriye DOKUNMAZ (additive), downgrade'li:
- weekly_skeletons: öğrenci başına tek etkin iskelet
- weekly_skeleton_slots: gün + (periyot) + ders satırları
- skeleton_ghost_actions: hayalet üzerindeki koç eylemi (kabul / başka konu /
  kaldır) — "bu hafta kaldırıldı" hafızası + kabul oranı ölçümü
Hayalet hücreler tabloda TUTULMAZ, rezerv YAPMAZ; iskeletten hesaplanır.
"""
from alembic import op
import sqlalchemy as sa

revision = "b3c6f9g0f44b"
down_revision = "a2b5e8f9e33a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_skeletons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False, server_default="Haftalık iskelet"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_weekly_skeletons_coach_id", "weekly_skeletons", ["coach_id"])

    op.create_table(
        "weekly_skeleton_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("skeleton_id", sa.Integer(),
                  sa.ForeignKey("weekly_skeletons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_routine", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_count", sa.Integer(), nullable=True),
    )
    op.create_index("ix_weekly_skeleton_slots_skeleton_id", "weekly_skeleton_slots", ["skeleton_id"])

    op.create_table(
        "skeleton_ghost_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot_id", sa.Integer(),
                  sa.ForeignKey("weekly_skeleton_slots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("chip_rank", sa.Integer(), nullable=True),
        sa.Column("chip_kind", sa.String(length=16), nullable=True),
        sa.Column("chip_count", sa.Integer(), nullable=True),
        sa.Column("section_id", sa.Integer(),
                  sa.ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_skeleton_ghost_actions_student_date", "skeleton_ghost_actions",
                    ["student_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_skeleton_ghost_actions_student_date", table_name="skeleton_ghost_actions")
    op.drop_table("skeleton_ghost_actions")
    op.drop_index("ix_weekly_skeleton_slots_skeleton_id", table_name="weekly_skeleton_slots")
    op.drop_table("weekly_skeleton_slots")
    op.drop_index("ix_weekly_skeletons_coach_id", table_name="weekly_skeletons")
    op.drop_table("weekly_skeletons")
