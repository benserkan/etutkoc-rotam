"""Katman 11.E — Sistem hata izleme (Sentry-tarzı grouping).

Her HTTP 5xx veya yakalanmamış exception bir ErrorEvent satırı üretir.
Aynı signature (exception_type + endpoint + stack_top hash) için dedup:
yeni satır yazılmaz, mevcut grup'un count + last_seen_at güncellenir.

Slow request: response_time_ms > eşik (varsayılan 1500ms) ayrı tabloda
loglanır — sebep tespiti için.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ErrorEvent(Base):
    """Hata grup (signature başına tek satır)."""

    __tablename__ = "error_events"
    __table_args__ = (
        Index("ix_error_signature", "signature", unique=True),
        Index("ix_error_resolved_last", "resolved_at", "last_seen_at"),
        Index("ix_error_endpoint", "endpoint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # SHA1(endpoint + exception_type + stack_top) — 40 hex char
    signature: Mapped[str] = mapped_column(String(40), nullable=False)

    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    exception_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    exception_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)

    count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    last_actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class SlowRequestLog(Base):
    """Yavaş request kaydı (response_time_ms > threshold). append-only."""

    __tablename__ = "slow_request_logs"
    __table_args__ = (
        Index("ix_slow_request_recorded", "recorded_at"),
        Index("ix_slow_request_endpoint", "endpoint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


# Eşikler
SLOW_REQUEST_THRESHOLD_MS = 1500
ERROR_RETENTION_DAYS = 30
SLOW_RETENTION_DAYS = 7


__all__ = [
    "ERROR_RETENTION_DAYS",
    "ErrorEvent",
    "SLOW_REQUEST_THRESHOLD_MS",
    "SLOW_RETENTION_DAYS",
    "SlowRequestLog",
]
