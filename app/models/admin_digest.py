"""AdminWeeklyDigest — kurum yöneticisine haftalık özet e-posta arşivi.

Stage 4: cron her Pazartesi 09:00 UTC çalışır, her aktif kuruma haftalık
özet e-postası gönderir. Her gönderim bu tabloya yazılır:
- (institution_id, week_start_date) UNIQUE — idempotency garantisi
- payload_json: o anki snapshot (kohort + risk + activity sayıları)
  → arşiv UI'da geçmiş haftaları göstermek için kullanılır
- recipient_count: kaç admin'e gönderildi
- recipient_emails: hangi admin'ler aldı (audit + KVKK izi)
- send_status: 'sent' / 'failed' / 'log_only' (EMAIL_ENABLED=false ortamında)

Tasarım kararı: NotificationLog'a koymadık çünkü onun parent_id alanı
zorunlu; admin alıcısı parent değil. Arşiv UI ihtiyacı için ayrı tablo
mantıklı.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.institution import Institution


class AdminWeeklyDigest(Base):
    __tablename__ = "admin_weekly_digests"
    __table_args__ = (
        UniqueConstraint(
            "institution_id", "week_start_date",
            name="uq_admin_digest_inst_week",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Haftanın başlangıç tarihi (Pazartesi günü). Aynı hafta için ikinci
    # gönderim üretilemez (UNIQUE).
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Snapshot — UI arşivinde aynı veriyi tekrar gösterebilmek için
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Gönderim sonucu
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recipient_emails: Mapped[str | None] = mapped_column(Text, nullable=True)
    send_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # 'sent' | 'failed' | 'log_only' | 'pending' | 'skipped_no_admin'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    institution: Mapped["Institution"] = relationship(
        "Institution", foreign_keys=[institution_id],
    )

    def __repr__(self) -> str:
        return (
            f"<AdminWeeklyDigest inst={self.institution_id} "
            f"week={self.week_start_date} status={self.send_status}>"
        )
