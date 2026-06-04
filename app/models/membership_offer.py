from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# Teklif tipi + durum sabitleri (gösterim amaçlı; backend mantığını etkilemez).
MEMBERSHIP_OFFER_TYPES = ("new", "renewal")
MEMBERSHIP_OFFER_STATUSES = ("active", "accepted", "cancelled", "expired")
# completion: None | requested (talep bıraktı) | havale_claimed (ödedim dedi) | activated


class MembershipOffer(Base):
    """Süper adminin WhatsApp ile gönderdiği üyelik teklifi (yeni üyelik/yenileme).

    Token bazlı public link → markalı sayfa → kullanıcı "Üye ol/Yenile" talebi
    bırakır veya havale/EFT ile ödediğini bildirir → süper admin manuel aktive
    eder. (İleride Iyzico kart + WhatsApp Cloud API ile genişler.)
    """

    __tablename__ = "membership_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    offer_type: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    plan_code: Mapped[str] = mapped_column(String(40), nullable=False)
    cycle: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    completion: Mapped[str | None] = mapped_column(String(20), nullable=True)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contact_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("contact_requests.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    target_user: Mapped["User | None"] = relationship("User", foreign_keys=[target_user_id])

    def __repr__(self) -> str:
        return f"<MembershipOffer {self.id} {self.token[:8]} {self.plan_code} {self.status}>"
