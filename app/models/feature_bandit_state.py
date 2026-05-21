"""Katman 7 — LinUCB Contextual Bandit Durum modeli.

Her FeatureCard (PUBLISHED + mockup) için bir satır: A ridge precision matrix
ve b reward-context vektörünün JSON serialize edilmiş hali.

Matrix/vector boyut sabittir (`bandit.CONTEXT_DIM` = 10). Boyut değişirse
eski state'ler `bandit.ensure_state` tarafından sıfırlanır.

Online güncelleme: telemetry.record_event → bandit.update_from_event
sonra db.commit.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FeatureBanditState(Base):
    """Tek kart için LinUCB öğrenme durumu."""

    __tablename__ = "feature_bandit_state"

    card_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("feature_cards.id", ondelete="CASCADE"),
        primary_key=True,
    )
    context_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    a_matrix_json: Mapped[str] = mapped_column(Text, nullable=False)
    b_vector_json: Mapped[str] = mapped_column(Text, nullable=False)
    alpha: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    reward_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # ---------- JSON roundtrip ----------

    @property
    def a_matrix(self) -> list[list[float]]:
        try:
            return list(json.loads(self.a_matrix_json or "[]"))
        except (TypeError, ValueError):
            return []

    @a_matrix.setter
    def a_matrix(self, m: list[list[float]]) -> None:
        self.a_matrix_json = json.dumps(m)

    @property
    def b_vector(self) -> list[float]:
        try:
            return list(json.loads(self.b_vector_json or "[]"))
        except (TypeError, ValueError):
            return []

    @b_vector.setter
    def b_vector(self, v: list[float]) -> None:
        self.b_vector_json = json.dumps(v)

    def __repr__(self) -> str:
        return (
            f"<FeatureBanditState card={self.card_id} dim={self.context_dim} "
            f"obs={self.reward_count}>"
        )


__all__ = ["FeatureBanditState"]
