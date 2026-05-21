"""SystemSecret — süper admin tarafından yönetilen merkezi gizli ayarlar.

API anahtarları (Anthropic, OpenAI) gibi sistem geneli sırlar burada **şifreli**
saklanır. Süper admin paneliden girilir/güncellenir; tüm servisler buradan okur
(yoksa env fallback). Değer asla düz dönmez — yalnız maskeli gösterilir.

Şifreleme: Fernet (anahtar `settings.session_secret`'tan türetilir). session_secret
değişirse eski değerler çözülemez (super admin yeniden girer) — defansif.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemSecret(Base):
    __tablename__ = "system_secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SystemSecret {self.name}>"
