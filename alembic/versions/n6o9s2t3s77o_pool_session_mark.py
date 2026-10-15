"""Havuz kalemi — rehberin seansta işaretlediği birim (K18, 2026-10-12, Adım 2b).

İki tamamlanma kaynağı ayrı tutulur: `completed` (öğrencinin kap kaydından, erken
uyarı yalnız buna bakar) · `session_marked` (rehber seansta geriye dönük toplu
işaretledi; kaynak kanıtıyla). Yüzdeye ikisi birden girer. Additive, downgrade'li.

Revision ID: n6o9s2t3s77o
Revises: n5o8r1s2r66n
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n6o9s2t3s77o"
down_revision: Union[str, None] = "n5o8r1s2r66n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("pool_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("session_marked", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("session_marked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("pool_items", schema=None) as batch_op:
        batch_op.drop_column("session_marked_at")
        batch_op.drop_column("session_marked")
