"""parent_notification_prefs.exam_approaching_enabled — sınav yaklaşıyor toggle

Revision ID: m5h1l3i4j44e
Revises: l4g0k2h3i33d
Create Date: 2026-05-08 18:00:00.000000

Faz 8 — Veli bildirimi lokalizasyon. EXAM_APPROACHING bildirim türü için
veli pref toggle'ı. Varsayılan True (açık) — mevcut velilere de retrofit.

NotificationKind enum'ı SQLAlchemy Enum üzerinden TEXT-based olarak saklandığı
için yeni 'exam_approaching' değeri için schema migration gerekmedi (ORM
yüklenirken tanınır). Sadece pref tablosuna toggle alanı ekliyoruz.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m5h1l3i4j44e"
down_revision: Union[str, None] = "l4g0k2h3i33d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("parent_notification_prefs") as batch:
        batch.add_column(
            sa.Column(
                "exam_approaching_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("parent_notification_prefs") as batch:
        batch.drop_column("exam_approaching_enabled")
