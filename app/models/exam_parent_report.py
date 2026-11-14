"""Deneme analiz raporu — veliye bağlantıyla giden sayfa (2026-11-13).

Koç "Veliye WhatsApp" dediğinde (ya da deneme duyurusu e-postasında) veliye
tahmin edilemez bir bağlantı gider: sade dilli analiz + Rota'nın sesiyle
dinleme + sunucunun ürettiği PDF. Giriş gerektirmez; token 60 gün geçerli,
koç iptal edebilir.

İçerik saklanmaz — her açılışta denemenin GÜNCEL verisinden kurulur (koç
satırları düzeltirse rapor da düzelir). Yalnız ses önbelleğe alınır;
`audio_signature` metnin özetidir, metin değişince ses yeniden üretilir.
"""
from __future__ import annotations

from datetime import datetime

from datetime import date

from sqlalchemy import Date, DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.database import Base

REPORT_TTL_DAYS = 60

# Rapor türleri (2026-11-14): deneme karnesi · gelişim raporu · haftalık rapor
REPORT_KIND_EXAM = "exam"
REPORT_KIND_PROGRESS = "progress"
REPORT_KIND_WEEKLY = "weekly"
REPORT_KINDS = (REPORT_KIND_EXAM, REPORT_KIND_PROGRESS, REPORT_KIND_WEEKLY)


class ExamParentReport(Base):
    __tablename__ = "exam_parent_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(16), default=REPORT_KIND_EXAM, server_default="exam")
    exam_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_results.id", ondelete="CASCADE"), index=True, nullable=True)
    #: haftalık raporda haftanın Pazartesi'si
    week_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: gelişim raporunda deneme serisi (exam_scope anahtarı; boş = varsayılan)
    series: Mapped[str | None] = mapped_column(String(64), nullable=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    audio: Mapped[bytes | None] = deferred(mapped_column(LargeBinary, nullable=True))
    audio_content_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    audio_signature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
