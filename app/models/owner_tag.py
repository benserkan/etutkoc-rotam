"""Owner etiket sistemi (Ticari Pano 2.0 — Faz B1).

Admin'in kurum/bağımsız öğretmen sahiplerine yapışkan etiket atayabilmesi:
VIP, Pilot, B2B referans, Stratejik, Demo, Enterprise vb.

Aynı owner birden çok etiket alabilir — etiketler renkli rozet olarak
360 sayfasında ve listelerde gösterilir, filtrelenebilir.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.user import User


class OwnerTagKind(str, enum.Enum):
    VIP = "vip"
    PILOT = "pilot"
    B2B_REFERENCE = "b2b_reference"
    STRATEGIC = "strategic"
    DEMO = "demo"
    ENTERPRISE = "enterprise"
    EARLY_ADOPTER = "early_adopter"
    AT_RISK_MANUAL = "at_risk_manual"


OWNER_TAG_LABELS_TR: dict[OwnerTagKind, str] = {
    OwnerTagKind.VIP: "VIP",
    OwnerTagKind.PILOT: "Pilot",
    OwnerTagKind.B2B_REFERENCE: "B2B Referans",
    OwnerTagKind.STRATEGIC: "Stratejik",
    OwnerTagKind.DEMO: "Demo",
    OwnerTagKind.ENTERPRISE: "Kurumsal (büyük)",
    OwnerTagKind.EARLY_ADOPTER: "Erken Benimseyen",
    OwnerTagKind.AT_RISK_MANUAL: "Risk (manuel)",
}


OWNER_TAG_DESCRIPTIONS: dict[OwnerTagKind, str] = {
    OwnerTagKind.VIP: "Yüksek değerli müşteri — özel ilgi gerekir.",
    OwnerTagKind.PILOT: "Pilot/deneme aşamasında — yakın takip.",
    OwnerTagKind.B2B_REFERENCE: "Referans verilebilir müşteri (case study/B2B).",
    OwnerTagKind.STRATEGIC: "Stratejik partner — özel anlaşma var.",
    OwnerTagKind.DEMO: "Demo hesap — gerçek müşteri değil.",
    OwnerTagKind.ENTERPRISE: "Büyük kurumsal müşteri — özel SLA.",
    OwnerTagKind.EARLY_ADOPTER: "Erken benimseyen — beta özelliklere açık.",
    OwnerTagKind.AT_RISK_MANUAL: "Admin manuel olarak risk işaretledi.",
}


# Rozet renkleri (Tailwind class prefix'i)
OWNER_TAG_COLORS: dict[OwnerTagKind, str] = {
    OwnerTagKind.VIP: "amber",
    OwnerTagKind.PILOT: "indigo",
    OwnerTagKind.B2B_REFERENCE: "purple",
    OwnerTagKind.STRATEGIC: "emerald",
    OwnerTagKind.DEMO: "slate",
    OwnerTagKind.ENTERPRISE: "blue",
    OwnerTagKind.EARLY_ADOPTER: "pink",
    OwnerTagKind.AT_RISK_MANUAL: "rose",
}


OWNER_TAG_ICONS: dict[OwnerTagKind, str] = {
    OwnerTagKind.VIP: "👑",
    OwnerTagKind.PILOT: "🚀",
    OwnerTagKind.B2B_REFERENCE: "🤝",
    OwnerTagKind.STRATEGIC: "🎯",
    OwnerTagKind.DEMO: "🧪",
    OwnerTagKind.ENTERPRISE: "🏛️",
    OwnerTagKind.EARLY_ADOPTER: "⚡",
    OwnerTagKind.AT_RISK_MANUAL: "⚠️",
}


class OwnerTag(Base):
    """Owner'a (kurum veya bağımsız öğretmen) atanmış etiket."""

    __tablename__ = "owner_tags"
    __table_args__ = (
        Index("ix_owner_tags_institution", "institution_id"),
        Index("ix_owner_tags_user", "user_id"),
        Index("ix_owner_tags_kind", "kind"),
        # Aynı kind aynı owner'a tek kez atanabilir
        UniqueConstraint("institution_id", "kind", name="uq_owner_tag_inst_kind"),
        UniqueConstraint("user_id", "kind", name="uq_owner_tag_user_kind"),
        CheckConstraint(
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
            name="ck_owner_tags_owner_xor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        server_default=text("'institution'"),
    )
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True,
    )
    kind: Mapped[OwnerTagKind] = mapped_column(
        Enum(OwnerTagKind), nullable=False,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    institution: Mapped["Institution | None"] = relationship(
        "Institution", foreign_keys=[institution_id],
    )
    user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id],
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_user_id],
    )

    def __repr__(self) -> str:
        return f"<OwnerTag {self.owner_type}={self.institution_id or self.user_id} {self.kind.value}>"


__all__ = [
    "OWNER_TAG_COLORS",
    "OWNER_TAG_DESCRIPTIONS",
    "OWNER_TAG_ICONS",
    "OWNER_TAG_LABELS_TR",
    "OwnerTag",
    "OwnerTagKind",
]
