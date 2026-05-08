"""Invitation modeli — kurumsal davetiye akışı için.

Sprint 5 (multi-tenant signup) — bir kurum yöneticisi (veya süper admin) bir
öğretmen için davetiye linki üretir. Davetiye token'ı tek seferlik;
kullanıldığında consumed_at ve consumed_by_user_id dolar.

Token URL-safe: secrets.token_urlsafe(32) → ~43 char base64.

İleride ücretli üyelik akışında bu model:
- Token süresi dolarsa "ödeme bekliyor" durumu
- Ödeme tamamlanınca token aktif olur
- Token kullanılınca hesap oluşur

Şu an: süre 7 gün, ödeme yok.
"""

from __future__ import annotations

import enum
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import UserRole

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.user import User


# Davetiye varsayılan geçerlilik süresi
INVITATION_TTL_DAYS = 7


class InvitationStatus(str, enum.Enum):
    PENDING = "pending"      # henüz kullanılmadı, süresi geçmedi
    CONSUMED = "consumed"    # kullanıldı (consumed_at dolu)
    EXPIRED = "expired"      # süresi geçti (expires_at < now, consumed_at null)
    REVOKED = "revoked"      # admin tarafından iptal edildi


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        UniqueConstraint("token", name="uq_invitation_token"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # URL-güvenli rastgele token (secrets.token_urlsafe ile üretilir)
    token: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Davetiye için pre-fill bilgileri (kullanıcı düzenleyebilir)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Yaratılacak kullanıcının rolü (şu an sadece TEACHER ve INSTITUTION_ADMIN)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    # Hangi kuruma bağlanacak (NULL = bağımsız teacher davetiyesi — nadir)
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Davetiyeyi kim oluşturdu (admin/institution_admin)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consumed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    institution: Mapped["Institution | None"] = relationship(
        "Institution", foreign_keys=[institution_id]
    )

    @property
    def status(self) -> InvitationStatus:
        if self.consumed_at is not None:
            return InvitationStatus.CONSUMED
        if self.revoked_at is not None:
            return InvitationStatus.REVOKED
        now = datetime.now(timezone.utc)
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            return InvitationStatus.EXPIRED
        return InvitationStatus.PENDING

    @property
    def is_usable(self) -> bool:
        return self.status == InvitationStatus.PENDING

    def __repr__(self) -> str:
        return f"<Invitation {self.email} role={self.role.value} status={self.status.value}>"


def default_expiry() -> datetime:
    """Davetiye için yeni expires_at değeri."""
    return datetime.now(timezone.utc) + timedelta(days=INVITATION_TTL_DAYS)
