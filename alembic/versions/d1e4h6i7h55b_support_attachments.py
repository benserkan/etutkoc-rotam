"""support_attachments: talebe dosya eki (jpg/png/webp/gif/pdf)

Revision ID: d1e4h6i7h55b
Revises: c0d3g5h6g44a
Create Date: 2026-05-23 16:00:00.000000

Additive — yalnız 1 yeni tablo ekler; mevcut veriyi ETKİLEMEZ. Downgrade'li.
Dosya verisi DB'de (LargeBinary) saklanır → dev (SQLite) + prod (Postgres)
taşınabilir, ayrı volume/S3 gerekmez. KVKK: yalnız talebin tarafları erişir,
talep silinince CASCADE ile silinir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e4h6i7h55b"
down_revision: Union[str, None] = "c0d3g5h6g44a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_attachments",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["support_requests.id"], ondelete="CASCADE",
                                name="fk_support_attachments_request_id"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL",
                                name="fk_support_attachments_uploaded_by_id_users"),
    )
    op.create_index("ix_support_attachments_request_id", "support_attachments", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_support_attachments_request_id", table_name="support_attachments")
    op.drop_table("support_attachments")
