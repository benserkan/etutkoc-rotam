"""app_settings: süper admin düzenlenebilir genel JSON ayarları (fiyat override)

Revision ID: x5y7b0c1b99v
Revises: w4x6a9b0a88u
Create Date: 2026-05-22 10:00:00.000000

Additive — yalnız yeni tablo. Mevcut veriyi ETKİLEMEZ. Downgrade'li.
Fiyat/üyelik override JSON'u burada (key="pricing"). Kod default + DB override.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "x5y7b0c1b99v"
down_revision: Union[str, None] = "w4x6a9b0a88u"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_settings_key", "app_settings", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_app_settings_key", table_name="app_settings")
    op.drop_table("app_settings")
