"""communication_logs — birleşik iletişim gözlem log'u (e-posta/push/whatsapp/sms)

Süper admin "İletişim Sağlığı" merkezinin tek kaynağı. Tüm kanal gönderimleri
(ne, kime, ne zaman, durum) tek tabloda toplanır. Mevcut NotificationLog +
whatsapp_dispatch_logs'a DOKUNMAZ (onlar cap/spam mantığını yürütür). Yalnız
yeni tablo eklenir — additive, downgrade'li.

Revision ID: p9q2t5u6t88o
Revises: o8p1s4t5s77n
Create Date: 2026-06-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p9q2t5u6t88o"
down_revision: Union[str, None] = "o8p1s4t5s77n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "communication_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("to_user_id", sa.Integer(), nullable=True),
        sa.Column("to_address", sa.String(length=320), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="sent"),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_commlog_channel_created", "communication_logs", ["channel", "created_at"]
    )
    op.create_index("ix_commlog_status", "communication_logs", ["status"])
    op.create_index(
        "ix_commlog_provider_msgid", "communication_logs", ["provider_message_id"]
    )
    op.create_index(
        "ix_commlog_to_user_created", "communication_logs", ["to_user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_commlog_to_user_created", table_name="communication_logs")
    op.drop_index("ix_commlog_provider_msgid", table_name="communication_logs")
    op.drop_index("ix_commlog_status", table_name="communication_logs")
    op.drop_index("ix_commlog_channel_created", table_name="communication_logs")
    op.drop_table("communication_logs")
