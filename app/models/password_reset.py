"""PasswordResetToken — self-service şifre sıfırlama (Dalga 7 P2).

Kullanıcı "şifremi unuttum" derse e-posta adresine tek-kullanımlık, kısa ömürlü
(60 dk) bir token gönderilir. Token tüketildiğinde (consumed_at) veya süresi
geçtiğinde geçersizdir.

Güvenlik:
- Token URL-safe: secrets.token_urlsafe(32) → ~43 char base64.
- Tek kullanımlık (consumed_at dolunca tekrar kullanılamaz).
- E-posta enumeration koruması: endpoint, kullanıcı var/yok ayrımı yapmaz
  (her zaman generic yanıt; token yalnız gerçek hesap için üretilir/gönderilir).
- requested_ip audit için saklanır.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# Sıfırlama tokenı geçerlilik süresi (dakika)
PASSWORD_RESET_TTL_MINUTES = 60


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_password_reset_token"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    @property
    def is_usable(self) -> bool:
        if self.consumed_at is not None:
            return False
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp > datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<PasswordResetToken user={self.user_id} usable={self.is_usable}>"


def default_reset_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)
