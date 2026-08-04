"""MomentEvent — bağlamsal uyarı/kart sinyalinin kullanıcıya sunulduğu iz.

Faz C (2026-08-04): TrialBanner/CreditPackCard gibi bağlamsal yüzeylerin
sinyalini taşıyan API yanıtı üretildiğinde günde bir kez yazılır (best-effort).
Sessizlik taraması (moments.silent_moment_report) bu tabloyu "koşulu sağlayan
ama sinyal almayan kullanıcı" tespitinde kullanır.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MomentEvent(Base):
    __tablename__ = "moment_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "moment_key", "day", name="uq_moment_event_user_key_day",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    moment_key: Mapped[str] = mapped_column(String(40), nullable=False)
    day: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
