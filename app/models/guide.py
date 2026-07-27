"""Rol bazlı rehber (onboarding guide) ilerleme durumu.

Her kullanıcı × rehber için TEK satır (uq_user_guide_state). Bölüm ilerlemesi
cihazdan bağımsız burada tutulur; "şimdi sen yap" kontrol listesi ise SAKLANMAZ,
guide_service gerçek veriden hesaplar (kitap var mı, program yayınlandı mı...).
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Rehber anahtarları
GUIDE_COACH_ONBOARDING = "coach_onboarding"
GUIDE_STUDENT_ONBOARDING = "student_onboarding"
GUIDE_PARENT_ONBOARDING = "parent_onboarding"

# status değerleri
GUIDE_STATUS_IN_PROGRESS = "in_progress"
GUIDE_STATUS_COMPLETED = "completed"
GUIDE_STATUS_DISMISSED = "dismissed"

GUIDE_STATUSES = {GUIDE_STATUS_IN_PROGRESS, GUIDE_STATUS_COMPLETED, GUIDE_STATUS_DISMISSED}


class UserGuideState(Base):
    __tablename__ = "user_guide_states"
    __table_args__ = (UniqueConstraint("user_id", "guide_key", name="uq_user_guide_state"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    guide_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=GUIDE_STATUS_IN_PROGRESS
    )
    current_chapter: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chapters_done: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Bölüm anahtarı → sonuna kadar izlenen adım indeksleri (JSON dict).
    # Kaldığı yerden devam bunun üzerinden hesaplanır; kapı DEĞİL, konum.
    steps_watched: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def chapters_done_list(self) -> list[str]:
        try:
            data = json.loads(self.chapters_done or "[]")
        except (TypeError, ValueError):
            return []
        return [str(x) for x in data] if isinstance(data, list) else []

    def set_chapters_done(self, chapters: list[str]) -> None:
        self.chapters_done = json.dumps(list(dict.fromkeys(chapters)), ensure_ascii=False)

    @property
    def steps_watched_map(self) -> dict[str, list[int]]:
        try:
            data = json.loads(self.steps_watched or "{}")
        except (TypeError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        out: dict[str, list[int]] = {}
        for k, v in data.items():
            if isinstance(v, list):
                out[str(k)] = sorted({int(x) for x in v if isinstance(x, (int, float))})
        return out

    def set_steps_watched(self, data: dict[str, list[int]]) -> None:
        self.steps_watched = json.dumps(
            {k: sorted(set(v)) for k, v in data.items()}, ensure_ascii=False
        )
