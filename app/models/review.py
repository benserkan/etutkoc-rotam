"""Stage 12 — Spaced repetition (FSRS-light) modelleri.

ReviewCard: bir öğrencinin bir Topic için tekrar kartı. (student_id, topic_id)
unique. Stability/difficulty FSRS state'i tutar; due_at scheduling için.

ReviewLog: her tekrar olayının audit log'u. Algoritma değişikliği veya UX
analizi için before/after değerler.

Kartlar Topic'e bağlı çünkü:
- Mevcut sistemde "soru-cevap" yok, "test çözüldü" sayım var
- Topic kataloğu Subject altında hazır (Maarif/LGS/Klasik)
- BookSection.topic_id de zaten var → entegrasyon kolay

Öğretmen kartları "seed" eder (Subject'in tüm topic'lerini öğrenci için açar),
öğrenci dilediği vade gelen kartı tekrar eder.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.curriculum import Topic
    from app.models.user import User


# State sabitleri (services/fsrs.py ile aynı; tek kaynak orada ama burada
# kolay kullanım için referans).
STATE_NEW = "new"
STATE_LEARNING = "learning"
STATE_REVIEW = "review"
STATE_RELEARNING = "relearning"

STATE_LABELS_TR = {
    STATE_NEW: "Yeni",
    STATE_LEARNING: "Öğreniliyor",
    STATE_REVIEW: "Pekiştirme",
    STATE_RELEARNING: "Yeniden öğrenme",
}


class ReviewCard(Base):
    """Öğrenci × Topic için tekrar kartı (FSRS state)."""
    __tablename__ = "review_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # FSRS state
    stability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATE_NEW, index=True
    )

    # Scheduling
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Sayım
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lapse_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    # İlişkiler
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    topic: Mapped["Topic"] = relationship("Topic")
    logs: Mapped[list["ReviewLog"]] = relationship(
        "ReviewLog", back_populates="card",
        cascade="all, delete-orphan",
        order_by="ReviewLog.reviewed_at.desc()",
    )

    __table_args__ = (
        UniqueConstraint("student_id", "topic_id", name="uq_review_card_student_topic"),
        Index("ix_review_card_due", "student_id", "due_at"),
    )

    def __repr__(self) -> str:
        return f"<ReviewCard student={self.student_id} topic={self.topic_id} state={self.state}>"


class ReviewLog(Base):
    """Her tekrar olayının audit log'u."""
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(
        ForeignKey("review_cards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )

    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-4
    elapsed_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    scheduled_days: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    stability_before: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stability_after: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    difficulty_before: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    difficulty_after: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    state_before: Mapped[str] = mapped_column(String(16), nullable=False, default=STATE_NEW)
    state_after: Mapped[str] = mapped_column(String(16), nullable=False, default=STATE_NEW)

    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # İlişkiler
    card: Mapped["ReviewCard"] = relationship("ReviewCard", back_populates="logs")

    def __repr__(self) -> str:
        return f"<ReviewLog card={self.card_id} rating={self.rating}>"
