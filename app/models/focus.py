"""Stage 14 — Pomodoro odak sessionları + gamification rozet kayıtları.

PomodoroSession: bir çalışma veya mola seansının ham logu.
StudentBadge: bir öğrencinin kazandığı rozetin kayıt satırı (kind + earned_at + metadata).

Rozetler kataloğu kodda (services/gamification.py içinde BADGES); DB sadece
"kim ne zaman kazandı" satırını tutar.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class PomodoroKind(str, enum.Enum):
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


POMODORO_KIND_LABELS_TR: dict[PomodoroKind, str] = {
    PomodoroKind.WORK: "Odak",
    PomodoroKind.SHORT_BREAK: "Kısa Mola",
    PomodoroKind.LONG_BREAK: "Uzun Mola",
}


class PomodoroSession(Base):
    """Tek bir pomodoro seansı (odak veya mola)."""
    __tablename__ = "pomodoro_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[PomodoroKind] = mapped_column(
        Enum(PomodoroKind), nullable=False, default=PomodoroKind.WORK
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    planned_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    actual_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interrupted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])

    def __repr__(self) -> str:
        return f"<PomodoroSession {self.kind.value} {self.actual_minutes}/{self.planned_minutes}m>"


class StudentBadge(Base):
    """Öğrencinin kazandığı bir rozet (idempotent: aynı kind tekrar verilmez)."""
    __tablename__ = "student_badges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    badge_kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    earned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Hangi koşulla kazanıldı (örn. "streak=7", "tasks_today=12"). JSON yerine
    # düz metin: SQLite/Postgres uyumu için Text.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])

    __table_args__ = (
        UniqueConstraint("student_id", "badge_kind", name="uq_student_badge"),
        Index("ix_student_badge_earned", "student_id", "earned_at"),
    )

    def __repr__(self) -> str:
        return f"<StudentBadge student={self.student_id} kind={self.badge_kind}>"
