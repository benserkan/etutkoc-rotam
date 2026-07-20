"""Bağımsız çalışma kayıtları (self-study).

Tatil/koçsuz dönemde öğrencinin program DIŞINDA kendi başına çözdüğü testlerin
izli kaydı. Eski anonim "öğrenci zaten çözmüştü" sayacının (SectionProgress.
completed_count'u doğrudan ezme) yerine geçer:

- Öğrenci BEYAN eder (status=pending, ilerlemeye dokunmaz) → koç onaylar
  (uygulanır) ya da reddeder.
- Koç doğrudan girebilir (source=coach, anında onaylı+uygulanır) — ama artık
  kim/ne zaman/ne kadar izi kalır (kurum şeffaflığı, Faz 2 raporu buradan okur).

Uygulama anında bölümün boş kapasitesine (test − rezerv − çözülmüş) KIRPILIR;
uygulanan miktar applied_count'ta saklanır → silme/geri alma birebir tersine
çevrilebilir. SectionProgress.manual_count bu yolla eklenen toplamı taşır
(completed = görevle çözülen + manual).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Kaynak: kaydı kim oluşturdu
SS_SOURCE_STUDENT = "student"  # öğrenci beyanı (koç onayı bekler)
SS_SOURCE_COACH = "coach"      # koç girişi (anında onaylı)

# Durum yaşam döngüsü
SS_STATUS_PENDING = "pending"
SS_STATUS_APPROVED = "approved"
SS_STATUS_REJECTED = "rejected"

SS_SOURCE_LABELS_TR = {
    SS_SOURCE_STUDENT: "Öğrenci beyanı",
    SS_SOURCE_COACH: "Koç girişi",
}
SS_STATUS_LABELS_TR = {
    SS_STATUS_PENDING: "Onay bekliyor",
    SS_STATUS_APPROVED: "Onaylandı",
    SS_STATUS_REJECTED: "Reddedildi",
}


class SelfStudyEntry(Base):
    __tablename__ = "self_study_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_book_id: Mapped[int] = mapped_column(
        ForeignKey("student_books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_section_id: Mapped[int] = mapped_column(
        ForeignKey("book_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_count: Mapped[int] = mapped_column(Integer, nullable=False)
    applied_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=SS_STATUS_PENDING, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    student = relationship("User", foreign_keys=[student_id])
    student_book = relationship("StudentBook")
    section = relationship("BookSection")
    created_by = relationship("User", foreign_keys=[created_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
