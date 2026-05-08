from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.book import Book, BookSection
    from app.models.user import User


class StudentBook(Base):
    __tablename__ = "student_books"
    __table_args__ = (UniqueConstraint("student_id", "book_id", name="uq_student_book"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped["User"] = relationship(
        "User", back_populates="student_books", foreign_keys=[student_id]
    )
    book: Mapped["Book"] = relationship("Book", back_populates="student_books")
    section_progress: Mapped[list["SectionProgress"]] = relationship(
        "SectionProgress", back_populates="student_book", cascade="all, delete-orphan"
    )

    @property
    def total_tests(self) -> int:
        return self.book.total_tests

    @property
    def reserved_tests(self) -> int:
        return sum(p.reserved_count for p in self.section_progress)

    @property
    def completed_tests(self) -> int:
        return sum(p.completed_count for p in self.section_progress)

    @property
    def remaining_tests(self) -> int:
        return self.total_tests - self.reserved_tests - self.completed_tests


class SectionProgress(Base):
    __tablename__ = "section_progress"
    __table_args__ = (
        UniqueConstraint("student_book_id", "book_section_id", name="uq_section_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_book_id: Mapped[int] = mapped_column(
        ForeignKey("student_books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_section_id: Mapped[int] = mapped_column(
        ForeignKey("book_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reserved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    student_book: Mapped["StudentBook"] = relationship(
        "StudentBook", back_populates="section_progress"
    )
    section: Mapped["BookSection"] = relationship("BookSection")

    @property
    def remaining(self) -> int:
        return self.section.test_count - self.reserved_count - self.completed_count
