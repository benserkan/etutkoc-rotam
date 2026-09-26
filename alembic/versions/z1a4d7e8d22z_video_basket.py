"""Video Sepeti — video_basket_items

Revision ID: z1a4d7e8d22z
Revises: y0z3c6d7c11y
Create Date: 2026-09-25

Koç öğrenci başına YouTube video oynatma listesi hazırlar (link yapıştırarak),
videolar konu gruplarına ayrılır, haftalık programa sürüklenir. Programa konan
kayıt task_id taşır (çok linkli video görevi); görev silinince SET NULL →
video sepete döner. Additive, downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "z1a4d7e8d22z"
down_revision = "y0z3c6d7c11y"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_basket_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("youtube_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("channel_title", sa.String(length=200), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("playlist_id", sa.String(length=64), nullable=True),
        sa.Column("playlist_title", sa.String(length=300), nullable=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="SET NULL"), nullable=True),
        sa.Column("group_key", sa.String(length=64), nullable=False),
        sa.Column("group_label", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="anlatim"),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_video_basket_items_student_id", "video_basket_items", ["student_id"])
    op.create_index("ix_video_basket_items_task_id", "video_basket_items", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_video_basket_items_task_id", table_name="video_basket_items")
    op.drop_index("ix_video_basket_items_student_id", table_name="video_basket_items")
    op.drop_table("video_basket_items")
