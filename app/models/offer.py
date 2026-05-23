"""Sprint D.1 (Ticari Pano 2.0 — Faz E Seviye 1) — Owner teklifi.

Admin bir owner'a (Institution veya bağımsız öğretmen User) özel teklif
sunabilir: indirim, deneme uzatma, plan upgrade, ücretsiz özellik,
onboarding eğitimi. Teklif token'lı public link olarak gönderilir
(login gerektirmez); owner yetkilisi linke tıklar, "Kabul" veya "Reddet"
butonlarıyla yanıt verir.

**Sprint F.3 — Owner pattern**: Mevcut kayıtlar `owner_type='institution'`
ile devam eder. Bağımsız öğretmen için `owner_type='user'` + `user_id`.
Kabul edilirse → otomatik plan değişimi (varsa) + PlanChangeHistory + audit.
"""

from __future__ import annotations

import enum
import secrets as _secrets
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.user import User


OFFER_OWNER_TYPES = ("institution", "user")


class OfferKind(str, enum.Enum):
    """Teklif türü."""
    DISCOUNT_PERCENT = "discount_percent"   # %X indirim
    DISCOUNT_FIXED = "discount_fixed"       # X ₺ sabit indirim
    TRIAL_EXTENSION = "trial_extension"     # Deneme süresi X gün uzat
    PLAN_UPGRADE = "plan_upgrade"           # Belirli plana ücretsiz/indirimli yükseltme
    FREE_FEATURE = "free_feature"           # Ek özellik bedava
    ONBOARDING_HOURS = "onboarding_hours"   # X saat onboarding eğitimi
    CUSTOM = "custom"                       # Serbest metin


OFFER_KIND_LABELS_TR: dict[OfferKind, str] = {
    OfferKind.DISCOUNT_PERCENT: "Yüzde indirim",
    OfferKind.DISCOUNT_FIXED: "Sabit tutar indirim (₺)",
    OfferKind.TRIAL_EXTENSION: "Deneme süresini uzat",
    OfferKind.PLAN_UPGRADE: "Pakete yükseltme (özel fiyat)",
    OfferKind.FREE_FEATURE: "Ücretsiz ek özellik",
    OfferKind.ONBOARDING_HOURS: "Onboarding / eğitim saati",
    OfferKind.CUSTOM: "Özel teklif (serbest)",
}


OFFER_KIND_ICONS: dict[OfferKind, str] = {
    OfferKind.DISCOUNT_PERCENT: "💸",
    OfferKind.DISCOUNT_FIXED: "💰",
    OfferKind.TRIAL_EXTENSION: "⏰",
    OfferKind.PLAN_UPGRADE: "⬆️",
    OfferKind.FREE_FEATURE: "🎁",
    OfferKind.ONBOARDING_HOURS: "🎓",
    OfferKind.CUSTOM: "📝",
}


class OfferStatus(str, enum.Enum):
    DRAFT = "draft"             # Admin oluşturdu, henüz göndermedi
    SENT = "sent"               # Kuruma gönderildi, cevap bekleniyor
    ACCEPTED = "accepted"       # Kurum kabul etti
    DECLINED = "declined"       # Kurum reddetti
    EXPIRED = "expired"         # Süresi doldu (otomatik veya manuel)
    CANCELLED = "cancelled"     # Admin iptal etti


OFFER_STATUS_LABELS_TR: dict[OfferStatus, str] = {
    OfferStatus.DRAFT: "Taslak",
    OfferStatus.SENT: "Gönderildi — cevap bekleniyor",
    OfferStatus.ACCEPTED: "Kabul edildi",
    OfferStatus.DECLINED: "Reddedildi",
    OfferStatus.EXPIRED: "Süresi doldu",
    OfferStatus.CANCELLED: "İptal edildi",
}


OFFER_STATUS_COLORS: dict[OfferStatus, str] = {
    OfferStatus.DRAFT: "slate",
    OfferStatus.SENT: "amber",
    OfferStatus.ACCEPTED: "emerald",
    OfferStatus.DECLINED: "rose",
    OfferStatus.EXPIRED: "slate",
    OfferStatus.CANCELLED: "slate",
}


def _generate_token() -> str:
    """40 karakter URL-safe token üret."""
    return _secrets.token_urlsafe(30)


class Offer(Base):
    """Bir owner'a (kurum veya bağımsız öğretmen) sunulan özel teklif."""

    __tablename__ = "offers"
    __table_args__ = (
        Index("ix_offers_institution_status", "institution_id", "status"),
        Index("ix_offers_user_status", "user_id", "status"),
        Index("ix_offers_token", "token", unique=True),
        Index("ix_offers_status_expires", "status", "expires_at"),
        CheckConstraint(
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
            name="ck_offers_owner_xor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'institution'"),
    )
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    # URL-safe public token — kurum bu URL ile teklifi görür (login yok)
    token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True,
        default=_generate_token,
    )
    kind: Mapped[OfferKind] = mapped_column(
        Enum(OfferKind), nullable=False,
    )
    # Sayısal değer (yüzde için 0-100, ₺ için tutar, gün için sayı, vb.)
    # Numeric → SQLite'ta REAL olur. None ise türe göre anlamsız (CUSTOM gibi).
    value: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # value'nun birimi (%, TRY, gün, saat) — UI gösterimi için
    value_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Geçerlilik süresi (ay) — sürekli indirim için 999 koyulabilir
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Kabul edilirse hangi plana geçilecek (PLAN_UPGRADE için zorunlu)
    new_plan: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Admin notu (UI'da görünür değil)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Kuruma gösterilecek başlık + mesaj
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    public_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[OfferStatus] = mapped_column(
        Enum(OfferStatus), nullable=False,
        default=OfferStatus.DRAFT,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Zaman damgaları (audit için)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Kullanıcı public teklif linkini ilk açtığında doldurulur (açıldı izleme)
    viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    decline_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Kabul edildiyse hangi PlanChangeHistory ile bağlandı
    plan_change_history_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_change_history.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    institution: Mapped["Institution | None"] = relationship(
        "Institution", foreign_keys=[institution_id],
    )
    owner_user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id],
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_user_id],
    )

    @property
    def owner_id(self) -> int | None:
        return self.institution_id if self.owner_type == "institution" else self.user_id

    @property
    def owner_detail_url(self) -> str:
        if self.owner_type == "institution":
            return f"/admin/revenue/institutions/{self.institution_id}"
        return f"/admin/revenue/users/{self.user_id}"

    def __repr__(self) -> str:
        return (
            f"<Offer #{self.id} owner={self.owner_type}:{self.owner_id} "
            f"{self.kind.value} status={self.status.value}>"
        )


__all__ = [
    "OFFER_KIND_ICONS",
    "OFFER_KIND_LABELS_TR",
    "OFFER_OWNER_TYPES",
    "OFFER_STATUS_COLORS",
    "OFFER_STATUS_LABELS_TR",
    "Offer",
    "OfferKind",
    "OfferStatus",
]
