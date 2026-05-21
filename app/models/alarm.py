"""Katman 11.F — Eşik tabanlı alarm sistemi.

Kural-tabanlı: AlarmRule satırı bir gözlem ölçüsü + eşik + pencere + cooldown
tanımlar. alarm_engine periyodik olarak (cron + manuel) çalıştığında kurala
uyan değer eşiği aşarsa AlarmEvent kaydı yazar ve channels'a göre bildirim
gönderir (email süper adminlere, in-app rozet).

Cooldown: aynı kural cooldown_minutes içinde tekrar tetiklenmez — alarm
yorgunluğunu önler. last_triggered_at + cooldown_minutes > now → skip.

Varsayılan kurallar (seed):
  - high_failed_logins   : 24h başarısız login > 50          → 60dk cooldown
  - oldest_queued_long   : en eski queued > 60dk             → 30dk cooldown
  - error_groups_open    : açık hata grubu > 5               → 60dk cooldown
  - abuse_open           : açık abuse sinyali > 0            → 30dk cooldown
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AlarmRule(Base):
    __tablename__ = "alarm_rules"
    __table_args__ = (
        Index("ix_alarm_rule_key", "key", unique=True),
        Index("ix_alarm_rule_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(60), nullable=False)  # high_failed_logins vb.
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Kanal: "email,in_app" gibi virgülle ayrılmış
    channels: Mapped[str] = mapped_column(String(60), nullable=False, default="email,in_app")

    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AlarmEvent(Base):
    """Bir kural tetiklendiğinde yazılan kayıt — geçmiş için."""

    __tablename__ = "alarm_events"
    __table_args__ = (
        Index("ix_alarm_event_rule_time", "rule_key", "triggered_at"),
        Index("ix_alarm_event_time", "triggered_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_key: Mapped[str] = mapped_column(String(60), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(160), nullable=False)

    value: Mapped[int] = mapped_column(Integer, nullable=False)
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="warn")

    channels_attempted: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    delivery_status: Mapped[str] = mapped_column(String(60), nullable=False, default="pending")

    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


# Varsayılan kurallar
DEFAULT_RULES: list[dict] = [
    {
        "key": "high_failed_logins",
        "name": "Yüksek başarısız login",
        "description": "Son 24 saatte başarısız giriş eşiği aşıldı.",
        "threshold": 50,
        "cooldown_minutes": 60,
    },
    {
        "key": "oldest_queued_long",
        "name": "Kuyrukta uzun süre bekleyen bildirim",
        "description": "En eski queued bildirim eşik dakikasından eski.",
        "threshold": 60,  # dakika
        "cooldown_minutes": 30,
    },
    {
        "key": "error_groups_open",
        "name": "Çok açık hata grubu",
        "description": "Resolved olmayan hata grubu eşiği aştı.",
        "threshold": 5,
        "cooldown_minutes": 60,
    },
    {
        "key": "abuse_open",
        "name": "Açık abuse sinyali",
        "description": "Resolved olmayan abuse sinyali eşiği aştı (0 = her tek sinyal alarmlar).",
        "threshold": 0,
        "cooldown_minutes": 30,
    },
]


__all__ = ["AlarmEvent", "AlarmRule", "DEFAULT_RULES"]
