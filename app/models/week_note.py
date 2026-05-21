"""Haftalık program notları.

Öğretmen, öğrencinin haftalık programına bağlı serbest hatırlatma maddeleri
yazar ("Haftaya kalemtraş getir", "TYT denemesi getir" gibi). Her madde
ayrı satır; sırası `order` ile sabit. Öğrenci öğrenci panelinde okur,
yazdırılan haftalık programda da görünür.

Hafta tanımı: `week_start` öğrencinin anchor bloğundaki ilk gündür
(`_student_week_start(student, target)`). Aynı (student_id, week_start)
için birden çok madde olabilir — birden çok kayıt eklenir.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class WeekNote(Base):
    """Öğrencinin bir haftasına bağlı tek madde (madde madde liste kaydı)."""

    __tablename__ = "week_notes"
    __table_args__ = (
        Index("ix_week_notes_student_week", "student_id", "week_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])

    def __repr__(self) -> str:
        return f"<WeekNote student={self.student_id} week={self.week_start} body={self.body[:30]!r}>"
