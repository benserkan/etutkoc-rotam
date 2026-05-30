"""P3 — WhatsApp Click-to-WA dispatch log.

Her URL üretildiğinde bir kayıt — koç/yön./admin'in WA niyetinin audit izi.
P6 spam guard hesaplaması bu tablodan: haftalık tavan, günlük 100+ uyarısı,
hedef başına ardışık mesaj sayısı.

Not: URL üretildi = mesaj gerçekten gönderildi anlamına gelmez. Koç linki
tıkladığında WhatsApp uygulamasında metin hazırlanır; gönderim son tıkı koçun
yapması gerekir. Yine de "tetik" anı log altındadır (analiz için yeterli).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.whatsapp_template import WhatsAppTemplate


class WhatsAppDispatchLog(Base):
    """Click-to-WA tetik kaydı (P3 — 2026-05-30)."""

    __tablename__ = "whatsapp_dispatch_logs"
    __table_args__ = (
        Index("ix_wadlog_sender_created", "sender_user_id", "created_at"),
        Index("ix_wadlog_target_created", "target_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    # Eski şablon silinse bile audit korunsun
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("whatsapp_templates.id", ondelete="SET NULL"), nullable=True,
    )
    params_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default=sa_text("'{}'"),
    )
    character_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sa_text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_user_id])
    target: Mapped["User | None"] = relationship("User", foreign_keys=[target_user_id])
    template: Mapped["WhatsAppTemplate | None"] = relationship(
        "WhatsAppTemplate", foreign_keys=[template_id]
    )
