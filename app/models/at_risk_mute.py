"""AtRiskMute — risk panelinde yanlış alarm sustur kaydı.

Öğretmen "bu öğrenci risk değil" derse 7 gün boyunca panelden gizler.
Süre dolunca tekrar görünür (yanlış pozitif kalıcı yok edilemez).

Tasarım:
- (teacher_id, student_id) unique — bir öğretmenin bir öğrencide birden çok
  aktif mute'u olamaz
- expires_at: süre dolunca silinmek yerine "geçmiş" olur — audit trail için
- created_at: ne zaman muteland (operatör log analizi için)
- reason: opsiyonel açıklama (öğretmen "tatil, dönecek" yazabilir)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# Mute süresi sabit — 7 gün. Değiştirmek istersen migration veya admin UI gerek.
AT_RISK_MUTE_DAYS = 7


class AtRiskMute(Base):
    __tablename__ = "at_risk_mutes"
    __table_args__ = (
        UniqueConstraint("teacher_id", "student_id", name="uq_at_risk_mute_pair"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_id])
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])

    @property
    def is_active(self) -> bool:
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp > datetime.now(timezone.utc)


def default_mute_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=AT_RISK_MUTE_DAYS)
