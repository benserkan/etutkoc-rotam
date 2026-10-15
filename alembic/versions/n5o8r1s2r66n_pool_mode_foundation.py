"""Haftalık görev havuzu modu — temel (2026-10-12, tasarım K1–K61).

Dershane öğrencisi için ALTERNATİF program modeli. Mevcut gün-gün yapı
DEĞİŞMEZ; her şey eklemeli:

  · users.program_mode            'gun_gun' (varsayılan, mevcut davranış) | 'havuz'
  · class_groups                  şube kaydı (konu konumu + ders programı günleri +
                                   kaynak seti); users.class_group metni bağ olarak kalır
  · study_periods                 dönem = iki gerçekleşen seans arası (1–14 gün)
  · pool_items                    havuz kalemi (ders + miktar + birim; konu/kaynak/gün
                                   etiketi isteğe bağlı; REZERV TUTMAZ)
  · tasks.pool_item_id            kap = o güne yazılan mevcut görev → kalem bağı

Additive, downgrade'li.

Revision ID: n5o8r1s2r66n
Revises: m4n7q0r1q55m
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n5o8r1s2r66n"
down_revision: Union[str, None] = "m4n7q0r1q55m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- öğrencide program modu (varsayılan mevcut davranış)
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            "program_mode", sa.String(16), nullable=False, server_default="gun_gun",
        ))

    # --- şube
    op.create_table(
        "class_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_key", sa.String(40), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("topic_positions", sa.Text(), nullable=True),
        sa.Column("lesson_days", sa.Text(), nullable=True),
        sa.Column("book_set_id", sa.Integer(),
                  sa.ForeignKey("book_sets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("scope_key", "name", name="uq_class_groups_scope_name"),
    )
    op.create_index("ix_class_groups_scope_key", "class_groups", ["scope_key"])

    # --- dönem
    op.create_table(
        "study_periods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("coach_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("opened_session_id", sa.Integer(),
                  sa.ForeignKey("coaching_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expected_next_on", sa.Date(), nullable=True),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("closed_session_id", sa.Integer(),
                  sa.ForeignKey("coaching_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="acik"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_study_periods_student_opened", "study_periods", ["student_id", "opened_on"])
    op.create_index("ix_study_periods_status", "study_periods", ["status"])

    # --- havuz kalemi
    op.create_table(
        "pool_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("period_id", sa.Integer(),
                  sa.ForeignKey("study_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.Integer(),
                  sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic_id", sa.Integer(),
                  sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("book_id", sa.Integer(),
                  sa.ForeignKey("books.id", ondelete="SET NULL"), nullable=True),
        sa.Column("book_section_id", sa.Integer(),
                  sa.ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("day_hint", sa.Date(), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="rehber"),
        sa.Column("teacher_homework", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approval", sa.String(16), nullable=False, server_default="yok"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("carry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cup_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_item_id", sa.Integer(),
                  sa.ForeignKey("pool_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("exam_result_id", sa.Integer(),
                  sa.ForeignKey("exam_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pool_items_period_id", "pool_items", ["period_id"])
    op.create_index("ix_pool_items_student_id", "pool_items", ["student_id"])

    # --- kap = görev → kalem bağı (SQLite ALTER-ADD-FK desteklemez → batch)
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pool_item_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_tasks_pool_item_id", ["pool_item_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_tasks_pool_item", "pool_items", ["pool_item_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_pool_item", type_="foreignkey")
        batch_op.drop_index("ix_tasks_pool_item_id")
        batch_op.drop_column("pool_item_id")
    op.drop_index("ix_pool_items_student_id", table_name="pool_items")
    op.drop_index("ix_pool_items_period_id", table_name="pool_items")
    op.drop_table("pool_items")
    op.drop_index("ix_study_periods_status", table_name="study_periods")
    op.drop_index("ix_study_periods_student_opened", table_name="study_periods")
    op.drop_table("study_periods")
    op.drop_index("ix_class_groups_scope_key", table_name="class_groups")
    op.drop_table("class_groups")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("program_mode")
