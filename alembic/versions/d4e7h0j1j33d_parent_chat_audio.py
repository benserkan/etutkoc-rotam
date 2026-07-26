"""Rota Veli Asistanı P3 — sohbet cevaplarına ses önbelleği

Rota'nın her cevap balonu istenirse seslendirilir: MP3 ilk dinlemede üretilir
ve mesaj satırında saklanır (tekrar dinleme kredisiz — P1 yorum deseni).
Mesajlar değişmez (immutable) olduğundan ses asla bayatlamaz. Additive.

Revision ID: d4e7h0j1j33d
Revises: c3d6g9h0h22c
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e7h0j1j33d"
down_revision = "c3d6g9h0h22c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parent_chat_messages", sa.Column("audio", sa.LargeBinary(), nullable=True))
    op.add_column(
        "parent_chat_messages",
        sa.Column("audio_content_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "parent_chat_messages",
        sa.Column("audio_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("parent_chat_messages", "audio_generated_at")
    op.drop_column("parent_chat_messages", "audio_content_type")
    op.drop_column("parent_chat_messages", "audio")
