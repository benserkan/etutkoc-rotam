"""Deneme analizi Faz 2 kalıcı kayıtları — hedef net + seans gündem kuyruğu.

Öğrenci silinince ikisi de CASCADE ile gider (yetim kayıt yok). Öğrenciyle
paylaşım notu denemenin kendi `analysis_meta`'sında durur (deneme silinince
birlikte gider).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExamTarget(Base):
    __tablename__ = "exam_targets"
    __table_args__ = (UniqueConstraint("student_id", "section", name="uq_exam_target_student_section"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(16), nullable=False)
    target_net: Mapped[float] = mapped_column(Float, nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subject_targets: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON {ders: net}
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    set_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SessionAgendaItem(Base):
    __tablename__ = "session_agenda_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    item_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    text: Mapped[str] = mapped_column(String(400), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="exam")
    exam_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_results.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
