"""Katman 6 — Ziyaretçi Davranış Telemetri (Feature Card Events).

Anasayfada kartlarla nasıl etkileşildiği ölçülür: gösterim, görüntüleme,
demo tıklama, CTA tıklama. Bu olaylar Katman 7'nin (öğrenen kart seçici /
contextual bandit) eğitim verisidir.

KVKK uyumlu:
  - Düz IP / User-Agent SAKLANMAZ; yalnız SHA256 hash (rotating salt)
  - Anon ziyaretçi: 40-karakter session_id cookie (HttpOnly, 90 gün)
  - viewer_id NULL ise anonim; varsa user.id
  - Saklama: 90 gün ham veri, sonra agreguta düşürülür (Katman 6.5 cron)
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeatureEventType(str, enum.Enum):
    """Ziyaretçi davranışı türü."""

    IMPRESSION = "impression"      # kart DOM'a girdi (sayfa render edildi)
    VIEW = "view"                  # kart viewport'a tamamen girdi (IntersectionObserver)
    DEMO_CLICK = "demo_click"      # "Demo İzle" butonuna tıklandı
    CTA_CLICK = "cta_click"        # kartın CTA butonuna tıklandı (Katman 1'deki cta_url)


FEATURE_EVENT_TYPE_LABELS_TR: dict[FeatureEventType, str] = {
    FeatureEventType.IMPRESSION: "Gösterim",
    FeatureEventType.VIEW: "Görüntüleme",
    FeatureEventType.DEMO_CLICK: "Demo tıklaması",
    FeatureEventType.CTA_CLICK: "CTA tıklaması",
}


class FeatureCardEvent(Base):
    """Tek ziyaretçi-kart-olay üçlüsünün kaydı."""

    __tablename__ = "feature_card_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    card_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("feature_cards.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Kart silinse bile event aynası kalsın (audit benzeri)
    card_slug: Mapped[str] = mapped_column(String(80), nullable=False)

    event_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Anon ziyaretçi oturum kimliği (cookie). Login varsa cookie hala set'li
    # olabilir; viewer_id'yi tercih ederiz ama session_id de tutarız.
    session_id: Mapped[str] = mapped_column(String(40), nullable=False)
    viewer_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    viewer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # KVKK: SHA256 hash (64 hex), düz değer asla DB'ye yazılmaz
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ua_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Katman 9 — A/B test çerçevesi: hangi variant'tan geldi (varsa)
    variant_slug: Mapped[str | None] = mapped_column(String(40), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<FeatureCardEvent id={self.id} card={self.card_slug!r} "
            f"type={self.event_type!r} session={self.session_id[:8]}...>"
        )

    @property
    def event_type_enum(self) -> FeatureEventType:
        try:
            return FeatureEventType(self.event_type)
        except ValueError:
            return FeatureEventType.IMPRESSION  # güvenli fallback


__all__ = [
    "FeatureCardEvent",
    "FeatureEventType",
    "FEATURE_EVENT_TYPE_LABELS_TR",
]
