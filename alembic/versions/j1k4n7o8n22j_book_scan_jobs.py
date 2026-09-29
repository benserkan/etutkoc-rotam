"""Tam kitap tarama işleri (süper admin, arka plan) — 2026-09-29.

book_scan_jobs: yüklenen PDF + ilerleme + sonuç taslağı (JSON). Additive,
downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "j1k4n7o8n22j"
down_revision = "i0j3m6n7m11i"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "book_scan_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_path", sa.String(500), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("toc_pages", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("page_offset", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stage", sa.String(255), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_book_scan_jobs_created_by_id", "book_scan_jobs", ["created_by_id"])
    op.create_index("ix_book_scan_jobs_status", "book_scan_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_book_scan_jobs_status", table_name="book_scan_jobs")
    op.drop_index("ix_book_scan_jobs_created_by_id", table_name="book_scan_jobs")
    op.drop_table("book_scan_jobs")
