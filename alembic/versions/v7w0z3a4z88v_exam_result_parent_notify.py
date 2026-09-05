"""Deneme sonucu veli duyurusu (2026-09-05)

Koç "Veliye duyur" düğmesine basınca veliye deneme sonucu e-postası gider.
Program duyurusuyla aynı desen: OTOMATİK DEĞİL, koçun kasıtlı eylemi.

Üç additive değişiklik:
  1. notificationkind enum'una EXAM_RESULT (PG native enum — üye eklenmezse
     bu bildirimi yazan uç prod'da 500 verir; dev SQLite VARCHAR, görünmez).
  2. parent_notification_prefs: exam_result_enabled (opt-out, default TRUE) +
     exam_result_wa_enabled (opt-in, default FALSE — KVKK deseni).
  3. exam_results.parent_notified_at — düğme "Duyuruldu"ya dönsün + mükerrer
     duyuru engellensin.

Revision ID: v7w0z3a4z88v
Revises: u6v9y2z3y77u
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v7w0z3a4z88v"
down_revision = "u6v9y2z3y77u"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE notificationkind ADD VALUE IF NOT EXISTS 'EXAM_RESULT'"
        )
    # SQLite: Enum VARCHAR olarak saklanır — işlem gerekmez.

    op.add_column(
        "parent_notification_prefs",
        sa.Column(
            "exam_result_enabled", sa.Boolean(), nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "parent_notification_prefs",
        sa.Column(
            "exam_result_wa_enabled", sa.Boolean(), nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "exam_results",
        sa.Column("parent_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exam_results", "parent_notified_at")
    op.drop_column("parent_notification_prefs", "exam_result_wa_enabled")
    op.drop_column("parent_notification_prefs", "exam_result_enabled")
    # PG enum üyesi güvenle düşürülemez; EXAM_RESULT kalır (zararsız).
