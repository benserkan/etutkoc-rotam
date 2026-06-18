from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.book import Book, BookSection
    from app.models.coach_work_block import CoachWorkBlock
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
    # Itemless (etkinlik/diğer) görevde öğrencinin çözdüğü soru sayısı. Kitap
    # kalemi olmayan görevlerde (Video/Özet/Tekrar/Diğer) öğrenci "olmayan
    # kitaptan test" gibi durumda çözdüğü soruyu girer → "çözülen test" hacmine
    # sayılır (görev kategorisi etkinlik kalır). Kalemli görevlerde kullanılmaz.
    solved_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Opsiyonel saat (0-23). NULL = saatsiz (eski davranış); set ise gün içi
    # sıralamada öncelik kazanır (hour NULLS LAST, order, id).
    scheduled_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Opsiyonel periyot (M6): "morning" | "noon" | "evening" | NULL.
    # NULL = period atanmamış. scheduled_hour'dan BAĞIMSIZ — koç açıkça seçer.
    # Hiç görev period dolu değilse öğrenci görünümü tek liste (geriye uyum).
    # En az 1 dolu ise 4 başlıklı bölüm: Sabah/Öğle/Akşam/Saatsiz.
    period: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Tip-spesifik bağlantı (video URL vb.). notes ise konu/açıklama için.
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Serbest iş bloğu bağı (Katman 3) — görev bir bloğa aitse blok "dağıtılan"a
    # sayar (görev planlananı). NULL = bağsız. Blok silinince SET NULL.
    work_block_id: Mapped[int | None] = mapped_column(
        ForeignKey("coach_work_blocks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Taslak/yayın mantığı: True iken görev sadece öğretmende görünür; False iken
    # öğrenci paneline iner ve veli duyurusuna aday olur. Smart default:
    # bugün/geçmiş tarihliler False, gelecek tarihliler True.
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Devret izi: görev, devret listesinden yeni haftaya taşınınca doldurulur →
    # listeden dinamik düşer; geçmiş program gezilirken "sonraki haftaya eklenmiş"
    # sayılır. NULL = henüz taşınmadı. Görev kaydı silinmez (geçmiş korunur).
    carried_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Devret kaynağı: bu görev başka bir görevden devredildiyse (devret listesinden
    # taşıma) kaynak görev id'si. Bu görev silinirse kaynağın carried_at'i temizlenir
    # → kaynak tekrar "tamamlanmayanlar" listesine döner (geri-al). Kaynak silinince
    # SET NULL.
    carried_from_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Bloğu silinmiş görev: Serbest Blok kitapsız kalem olarak saklanır; blok
    # silinince work_block_id NULL'a düşer ve kitapsız kalem yanlışlıkla DENEME
    # sınıflanırdı. True iken görev DENEME değil 'etkinlik/Diğer' sayılır (program
    # verisi değişmez). Blok silme + blok görevini carry ile taşıma bunu set eder.
    block_detached: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )

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
    work_block: Mapped["CoachWorkBlock | None"] = relationship(
        "CoachWorkBlock", back_populates="tasks", foreign_keys=[work_block_id]
    )

    def __repr__(self) -> str:
        return f"<Task {self.date} {self.title}>"


class TaskBookItem(Base):
    __tablename__ = "task_book_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Kitapsız "deneme" kalemi (tam LGS/TYT denemesi) için book/section NULL olabilir;
    # bu durumda label deneme adını taşır, rezerv/kapasite atlanır.
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    book_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_sections.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    planned_count: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wrong_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # "Ölü rezerv" izi: haftası/programı geçmiş tamamlanmamış görevin yapılmamış
    # rezerv kısmı serbest bırakılınca doldurulur (reconcile_past_reservations).
    # NULL = canlı rezerv; dolu = serbest bırakıldı → tekrar iade edilmez (görev
    # sonradan silinse bile çift-iade önlenir). Geçmiş kayıt (planned/completed)
    # DEĞİŞMEZ — yalnız rezerv kilidi kalkar.
    reservation_released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    task: Mapped["Task"] = relationship("Task", back_populates="book_items")
    book: Mapped["Book | None"] = relationship("Book")
    section: Mapped["BookSection | None"] = relationship("BookSection")

    def __repr__(self) -> str:
        return f"<TaskBookItem {self.planned_count} from section {self.book_section_id}>"
