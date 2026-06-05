"""SignupPhoneVerification — hesap OLUŞMADAN ÖNCE telefon OTP'si (#5 telefon kapısı).

Mevcut PhoneVerification user_id'ye bağlı (hesap-sonrası). Signup'ta kullanıcı henüz
yok → telefon-anahtarlı bu tablo. Kapı yalnız SMS_ENABLED iken kullanılır (DORMANT
until SMS OTP paketi). 6 haneli kod, 10dk TTL, 5 deneme, tek kullanım.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SignupPhoneVerification(Base):
    __tablename__ = "signup_phone_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False, default="sms")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
