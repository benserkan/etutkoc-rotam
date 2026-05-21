"""ExamResult — öğrencinin girdiği deneme sınavı sonucu (KP4 — Akademik Çıktı).

Koç (öğretmen) öğrencisinin deneme sonucunu girer: doğru/yanlış/boş sayıları +
opsiyonel ders kırılımı. Net, sınav türüne göre otomatik hesaplanır.

Net hesabı (Türk sınav sistemi):
- LGS: 3 yanlış 1 doğruyu götürür → net = D - Y/3
- YKS (TYT/AYT_*): 4 yanlış 1 doğruyu götürür → net = D - Y/4

Tasarım kararları (2026-05-20):
- subject_nets: JSON metin (ders kırılımı listesi). Native JSON yerine Text —
  audit_logs.details_json deseni; serialize/deserialize servis katmanında.
- created_by_id NULL olabilir (öğretmen silinirse kayıt korunur, SET NULL).
- student_id CASCADE: öğrenci silinince deneme geçmişi de gider.
- net float olarak saklanır (D - Y/penalty); kurum panosu (KP4b) bunu agregeler.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.curriculum import ExamSection

if TYPE_CHECKING:
    from app.models.user import User


def section_penalty(section: ExamSection) -> int:
    """Yanlış cezası katsayısı: kaç yanlış 1 doğruyu götürür."""
    return 3 if section == ExamSection.LGS else 4


def compute_net(correct: int, wrong: int, section: ExamSection) -> float:
    """net = doğru - yanlış/ceza. Negatife düşmez (taban 0)."""
    raw = correct - (wrong / section_penalty(section))
    return round(max(raw, 0.0), 2)


class ExamResult(Base):
    __tablename__ = "exam_results"
    __table_args__ = (
        Index("ix_exam_result_student_date", "student_id", "exam_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    section: Mapped[ExamSection] = mapped_column(Enum(ExamSection), nullable=False)

    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_wrong: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_blank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Ders kırılımı — JSON metin: [{"name", "correct", "wrong", "blank", "net"}]
    subject_nets: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped["User"] = relationship(
        "User", foreign_keys=[student_id]
    )

    def __repr__(self) -> str:
        return f"<ExamResult s={self.student_id} {self.section.value} net={self.net}>"
