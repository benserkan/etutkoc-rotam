"""PaymentLink — süper admin tarafından oluşturulan ödeme linki (Paket Ö2a).

Kurum self-serve ödeme yapamaz çünkü kurum fiyatları "özel teklif" olabilir
(Enterprise tier null monthly_total döner). Süper admin elle tutar + plan
girerek link oluşturur → kuruma e-posta/WhatsApp ile gönderir → kurum
yöneticisi linke tıklar, login olur, "Şimdi Öde" der → Iyzico Checkout
→ ödeme tamam → plan aktive + link `consumed` işaretlenir.

Owner-agnostic: target_owner_type 'institution' veya 'user' (bağımsız koç).
Şu an pratikte yalnız kurum için kullanılıyor, koç self-serve akışıyla
ödüyor; ama future-proof olarak ikisini de destekliyor (manuel teklif
indirimi, mentorluk geçici paket vs.).

Yaşam döngüsü:
  active → consumed (başarılı ödeme)
  active → expired (cron + expires_at)
  active → cancelled (admin elle iptal)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.payment_transaction import PaymentTransaction
    from app.models.user import User


LINK_STATUS_ACTIVE = "active"
LINK_STATUS_CONSUMED = "consumed"
LINK_STATUS_EXPIRED = "expired"
LINK_STATUS_CANCELLED = "cancelled"

LINK_OWNER_INSTITUTION = "institution"
LINK_OWNER_USER = "user"

LINK_STATUS_LABELS_TR: dict[str, str] = {
    LINK_STATUS_ACTIVE: "Aktif (ödeme bekliyor)",
    LINK_STATUS_CONSUMED: "Ödendi",
    LINK_STATUS_EXPIRED: "Süresi doldu",
    LINK_STATUS_CANCELLED: "İptal edildi",
}


class PaymentLink(Base):
    __tablename__ = "payment_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 32-char hex (uuid4) — public URL'in token'ı: /payment/link/{token}
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    target_owner_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_owner_id: Mapped[int] = mapped_column(nullable=False, index=True)

    plan_code: Mapped[str] = mapped_column(String(50), nullable=False)
    cycle: Mapped[str] = mapped_column(String(20), nullable=False)  # monthly | annual

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")

    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=LINK_STATUS_ACTIVE, index=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    consumed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    consumed_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True,
    )
    created_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    consumed_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[consumed_by_user_id],
    )
    created_by_admin: Mapped["User | None"] = relationship(
        foreign_keys=[created_by_admin_id],
    )
    consumed_transaction: Mapped["PaymentTransaction | None"] = relationship(
        foreign_keys=[consumed_transaction_id],
    )

    @property
    def is_usable(self) -> bool:
        """Bu link ödemeye uygun mu? (active + süresi geçmemiş)"""
        if self.status != LINK_STATUS_ACTIVE:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True

    @property
    def status_resolved(self) -> str:
        """expires_at geçmişse 'expired' döndür (DB henüz cron'la güncellenmemiş olabilir)."""
        if self.status == LINK_STATUS_ACTIVE and self.expires_at and self.expires_at < datetime.utcnow():
            return LINK_STATUS_EXPIRED
        return self.status
