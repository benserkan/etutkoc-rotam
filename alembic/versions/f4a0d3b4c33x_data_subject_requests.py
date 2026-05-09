"""data_subject_requests tablosu (KVKK madde 11)

Revision ID: f4a0d3b4c33x
Revises: e3z9c2a3b22w
Create Date: 2026-05-09 14:00:00.000000

Stage 10 — KVKK denetim + veri ihracı + RTBF:
- data_subject_requests: kullanıcının kendi verisi için açtığı export/delete/
  rectification talepleri. 30g grace period (delete için process_after) +
  admin işleme/red akışı + payload_json (export içeriği).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a0d3b4c33x"
down_revision: Union[str, None] = "e3z9c2a3b22w"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_subject_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("requester_user_id", sa.Integer(), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("process_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["requester_user_id"], ["users.id"],
            ondelete="SET NULL", name="fk_dsr_requester",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"], ["users.id"],
            ondelete="SET NULL", name="fk_dsr_target",
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"],
            ondelete="SET NULL", name="fk_dsr_institution",
        ),
        sa.ForeignKeyConstraint(
            ["processed_by_user_id"], ["users.id"],
            ondelete="SET NULL", name="fk_dsr_processed_by",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("data_subject_requests") as batch:
        batch.create_index("ix_dsr_target_status", ["target_user_id", "status"])
        batch.create_index("ix_dsr_kind_status", ["kind", "status"])
        batch.create_index("ix_dsr_status_processed", ["status", "process_after"])
        batch.create_index(
            "ix_data_subject_requests_target_user_id", ["target_user_id"],
        )
        batch.create_index(
            "ix_data_subject_requests_requester_user_id",
            ["requester_user_id"],
        )
        batch.create_index(
            "ix_data_subject_requests_created_at", ["created_at"],
        )


def downgrade() -> None:
    op.drop_table("data_subject_requests")
