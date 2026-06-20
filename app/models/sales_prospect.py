"""Hedef Havuzu — sisteme ÜYE OLMAYAN potansiyel kurum/koç kayıtları.

Süper admin, tanıtım + kişiye özel üyelik teklifi göndermek istediği (rehberindeki
ya da sonradan eklediği) kurum yöneticisi / bağımsız koçları burada tutar. Üyelik
teklifi (membership_offers) bir prospect'i hedef alabilir → markalı /membership
linki + (Meta hazır olunca) WhatsApp Cloud API branded mesaj.

Sistem kullanıcısı (User) DEĞİL — yalnız telefon + ad bazlı satış adayı. Üye
olunca status=member işaretlenir (istenirse gerçek User'a bağlanır).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# --- Hedef tipi ---
PROSPECT_KIND_INSTITUTION = "institution"
PROSPECT_KIND_COACH = "coach"
PROSPECT_KINDS = (PROSPECT_KIND_INSTITUTION, PROSPECT_KIND_COACH)
PROSPECT_KIND_LABELS_TR = {
    PROSPECT_KIND_INSTITUTION: "Kurum",
    PROSPECT_KIND_COACH: "Bağımsız Koç",
}

# --- Kaynak ---
PROSPECT_SOURCES = ("manual", "contact", "referral", "inbound")
PROSPECT_SOURCE_LABELS_TR = {
    "manual": "Elle eklendi",
    "contact": "Telefon rehberi",
    "referral": "Tavsiye",
    "inbound": "Gelen talep",
}

# --- Durum (satış hunisi) ---
PROSPECT_STATUS_NEW = "new"
PROSPECT_STATUS_CONTACTED = "contacted"
PROSPECT_STATUS_INTERESTED = "interested"
PROSPECT_STATUS_MEMBER = "member"
PROSPECT_STATUS_NOT_INTERESTED = "not_interested"
PROSPECT_STATUS_UNREACHABLE = "unreachable"
PROSPECT_STATUSES = (
    PROSPECT_STATUS_NEW, PROSPECT_STATUS_CONTACTED, PROSPECT_STATUS_INTERESTED,
    PROSPECT_STATUS_MEMBER, PROSPECT_STATUS_NOT_INTERESTED, PROSPECT_STATUS_UNREACHABLE,
)
PROSPECT_STATUS_LABELS_TR = {
    PROSPECT_STATUS_NEW: "Yeni",
    PROSPECT_STATUS_CONTACTED: "İletişime geçildi",
    PROSPECT_STATUS_INTERESTED: "İlgileniyor",
    PROSPECT_STATUS_MEMBER: "Üye oldu",
    PROSPECT_STATUS_NOT_INTERESTED: "İlgilenmiyor",
    PROSPECT_STATUS_UNREACHABLE: "Ulaşılamadı",
}


class SalesProspect(Base):
    """Sisteme üye olmayan potansiyel kurum/koç (satış adayı)."""

    __tablename__ = "sales_prospects"
    __table_args__ = (
        Index("ix_prospect_phone", "phone"),
        Index("ix_prospect_status", "status"),
        Index("ix_prospect_kind", "kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)  # E.164 normalize
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default=PROSPECT_KIND_COACH)
    org_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source: Mapped[str] = mapped_column(String(24), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PROSPECT_STATUS_NEW)
    # WhatsApp izni (Meta opt-in/kalite politikası için) — soğuk listede dikkat.
    opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_contacted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_admin_id])

    def __repr__(self) -> str:
        return f"<SalesProspect {self.id} {self.name} {self.phone} {self.status}>"
