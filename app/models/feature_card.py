"""Katman 1 — Özellik Kataloğu (Feature Catalog).

Sistemde tanıtıma değer her özelliğin (Rotam, Veli Bildirimleri, AYT Alan
Filtresi, vb.) tek satırda toplandığı katalog. Anasayfa kartları, demo
linkleri, hedef rol/alan sınıflandırması, yayın durumu hep buradan beslenir.

Sonraki katmanlar (skorlama, telemetri, öğrenen seçici) bu satırlara EK
tablolar koyacak — bu modele dokunmazlar.

Tasarım kararları (2026-05-14):
- slug UNIQUE → URL parçası + programatik referans (ör. "rotam", "daily-plan")
- target_roles / benefits / pain_points → JSON Text (project konvansiyonu;
  sa.JSON yerine Text + json.dumps/loads app katmanında)
- domain / tier / status → String kolonu (SystemAnnouncement kalıbı; alembic
  enum migration ağrısını yaratmaz, label dict ayrı)
- demo_slug nullable; varsa "Demo İzle" butonu /demos?play={slug}'a gider.
  Yoksa buton render edilmez.
- Skorlama/telemetri/embedding alanları YOK — kendi katmanlarında ayrı tablo.
- Tenant bazlı görünürlük YOK — kart tanıtım amaçlı, herkese aynı (feature_flag
  ayrı bir mekanizma).
- "Yakında" durumu YOK — DRAFT görünmez, PUBLISHED görünür.
"""

from __future__ import annotations

import enum
import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import UserRole


# ---------------------------- Enum'lar ----------------------------


class FeatureDomain(str, enum.Enum):
    """Özelliğin hitap ettiği alan."""
    LGS = "lgs"
    YKS = "yks"
    KURUMSAL = "kurumsal"
    VELI = "veli"
    GENEL = "genel"
    MOBIL = "mobil"


class FeatureTier(str, enum.Enum):
    """Özellik düzeyi — kart önemini sınıflar."""
    CORE = "core"                # Ana kabiliyet (Rotam, Görev dağıtımı)
    ENHANCEMENT = "enhancement"   # Mevcut özelliğin iyileştirmesi
    EXPERIMENTAL = "experimental" # Deneysel, geri çekilebilir


class FeatureStatus(str, enum.Enum):
    """Yayın durumu — anasayfa görünürlüğünü belirler."""
    DRAFT = "draft"             # Çalışılıyor, görünmez
    PUBLISHED = "published"     # Canlı — anasayfada gösterilir
    HIDDEN = "hidden"           # Geçici gizli (canlı ama gösterme)
    DEPRECATED = "deprecated"   # Kullanım dışı, arşiv


FEATURE_DOMAIN_LABELS_TR: dict[FeatureDomain, str] = {
    FeatureDomain.LGS: "LGS",
    FeatureDomain.YKS: "YKS",
    FeatureDomain.KURUMSAL: "Kurumsal",
    FeatureDomain.VELI: "Veli",
    FeatureDomain.GENEL: "Genel",
    FeatureDomain.MOBIL: "Mobil",
}

FEATURE_TIER_LABELS_TR: dict[FeatureTier, str] = {
    FeatureTier.CORE: "Ana Kabiliyet",
    FeatureTier.ENHANCEMENT: "İyileştirme",
    FeatureTier.EXPERIMENTAL: "Deneysel",
}

FEATURE_STATUS_LABELS_TR: dict[FeatureStatus, str] = {
    FeatureStatus.DRAFT: "Taslak",
    FeatureStatus.PUBLISHED: "Yayında",
    FeatureStatus.HIDDEN: "Gizli",
    FeatureStatus.DEPRECATED: "Kaldırıldı",
}

# Status badge renkleri (Tailwind token'ı)
FEATURE_STATUS_BADGES: dict[FeatureStatus, str] = {
    FeatureStatus.DRAFT: "slate",
    FeatureStatus.PUBLISHED: "emerald",
    FeatureStatus.HIDDEN: "amber",
    FeatureStatus.DEPRECATED: "rose",
}


# ---------------------------- Tablo ----------------------------


class FeatureCard(Base):
    """Tanıtıma değer bir özelliğin katalog kaydı.

    Anasayfa kartı render etmek için gereken tüm görsel + sınıflandırma +
    yönetim alanlarını tutar. Skorlama/öğrenme verisi YOK (Katman 5-7).
    """
    __tablename__ = "feature_cards"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_feature_card_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # --- Kimlik ---
    # URL-güvenli benzersiz isim; programatik referans (örn. demo slug ile aynı olabilir)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)

    # Anasayfa kart rozeti — kategori ipucu (örn. "📅 GÜNLÜK ROTA")
    # category_icon: emoji veya küçük karakter ("📅", "🧠", "⚠️")
    # category_label: rozet metni; render'da UPPERCASE'e çevrilir
    category_icon: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="✨",
    )
    category_label: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="",
    )

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    # Anasayfa kart açıklama paragrafı — <strong> ve <em> destekler.
    # Migration p4l1o3m4n22h ile 240→400 char (paragraf için yer açıldı).
    tagline: Mapped[str] = mapped_column(
        String(400), nullable=False, server_default="",
    )
    # Detay sayfasında veya tooltip'te kullanılır — anasayfa kartında GÖRÜNMEZ
    description_md: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="",
    )

    # --- Görsel ---
    # Lucide ikon adı (örn. "compass", "sparkles", "users")
    icon: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="sparkles",
    )
    # Kart üst şerit rengi; Tailwind token veya hex
    accent_color: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="#3b82f6",
    )

    # --- İçerik listeleri (JSON-as-Text) ---
    # ["student","teacher","parent","institution_admin","super_admin"]
    target_roles_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="[]",
    )
    # "Bu özelliğin sağladıkları" — kısa madde listesi
    benefits_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="[]",
    )
    # "Hangi sorunu çözüyor" — kısa madde listesi
    pain_points_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="[]",
    )

    # --- Demo bağlantısı ---
    # /demos?play={demo_slug} — boşsa "Demo İzle" butonu gizlenir
    demo_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Demo butonu yanında küçük etiket (örn. "2 dk · 8 sahne") — boş bırakılabilir
    demo_duration_label: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Anasayfa sağ-yan görsel şablon referansı — app/services/mockup_registry.py
    # içinde kayıtlı key (örn. "daily_schedule", "fsrs_rating"). Boşsa
    # görsel render edilmez. Yeni mockup eklemek için: registry'ye kayıt yap.
    mockup_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # --- Sınıflandırma (String'de tutulur, enum_enum property'leri ile parse) ---
    domain: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="genel",
    )
    tier: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="enhancement",
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="draft",
    )

    # --- Tarih/kaynak ---
    introduced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    # Katman 3 auto-discovery dolduracak
    introduced_in_commit: Mapped[str | None] = mapped_column(
        String(40), nullable=True,
    )
    pr_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- Kürasyon ---
    # 1 (düşük öncelik) - 5 (kritik strateji). Katman 5 skorlamada kullanılacak.
    strategic_priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("3"),
    )
    manual_pin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("0"),
    )
    pin_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    manual_hide: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("0"),
    )

    # --- CTA ---
    cta_label: Mapped[str] = mapped_column(
        String(80), nullable=False, server_default="Detayları gör",
    )
    cta_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # --- Audit ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    # ---------------------- JSON yardımcıları ----------------------

    @property
    def target_roles(self) -> list[str]:
        try:
            return list(json.loads(self.target_roles_json or "[]"))
        except (TypeError, ValueError):
            return []

    @target_roles.setter
    def target_roles(self, value: list) -> None:
        cleaned: list[str] = []
        for v in value or []:
            if isinstance(v, UserRole):
                cleaned.append(v.value)
            elif isinstance(v, str):
                cleaned.append(v)
        self.target_roles_json = json.dumps(cleaned, ensure_ascii=False)

    @property
    def benefits(self) -> list[str]:
        try:
            return list(json.loads(self.benefits_json or "[]"))
        except (TypeError, ValueError):
            return []

    @benefits.setter
    def benefits(self, value: list[str]) -> None:
        cleaned: list[str] = []
        for s in (value or []):
            t = str(s).strip()
            if t:
                cleaned.append(t)
        self.benefits_json = json.dumps(cleaned, ensure_ascii=False)

    @property
    def pain_points(self) -> list[str]:
        try:
            return list(json.loads(self.pain_points_json or "[]"))
        except (TypeError, ValueError):
            return []

    @pain_points.setter
    def pain_points(self, value: list[str]) -> None:
        cleaned: list[str] = []
        for s in (value or []):
            t = str(s).strip()
            if t:
                cleaned.append(t)
        self.pain_points_json = json.dumps(cleaned, ensure_ascii=False)

    # ---------------------- Enum property'leri ----------------------

    @property
    def domain_enum(self) -> FeatureDomain:
        try:
            return FeatureDomain(self.domain)
        except ValueError:
            return FeatureDomain.GENEL

    @property
    def tier_enum(self) -> FeatureTier:
        try:
            return FeatureTier(self.tier)
        except ValueError:
            return FeatureTier.ENHANCEMENT

    @property
    def status_enum(self) -> FeatureStatus:
        try:
            return FeatureStatus(self.status)
        except ValueError:
            return FeatureStatus.DRAFT

    # ---------------------- Görünürlük yardımcıları ----------------------

    def is_visible_on_homepage(self) -> bool:
        """Anasayfada gösterilebilir mi? PUBLISHED + manual_hide=False."""
        if self.manual_hide:
            return False
        return self.status_enum == FeatureStatus.PUBLISHED

    def is_pinned(self, now: datetime | None = None) -> bool:
        """Manuel sabitlenmiş ve süresi dolmamış mı?"""
        if not self.manual_pin:
            return False
        if self.pin_until is None:
            return True  # süresiz sabit
        if now is None:
            now = datetime.now(timezone.utc)
        pu = self.pin_until
        if pu.tzinfo is None:
            pu = pu.replace(tzinfo=timezone.utc)
        return pu > now

    def __repr__(self) -> str:
        return f"<FeatureCard {self.slug} status={self.status}>"
