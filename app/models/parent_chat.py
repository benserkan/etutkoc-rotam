"""Rota Veli Asistanı P2 — sohbet mesajı modeli.

Veli↔Rota yazılı sohbeti (çocuk bağlamında). Mesajlar saklanır: veli eski
konuşmalarını görür; son PCM_CONTEXT_MESSAGES mesaj Gemini bağlamına girer.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.database import Base

PCM_ROLE_VELI = "veli"
PCM_ROLE_ROTA = "rota"
PCM_ROLES = (PCM_ROLE_VELI, PCM_ROLE_ROTA)

# Veli başına günde en fazla SORU (kredisiz karşılama/okuma sınırsız)
PC_CHAT_DAILY_LIMIT = 10
# Gemini bağlamına giren son mesaj sayısı
PCM_CONTEXT_MESSAGES = 10
# Soru uzunluk sınırları
PCM_MIN_LEN = 2
PCM_MAX_LEN = 500
# Veli başına günde en fazla SESLİ SORU çevirisi (STT)
PC_STT_DAILY_LIMIT = 15


class ParentChatMessage(Base):
    __tablename__ = "parent_chat_messages"
    __table_args__ = (
        Index("ix_parent_chat_thread", "parent_id", "student_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(8), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # P3: Rota cevabının ses önbelleği — ilk dinlemede üretilir, saklanır
    # (deferred: liste sorguları byte'ları yüklemez). Mesaj immutable → ses
    # bayatlamaz.
    audio: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    audio_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ParentChatMessage p={self.parent_id} s={self.student_id} {self.role}>"
