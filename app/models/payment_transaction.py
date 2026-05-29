"""PaymentTransaction — self-serve ödeme akışı (Ödeme Paket Ö1).

Iyzico Checkout Form akışı: koç /teacher/plan'da paket seçer → bu satır
`pending` olarak yaratılır + Iyzico'ya init request gider → Iyzico
`paymentPageUrl` döner → koç oraya yönlenir (3DS) → Iyzico bizim
`payment_callback_url`'imize geri redirect eder + `token` ile → biz
Iyzico'dan ödeme durumunu çekeriz → `status` güncellenir →
`succeeded` ise `change_plan` çağrılır.

Provider-agnostic: provider='iyzico'|'shopier'|'manual'. Manuel (admin elle
aktive et) için de satır açılabilir, ama şimdilik sadece iyzico kullanır.

Idempotency: aynı `provider_reference` (Iyzico conversationId) ile birden çok
callback gelebilir; servis son satırı bulup `status` zaten succeeded ise
no-op yapar.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# Durum kodları — String enum yerine sabit ile (migration kolaylığı).
STATUS_PENDING = "pending"
STATUS_3DS_PENDING = "3ds_pending"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_EXPIRED = "expired"
STATUS_REFUNDED = "refunded"

# Sağlayıcı kodları
PROVIDER_IYZICO = "iyzico"
PROVIDER_SHOPIER = "shopier"
PROVIDER_MANUAL = "manual"

# Ödeme döngüsü
CYCLE_MONTHLY = "monthly"
CYCLE_ANNUAL = "annual"
CYCLE_ONE_TIME = "one_time"


STATUS_LABELS_TR: dict[str, str] = {
    STATUS_PENDING: "Bekliyor",
    STATUS_3DS_PENDING: "3D Secure bekliyor",
    STATUS_SUCCEEDED: "Başarılı",
    STATUS_FAILED: "Başarısız",
    STATUS_EXPIRED: "Süresi doldu",
    STATUS_REFUNDED: "İade edildi",
}


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # iyzico'da bu conversationId (bizim ürettiğimiz UUID).
    # Iyzico'nun döndürdüğü paymentId'yi raw_response içinde saklarız.
    provider_reference: Mapped[str | None] = mapped_column(
        String(200), nullable=True, index=True,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="TRY")

    plan_code: Mapped[str] = mapped_column(String(50), nullable=False)
    cycle: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_PENDING, index=True,
    )
    status_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    raw_request: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Bu ödeme bir PaymentLink üzerinden mi tetiklendi? (kurum akışı)
    payment_link_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_links.id", ondelete="SET NULL"), nullable=True,
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])

    @property
    def is_terminal(self) -> bool:
        """Status değişmeyecek mi (succeeded/failed/expired/refunded)?"""
        return self.status in {
            STATUS_SUCCEEDED, STATUS_FAILED, STATUS_EXPIRED, STATUS_REFUNDED,
        }
