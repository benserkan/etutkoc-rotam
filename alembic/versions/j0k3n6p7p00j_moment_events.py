"""Moment sağlık taraması (Faz C, 2026-08-04) — bağlamsal uyarı gösterim izi.

moment_events: bir bağlamsal uyarı/kart sinyali kullanıcıya SUNULDUĞUNDA
(ilgili API yanıtı sinyali taşıdığında) günde bir kez yazılır. Gecelik/saatlik
sessizlik taraması "koşulu sağlayan + panelde gezen ama sinyal ALMAYAN"
kullanıcıyı yakalar → süper admine alarm (e-posta kesintisi dersinin bağlamsal
uyarılara uygulanması: ölçülmeyen kırılma sessiz kalır).

Additive — mevcut veri etkilenmez.

Revision ID: j0k3n6p7p00j
Revises: i9j2m5o6o99i
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "j0k3n6p7p00j"
down_revision = "i9j2m5o6o99i"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("moment_key", sa.String(length=40), nullable=False),
        # 'YYYY-MM-DD' — kullanıcı+moment+gün tekilliği (günde 1 kayıt yeter)
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "user_id", "moment_key", "day", name="uq_moment_event_user_key_day",
        ),
    )
    op.create_index(
        "ix_moment_events_key_time", "moment_events",
        ["moment_key", "occurred_at"],
    )
    op.create_index("ix_moment_events_user", "moment_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_moment_events_user", table_name="moment_events")
    op.drop_index("ix_moment_events_key_time", table_name="moment_events")
    op.drop_table("moment_events")
