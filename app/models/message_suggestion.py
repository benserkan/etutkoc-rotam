"""Koçun WhatsApp mesaj önerilerine verdiği karar (2026-11-14).

Sistem öğrenci hakkında bir şey fark ettiğinde (sorun, gelişme, yeni rapor,
hatırlatma) koça hazır mesaj önerir. Koç ya gönderir ya atlar; kayıt aynı
önerinin tekrar çıkmasını engeller ve "bugün kaç mesaj gönderdin" sayacını
besler. Cevap takibi YOK (kullanıcı kararı).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ACTION_SENT = "sent"
ACTION_SKIPPED = "skipped"


class MessageSuggestionAction(Base):
    __tablename__ = "message_suggestion_actions"
    __table_args__ = (
        UniqueConstraint("student_id", "audience", "suggestion_key", name="uq_msgsugg_student_aud_key"),
        Index("ix_msgsugg_coach_created", "coach_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    #: "parent" | "student"
    audience: Mapped[str] = mapped_column(String(10), nullable=False)
    suggestion_key: Mapped[str] = mapped_column(String(120), nullable=False)
    #: "sent" | "skipped"
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
