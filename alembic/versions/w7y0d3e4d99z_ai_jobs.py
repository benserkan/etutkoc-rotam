"""ai_jobs — arka plan yapay zekâ işi (deneme karnesi okuma)

Revision ID: w7y0d3e4d99z
Revises: v6x9c2d3c88y
Create Date: 2026-10-29

Karne okuma tek istekte 2–5 dk sürüyordu (Cloudflare 100 sn sınırı + bağlantı
kopunca sonuç kaybı). Yükle → arka planda oku → taslak → önizle/kaydet.
Additive; downgrade tabloyu düşürür.
"""
import sqlalchemy as sa
from alembic import op

revision = "w7y0d3e4d99z"
down_revision = "v6x9c2d3c88y"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(255), nullable=True),
        sa.Column("params_json", sa.Text(), nullable=True),
        sa.Column("input_data", sa.LargeBinary(), nullable=True),
        sa.Column("input_filename", sa.String(255), nullable=True),
        sa.Column("input_content_type", sa.String(100), nullable=True),
        sa.Column("input_sha256", sa.String(64), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details_json", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits_charged", sa.Integer(), nullable=True),
        sa.Column("consumed_exam_id", sa.Integer(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_jobs_kind", "ai_jobs", ["kind"])
    op.create_index("ix_ai_jobs_owner_id", "ai_jobs", ["owner_id"])
    op.create_index("ix_ai_jobs_student_id", "ai_jobs", ["student_id"])
    op.create_index("ix_ai_jobs_status", "ai_jobs", ["status"])
    op.create_index("ix_ai_jobs_input_sha256", "ai_jobs", ["input_sha256"])


def downgrade() -> None:
    op.drop_table("ai_jobs")
