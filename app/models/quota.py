"""Stage 8 — Kurum kuotaları (anlık entity sayım limitleri).

Kredi sisteminden (`usage.py`) farklı:
- Kredi: aylık tüketilebilir kaynak (AI çağrısı, e-posta) — period bazlı reset
- Kuota: anlık entity sayısı (öğretmen, öğrenci, kurum admin) — yaratılınca
  "limit doldu" engeli; sayı düşünce yer açılır

Plan başına default kuotalar `app/services/quotas.py:PLAN_QUOTAS` içinde.
Süper admin manuel override koyabilir (örn. "free planındaki müşterimize bu
ay özel 50 öğrenci açıyoruz").

`override_value = -1` → sınırsız (enterprise default).
`override_value = 0` → kapalı (hiç oluşturulamaz — nadir kullanım).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.institution import Institution


class InstitutionQuotaOverride(Base):
    """Bir kuruma özel kuota override.

    quota_key: 'teachers' | 'students' | 'institution_admins' | gelecek anahtarlar
    override_value: -1 = sınırsız, 0 = kapalı, N>0 = sayı limiti
    """
    __tablename__ = "institution_quota_overrides"
    __table_args__ = (
        UniqueConstraint(
            "institution_id", "quota_key",
            name="uq_quota_override_inst_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    quota_key: Mapped[str] = mapped_column(String(40), nullable=False)
    override_value: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    institution: Mapped["Institution"] = relationship("Institution")

    def __repr__(self) -> str:
        return (
            f"<QuotaOverride inst={self.institution_id} "
            f"{self.quota_key}={self.override_value}>"
        )
