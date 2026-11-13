"""Deneme analiz raporu bağlantıları (veliye WhatsApp/e-posta) — 2026-11-13.

Revision ID: e5g8l1m2l77h
Revises: d4f7k0l1k66g
"""
from alembic import op
import sqlalchemy as sa

revision = "e5g8l1m2l77h"
down_revision = "d4f7k0l1k66g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_parent_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exam_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audio", sa.LargeBinary(), nullable=True),
        sa.Column("audio_content_type", sa.String(40), nullable=True),
        sa.Column("audio_signature", sa.String(64), nullable=True),
        sa.Column("audio_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_exam_parent_reports_token", "exam_parent_reports", ["token"], unique=True)
    op.create_index("ix_exam_parent_reports_exam_id", "exam_parent_reports", ["exam_id"])
    op.create_index("ix_exam_parent_reports_student_id", "exam_parent_reports", ["student_id"])


def downgrade() -> None:
    op.drop_table("exam_parent_reports")
