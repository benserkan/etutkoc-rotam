"""membership_offers — K2 Cloud API branded gönderim izi (wa_sent_at + wa_message_id)

Süper admin "WhatsApp ile gönder (Cloud API)" ile branded şablon yollayınca
gönderim zamanı + Meta message id saklanır (teslim takibi comm_log ile eşleşir).
Additive, downgrade'li.

Revision ID: s2t5v8w9v11s
Revises: r1s4u7v8u00r
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "s2t5v8w9v11s"
down_revision: Union[str, None] = "r1s4u7v8u00r"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("membership_offers") as batch:
        batch.add_column(sa.Column("wa_sent_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("wa_message_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("membership_offers") as batch:
        batch.drop_column("wa_message_id")
        batch.drop_column("wa_sent_at")
