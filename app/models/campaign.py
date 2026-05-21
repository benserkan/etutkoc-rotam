"""Sprint E.1 (Ticari Pano 2.0 — Faz E Seviye 2) — Toplu kampanya.

Admin önceden tanımlı bir segment (free planda olan, trial bitiyor, pause modunda
30+ gün, vb.) seçer ve hepsine aynı (veya A/B varyantlı) teklifi gönderir.

Akış:
  1) Admin segment + offer template + (varsa) A/B varyant seçer → status=DRAFT
  2) Admin "Önizle" der → eligible kurumlar listelenir
  3) Admin "Başlat" der → status=RUNNING
     a) Her hedef kurum için bir Offer üretilir (Offer modeli ile reuse)
     b) Her Offer için CampaignRecipient kaydı oluşur
     c) E-postalar gönderilir (offer_invitation.html)
  4) Sonuç paneli: targeted/sent/opened/clicked/accepted/declined/expired funnel

A/B akışı:
  - variant_a (offer_a_kind/value/...) ve variant_b (offer_b_kind/value/...) ayrı
  - Hash(institution_id) tek/çift'e göre A veya B'ye düşer (deterministik split)
  - Sonuç panelinde her varyantın conversion oranı ayrı gösterilir
"""

from __future__ import annotations

import enum
from datetime import datetime
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
    from app.models.offer import Offer
    from app.models.user import User


CAMPAIGN_RECIPIENT_OWNER_TYPES = ("institution", "user")


class CampaignSegment(str, enum.Enum):
    """Önceden tanımlı hedef segmentler."""
    FREE_PLAN = "free_plan"                  # Ücretsiz planda olan kurumlar
    TRIAL_ENDING_7D = "trial_ending_7d"      # Trial önümüzdeki 7 günde bitiyor
    PAUSED_30D = "paused_30d"                # 30+ gün pause modunda
    CHAMPION = "champion"                    # Sağlık skoru yüksek + ödeyen + 6+ ay aktif
    PAYING_AT_RISK = "paying_at_risk"        # Ödeyen ama sağlık skoru risk/kritik
    NEVER_LOGGED_IN = "never_logged_in"      # Kayıt olmuş ama hiç giriş yapmamış
    CUSTOM_PLAN = "custom_plan"              # Belirli bir plan kodundakiler (filter)


CAMPAIGN_SEGMENT_LABELS_TR: dict[CampaignSegment, str] = {
    CampaignSegment.FREE_PLAN: "Ücretsiz planda olanlar",
    CampaignSegment.TRIAL_ENDING_7D: "Denemesi 7 gün içinde bitenler",
    CampaignSegment.PAUSED_30D: "30+ gün pause modunda olanlar",
    CampaignSegment.CHAMPION: "Champion — sağlıklı, ödeyen, 6+ ay aktif",
    CampaignSegment.PAYING_AT_RISK: "Ödeyen ama risk altında",
    CampaignSegment.NEVER_LOGGED_IN: "Hiç giriş yapmamış olanlar",
    CampaignSegment.CUSTOM_PLAN: "Belirli plandakiler (özel filtre)",
}


CAMPAIGN_SEGMENT_DESCRIPTIONS: dict[CampaignSegment, str] = {
    CampaignSegment.FREE_PLAN: "Free / Ücretsiz plandaki tüm aktif kurumlar — upgrade kampanyası için ideal.",
    CampaignSegment.TRIAL_ENDING_7D: "Trial bitmeden son uyarı + indirimli kalıcı plan teklifi.",
    CampaignSegment.PAUSED_30D: "Uzun pause modundakileri geri kazanma kampanyası.",
    CampaignSegment.CHAMPION: "En değerli müşteriler — referans/yıllık plan/elite upgrade için aday.",
    CampaignSegment.PAYING_AT_RISK: "Ödüyor ama kullanım/sağlık düşüyor — kaybetmemek için yumuşak müdahale.",
    CampaignSegment.NEVER_LOGGED_IN: "Kayıt olmuş ama hiç deneyimlememiş — onboarding daveti.",
    CampaignSegment.CUSTOM_PLAN: "Belirli bir plan kodunu hedefler — ileri seviye filtre.",
}


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"                 # Admin tasarlıyor, henüz başlatılmadı
    RUNNING = "running"             # Aktif — recipient'lara gönderildi
    PAUSED = "paused"               # Admin geçici durdurdu
    COMPLETED = "completed"         # Süresi doldu veya admin bitirdi
    CANCELLED = "cancelled"         # Admin başlamadan iptal etti


CAMPAIGN_STATUS_LABELS_TR: dict[CampaignStatus, str] = {
    CampaignStatus.DRAFT: "Taslak",
    CampaignStatus.RUNNING: "Çalışıyor",
    CampaignStatus.PAUSED: "Duraklatıldı",
    CampaignStatus.COMPLETED: "Tamamlandı",
    CampaignStatus.CANCELLED: "İptal edildi",
}


CAMPAIGN_STATUS_COLORS: dict[CampaignStatus, str] = {
    CampaignStatus.DRAFT: "slate",
    CampaignStatus.RUNNING: "emerald",
    CampaignStatus.PAUSED: "amber",
    CampaignStatus.COMPLETED: "indigo",
    CampaignStatus.CANCELLED: "slate",
}


class RecipientStatus(str, enum.Enum):
    """Bir recipient'in kampanyadaki durum noktası — funnel için."""
    TARGETED = "targeted"           # Listede ama henüz gönderilmedi
    SENT = "sent"                   # E-posta yollandı
    ACCEPTED = "accepted"           # Offer kabul edildi
    DECLINED = "declined"           # Offer reddedildi
    EXPIRED = "expired"             # Offer süresi doldu (cevap yok)
    BOUNCED = "bounced"             # E-posta gönderilemedi


RECIPIENT_STATUS_LABELS_TR: dict[RecipientStatus, str] = {
    RecipientStatus.TARGETED: "Hedefte",
    RecipientStatus.SENT: "Gönderildi",
    RecipientStatus.ACCEPTED: "Kabul",
    RecipientStatus.DECLINED: "Ret",
    RecipientStatus.EXPIRED: "Süre doldu",
    RecipientStatus.BOUNCED: "E-posta hata",
}


class Campaign(Base):
    """Toplu kampanya — segment + offer template + zaman penceresi + A/B varyant."""

    __tablename__ = "campaigns"
    __table_args__ = (
        Index("ix_campaigns_status", "status"),
        Index("ix_campaigns_segment", "segment"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    segment: Mapped[CampaignSegment] = mapped_column(
        Enum(CampaignSegment), nullable=False,
    )
    # CUSTOM_PLAN için plan kodu (örn. "solo_free")
    segment_filter_plan: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), nullable=False,
        default=CampaignStatus.DRAFT,
    )

    # --- Varyant A (zorunlu) ---
    variant_a_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    variant_a_title: Mapped[str] = mapped_column(String(255), nullable=False)
    variant_a_value: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    variant_a_duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variant_a_new_plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variant_a_public_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Varyant B (opsiyonel — A/B testi için) ---
    has_variant_b: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    variant_b_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variant_b_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    variant_b_value: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    variant_b_duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    variant_b_new_plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    variant_b_public_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Kampanya geçerlilik penceresi
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Her offer'ın geçerlilik süresi (gün)
    offer_expires_in_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=14,
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_user_id],
    )
    recipients: Mapped[list["CampaignRecipient"]] = relationship(
        "CampaignRecipient",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Campaign #{self.id} '{self.name}' "
            f"seg={self.segment.value} status={self.status.value}>"
        )


class CampaignRecipient(Base):
    """Bir kampanyadaki tek bir hedef (kurum veya bağımsız öğretmen + Offer)."""

    __tablename__ = "campaign_recipients"
    __table_args__ = (
        Index("ix_campaign_recipients_campaign", "campaign_id"),
        Index("ix_campaign_recipients_inst", "institution_id"),
        Index("ix_campaign_recipients_user", "user_id"),
        Index("ix_campaign_recipients_status", "campaign_id", "status"),
        CheckConstraint(
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
            name="ck_campaign_recipients_owner_xor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False,
    )
    owner_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        server_default=text("'institution'"),
    )
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True,
    )
    # A/B testinde hangi varyant gönderildi
    variant: Mapped[str] = mapped_column(
        String(1), nullable=False, default="A",
    )
    # Üretilen Offer (NULL = henüz launch edilmedi, sadece TARGETED)
    offer_id: Mapped[int | None] = mapped_column(
        ForeignKey("offers.id", ondelete="SET NULL"), nullable=True,
    )

    status: Mapped[RecipientStatus] = mapped_column(
        Enum(RecipientStatus), nullable=False,
        default=RecipientStatus.TARGETED,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    error_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="recipients",
    )
    institution: Mapped["Institution | None"] = relationship(
        "Institution", foreign_keys=[institution_id],
    )
    user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id],
    )
    offer: Mapped["Offer | None"] = relationship("Offer")

    @property
    def owner_id(self) -> int | None:
        return self.institution_id if self.owner_type == "institution" else self.user_id

    @property
    def owner_detail_url(self) -> str:
        oid = self.owner_id
        if self.owner_type == "institution":
            return f"/admin/revenue/institutions/{oid}"
        return f"/admin/revenue/users/{oid}"

    @property
    def owner_display_name(self) -> str:
        if self.owner_type == "institution" and self.institution is not None:
            return self.institution.name
        if self.owner_type == "user" and self.user is not None:
            return self.user.full_name or self.user.email
        return f"#{self.owner_id}" if self.owner_id else "—"

    def __repr__(self) -> str:
        return (
            f"<CampaignRecipient camp={self.campaign_id} "
            f"{self.owner_type}={self.owner_id} {self.variant} {self.status.value}>"
        )


__all__ = [
    "CAMPAIGN_RECIPIENT_OWNER_TYPES",
    "CAMPAIGN_SEGMENT_DESCRIPTIONS",
    "CAMPAIGN_SEGMENT_LABELS_TR",
    "CAMPAIGN_STATUS_COLORS",
    "CAMPAIGN_STATUS_LABELS_TR",
    "Campaign",
    "CampaignRecipient",
    "CampaignSegment",
    "CampaignStatus",
    "RECIPIENT_STATUS_LABELS_TR",
    "RecipientStatus",
]
