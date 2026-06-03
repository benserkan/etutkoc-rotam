from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.curriculum import Subject
    from app.models.task import Task
    from app.models.user import User


# Birim sabitleri (gösterim amaçlı — backend mantığını etkilemez).
WORK_BLOCK_UNITS = ("test", "soru", "deneme")
# Durum sabitleri.
WORK_BLOCK_STATUSES = ("active", "done", "archived")


class CoachWorkBlock(Base):
    """Koçun tanımladığı serbest iş bloğu (Katman 3).

    Birbirine bağlı, genelde SİSTEM-DIŞI bir iş yığını (özel ders soruları, başka
    öğretmenin ödevi). Sistemde kitabı olmadığı için Kaynak Durumu izleyemez →
    blok bir TOPLAM hedef (total_count) tutar; koç günlere görev dağıttıkça
    (Task.work_block_id) "dağıtılan / kalan" hesaplanır. Rezerv YOK (kapasite
    kitaptan düşmez); yalnız sayaç. Yalnız koça özel.
    """

    __tablename__ = "coach_work_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="test")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    coach: Mapped["User | None"] = relationship("User", foreign_keys=[coach_id])
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    subject: Mapped["Subject | None"] = relationship("Subject")
    tasks: Mapped[list["Task"]] = relationship(
        "Task", back_populates="work_block", foreign_keys="Task.work_block_id"
    )

    def __repr__(self) -> str:
        return f"<CoachWorkBlock {self.id} {self.title!r} total={self.total_count}>"
