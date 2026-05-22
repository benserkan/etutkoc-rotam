"""ContactRequest — kurumsal/genel iletişim talebi.

Kurumlar için fiyat gösterilmez; /pricing kurumsal bölümünden form doldurulur.
Talep hem e-posta ile satış kutusuna gider hem süper admin panelde listelenir.
Kişisel veri (ad/e-posta/telefon) → KVKK: yalnız satış/yönetim erişir, amaç
iletişime geçmek; saklama talebin kapanmasıyla sınırlı.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# Talep durumu (sade dil — jargon yok)
CONTACT_STATUS_NEW = "new"
CONTACT_STATUS_CONTACTED = "contacted"
CONTACT_STATUS_CLOSED = "closed"

CONTACT_STATUS_LABELS_TR: dict[str, str] = {
    CONTACT_STATUS_NEW: "Yeni",
    CONTACT_STATUS_CONTACTED: "İletişime geçildi",
    CONTACT_STATUS_CLOSED: "Kapatıldı",
}

# Talebin geldiği yer
CONTACT_SOURCE_LABELS_TR: dict[str, str] = {
    "pricing_institution": "Fiyatlandırma — Kurumsal",
    "pricing_general": "Fiyatlandırma — Genel",
    "subscription_request": "Abonelik talebi (koç)",
    "other": "Diğer",
}


class ContactRequest(Base):
    __tablename__ = "contact_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Talep eden
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    institution_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    coach_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[str] = mapped_column(String(40), nullable=False, default="pricing_institution")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CONTACT_STATUS_NEW, index=True)

    # Yönetim
    handled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<ContactRequest {self.id} {self.email} {self.status}>"
