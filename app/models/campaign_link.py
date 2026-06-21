"""Kampanya / genel tanıtım linki — WhatsApp gruplarına paylaşılabilen, kişiye
ÖZEL OLMAYAN markalı landing.

Üyelik teklifi (membership_offers) 1:1'dir (bir token = bir aday, kabul edilince
kapanır). Kampanya linki 1:çok'tur: tek token, birçok ziyaretçi. Cloud API gruba
mesaj atamadığından (Meta kısıtı), admin bu linki gruba elle paylaşır; tıklayan
herkes markalı teklifi görüp ad+telefon bırakır → SalesProspect (lead) +
ContactRequest → admin "İletişim Talepleri"nde mevcut onboard akışıyla aktive eder.

Plan/tutar/kopya membership ile AYNI kaynaktan beslenir (pricing); fark: hedef
yok + lead formu (çok ziyaretçi).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


CAMPAIGN_STATUS_ACTIVE = "active"
CAMPAIGN_STATUS_PAUSED = "paused"
CAMPAIGN_STATUS_ARCHIVED = "archived"
CAMPAIGN_STATUSES = (CAMPAIGN_STATUS_ACTIVE, CAMPAIGN_STATUS_PAUSED, CAMPAIGN_STATUS_ARCHIVED)
CAMPAIGN_STATUS_LABELS_TR = {
    CAMPAIGN_STATUS_ACTIVE: "Yayında",
    CAMPAIGN_STATUS_PAUSED: "Duraklatıldı",
    CAMPAIGN_STATUS_ARCHIVED: "Arşivlendi",
}


class CampaignLink(Base):
    """Public, tekrar kullanılabilir markalı kampanya linki (grup paylaşımı)."""

    __tablename__ = "campaign_links"
    __table_args__ = (
        Index("ix_campaign_link_token", "token"),
        Index("ix_campaign_link_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)  # admin etiketi (iç)
    # audience: koç vitrinine mi kurum vitrinine mi (kopya + onboard hedefi)
    audience: Mapped[str] = mapped_column(String(16), nullable=False, default="coach")
    plan_code: Mapped[str] = mapped_column(String(50), nullable=False)
    cycle: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = liste fiyatı
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=CAMPAIGN_STATUS_ACTIVE)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lead_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_admin_id])

    def __repr__(self) -> str:
        return f"<CampaignLink {self.id} {self.name} {self.status} leads={self.lead_count}>"
