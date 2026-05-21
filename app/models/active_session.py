"""Katman 11.A — Aktif kullanıcı oturumları.

Her başarılı login bir ActiveSession satırı yazar. Süper admin paneli bu tablodan
şu an kim sistemde, hangi IP'den, ne kadar zamandır görür ve uzaktan oturum
sonlandırma yapabilir. terminated_at NULL = canlı oturum.

Tasarım:
- session_token: starlette session cookie'sine yazılan rastgele 32-byte değer.
  Bu sayede ActiveSession kaydı starlette'in opaque session ID'sinden bağımsız.
- last_seen_at: her HTTP request'te (get_current_user içinde) güncellenir.
- terminated_at + termination_reason: revoke (admin), logout (kullanıcı),
  password_change (otomatik) — sebep ayrımı için.
- ip / user_agent: tam değer (KVKK denetim açısından gerekli, hash'lenmez —
  güvenlik denetimi tek bir admin tarafından görüntülenir, telemetri değil).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActiveSession(Base):
    __tablename__ = "active_sessions"
    __table_args__ = (
        Index("ix_active_sessions_user_login", "user_id", "login_at"),
        Index("ix_active_sessions_terminated", "terminated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    terminated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    termination_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)


# Termination reason sözlüğü — UI'da Türkçe etiket
TERMINATION_REASON_LABELS_TR: dict[str, str] = {
    "logout": "Kullanıcı çıktı",
    "admin_revoke": "Admin uzaktan kapattı",
    "password_change": "Şifre değişti",
    "expired": "Oturum süresi doldu",
}


__all__ = ["ActiveSession", "TERMINATION_REASON_LABELS_TR"]
