"""task link_url column — Stage 15 type-specific task content

Revision ID: l0g6j9h0i99d
Revises: k9f5i8g9h88c
Create Date: 2026-05-12 15:30:00.000000

Görev tipi (video/özet/tekrar) içeriğini taşımak için tasks tablosuna
link_url eklendi. Video tipinde YouTube URL'i tutar; diğer tipler için
opsiyonel ek bağlantı alanı. Konu metni mevcut `notes` kolonunda kalır.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l0g6j9h0i99d"
down_revision: Union[str, None] = "k9f5i8g9h88c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("link_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("link_url")
