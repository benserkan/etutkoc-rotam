"""CoachDeviceLink — bağımsız koç hesabının giriş yaptığı cihazlar.

2026-10-02: ücretsiz paketin (Keşif, 3 öğrenci) ve 14 günlük denemenin aynı
kişi tarafından birden çok hesapla çoğaltılmasını yakalamak için. Cihaz kimliği
web'de kalıcı `etk_dev` çerezi, mobilde kurulum kimliği (X-Device-Id); ham değer
saklanmaz, SHA-256 özeti tutulur. Kullanım: app/services/free_tier_guard.py.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CoachDeviceLink(Base):
    __tablename__ = "coach_device_links"
    __table_args__ = (
        UniqueConstraint("user_id", "device_hash", name="uq_coach_device_user_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    device_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
