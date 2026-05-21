"""Katman 11.A — Şüpheli IP takibi (brute force koruması).

Her başarısız login (kullanıcı bulunamadı, yanlış şifre, kilitli hesap)
SuspiciousIp satırına işlenir. Aynı IP 1 saatte 10+ farklı email denerse
veya 30+ toplam fail üretirse otomatik 1 saat blok.

Tasarım:
- Tek IP başına tek satır (upsert) → liste kabarmaz.
- distinct_emails_json: son 20 farklı email (truncate edilir, ham veri değil).
- blocked_until: NULL = blok yok, geçmişse blok bitti, gelecek = aktif blok.
- block_reason: "auto_emails_threshold", "auto_fails_threshold", "manual".
- KVKK: bu tablo süper admin tarafından okunan güvenlik denetim verisi —
  ham IP saklanır (anonimleştirilmez), 90 gün sonra temizlenmeli (Faz 1.5).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SuspiciousIp(Base):
    __tablename__ = "suspicious_ips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_email_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    # JSON array — son 20 farklı email (truncate). Tam tarihçe AuditLog'da.
    distinct_emails_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    blocked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    block_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    blocked_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    block_note: Mapped[str | None] = mapped_column(String(255), nullable=True)


BLOCK_REASON_LABELS_TR: dict[str, str] = {
    "auto_emails_threshold": "Otomatik: çok farklı e-posta denemesi",
    "auto_fails_threshold": "Otomatik: çok fazla başarısız giriş",
    "manual": "Manuel admin engellemesi",
}


__all__ = ["SuspiciousIp", "BLOCK_REASON_LABELS_TR"]
