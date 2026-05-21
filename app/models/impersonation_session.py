"""Katman 11.B — Süper admin kimliğe-bürünme oturumları.

Mevcut impersonate akışı yalnızca AuditLog'a yazıyordu (IMPERSONATE_START/END).
11.B bunu yapısallaştırır:
  - Zorunlu gerekçe (reason, min 10 / max 200 karakter)
  - Otomatik 30 dk expire (uzatmak için yeni impersonate başlatmak gerek)
  - Süper admin panosunda aktif oturumlar görünür, manuel sonlandırma yapılır
  - Tarihçe sorgulanabilir: kim kimi ne kadar süre, hangi gerekçeyle taklit etti

end_reason değerleri:
  - "manual"   — admin /admin/impersonate/end ile çıktı
  - "expired"  — 30 dk doldu, deps.py auto-end yaptı
  - "revoked"  — başka bir süper admin panodan sonlandırdı
  - "logout"   — kullanıcı tam logout yaptı
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImpersonationSession(Base):
    __tablename__ = "impersonation_sessions"
    __table_args__ = (
        Index("ix_impersonation_active", "ended_at"),
        Index("ix_impersonation_actor_started", "actor_user_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ended_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


IMPERSONATION_END_REASON_LABELS_TR: dict[str, str] = {
    "manual": "Admin çıkış yaptı",
    "expired": "30 dakika doldu (oto)",
    "revoked": "Başka admin sonlandırdı",
    "logout": "Tam çıkış",
}


# Zorunlu reason karakter sınırları
REASON_MIN_LENGTH = 10
REASON_MAX_LENGTH = 200
IMPERSONATION_MAX_DURATION_MINUTES = 30


__all__ = [
    "IMPERSONATION_END_REASON_LABELS_TR",
    "IMPERSONATION_MAX_DURATION_MINUTES",
    "ImpersonationSession",
    "REASON_MAX_LENGTH",
    "REASON_MIN_LENGTH",
]
