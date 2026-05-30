"""WhatsApp şablon registry (P2 — 2026-05-30).

Manuel Click-to-WhatsApp Faz 1'in temeli: koç/kurum yön./süper admin tek tık
ile şablondan veliye/öğrenciye/öğretmene mesaj gönderir. Şablonlar DB'de,
süper admin tarafından düzenlenebilir. 35 önceden tanımlı şablon idempotent
seed scripti ile yüklenir; sonraki seed çalışmaları kullanıcı edit'lerini
EZMEZ (key varsa atla).

Click-to-WA URL üretimi (P3), tekli/toplu gönderim UI (P4-P5), audit + spam
guard (P6) ayrı paketlerde ele alınır.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# Kategori sabitleri — kullanıcı tipine göre gruplandırma
CATEGORY_VELI = "veli"
CATEGORY_OGRENCI = "ogrenci"
CATEGORY_KURUM_OGRETMEN = "kurum_ogretmen"
CATEGORY_KURUM_VELI = "kurum_veli"
CATEGORY_KURUM_OGRENCI = "kurum_ogrenci"
CATEGORY_ADMIN_YONETICI = "admin_yonetici"
CATEGORY_ADMIN_SISTEM = "admin_sistem"

ALL_CATEGORIES = (
    CATEGORY_VELI,
    CATEGORY_OGRENCI,
    CATEGORY_KURUM_OGRETMEN,
    CATEGORY_KURUM_VELI,
    CATEGORY_KURUM_OGRENCI,
    CATEGORY_ADMIN_YONETICI,
    CATEGORY_ADMIN_SISTEM,
)

CATEGORY_LABELS_TR: dict[str, str] = {
    CATEGORY_VELI: "Koç → Veli",
    CATEGORY_OGRENCI: "Koç → Öğrenci",
    CATEGORY_KURUM_OGRETMEN: "Kurum → Öğretmen",
    CATEGORY_KURUM_VELI: "Kurum → Veli (toplu)",
    CATEGORY_KURUM_OGRENCI: "Kurum → Öğrenci (toplu)",
    CATEGORY_ADMIN_YONETICI: "Süper Admin → Yönetici/Koç",
    CATEGORY_ADMIN_SISTEM: "Süper Admin → Sistem geneli",
}

# Hedef rol — şablonu kim kullanır (UI filter + yetki)
TARGET_TEACHER = "teacher"
TARGET_INSTITUTION_ADMIN = "institution_admin"
TARGET_SUPER_ADMIN = "super_admin"
TARGET_ANY = "any"  # birden fazla rol kullanır (UI'da filtrelenmez)

ALL_TARGET_ROLES = (TARGET_TEACHER, TARGET_INSTITUTION_ADMIN, TARGET_SUPER_ADMIN, TARGET_ANY)

TARGET_ROLE_LABELS_TR: dict[str, str] = {
    TARGET_TEACHER: "Koç / Öğretmen",
    TARGET_INSTITUTION_ADMIN: "Kurum Yöneticisi",
    TARGET_SUPER_ADMIN: "Süper Admin",
    TARGET_ANY: "Hepsi",
}


class WhatsAppTemplate(Base):
    """WhatsApp Click-to-WA şablonu — DB'de yönetilir, süper admin CRUD'lar."""

    __tablename__ = "whatsapp_templates"
    __table_args__ = (
        Index("ix_wat_category_sort", "category", "sort_order"),
        Index("ix_wat_target_role", "target_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    target_role: Mapped[str] = mapped_column(
        String(40), nullable=False, default=TARGET_ANY,
        server_default=sa_text("'any'"),
    )
    name_tr: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=sa_text("''"),
    )
    # Değişkenli metin — örn. "Merhaba {{veli_adi}}, {{ogrenci_adi}} bu hafta..."
    content_template: Mapped[str] = mapped_column(Text, nullable=False)
    # JSON list[{key,label_tr,example}] — önizleme + UI etiket için
    variables_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default=sa_text("'[]'"),
    )
    # Tarih seçici gerekli mi (toplantı/etkinlik şablonları için)
    requires_date: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=sa_text("false"),
    )
    # Toplu gönderim için uygun mu (bayram/duyuru gibi)
    allow_bulk: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=sa_text("false"),
    )
    # Koç ekstra serbest metin ekleyebilir mi
    allow_freeform_note: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=sa_text("false"),
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, default=100, nullable=False, server_default=sa_text("100"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=sa_text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    updated_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[updated_by_id]
    )
