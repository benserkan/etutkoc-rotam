"""TaskTemplate — öğretmenin sık kullandığı görev kalıbı (görev şablonu).

BookTemplate (kitabın bölüm yapısı) ile KARIŞTIRILMAMALI. Görev şablonu, bir
görevin kalemlerini (kitap + bölüm + test sayısı) kaydeder; haftalık/günlük
plana eklerken 'Şablondan' ile tek tıkla aynı görev oluşturulur.

Öğretmen-düzeyinde (teacher_id) — öğretmenin tüm öğrencilerinde yeniden kullanılır
(öğrencinin ilgili kitabı atanmışsa). Uygulama anında normal görev-ekleme
doğrulamaları çalışır (kitap sahipliği + bölüm uyumu + öğrenci ataması + rezerv).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.task import TaskType

if TYPE_CHECKING:
    from app.models.book import Book, BookSection
    from app.models.user import User


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False, default=TaskType.TEST)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_id])
    items: Mapped[list["TaskTemplateItem"]] = relationship(
        "TaskTemplateItem",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="TaskTemplateItem.id",
    )

    def __repr__(self) -> str:
        return f"<TaskTemplate #{self.id} {self.name!r}>"


class TaskTemplateItem(Base):
    __tablename__ = "task_template_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("task_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    book_section_id: Mapped[int] = mapped_column(
        ForeignKey("book_sections.id", ondelete="CASCADE"), nullable=False
    )
    planned_count: Mapped[int] = mapped_column(Integer, nullable=False)

    template: Mapped["TaskTemplate"] = relationship("TaskTemplate", back_populates="items")
    book: Mapped["Book"] = relationship("Book", foreign_keys=[book_id])
    section: Mapped["BookSection"] = relationship("BookSection", foreign_keys=[book_section_id])

    def __repr__(self) -> str:
        return f"<TaskTemplateItem #{self.id} tpl={self.template_id}>"
