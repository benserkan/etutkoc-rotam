"""Generic telefon OTP doğrulama (P1 — 2026-05-30).

Tüm roller için tek tablo. `parent_phone_verifications` (veli-spesifik) ile
çakışmaz; o eski tablo yalnız `/parent/settings/whatsapp/*` akışında kullanılır
(deprecated; P1 sonrası bu akış da /me/phone/*'a yönlenecek).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class PhoneVerification(Base):
    """OTP doğrulama kaydı — SMS ile telefon doğrulamada kullanılır.

    Yaşam döngüsü:
      1. Kullanıcı /me/phone/start çağırır → kod üretilir, SMS atılır,
         buraya satır yazılır (consumed_at = NULL, expires_at = now + 10dk).
      2. /me/phone/verify çağırır → kod kontrol edilir, başarılıysa
         User.phone (veya phone_secondary, slot'a göre) güncellenir,
         consumed_at = now set edilir.
      3. 60sn cooldown: aynı user_id için son satır 60 saniyeden eskiyse
         yeni satır yazılabilir, eskisi (consumed_at = NULL) iptal edilir.
      4. attempts >= 5 olunca brute-force koruması: SUPPRESSED.
    """

    __tablename__ = "phone_verifications"
    __table_args__ = (
        Index("ix_phone_ver_user_created", "user_id", "created_at"),
        Index("ix_phone_ver_phone", "phone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)  # E.164
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    # "primary" | "secondary" — yalnız veli secondary kullanır
    slot: Mapped[str] = mapped_column(
        String(16), nullable=False, default="primary",
        server_default=sa_text("'primary'"),
    )
    # "sms" | "whatsapp" — P1: yalnız SMS desteklenir
    channel: Mapped[str] = mapped_column(
        String(16), nullable=False, default="sms",
        server_default=sa_text("'sms'"),
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
