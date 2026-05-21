"""Sprint B (Ticari Pano 2.0 — Faz B/D) — CRM modeli: not + aksiyon.

Bir "billing owner" ile ilgili "müşteri ilişkileri" hafızası:

  - CrmNote: admin'in elle yazdığı sade not (kronolojik). "5 Mayıs'ta Hasan
    Bey ile telefon görüşmesi", "Yıllığa geçmeyi düşünüyorlar" vs.
  - CrmAction: yapılan/yapılacak temas (arama, e-posta, WhatsApp, görüşme,
    teklif sunma) — sonuç ve takip tarihi ile.

**Owner pattern (Sprint F.3'te genişletildi):** Hem `Institution` hem
bağımsız öğretmen (`User` role=TEACHER + institution_id=NULL) için CRM
not/aksiyon tutulabilir. `owner_type` ('institution' | 'user') ile
hangi tablodaki kayıtla ilişkili belirlenir; ilgili FK doludur, diğeri NULL.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


CRM_OWNER_TYPES = ("institution", "user")


def _crm_owner_xor_check(table: str) -> CheckConstraint:
    """owner_type ile FK'lerin XOR uyumu — tam birinin set olması zorunlu."""
    return CheckConstraint(
        "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
        "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
        name=f"ck_{table}_owner_xor",
    )

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.user import User


class CrmActionKind(str, enum.Enum):
    CALL = "call"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    MEETING = "meeting"
    OFFER_SENT = "offer_sent"
    ONBOARDING = "onboarding"
    OTHER = "other"


CRM_ACTION_KIND_LABELS_TR: dict[CrmActionKind, str] = {
    CrmActionKind.CALL: "Telefon araması",
    CrmActionKind.EMAIL: "E-posta",
    CrmActionKind.WHATSAPP: "WhatsApp",
    CrmActionKind.MEETING: "Yüz yüze görüşme",
    CrmActionKind.OFFER_SENT: "Teklif sunuldu",
    CrmActionKind.ONBOARDING: "Onboarding / eğitim",
    CrmActionKind.OTHER: "Diğer",
}

CRM_ACTION_KIND_ICONS: dict[CrmActionKind, str] = {
    CrmActionKind.CALL: "📞",
    CrmActionKind.EMAIL: "✉️",
    CrmActionKind.WHATSAPP: "💬",
    CrmActionKind.MEETING: "🤝",
    CrmActionKind.OFFER_SENT: "🎁",
    CrmActionKind.ONBOARDING: "🎓",
    CrmActionKind.OTHER: "📌",
}


class CrmActionResult(str, enum.Enum):
    SUCCESS = "success"             # Başarılı temas (cevap alındı, iyi sonuç)
    NO_ANSWER = "no_answer"          # Cevap yok / ulaşılamadı
    DECLINED = "declined"            # Teklif reddedildi / ilgilenmiyor
    SCHEDULED = "scheduled"          # Takip planlandı
    DONE = "done"                    # Tamamlandı, beklenen sonuç
    PENDING = "pending"              # Henüz tamamlanmadı (gelecek aksiyon)
    OTHER = "other"


CRM_ACTION_RESULT_LABELS_TR: dict[CrmActionResult, str] = {
    CrmActionResult.SUCCESS: "Başarılı",
    CrmActionResult.NO_ANSWER: "Cevap yok",
    CrmActionResult.DECLINED: "Reddedildi",
    CrmActionResult.SCHEDULED: "Takip planlandı",
    CrmActionResult.DONE: "Tamamlandı",
    CrmActionResult.PENDING: "Bekliyor",
    CrmActionResult.OTHER: "Diğer",
}

CRM_ACTION_RESULT_COLORS: dict[CrmActionResult, str] = {
    CrmActionResult.SUCCESS: "emerald",
    CrmActionResult.NO_ANSWER: "slate",
    CrmActionResult.DECLINED: "rose",
    CrmActionResult.SCHEDULED: "amber",
    CrmActionResult.DONE: "emerald",
    CrmActionResult.PENDING: "indigo",
    CrmActionResult.OTHER: "slate",
}


class CrmNote(Base):
    """Bir owner (kurum veya bağımsız öğretmen) ile ilgili admin notu (kronolojik)."""

    __tablename__ = "crm_notes"
    __table_args__ = (
        Index("ix_crm_notes_inst_created", "institution_id", "created_at"),
        Index("ix_crm_notes_pinned", "institution_id", "pinned"),
        Index("ix_crm_notes_user_created", "user_id", "created_at"),
        _crm_owner_xor_check("crm_notes"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'institution'"),
    )
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Sabitle (top'ta gözüksün) — admin önemli notları en üstte tutmak için
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    institution: Mapped["Institution | None"] = relationship(
        "Institution", foreign_keys=[institution_id],
    )
    owner_user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id],
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_user_id],
    )


class CrmAction(Base):
    """Bir owner'a (kurum/öğretmen) yapılan/yapılacak temas."""

    __tablename__ = "crm_actions"
    __table_args__ = (
        Index("ix_crm_actions_inst_created", "institution_id", "created_at"),
        Index("ix_crm_actions_followup", "institution_id", "follow_up_at"),
        Index("ix_crm_actions_user_created", "user_id", "created_at"),
        Index("ix_crm_actions_user_followup", "user_id", "follow_up_at"),
        _crm_owner_xor_check("crm_actions"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'institution'"),
    )
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    kind: Mapped[CrmActionKind] = mapped_column(
        Enum(CrmActionKind), nullable=False,
    )
    # Kısa özet — "Yıllığa geçmeyi konuştuk, düşünecek"
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    # Uzun not (opsiyonel) — detay
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[CrmActionResult] = mapped_column(
        Enum(CrmActionResult), nullable=False,
        default=CrmActionResult.PENDING,
    )

    # Takip tarihi — "Bunu 7 Mayıs'ta tekrar ara"
    follow_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    institution: Mapped["Institution | None"] = relationship(
        "Institution", foreign_keys=[institution_id],
    )
    owner_user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id],
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_user_id],
    )


__all__ = [
    "CRM_ACTION_KIND_ICONS",
    "CRM_ACTION_KIND_LABELS_TR",
    "CRM_ACTION_RESULT_COLORS",
    "CRM_ACTION_RESULT_LABELS_TR",
    "CRM_OWNER_TYPES",
    "CrmAction",
    "CrmActionKind",
    "CrmActionResult",
    "CrmNote",
]
