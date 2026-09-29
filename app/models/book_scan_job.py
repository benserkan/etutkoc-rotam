"""Tam kitap tarama işi (süper admin, arka plan) — 2026-09-29.

Süper admin tam kitap PDF'ini yükler → web sürecinde arka plan iş parçacığı
`book_pipeline.run_pipeline`'ı koşar (içindekiler + gövde taraması + sağlamlık
kapıları) → sonuç TASLAK olarak burada saklanır; admin katalog formuna aktarıp
onaylar. PDF geçici klasörde tutulur, iş bitince silinir.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_DONE = "done"
JOB_FAILED = "failed"

JOB_STATUS_LABELS_TR = {
    JOB_QUEUED: "Sırada",
    JOB_RUNNING: "Taranıyor",
    JOB_DONE: "Bitti",
    JOB_FAILED: "Başarısız",
}


class BookScanJob(Base):
    __tablename__ = "book_scan_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    toc_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    page_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=JOB_QUEUED, index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stage: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
