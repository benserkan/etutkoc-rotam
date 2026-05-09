"""Stage 9 (Faz 2) — Add-on (ek paket) sistemi.

Kullanıcı veya kurum, ana planına ek olarak şu paketleri satın alabilir:
- WhatsApp Veli Paketi (500 mesaj/ay)
- AI Plus (+1000 kredi/ay)
- Veli Portalı erişimi (Solo planlarında ücretli)

Add-on aktifken:
- WhatsApp paketi aktif ise: parent_notifications_whatsapp feature flag
  KAPALI olsa bile bu kuruma açık sayılır + ek WhatsApp mesaj kotası
- AI Plus aktif ise: aylık kredi havuzuna +1000 eklenir
- Veli Portalı aktif ise: parent panel açılır

Add-on'lar aylık dönemde tüketilir; her ayın 1'inde yenilenir (cron).
İptal anında ay sonuna kadar geçerli kalır.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AddonKind(str, enum.Enum):
    WHATSAPP_PARENT = "whatsapp_parent"   # 500 WhatsApp mesajı/ay
    AI_PLUS = "ai_plus"                    # +1000 kredi/ay
    PARENT_PORTAL = "parent_portal"        # Veli paneli erişimi


ADDON_LABELS_TR: dict[AddonKind, str] = {
    AddonKind.WHATSAPP_PARENT: "WhatsApp Veli Paketi",
    AddonKind.AI_PLUS: "AI Plus (Ekstra Kredi)",
    AddonKind.PARENT_PORTAL: "Veli Portalı",
}

ADDON_DESCRIPTIONS_TR: dict[AddonKind, str] = {
    AddonKind.WHATSAPP_PARENT:
        "Velilere otomatik WhatsApp bildirimleri (haftalık rapor, performans uyarıları, "
        "öğretmen notları). Aylık 500 mesaj kotası dahil.",
    AddonKind.AI_PLUS:
        "Yapay zeka önerilerini sınırsızca kullanmak için aylık 1000 ekstra kredi. "
        "Kitap şablonu önerisi, öğrenci performans analizi gibi özelliklerde harcanır.",
    AddonKind.PARENT_PORTAL:
        "Velilere kendi panelinde çocuğunun haftalık raporlarını ve performans grafiklerini "
        "görme yetkisi (Solo planlarında ek paket; Pro+ planlarında dahildir).",
}

# Aylık fiyat (Türk Lirası, KDV dahil)
ADDON_MONTHLY_PRICE_TRY: dict[AddonKind, int] = {
    AddonKind.WHATSAPP_PARENT: 99,
    AddonKind.AI_PLUS: 149,
    AddonKind.PARENT_PORTAL: 49,
}

# Add-on'un ek olarak verdiği kredi/mesaj kotası
ADDON_MONTHLY_QUOTA: dict[AddonKind, dict[str, int]] = {
    AddonKind.WHATSAPP_PARENT: {"whatsapp_messages": 500},
    AddonKind.AI_PLUS: {"credits": 1000},
    AddonKind.PARENT_PORTAL: {},   # özellik açma — kotasız
}


class Addon(Base):
    """Bir kuruma veya bağımsız öğretmene ait aktif/iptal edilmiş add-on kaydı.

    UNIQUE(owner_type, owner_id, addon_kind, period_start) — aynı dönem
    için aynı add-on'dan iki adet alınamaz.

    İptal akışı: cancelled_at set edilir, ama period_end'e kadar geçerli
    kalır. Sonraki dönemde yenilenmez.
    """
    __tablename__ = "addons"
    __table_args__ = (
        UniqueConstraint(
            "owner_type", "owner_id", "addon_kind", "period_start",
            name="uq_addon_owner_kind_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    addon_kind: Mapped[AddonKind] = mapped_column(
        Enum(AddonKind), nullable=False,
    )

    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    # Auto-renew açıksa period bitiminde yeni dönem başlar; cancelled_at
    # set edilirse kapanır.
    auto_renew: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # İptali kim yaptı (admin tarafından mı, kullanıcı mı)
    cancelled_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    # Aylık fiyat (snapshot — paket fiyatı sonradan değişirse bu satıra
    # yansımasın diye)
    price_try: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Ek bağlam (kampanya kodu, hediye kapsamı vb.)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    @property
    def is_active(self) -> bool:
        """Add-on'un şu anda etkin olduğunu kontrol et."""
        from datetime import timezone as _tz
        now = datetime.now(_tz.utc)
        period_end = self.period_end
        if period_end and period_end.tzinfo is None:
            period_end = period_end.replace(tzinfo=_tz.utc)
        return period_end is not None and period_end > now

    def __repr__(self) -> str:
        return (
            f"<Addon {self.owner_type}#{self.owner_id} "
            f"{self.addon_kind.value} until {self.period_end}>"
        )
