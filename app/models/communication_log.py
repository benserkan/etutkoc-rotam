"""Birleşik iletişim log'u — TÜM kanalların tek gözlem kaydı.

E-posta + mobil push + WhatsApp + SMS gönderimlerinin "ne, kime, ne zaman,
hangi durumda" kaydı tek tabloda toplanır. Süper admin "İletişim Sağlığı"
merkezi BU tablodan beslenir (kanal sekmeleri + filtreli drill-down + sağlık %).

Mevcut tablolardan (NotificationLog cap/dedup, whatsapp_dispatch_logs spam-guard)
BAĞIMSIZDIR — onlar kendi mantıklarını yürütmeye devam eder; bu tablo yalnız
gözlemlenebilirlik içindir. Tek merkezden (`app.services.comm_log`) yazılır.

channel/status DB enum'u DEĞİL düz VARCHAR (usage_events.kind deseni) — yeni
değer eklemek migration gerektirmesin.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# --- Kanal sabitleri ---
CHANNEL_EMAIL = "email"
CHANNEL_PUSH = "push"
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_SMS = "sms"
CHANNELS = (CHANNEL_EMAIL, CHANNEL_PUSH, CHANNEL_WHATSAPP, CHANNEL_SMS)

CHANNEL_LABELS_TR = {
    CHANNEL_EMAIL: "E-posta",
    CHANNEL_PUSH: "Mobil Bildirim",
    CHANNEL_WHATSAPP: "WhatsApp",
    CHANNEL_SMS: "SMS",
}

# --- Durum sabitleri ---
STATUS_QUEUED = "queued"          # kuyruğa alındı (henüz gönderilmedi)
STATUS_SENT = "sent"              # sağlayıcıya teslim edildi (kabul)
STATUS_DELIVERED = "delivered"    # alıcıya ulaştı (webhook teyidi)
STATUS_BOUNCED = "bounced"        # geri döndü (kalıcı teslim hatası)
STATUS_FAILED = "failed"          # gönderim hatası (bizden/sağlayıcıdan)
STATUS_SUPPRESSED = "suppressed"  # bilinçli gönderilmedi (tercih/mute/abonelik)
STATUSES = (
    STATUS_QUEUED, STATUS_SENT, STATUS_DELIVERED, STATUS_BOUNCED,
    STATUS_FAILED, STATUS_SUPPRESSED,
)

STATUS_LABELS_TR = {
    STATUS_QUEUED: "Kuyrukta",
    STATUS_SENT: "Gönderildi",
    STATUS_DELIVERED: "Ulaştı",
    STATUS_BOUNCED: "Geri döndü",
    STATUS_FAILED: "Başarısız",
    STATUS_SUPPRESSED: "Gönderilmedi (tercih)",
}

# Sağlık hesabında "başarılı" sayılan durumlar (success / (success+fail) oranı).
SUCCESS_STATUSES = (STATUS_SENT, STATUS_DELIVERED)
FAILURE_STATUSES = (STATUS_BOUNCED, STATUS_FAILED)


class CommunicationLog(Base):
    """Tüm kanal gönderimlerinin append-only gözlem kaydı."""

    __tablename__ = "communication_logs"
    __table_args__ = (
        Index("ix_commlog_channel_created", "channel", "created_at"),
        Index("ix_commlog_status", "status"),
        Index("ix_commlog_provider_msgid", "provider_message_id"),
        Index("ix_commlog_to_user_created", "to_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    to_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # E-posta: tam adres · SMS/WhatsApp: telefon · Push: maskeli token
    to_address: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STATUS_SENT
    )
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Durum sonradan değişebilir (sent → delivered/bounced webhook ile).
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    to_user: Mapped["User | None"] = relationship("User", foreign_keys=[to_user_id])
