"""Stage 7 — Feature flags: özellikleri runtime'da aç/kapa.

Süper admin şu kararı verebilsin:
- "Bu özellik artık herkese kapalı" (global False)
- "Bu kuruma özel açık tut" (override per-institution)
- "Yeni AI özelliğini sadece pilot kuruma aç" (default kapalı, override aç)

İki tablo:
- FeatureFlag: ana liste (key + global default)
- FeatureFlagOverride: per-kurum override (None institution_id = global ayar
  yeterli; varsa o satır kullanılır)

Bilinçli sadelik:
- Yüzde (percentage rollout) yok — bu ölçekte gereksiz karmaşa
- User cohort'ları yok — kurum granularitesi yeterli
- Versiyonlama yok — tek satır, last write wins (audit log değişiklikleri yakalar)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
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


class FeatureFlag(Base):
    """Bir özellik bayrağı — global default + isimli kayıt.

    `key` programatik referans (örn. "ai_book_template"). UI'da `description`
    okunur, kod tarafından `is_enabled(key)` çağrılır.
    """
    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint("key", name="uq_feature_flag_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Snake_case anahtarsız geçilmez — kod kullanır
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled_globally: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    overrides: Mapped[list["FeatureFlagOverride"]] = relationship(
        "FeatureFlagOverride",
        back_populates="flag",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<FeatureFlag {self.key} global={self.enabled_globally}>"


class FeatureFlagOverride(Base):
    """Bir bayrağın belirli kurum için override'ı.

    UNIQUE(flag_id, institution_id): aynı kuruma 2 override yok.
    Override varsa global ayardan ÖNCE değerlendirilir.
    """
    __tablename__ = "feature_flag_overrides"
    __table_args__ = (
        UniqueConstraint(
            "feature_flag_id", "institution_id",
            name="uq_feature_flag_override_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feature_flag_id: Mapped[int] = mapped_column(
        ForeignKey("feature_flags.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    flag: Mapped["FeatureFlag"] = relationship(
        "FeatureFlag", back_populates="overrides",
    )
    institution: Mapped["Institution"] = relationship("Institution")

    def __repr__(self) -> str:
        return (
            f"<FeatureFlagOverride flag={self.feature_flag_id} "
            f"inst={self.institution_id} enabled={self.enabled}>"
        )
