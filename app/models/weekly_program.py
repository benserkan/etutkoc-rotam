"""WeeklyProgram — koç yeni program oluştur akışı (WP1, 2026-05-31).

Tasarım kararı: Task tablosuna program_id EKLEMEZ — geriye uyumluluk %100.
Program sadece "tarih aralığı kapısı": aktif program = today ∈ [start, end];
gösterilecek görevler = Task.date BETWEEN start AND end.

Gizlilik (KVKK): notes alanı koça özel; öğrenci/veli görmez (servis filter).

Kullanım:
  - Koç "Yeni Program Oluştur" → create_program(student, start, end, name)
  - Hafta sayfası açılır → get_active_program(student, today) → görevler süzülür
  - Bayram: yeni program → eski hâlâ erişilebilir, yeni aktif olur
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class WeeklyProgram(Base):
    __tablename__ = "weekly_programs"
    __table_args__ = (
        Index(
            "ix_weekly_programs_student_dates",
            "student_id", "start_date", "end_date",
        ),
        Index("ix_weekly_programs_coach_id", "coach_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Her ikisi DAHIL (closed range). Süre = (end - start).days + 1, 1-14 aralığı.
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Opsiyonel etiket: "Bayram Haftası", "Yarıyıl Tatili" gibi
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    student: Mapped["User"] = relationship(
        "User", foreign_keys=[student_id]
    )
    coach: Mapped["User | None"] = relationship(
        "User", foreign_keys=[coach_id]
    )

    @property
    def day_count(self) -> int:
        """Süre, her iki tarih dahil (start=end ise 1)."""
        return (self.end_date - self.start_date).days + 1

    @property
    def label(self) -> str:
        """Sayfada görünecek varsayılan etiket."""
        if self.name:
            return self.name
        return f"{self.start_date.isoformat()} – {self.end_date.isoformat()}"

    def contains(self, d: date) -> bool:
        """d bu programa düşer mi (her iki uç dahil)."""
        return self.start_date <= d <= self.end_date

    def __repr__(self) -> str:
        return (
            f"<WeeklyProgram id={self.id} student={self.student_id} "
            f"{self.start_date}→{self.end_date}>"
        )
