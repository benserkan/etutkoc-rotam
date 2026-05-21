"""Katman 9 — A/B Test Deneyi modeli.

Tek seferde bir aktif deney politikası: status=running olan ilk deney
landing'i etkiler. Variants JSON listesi:

    [
      {"slug": "ctrl",  "label": "Tam karışım",
       "strategy": "hybrid_full",  "weight": 50, "is_control": true},
      {"slug": "test",  "label": "Bandit'siz",
       "strategy": "fuzzy_only",   "weight": 50, "is_control": false},
    ]

weight: 0-100 traffic yüzdesi; toplam 100 olmalı.
strategy: app.services.landing_strategies'deki registry anahtarı.

Ziyaretçi → variant atama deterministik hash ile (session_id + experiment.slug).
"""

from __future__ import annotations

import enum
import json
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExperimentStatus(str, enum.Enum):
    DRAFT = "draft"           # taslak — landing etkilemiyor
    RUNNING = "running"       # aktif — variant ataması yapılıyor
    PAUSED = "paused"         # geçici durdurma — variant ataması yok
    COMPLETED = "completed"   # bitti — sonuçlar görüntülenebilir


EXPERIMENT_STATUS_LABELS_TR: dict[ExperimentStatus, str] = {
    ExperimentStatus.DRAFT: "Taslak",
    ExperimentStatus.RUNNING: "Çalışıyor",
    ExperimentStatus.PAUSED: "Duraklatıldı",
    ExperimentStatus.COMPLETED: "Tamamlandı",
}

EXPERIMENT_STATUS_BADGES: dict[ExperimentStatus, str] = {
    ExperimentStatus.DRAFT: "slate",
    ExperimentStatus.RUNNING: "emerald",
    ExperimentStatus.PAUSED: "amber",
    ExperimentStatus.COMPLETED: "indigo",
}


class FeatureExperiment(Base):
    __tablename__ = "feature_experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        default=ExperimentStatus.DRAFT.value)
    variants_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ---------- JSON roundtrip ----------

    @property
    def variants(self) -> list[dict]:
        try:
            return list(json.loads(self.variants_json or "[]"))
        except (TypeError, ValueError):
            return []

    @variants.setter
    def variants(self, value: list[dict]) -> None:
        self.variants_json = json.dumps(value, ensure_ascii=False)

    @property
    def status_enum(self) -> ExperimentStatus:
        try:
            return ExperimentStatus(self.status)
        except ValueError:
            return ExperimentStatus.DRAFT

    def __repr__(self) -> str:
        return f"<FeatureExperiment slug={self.slug!r} status={self.status}>"


__all__ = [
    "ExperimentStatus",
    "EXPERIMENT_STATUS_LABELS_TR",
    "EXPERIMENT_STATUS_BADGES",
    "FeatureExperiment",
]
