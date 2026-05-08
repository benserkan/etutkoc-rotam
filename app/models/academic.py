from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ExamTarget(str, enum.Enum):
    """Akademik yılın hedef sınavı.

    LGS  : 8. sınıf merkezi sınav, Haziran sonunda.
    YKS  : 12. sınıf + mezun, Haziran ortasında (TYT + AYT).
    NONE : Sınav yok (5-7 ve 9-11 ara sınıflar). UI'da "Yıl sonu" gösterilir.
    """
    LGS = "lgs"
    YKS = "yks"
    NONE = "none"


EXAM_TARGET_LABELS: dict[ExamTarget, str] = {
    ExamTarget.LGS: "LGS",
    ExamTarget.YKS: "YKS",
    ExamTarget.NONE: "Yıl Sonu",
}


class AcademicPhaseKind(str, enum.Enum):
    """Akademik yıl içinde dönem tipi.

    REGULAR       : Olağan okul dönemi — okul saati düşülür, hafta içi yoğun.
    WINTER_BREAK  : Yarıyıl tatili — okul yok, kısa hafta, yaz kampına benzer.
    SUMMER_CAMP   : Yaz kampı — okul yok, hafta sonu da çalışma, yoğun program.
    EXAM_PREP     : Sınav hazırlık dönemi — son N hafta, deneme ağırlıklı.
    """
    REGULAR = "regular"
    WINTER_BREAK = "winter_break"
    SUMMER_CAMP = "summer_camp"
    EXAM_PREP = "exam_prep"


ACADEMIC_PHASE_KIND_LABELS: dict[AcademicPhaseKind, str] = {
    AcademicPhaseKind.REGULAR: "Olağan Dönem",
    AcademicPhaseKind.WINTER_BREAK: "Yarıyıl Tatili",
    AcademicPhaseKind.SUMMER_CAMP: "Yaz Kampı",
    AcademicPhaseKind.EXAM_PREP: "Sınav Hazırlık",
}

# UI rozeti için kısa etiket + emoji
ACADEMIC_PHASE_KIND_BADGES: dict[AcademicPhaseKind, str] = {
    AcademicPhaseKind.REGULAR: "📚 Olağan",
    AcademicPhaseKind.WINTER_BREAK: "❄️ Tatil",
    AcademicPhaseKind.SUMMER_CAMP: "🌞 Yaz Kampı",
    AcademicPhaseKind.EXAM_PREP: "🎯 Sınav Hazırlık",
}

# Plan motoru kapasite çarpanı: günlük öneri sayısı bu çarpanla ölçeklendirilir.
# Yaz kampı + tatil: okul yok, öğrenci daha çok zaman ayırır → kapasite arttı.
# Sınav hazırlık: son haftalar yoğunlaştırılır.
ACADEMIC_PHASE_CAPACITY_MULTIPLIER: dict[AcademicPhaseKind, float] = {
    AcademicPhaseKind.REGULAR: 1.0,
    AcademicPhaseKind.WINTER_BREAK: 1.4,
    AcademicPhaseKind.SUMMER_CAMP: 1.5,
    AcademicPhaseKind.EXAM_PREP: 1.3,
}

# Yaz kampı/tatil dönemlerinde hafta sonları da çalışma günü kabul edilir;
# olağan dönemde hafta sonu kapasite normal, suggestion engine geçmiş
# desenden öğrenir. Bu flag "okul yok" sinyali olarak kullanılır.
ACADEMIC_PHASE_NO_SCHOOL: dict[AcademicPhaseKind, bool] = {
    AcademicPhaseKind.REGULAR: False,
    AcademicPhaseKind.WINTER_BREAK: True,
    AcademicPhaseKind.SUMMER_CAMP: True,
    AcademicPhaseKind.EXAM_PREP: False,
}


class AcademicYear(Base):
    __tablename__ = "academic_years"
    __table_args__ = (UniqueConstraint("teacher_id", "name", name="uq_academic_year_teacher_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    # Akademik yılın temsil ettiği Eylül-yılı (örn "2025-2026" → 2025).
    # Maarif/Klasik kohort tahmininde kullanılır: öğrencinin grade_level +
    # academic_year.start_year'dan implicit "9'a giriş yılı" türetilir.
    start_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Hedef sınav. Mevcut yıllar migration'da LGS varsayılır (geriye uyum).
    exam_target: Mapped[ExamTarget] = mapped_column(
        Enum(ExamTarget), nullable=False, server_default=ExamTarget.LGS.name
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    students: Mapped[list["User"]] = relationship(
        "User", back_populates="academic_year", foreign_keys="User.academic_year_id"
    )
    phases: Mapped[list["AcademicPhase"]] = relationship(
        "AcademicPhase",
        back_populates="academic_year",
        cascade="all, delete-orphan",
        order_by="AcademicPhase.start_date",
    )

    @property
    def exam_label(self) -> str:
        """UI metinleri için kısa etiket: 'LGS', 'YKS', 'Yıl Sonu'."""
        return EXAM_TARGET_LABELS.get(self.exam_target, "—")

    def active_phase_on(self, day: date) -> "AcademicPhase | None":
        """Verilen tarihte aktif olan phase'i döndür (yoksa None).

        Birden fazla phase aralığa girerse start_date'i en geç olanı tercih
        et (overlap durumunda en yeni dönemi öncelikle).
        """
        candidates = [p for p in self.phases if p.start_date <= day <= p.end_date]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.start_date)

    def __repr__(self) -> str:
        return f"<AcademicYear {self.name}>"


class AcademicPhase(Base):
    """Akademik yıl içinde tanımlanmış zaman dilimi.

    Örnek kullanım:
      - "1. Dönem"       (REGULAR, Eyl-Oca)
      - "Yarıyıl Tatili" (WINTER_BREAK, ~2 hafta Şub başı)
      - "2. Dönem"       (REGULAR, Şub-Haz)
      - "Yaz Kampı"      (SUMMER_CAMP, Haz-Ağu)
      - "Sınav Hazırlık" (EXAM_PREP, sınav öncesi son ~6 hafta)

    Plan motoru ileride bu phase'leri günlük kapasite hesabında kullanabilir
    (örn yaz kampında okul saati düşülmez). Şu anda görünür gösterim için.
    """

    __tablename__ = "academic_phases"
    __table_args__ = (
        Index("ix_academic_phase_year", "academic_year_id"),
        Index("ix_academic_phase_dates", "start_date", "end_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[AcademicPhaseKind] = mapped_column(
        Enum(AcademicPhaseKind), nullable=False, default=AcademicPhaseKind.REGULAR
    )
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    academic_year: Mapped["AcademicYear"] = relationship(
        "AcademicYear", back_populates="phases"
    )

    @property
    def kind_label(self) -> str:
        return ACADEMIC_PHASE_KIND_LABELS.get(self.kind, "—")

    @property
    def kind_badge(self) -> str:
        return ACADEMIC_PHASE_KIND_BADGES.get(self.kind, "—")

    @property
    def capacity_multiplier(self) -> float:
        """Plan motoru kapasite çarpanı (günlük öneri sayısını ölçekler)."""
        return ACADEMIC_PHASE_CAPACITY_MULTIPLIER.get(self.kind, 1.0)

    @property
    def is_no_school(self) -> bool:
        """Bu phase okul-tatili mi? (Yaz kampı + Yarıyıl tatili → True)"""
        return ACADEMIC_PHASE_NO_SCHOOL.get(self.kind, False)

    def __repr__(self) -> str:
        return f"<AcademicPhase {self.name} {self.kind.value}>"
