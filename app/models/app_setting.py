"""AppSetting — süper admin tarafından düzenlenebilen genel JSON ayarları.

Sır DEĞİL (API anahtarları için `system_secret` var, şifreli). Burada fiyat/üyelik
yapılandırması gibi düz config JSON tutulur. Kod default + DB override deseni:
ayar yoksa kod varsayılanı geçerli; süper admin kaydedince override devreye girer.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<AppSetting {self.key}>"
