"""StudentDayNote — öğrencinin gün-bazlı serbest düşünce notu (autosave).

Öğrenci /student/day'de o günün akışına dair serbest yorum yazar; her yazışta
otomatik kaydedilir (buton yok). Koç salt-okuma görür. (student_id, date) unique.
"""
from __future__ import annotations

from datetime import date as _date, datetime

from sqlalchemy import (
    Date, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StudentDayNote(Base):
    __tablename__ = "student_day_notes"
    __table_args__ = (
        UniqueConstraint("student_id", "date", name="uq_student_day_note"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[_date] = mapped_column(Date, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
