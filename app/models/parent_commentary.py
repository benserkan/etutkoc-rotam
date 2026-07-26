"""Rota Veli Asistanı — yorum önbelleği (P1).

Çocuk başına TÜR başına (program | deneme) tek güncel yorum. İki metin taşır:
  - sections_json: ekran metni bölümleri [{"title","body"}] — rakamlı, okunaklı
  - speech_text:   seslendirme metni — sayılar yazıyla, TTS kurallarına uygun
Ses (audio) İLK dinlemede üretilip burada saklanır (deferred — liste/detay
sorguları yüklemez); yorum yeniden üretilince ses temizlenir (metinle ses
asla ayrışmaz). based_on_json bayatlık imzasıdır (program: hafta + görev
sayıları · deneme: son deneme id listesi) — is_stale HESAPLANIR, saklanmaz.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.database import Base

PC_KIND_PROGRAM = "program"
PC_KIND_DENEME = "deneme"
PC_KINDS = (PC_KIND_PROGRAM, PC_KIND_DENEME)

PC_KIND_LABELS_TR = {
    PC_KIND_PROGRAM: "Program yorumu",
    PC_KIND_DENEME: "Deneme yorumu",
}

# Veli başına günde en fazla yorum ÜRETİMİ (okuma/dinleme sınırsız — kredisiz).
PC_DAILY_GENERATION_LIMIT = 6


class ParentCommentary(Base):
    __tablename__ = "parent_commentaries"
    __table_args__ = (
        UniqueConstraint("student_id", "kind", name="uq_parent_commentary"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)

    sections_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    speech_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    based_on_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")

    # Ses — yalnız istenince üretilir; deferred: audio kolonunu açıkça
    # undefer etmeyen sorgular byte'ları YÜKLEMEZ.
    audio: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    audio_content_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    generated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    # -- JSON yardımcıları ---------------------------------------------------
    @property
    def sections(self) -> list[dict]:
        try:
            v = json.loads(self.sections_json or "[]")
            return v if isinstance(v, list) else []
        except (ValueError, TypeError):
            return []

    def set_sections(self, sections: list[dict]) -> None:
        self.sections_json = json.dumps(sections, ensure_ascii=False)

    @property
    def based_on(self) -> dict:
        try:
            v = json.loads(self.based_on_json or "{}")
            return v if isinstance(v, dict) else {}
        except (ValueError, TypeError):
            return {}

    def set_based_on(self, sig: dict) -> None:
        self.based_on_json = json.dumps(sig, ensure_ascii=False)

    def __repr__(self) -> str:
        return f"<ParentCommentary s={self.student_id} kind={self.kind}>"
