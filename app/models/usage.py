"""Stage 6 — kullanım ölçümü ve kredi sistemi.

Kiro tarzı kredi soyutlaması: AI/email/WhatsApp çağrıları, kullanıcıya token
yerine "kredi" olarak gösterilir. Plan başına aylık kota; aşıma yaklaşınca
uyarı, aşımda kurum için manuel hard-block, bağımsız öğretmen için 5 saat
soğuma.

İki tablo:
- UsageEvent: append-only event log (kim, ne, ne kadar, ne zaman)
- CreditAccount: aylık snapshot (allocated/used/blocked) — sahip+period UNIQUE

Polymorphic owner: owner_type='institution' | 'user', owner_id=ilgili PK.
- Kurum içi (institution_admin/teacher/student): owner=institution
- Bağımsız öğretmen (institution_id=NULL teacher): owner=user
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UsageOwnerType(str, enum.Enum):
    INSTITUTION = "institution"
    USER = "user"


class UsageKind(str, enum.Enum):
    """Kredi tüketen çağrı tipleri.

    Yeni bir tip eklerken `app/services/credits.py:KIND_CREDITS` map'ine de
    kredi maliyeti ekle — yoksa default 1 kredi alınır (defansif).
    """
    AI_BOOK_TEMPLATE = "ai_book_template"   # Claude — kitap şablonu önerisi
    AI_INSIGHTS = "ai_insights"             # Claude — öğrenci performans analizi
    AI_SESSION_CAPTURE = "ai_session_capture"  # Gemini vision — foto seans yakalama (KS3a)
    AI_SESSION_VOICE = "ai_session_voice"   # (eski) sesli yapılandırma — yerini AI_TRANSCRIBE aldı
    AI_TRANSCRIBE = "ai_transcribe"         # Gemini — alan dikte (saf ses→metin, KS3b)
    AI_COACHING_INSIGHT = "ai_coaching_insight"  # Gemini — seans geçmişi → koçluk içgörüsü (KS4)
    AI_PARENT_INSIGHT = "ai_parent_insight"  # Gemini — konu perf + deneme → veli içgörüsü (P2b)
    AI_CAREER_SYNTHESIS = "ai_career_synthesis"  # Gemini — anket sonuçları + akademik veri → kariyer önerisi
    EMAIL_SEND = "email_send"               # SMTP/SendGrid e-posta
    WHATSAPP_SEND = "whatsapp_send"         # Meta Cloud API mesaj
    OTHER = "other"


USAGE_KIND_LABELS_TR: dict[UsageKind, str] = {
    UsageKind.AI_BOOK_TEMPLATE: "AI Kitap Şablonu",
    UsageKind.AI_INSIGHTS: "AI Performans Analizi",
    UsageKind.AI_SESSION_CAPTURE: "AI Seans Yakalama (Foto)",
    UsageKind.AI_SESSION_VOICE: "AI Seans Yakalama (Ses)",
    UsageKind.AI_TRANSCRIBE: "AI Sesli Dikte",
    UsageKind.AI_COACHING_INSIGHT: "AI Koçluk İçgörüsü",
    UsageKind.AI_PARENT_INSIGHT: "AI Veli İçgörüsü",
    UsageKind.AI_CAREER_SYNTHESIS: "AI Kariyer Sentezi",
    UsageKind.EMAIL_SEND: "E-posta",
    UsageKind.WHATSAPP_SEND: "WhatsApp Mesajı",
    UsageKind.OTHER: "Diğer",
}


class UsageEvent(Base):
    """Append-only kullanım kayıtları — billing/audit için.

    Her satır tek bir çağrıyı temsil eder. Geriye dönük rapor + hata ayıklama
    için ham log; CreditAccount.used_credits bu tablodan agrega edilir.
    """
    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_owner_time",
              "owner_type", "owner_id", "occurred_at"),
        Index("ix_usage_events_owner_period",
              "owner_type", "owner_id", "period_year_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[UsageOwnerType] = mapped_column(
        Enum(UsageOwnerType), nullable=False,
    )
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # native Postgres ENUM DEĞİL → plain VARCHAR. Yeni UsageKind değerleri
    # (AI_*) migration/ALTER TYPE gerektirmeden çalışır; "invalid input value
    # for enum usagekind" 500'leri önlenir. SQLAlchemy üye ADINI saklar
    # (create_constraint=False → CHECK yok), mevcut prod verisiyle tutarlı.
    kind: Mapped[UsageKind] = mapped_column(
        Enum(UsageKind, native_enum=False, create_constraint=False, length=40),
        nullable=False,
    )
    credits: Mapped[int] = mapped_column(Integer, nullable=False)

    # 'YYYY-MM' formatı — CreditAccount.period_year_month ile join + hızlı agrega
    period_year_month: Mapped[str] = mapped_column(
        String(7), nullable=False, index=True,
    )

    # Hangi çağrı, kaç token, hangi kullanıcı tetikledi vb. — JSON olarak.
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Bu event'i tetikleyen aktör (kullanıcı). Kurum hesabında bile
    # "hangi öğretmen tetikledi" sorusunu cevaplamak için. NULL = sistem cron.
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<UsageEvent {self.owner_type.value}#{self.owner_id} "
            f"{self.kind.value} {self.credits}c>"
        )


class CreditAccount(Base):
    """Aylık kredi bakiyesi — sahip + period başına 1 satır.

    Her ayın 1'inde cron yeni period için satır oluşturur (refill).
    `used_credits` event'ler atomik artırılır; `allocated_credits` plana göre
    set edilir + super admin manuel bonus ekleyebilir.

    Hard-block: super admin manuel toggle (varsayılan kapalı kurum için).
    Bağımsız öğretmen için %100'e ulaşınca otomatik blocked_until=now+5h
    set edilir; süre dolunca otomatik resume (sorgu zamanında kontrol).
    """
    __tablename__ = "credit_accounts"
    __table_args__ = (
        UniqueConstraint(
            "owner_type", "owner_id", "period_year_month",
            name="uq_credit_account_owner_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[UsageOwnerType] = mapped_column(
        Enum(UsageOwnerType), nullable=False, index=True,
    )
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    period_year_month: Mapped[str] = mapped_column(
        String(7), nullable=False,  # 'YYYY-MM'
    )

    # Plan'dan gelen taban + super admin manuel bonus dahil toplam tahsis
    allocated_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Bu ay kullanılmış toplam kredi (UsageEvent.credits toplamı)
    used_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Super admin manuel eklediği bonus kredi (ayrı izleme — UI'da göster)
    bonus_credits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Plan kodu (snapshot — kurumun planı sonradan değişirse bu period için
    # ne ile başladığını görmek için). 'free' | 'starter' | 'professional' | custom
    plan_code: Mapped[str] = mapped_column(String(32), nullable=False, default="free")

    # %80 uyarısı bu period'da gönderildi mi — tek seferlik
    warn_80_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Super admin tarafından manuel etkinleştirilen sert blok (kurumlar için).
    # Default kapalı — kurumu rahatsız etmemek için sadece manuel açılır.
    hard_block_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )

    # Bağımsız öğretmen %100'e ulaşınca otomatik set edilir; süre dolana kadar
    # yeni kredi tüketen çağrı reddedilir. Süre dolunca otomatik unblock.
    blocked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ----- Hesaplanmış property'ler -----

    @property
    def total_allocated(self) -> int:
        """Tahsis + bonus toplamı — UI'da 'kullanılabilir tavan'."""
        return self.allocated_credits + self.bonus_credits

    @property
    def remaining_credits(self) -> int:
        """Kalan kredi (negatif olabilir — aşım durumunda)."""
        return self.total_allocated - self.used_credits

    @property
    def usage_pct(self) -> int:
        """0-100+ kullanım yüzdesi (aşımda 100'ün üstüne çıkabilir)."""
        if self.total_allocated <= 0:
            return 0
        return int(round(100 * self.used_credits / self.total_allocated))

    def is_currently_blocked(self, now: datetime | None = None) -> bool:
        """Şu an blok aktif mi (hard-block veya cooldown)."""
        if self.hard_block_enabled:
            return True
        if self.blocked_until is None:
            return False
        if now is None:
            from datetime import timezone
            now = datetime.now(timezone.utc)
        bu = self.blocked_until
        if bu.tzinfo is None:
            from datetime import timezone
            bu = bu.replace(tzinfo=timezone.utc)
        return bu > now

    def __repr__(self) -> str:
        return (
            f"<CreditAccount {self.owner_type.value}#{self.owner_id} "
            f"{self.period_year_month} {self.used_credits}/{self.total_allocated}>"
        )
