"""Genişletilmiş iletişim metadata (Ticari Pano 2.0 — Faz B3).

Kurum/bağımsız öğretmen için ek iletişim alanları: yetkili kişi adı/unvanı,
cep telefonu, WhatsApp, LinkedIn URL, web sitesi, serbest not.

Tek-bir-kayıt-per-owner (1:1). Owner sayfasında collapsible form ile yönetilir.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.user import User


class OwnerContact(Base):
    """Owner başına 1 tane genişletilmiş iletişim kaydı."""

    __tablename__ = "owner_contacts"
    __table_args__ = (
        Index("ix_owner_contacts_institution", "institution_id"),
        Index("ix_owner_contacts_user", "user_id"),
        UniqueConstraint("institution_id", name="uq_owner_contact_institution"),
        UniqueConstraint("user_id", name="uq_owner_contact_user"),
        CheckConstraint(
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
            name="ck_owner_contacts_owner_xor",
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

    # Yetkili kişi
    responsible_person_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    responsible_person_title: Mapped[str | None] = mapped_column(
        String(120), nullable=True,
    )

    # İletişim
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Adres / fatura adresi
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Serbest not — sözleşme uyarısı, özel anlaşma detayı vb.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    institution: Mapped["Institution | None"] = relationship(
        "Institution", foreign_keys=[institution_id],
    )
    user: Mapped["User | None"] = relationship(
        "User", foreign_keys=[user_id],
    )
    updated_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[updated_by_user_id],
    )

    def __repr__(self) -> str:
        return f"<OwnerContact {self.owner_type}={self.institution_id or self.user_id}>"


__all__ = ["OwnerContact"]
