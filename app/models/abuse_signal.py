"""Katman 11.C — Kötüye kullanım (abuse) sinyalleri.

Periyodik tespit servisi (cron + anlık panodan tarama) bir veya birden çok
kuralı tetiklediğinde bu tabloya satır yazar. Süper admin panosunda görünür,
gerekirse "çözüldü" işaretler ya da hesabı/kurumu kısıtlar.

Sinyal türleri (kind):
  MASS_INVITATION         — bir öğretmen 1 saatte 50+ veli daveti
  MASS_NOTIFICATION       — bir tenant 1 saatte 200+ bildirim üretti
  MULTI_ACCOUNT_SAME_DEVICE — aynı UA+IP'den 3+ farklı user_id login 24h
  UNSUBSCRIBE_SPIKE       — tek tenant'tan 24h içinde 10+ unsubscribe/pause

Severity:
  INFO     — bilgi için izleniyor, otomatik aksiyon yok
  WARN     — admin gözden geçirmeli (varsayılan)
  CRITICAL — derhal müdahale gerekir

Dedup: aynı (kind, actor_user_id, tenant_id) için 24 saat içinde "open" sinyal
varsa yeni satır yazmak yerine count + window_end + last_seen_at güncellenir.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AbuseSignal(Base):
    __tablename__ = "abuse_signals"
    __table_args__ = (
        Index("ix_abuse_kind_resolved", "kind", "resolved_at"),
        Index("ix_abuse_actor", "actor_user_id"),
        Index("ix_abuse_tenant", "tenant_id"),
        Index("ix_abuse_detected", "detected_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False, default="warn")

    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    tenant_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True
    )

    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(String(500), nullable=True)


# Sinyal türü etiketleri
ABUSE_KIND_LABELS_TR: dict[str, str] = {
    "mass_invitation": "Toplu veli daveti",
    "mass_notification": "Toplu bildirim üretimi",
    "multi_account_same_device": "Tek cihazdan çoklu hesap",
    "unsubscribe_spike": "Toplu sessizleştirme/çıkış",
    "signup_velocity": "Aynı ağdan çoklu koç kaydı",
}

ABUSE_KIND_DESCRIPTIONS_TR: dict[str, str] = {
    "mass_invitation": (
        "Bir öğretmen kısa sürede çok sayıda veli daveti gönderdi — "
        "yanlış liste veya kötüye kullanım olabilir."
    ),
    "mass_notification": (
        "Bir kurumdan kısa sürede çok sayıda bildirim üretildi — "
        "alıcılara taciz veya teknik döngü olabilir."
    ),
    "multi_account_same_device": (
        "Aynı cihazdan birden fazla farklı hesap giriş yaptı — "
        "şifre paylaşımı veya yaratıcı kötüye kullanım."
    ),
    "unsubscribe_spike": (
        "Bir kurumdan toplu sessizleştirme — alıcı şikayet yoğunluğu işareti."
    ),
    "signup_velocity": (
        "Aynı IP'den 24 saatte birden çok koç hesabı açıldı — ücretsiz öğrenci "
        "limitini çoklu hesapla aşma (çiftlik) girişimi olabilir. Hesapları "
        "inceleyin; mass farming durumunda pasifleştirin."
    ),
}

SEVERITY_LABELS_TR: dict[str, str] = {
    "info": "Bilgi",
    "warn": "Uyarı",
    "critical": "Kritik",
}

SEVERITY_BADGE_COLOR: dict[str, str] = {
    "info": "slate",
    "warn": "amber",
    "critical": "rose",
}


# Eşikler — abuse_detection.py kullanır
THRESHOLD_MASS_INVITATION_PER_HOUR = 50
THRESHOLD_MASS_NOTIFICATION_PER_HOUR = 200
THRESHOLD_MULTI_ACCOUNT_DISTINCT_USERS = 3  # 3 hesap/cihaz çiftliği yakalanır;
# yanlış-pozitif (impersonation + süper admin) dedektörde imp_by/role ile dışlanır
THRESHOLD_UNSUBSCRIBE_SPIKE_PER_DAY = 10

# Dedup penceresi: aynı sinyal 24 saat içinde tekrarsa upsert
DEDUP_WINDOW_HOURS = 24


__all__ = [
    "ABUSE_KIND_DESCRIPTIONS_TR",
    "ABUSE_KIND_LABELS_TR",
    "AbuseSignal",
    "DEDUP_WINDOW_HOURS",
    "SEVERITY_BADGE_COLOR",
    "SEVERITY_LABELS_TR",
    "THRESHOLD_MASS_INVITATION_PER_HOUR",
    "THRESHOLD_MASS_NOTIFICATION_PER_HOUR",
    "THRESHOLD_MULTI_ACCOUNT_DISTINCT_USERS",
    "THRESHOLD_UNSUBSCRIBE_SPIKE_PER_DAY",
]
