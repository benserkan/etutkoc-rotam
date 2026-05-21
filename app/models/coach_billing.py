"""Bağımsız koç ↔ öğrenci tahsilatı (KS2).

Koç parayı genelde öğrenci/veliden elden, aylık biriktirilmiş olarak alır.
Bu modül koç↔öğrenci ilişkisidir — admin tarafındaki platform↔koç `Invoice`
(Owner-pattern) ile KARIŞTIRILMAMALI.

- `CoachStudentRate`: öğrenci başına seans ücreti (tek satır/öğrenci, upsert).
- `CoachPayment`: alınan ödeme kaydı (tutar, tarih, yöntem, hangi ay).

Aylık hesap modelde DEĞİL — hesaplanır: o ay status=DONE seans × ücret − ödenen.
Erişim: yalnız o koç (sahiplik 404). KVKK: ticari kişisel veri, koça özel.
"""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

if TYPE_CHECKING:
    pass

from app.database import Base


class CoachPaymentMethod(str, enum.Enum):
    CASH = "cash"          # elden / nakit
    TRANSFER = "transfer"  # havale/EFT
    OTHER = "other"


COACH_PAYMENT_METHOD_LABELS: dict[CoachPaymentMethod, str] = {
    CoachPaymentMethod.CASH: "Nakit / elden",
    CoachPaymentMethod.TRANSFER: "Havale / EFT",
    CoachPaymentMethod.OTHER: "Diğer",
}


class CoachStudentRate(Base):
    __tablename__ = "coach_student_rates"
    __table_args__ = (
        UniqueConstraint("student_id", name="uq_coach_student_rate_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Seans başına ücret (TL, tam sayı yeterli)
    session_fee: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )


class CoachPayment(Base):
    __tablename__ = "coach_payments"
    __table_args__ = (
        Index("ix_coach_payment_student_period", "student_id", "period_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[CoachPaymentMethod] = mapped_column(
        Enum(CoachPaymentMethod), nullable=False,
        server_default=CoachPaymentMethod.CASH.name,
    )
    # Hangi ayı kapatıyor — "YYYY-MM" (aylık hesapla eşleşir)
    period_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
