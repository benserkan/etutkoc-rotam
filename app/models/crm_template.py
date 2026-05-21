"""CRM aksiyon şablonları (Ticari Pano 2.0 — Faz B4).

Admin önceden hazırlanmış e-posta / SMS / arama scripti taslaklarını burada
saklayıp aksiyon oluştururken seçim yaparak otomatik dolduruyor.

Placeholders (`{{owner_name}}`, `{{plan}}`, `{{trial_ends_at}}`) render
sırasında sunucu tarafında değiştirilir.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.crm import CrmActionKind

if TYPE_CHECKING:
    from app.models.user import User


class CrmActionTemplate(Base):
    """Aksiyon oluştururken seçilebilen taslak (kind + konu + gövde)."""

    __tablename__ = "crm_action_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[CrmActionKind] = mapped_column(
        Enum(CrmActionKind), nullable=False, index=True,
    )
    # E-posta için konu satırı (call/whatsapp için boş bırakılabilir)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Gövde — şablon içeriği, placeholderlar render anında değiştirilir
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Açıklama (admin için, ne zaman kullanılır)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_user_id],
    )

    def __repr__(self) -> str:
        return f"<CrmActionTemplate '{self.name}' kind={self.kind.value}>"


__all__ = ["CrmActionTemplate"]
