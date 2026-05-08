"""Cron schedule modeli — admin-editable bildirim zamanlamaları."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CronSchedule(Base):
    """Bir cron job'ın çalışma zaman bilgileri.

    job_key: registry'deki fonksiyona referans (ör. 'daily_summary')
    hour/minute: günün saatinde çalışma noktası (UTC olarak yorumlanır)
    day_of_week: 0=Pazartesi..6=Pazar; NULL = her gün
    last_run_at: en son çalıştığı zaman (catch-up için kontrol edilir)
    last_status: 'success' | 'failed' | 'skipped'
    """

    __tablename__ = "cron_schedules"
    __table_args__ = (UniqueConstraint("job_key", name="uq_cron_job_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_key: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def time_label(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"

    @property
    def dow_label(self) -> str:
        if self.day_of_week is None:
            return "Her gün"
        labels = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        return labels[self.day_of_week]
