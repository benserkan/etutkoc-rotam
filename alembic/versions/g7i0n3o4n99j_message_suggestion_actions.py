"""message_suggestion_actions — koçun WhatsApp mesaj önerisi kararları

Revision ID: g7i0n3o4n99j
Revises: f6h9m2n3m88i
Create Date: 2026-11-14
"""
from alembic import op
import sqlalchemy as sa

revision = "g7i0n3o4n99j"
down_revision = "f6h9m2n3m88i"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "message_suggestion_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("audience", sa.String(10), nullable=False),
        sa.Column("suggestion_key", sa.String(120), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "audience", "suggestion_key", name="uq_msgsugg_student_aud_key"),
    )
    op.create_index("ix_msgsugg_coach_created", "message_suggestion_actions", ["coach_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_msgsugg_coach_created", table_name="message_suggestion_actions")
    op.drop_table("message_suggestion_actions")
