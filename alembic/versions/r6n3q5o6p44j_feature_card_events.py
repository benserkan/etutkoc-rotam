"""feature_card_events — anasayfa kart davranış telemetri tablosu (Katman 6)

Revision ID: r6n3q5o6p44j
Revises: q5m2p4n5o33i
Create Date: 2026-05-15 11:00:00.000000

Ziyaretçinin anasayfada hangi kartı gördüğü/tıkladığı ölçülür. Bu veri
Katman 7'nin (öğrenen kart seçici / contextual bandit) eğitim girdisidir.

KVKK uyumlu:
  - Düz IP ve User-Agent SAKLANMAZ — yalnız SHA256 hash (rotating salt)
  - Anon ziyaretçi: session_id 40-karakter cookie (90 gün TTL)
  - viewer_id NULL ise anonim; varsa login user.id
  - 90 gün ham veri saklanır, sonra cron ile agreguta düşürülür (Katman 6.5)

İndeksler:
  - (card_id, event_type) — kart başına agregat sayım sorgusu
  - (session_id, created_at) — server-side throttle: aynı session+slug+event
    10sn içinde tekrar gelirse no-op
  - (created_at) — saklama politikası temizliği
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r6n3q5o6p44j"
down_revision: Union[str, None] = "q5m2p4n5o33i"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feature_card_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "card_id",
            sa.Integer(),
            sa.ForeignKey("feature_cards.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("card_slug", sa.String(length=80), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("viewer_role", sa.String(length=20), nullable=True),
        sa.Column(
            "viewer_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # SHA256 hex = 64 char; salt server tarafında, KVKK uyumlu
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("ua_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_feature_card_events_card_event",
        "feature_card_events",
        ["card_id", "event_type"],
    )
    op.create_index(
        "ix_feature_card_events_session_time",
        "feature_card_events",
        ["session_id", "created_at"],
    )
    op.create_index(
        "ix_feature_card_events_created_at",
        "feature_card_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_feature_card_events_created_at", table_name="feature_card_events")
    op.drop_index("ix_feature_card_events_session_time", table_name="feature_card_events")
    op.drop_index("ix_feature_card_events_card_event", table_name="feature_card_events")
    op.drop_table("feature_card_events")
