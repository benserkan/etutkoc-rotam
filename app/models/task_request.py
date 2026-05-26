from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.book import Book, BookSection
    from app.models.task import Task
    from app.models.user import User


class RequestType(str, enum.Enum):
    CHANGE = "change"      # Mevcut görevde sadece sayı değişikliği
    REPLACE = "replace"    # Mevcut görevin kaynağını/bölümünü tamamen değiştir
    REMOVE = "remove"      # Görevi tamamen çıkarma talebi
    ADD = "add"            # Yeni görev önerisi (öğrenci ekleme istiyor)
    QUESTION = "question"  # Soru/yorum — eylem gerektirmez


class RequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"  # öğrenci geri çekti
    RESOLVED = "resolved"    # soru cevaplandı, eylem yok


REQUEST_TYPE_LABELS: dict[RequestType, str] = {
    RequestType.CHANGE: "Sayı değiştir",
    RequestType.REPLACE: "Kaynağı değiştir",
    RequestType.REMOVE: "Çıkar",
    RequestType.ADD: "Ekle",
    RequestType.QUESTION: "Soru",
}

REQUEST_STATUS_LABELS: dict[RequestStatus, str] = {
    RequestStatus.PENDING: "Bekliyor",
    RequestStatus.APPROVED: "Onaylandı",
    RequestStatus.REJECTED: "Reddedildi",
    RequestStatus.WITHDRAWN: "Geri çekildi",
    RequestStatus.RESOLVED: "Cevaplandı",
}


class TaskRequest(Base):
    """Öğrencinin programa dair karşılıklı iletişim taleplerini tutar.

    Her TaskRequest bir talep durumudur:
    - CHANGE: mevcut bir Task üzerinde sayı/bölüm değişikliği talebi
    - REMOVE: mevcut bir Task'ın çıkarılması talebi
    - ADD: yeni bir görev önerisi (proposed_* alanlarıyla doldurulur)
    - QUESTION: açıklama/yorum (genel, eylem gerektirmez)

    Onay akışı: öğretmen approve → ilgili işlem otomatik uygulanır.
    """

    __tablename__ = "task_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Mevcut göreve referans (CHANGE / REMOVE / QUESTION-on-task için); ADD için NULL
    # ondelete=SET NULL: REMOVE talebi onaylanınca task silinir AMA request kalır
    # (status=approved, audit izi korunur). CASCADE iken endpoint db.refresh(req)
    # InvalidRequestError → HTTP 500 fırlatıyordu (26.05.2026 incidenti).
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )

    type: Mapped[RequestType] = mapped_column(Enum(RequestType), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False, index=True
    )

    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Önerilen alanlar (CHANGE veya ADD için bazıları doldurulur)
    proposed_book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True
    )
    proposed_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True
    )
    proposed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    proposed_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    teacher_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_id])
    task: Mapped["Task | None"] = relationship("Task", foreign_keys=[task_id])
    proposed_book: Mapped["Book | None"] = relationship("Book", foreign_keys=[proposed_book_id])
    proposed_section: Mapped["BookSection | None"] = relationship(
        "BookSection", foreign_keys=[proposed_section_id]
    )

    def __repr__(self) -> str:
        return f"<TaskRequest #{self.id} {self.type.value} {self.status.value}>"
