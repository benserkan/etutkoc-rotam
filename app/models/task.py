from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.book import Book, BookSection
    from app.models.user import User


class TaskType(str, enum.Enum):
    TEST = "test"
    VIDEO = "video"
    OZET = "ozet"
    TEKRAR = "tekrar"
    OTHER = "other"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


TASK_TYPE_LABELS: dict[TaskType, str] = {
    TaskType.TEST: "Test",
    TaskType.VIDEO: "Video İzleme",
    TaskType.OZET: "Özet Çıkarma",
    TaskType.TEKRAR: "Konu Tekrarı",
    TaskType.OTHER: "Diğer",
}


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False, default=TaskType.TEST)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped["User"] = relationship(
        "User", back_populates="tasks", foreign_keys=[student_id]
    )
    book_items: Mapped[list["TaskBookItem"]] = relationship(
        "TaskBookItem", back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Task {self.date} {self.title}>"


class TaskBookItem(Base):
    __tablename__ = "task_book_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    book_section_id: Mapped[int] = mapped_column(
        ForeignKey("book_sections.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    planned_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wrong_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    task: Mapped["Task"] = relationship("Task", back_populates="book_items")
    book: Mapped["Book"] = relationship("Book")
    section: Mapped["BookSection"] = relationship("BookSection")

    def __repr__(self) -> str:
        return f"<TaskBookItem {self.planned_count} from section {self.book_section_id}>"
