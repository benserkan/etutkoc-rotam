"""Rota Veli Asistanı P2 — parent_chat_messages (yazılı sohbet geçmişi)

Veli, Rota'ya çocuğu hakkında soru sorar; sorular ve cevaplar saklanır (veli
eski konuşmalarını görür; son ~10 mesaj bağlama girer). KVKK: hesap silinince
mesajlar CASCADE ile silinir. Additive; mevcut veriye dokunmaz.

Revision ID: c3d6g9h0h22c
Revises: b2c5f8g9g11b
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d6g9h0h22c"
down_revision = "b2c5f8g9g11b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parent_chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "parent_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "student_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("role", sa.String(length=8), nullable=False),  # veli | rota
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_parent_chat_thread", "parent_chat_messages",
        ["parent_id", "student_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_parent_chat_thread", table_name="parent_chat_messages")
    op.drop_table("parent_chat_messages")
