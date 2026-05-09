"""Stage 9 (Faz 2) — Plan değişiklik geçmişi.

Bir kurum veya bağımsız öğretmenin plan değişiklikleri burada izlenir:
- "Free → Solo Pro" (kullanıcı yükseltti)
- "Pilot → Etüt Standart" (trial sonu otomatik)
- "Solo Pro → Solo Free" (downgrade)
- "Solo Free → Solo Pro (akademik yıl)" (yıllık peşin)

Audit içindir, billing/invoice değildir. İleride faturalama eklendiğinde
ayrı bir Invoice modeli olur.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlanChangeReason(str, enum.Enum):
    """Plan değişikliğinin sebebi."""
    SIGNUP = "signup"               # Yeni kayıt — trial başladı
    TRIAL_EXPIRED = "trial_expired"  # 14g/30g trial bittiğinde otomatik düşüş
    UPGRADE = "upgrade"              # Kullanıcı yükseltti
    DOWNGRADE = "downgrade"          # Kullanıcı veya admin alçalttı
    ADMIN_OVERRIDE = "admin_override"  # Süper admin manuel değiştirdi
    PAUSE = "pause"                  # Yaz pause moduna geçti
    RESUME = "resume"                # Pause'dan döndü
    GUARANTEE_EXTEND = "guarantee_extend"  # 60g performans garantisi 1 ay uzatma
    ACADEMIC_YEAR_RENEWAL = "academic_year_renewal"  # Yıllık plan yenilendi


class PlanOwnerType(str, enum.Enum):
    INSTITUTION = "institution"
    USER = "user"


class PlanChangeHistory(Base):
    """Plan değişikliği audit kaydı."""
    __tablename__ = "plan_change_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[PlanOwnerType] = mapped_column(
        Enum(PlanOwnerType), nullable=False, index=True,
    )
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    from_plan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_plan: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[PlanChangeReason] = mapped_column(
        Enum(PlanChangeReason), nullable=False,
    )
    # Değişikliği tetikleyen kullanıcı (kim tıkladı). Cron/sistem ise NULL.
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    # Ek bağlam: "60 gün performans garantisi nedeniyle 1 ay uzatma" gibi.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<PlanChange {self.owner_type.value}#{self.owner_id} "
            f"{self.from_plan or '?'} → {self.to_plan} ({self.reason.value})>"
        )
