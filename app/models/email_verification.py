"""EmailVerificationToken — kayıt sonrası e-posta doğrulama (Dalga 7 P3).

Soft doğrulama: kullanıcı kayıt olur, hemen giriş yapar, panelde "e-postanı
doğrula" banner'ı görür. Doğrulama token'ı e-posta ile gönderilir; tüketildiğinde
User.email_verified_at dolar.

Token URL-safe: secrets.token_urlsafe(32). 7 gün geçerli, tek kullanımlık.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


EMAIL_VERIFICATION_TTL_DAYS = 7


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_email_verification_token"),
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


def default_verification_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=EMAIL_VERIFICATION_TTL_DAYS)
