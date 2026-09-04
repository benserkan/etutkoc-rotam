"""Öğrenci sınıf dönemleri (2026-09-04).

Bir öğrenci sınıf atladığında geçmiş yılın verisi (görev/deneme/kitap) yerinde
kalır; hangi döneme ait olduğu **tarihinden** çözülür. Bu tablo yalnız SINIRI
kaydeder — veri satırlarına kolon eklenmez, hiçbir kayıt taşınmaz/silinmez.

Sınır kuralı (`grade_period_service.compute_boundary`):
    başlangıç = min(yükseltme tarihi, aynı takvim yılının 1 Eylül'ü)
Böylece geç yükseltme (10 Ekim → 1 Eylül'e çekilir; Eylül-Ekim görevleri yeni
sınıfa yazılır) ve erken yükseltme (15 Temmuz yaz kampı → 15 Temmuz kalır; yaz
çalışması eski sınıfa karışmaz) aynı formülle doğru sonuç verir.

`ended_on IS NULL` = güncel dönem. Her öğrencinin en fazla bir güncel dönemi olur.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StudentGradePeriod(Base):
    """Öğrencinin bir sınıf/öğretim dönemi (8. sınıf 2025-26 gibi)."""

    __tablename__ = "student_grade_periods"
    __table_args__ = (
        Index("ix_sgp_student_started", "student_id", "started_on"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Dönem başındaki profil anlık görüntüsü (öğrenci sonradan değişse de
    # geçmiş dönem doğru etiketlenir).
    grade_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_graduate: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    # CurriculumModel.value (lgs | maarif_lise | klasik_lise) — düz VARCHAR:
    # PG native enum yükü yok, ileride yeni model eklemek migration istemez.
    curriculum_model: Mapped[str | None] = mapped_column(String(32), nullable=True)
    track: Mapped[str | None] = mapped_column(String(16), nullable=True)
    academic_year_id: Mapped[int | None] = mapped_column(
        ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True
    )

    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    # NULL = güncel dönem (henüz kapanmadı)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped["User"] = relationship(  # noqa: F821
        "User", foreign_keys=[student_id]
    )

    @property
    def is_current(self) -> bool:
        return self.ended_on is None

    @property
    def grade_label(self) -> str:
        if self.is_graduate:
            return "Mezun"
        if self.grade_level is None:
            return "—"
        return f"{self.grade_level}. Sınıf"
