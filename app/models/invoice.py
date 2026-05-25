"""Sprint A.2 (Ticari Pano 2.0 — Faz F kısmi) — Owner faturaları.

Ödeme takvimi panelini gerçek veriyle besler. Her aktif ödeyen "owner"
(Institution veya bağımsız öğretmen User) için periyodik fatura kaydı tutulur.

**Owner pattern (Sprint F.3'te genişletildi):** Mevcut kayıtlar institution'a
aitti — `owner_type='institution'` ile devam eder. Bağımsız öğretmen
(role=TEACHER + institution_id=NULL) için `owner_type='user'` + `user_id`
doldurulur. XOR check ile tam birinin set olması zorunlu.

Status:
  - pending / paid / overdue / failed / refunded / cancelled

Stripe/Paykasa entegrasyonu eklendiğinde provider_invoice_id,
gateway_response_json gibi alanlar eklenebilir.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.user import User


INVOICE_OWNER_TYPES = ("institution", "user")


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"          # Vadesi gelmedi, bekliyor
    PAID = "paid"                # Ödendi
    OVERDUE = "overdue"          # Vade geçti, ödenmedi
    FAILED = "failed"            # Tahsilat başarısız
    REFUNDED = "refunded"        # İade edildi
    CANCELLED = "cancelled"      # Admin iptal etti


# UI sözlüğü
INVOICE_STATUS_LABELS_TR: dict[InvoiceStatus, str] = {
    InvoiceStatus.PENDING: "Bekliyor (vade gelmedi)",
    InvoiceStatus.PAID: "Ödendi",
    InvoiceStatus.OVERDUE: "Gecikti",
    InvoiceStatus.FAILED: "Tahsilat başarısız",
    InvoiceStatus.REFUNDED: "İade",
    InvoiceStatus.CANCELLED: "İptal",
}

INVOICE_STATUS_BADGE_COLOR: dict[InvoiceStatus, str] = {
    InvoiceStatus.PENDING: "slate",
    InvoiceStatus.PAID: "emerald",
    InvoiceStatus.OVERDUE: "rose",
    InvoiceStatus.FAILED: "rose",
    InvoiceStatus.REFUNDED: "amber",
    InvoiceStatus.CANCELLED: "slate",
}


class PaymentMethod(str, enum.Enum):
    CARD = "card"                # Kredi kartı (otomatik tahsilat)
    BANK_TRANSFER = "bank_transfer"  # EFT/Havale (manuel)
    MANUAL = "manual"            # Admin tarafından elle "ödenmiş" işaretlendi


PAYMENT_METHOD_LABELS_TR: dict[PaymentMethod, str] = {
    PaymentMethod.CARD: "Kredi kartı",
    PaymentMethod.BANK_TRANSFER: "EFT / Havale",
    PaymentMethod.MANUAL: "Manuel kayıt",
}


class Invoice(Base):
    """Owner faturası — ödeme takvimi ve dunning için temel kayıt.
    Owner = Institution veya bağımsız öğretmen User (XOR)."""

    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_institution_status", "institution_id", "status"),
        Index("ix_invoices_user_status", "user_id", "status"),
        # ix_invoices_due_at: due_at kolonunda index=True ile zaten üretiliyor —
        # açık tanım çift indeks (create_all'da "already exists") yapıyordu, kaldırıldı.
        Index("ix_invoices_status_due", "status", "due_at"),
        CheckConstraint(
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
            name="ck_invoices_owner_xor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'institution'"),
    )
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    # Bu faturanın hangi paket için kesildiği (Institution.plan zaman içinde
    # değişebilir, fatura kesim anındaki plan kodu burada saklanır).
    plan: Mapped[str] = mapped_column(String(32), nullable=False)
    # Ücret tutarı — TL, kuruşsuz (örn. 2999). İndirim uygulandıysa burası
    # net tutar; gross_amount_try ek alan ise ileride eklenebilir.
    amount_try: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), nullable=False, default=InvoiceStatus.PENDING,
    )

    # Dönem aralığı (örn. 2026-09-01 → 2026-10-01)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    # Vade — ödeme bu tarihte beklenir
    due_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    # Tahsilat zamanı (paid_at = NULL → henüz ödenmedi)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    payment_method: Mapped[PaymentMethod | None] = mapped_column(
        Enum(PaymentMethod), nullable=True,
    )
    # Otomatik denenme sayısı (dunning için)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Dunning aşaması: hangi hatırlatmaya gönderildi (D-7, D-3, D-1, D+1, D+3, D+7)
    last_reminder_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_reminder_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Admin notları (manuel iptal sebebi, ödeme ertelemesi vb.)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Arşivleme (soft archive) — 3 yıldan eski kayıtlar veya admin manuel arşiv
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    archived_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    archive_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    institution: Mapped["Institution | None"] = relationship(
        "Institution", foreign_keys=[institution_id],
    )
    owner_user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id],
    )

    @property
    def owner_id(self) -> int:
        """Owner ID (institution_id veya user_id — XOR ile tam biri set)."""
        return self.institution_id if self.owner_type == "institution" else self.user_id

    @property
    def owner_detail_url(self) -> str:
        """Owner detay sayfası (ticari 360)."""
        if self.owner_type == "institution":
            return f"/admin/revenue/institutions/{self.institution_id}"
        return f"/admin/revenue/users/{self.user_id}"

    def __repr__(self) -> str:
        return (
            f"<Invoice #{self.id} owner={self.owner_type}:{self.owner_id} "
            f"{self.amount_try}₺ {self.status.value} due={self.due_at}>"
        )


__all__ = [
    "INVOICE_OWNER_TYPES",
    "INVOICE_STATUS_BADGE_COLOR",
    "INVOICE_STATUS_LABELS_TR",
    "Invoice",
    "InvoiceStatus",
    "PAYMENT_METHOD_LABELS_TR",
    "PaymentMethod",
]
