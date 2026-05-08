from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.book import Book, BookSection
    from app.models.user import User


class FeedbackAction(str, enum.Enum):
    REJECTED = "rejected"
    # Kabul gerçek Task'a dönüştüğü için ayrıca kaydedilmiyor;
    # ileride "örtük kabul" sinyali için ACCEPTED da kullanılabilir.
    ACCEPTED = "accepted"


class SuggestionFeedback(Base):
    """Öğretmenin bir öneri için verdiği manuel geribildirim (özellikle ret).

    Aynı (öğrenci, kitap, bölüm, haftagünü, aksiyon) için tekil kayıt; tekrar
    reddedilirse `created_at` güncellenir. Tarih bozunumu (decay) motor
    tarafında hesaplanır — eski kayıtlar zamanla etkisiz kalır.
    """

    __tablename__ = "suggestion_feedback"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "book_id",
            "book_section_id",
            "day_of_week",
            "action",
            name="uq_feedback_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_section_id: Mapped[int] = mapped_column(
        ForeignKey("book_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 0-6 veya NULL (genel red, spesifik güne değil)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[FeedbackAction] = mapped_column(
        Enum(FeedbackAction), nullable=False, default=FeedbackAction.REJECTED
    )
    count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
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
    book: Mapped["Book"] = relationship("Book", foreign_keys=[book_id])
    section: Mapped["BookSection"] = relationship("BookSection", foreign_keys=[book_section_id])

    def __repr__(self) -> str:
        return f"<SuggestionFeedback student={self.student_id} book={self.book_id} sec={self.book_section_id} dow={self.day_of_week} {self.action.value}>"
