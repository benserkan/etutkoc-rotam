"""Stage 10 — KVKK Madde 11 veri sahibi talep kayıtları.

KVKK 11/2'de tanımlı haklara karşılık gelen 3 ana talep tipi:
- 'export'      : Veri ihracı / data portability — kullanıcı kendi verisini ister
- 'delete'      : Unutulma hakkı / RTBF — kullanıcı silinmek ister
- 'rectification': Düzeltme talebi — yanlış kişisel bilgiyi düzeltme

İş akışı:
- pending     : Talep oluştu, değerlendirilmeyi bekliyor
- processing  : İşleme başlandı (özellikle delete: 30 gün grace period)
- completed   : Talep gerçekleşti (export indirildi / kullanıcı anonimize edildi /
                düzeltme uygulandı)
- cancelled   : Kullanıcı veya admin iptal etti
- rejected    : Reddedildi (yetki, veri uyuşmazlığı vs.)

İz: requester_user_id (talebi yapan), target_user_id (verisi etkilenen kişi —
self-talep için aynı), processed_by_user_id (talebi sonlandıran).
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class DataRequestKind(str, enum.Enum):
    EXPORT = "export"
    DELETE = "delete"
    RECTIFICATION = "rectification"


class DataRequestStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"     # delete için 30g grace
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


DATA_REQUEST_KIND_LABELS_TR = {
    DataRequestKind.EXPORT: "Veri İhracı",
    DataRequestKind.DELETE: "Hesabımı Sil",
    DataRequestKind.RECTIFICATION: "Bilgi Düzeltme",
}

DATA_REQUEST_STATUS_LABELS_TR = {
    DataRequestStatus.PENDING: "Bekliyor",
    DataRequestStatus.PROCESSING: "İşleniyor",
    DataRequestStatus.COMPLETED: "Tamamlandı",
    DataRequestStatus.CANCELLED: "İptal Edildi",
    DataRequestStatus.REJECTED: "Reddedildi",
}


# Silme talebinde kullanıcıya tanınan iptal süresi (gün)
DELETE_GRACE_PERIOD_DAYS = 30


class DataSubjectRequest(Base):
    """KVKK madde 11 veri sahibi talep kaydı.

    target_user_id: verisi etkilenecek kişi.
    requester_user_id: talebi açan (self-talepte target ile aynı; admin
        adına talep açıyorsa farklı).
    institution_id: kurum scope'u — tenant izolasyonu için sorgu kolaylığı.
    """
    __tablename__ = "data_subject_requests"
    __table_args__ = (
        Index("ix_dsr_target_status", "target_user_id", "status"),
        Index("ix_dsr_kind_status", "kind", "status"),
        Index("ix_dsr_status_processed", "status", "process_after"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[DataRequestKind] = mapped_column(
        Enum(DataRequestKind), nullable=False,
    )
    status: Mapped[DataRequestStatus] = mapped_column(
        Enum(DataRequestStatus), nullable=False,
        default=DataRequestStatus.PENDING,
    )

    # Talebi yapan + etkilenecek kişi (self talepte ikisi aynı)
    requester_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
    )
    # Tenant scope (varsa) — admin paneli için filtre kolaylığı
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True,
    )

    # Talep gerekçesi (kullanıcı yazdığı serbest metin)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 30g grace sonrası işlenecek tarih (delete için). NULL = derhal.
    process_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Talebi sonlandıran admin
    processed_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Admin notu (red sebebi, işleme detayları)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Export için snapshot dosyasının yolu / inline JSON içeriği
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, index=True,
    )

    # İlişkiler — UI'da listelerken N+1 önlemek için joinedload
    target_user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[target_user_id], viewonly=True,
    )
    requester_user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[requester_user_id], viewonly=True,
    )
    processed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[processed_by_user_id], viewonly=True,
    )

    def __repr__(self) -> str:
        return (
            f"<DataSubjectRequest #{self.id} {self.kind.value} "
            f"target={self.target_user_id} status={self.status.value}>"
        )
