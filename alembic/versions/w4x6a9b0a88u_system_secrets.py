"""system_secrets: süper admin merkezi şifreli sırlar (API anahtarları)

Revision ID: w4x6a9b0a88u
Revises: v3w5z8a9z77t
Create Date: 2026-05-21 17:30:00.000000

Additive — yalnız yeni tablo. Mevcut veriyi ETKİLEMEZ. Downgrade'li.
API anahtarları (Anthropic/OpenAI) süper admin panelinden şifreli saklanır.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w4x6a9b0a88u"
down_revision: Union[str, None] = "v3w5z8a9z77t"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_secrets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_secrets_name", "system_secrets", ["name"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_system_secrets_name", table_name="system_secrets")
    op.drop_table("system_secrets")
