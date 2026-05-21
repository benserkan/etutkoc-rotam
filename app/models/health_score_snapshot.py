"""Sprint F.1 (Ticari Pano 2.0 — Faz C) — Sağlık Skoru günlük snapshot.

Owner başına günde 1 satır: user-facing 0-100 skor + bileşen detay (JSON).
Geçmiş 14-30 günü tutmak yeter; "7 gün üst üste düşüş" tetikleyici için
geriye doğru gidip karşılaştırma yapılır.

**Sprint F.3 — Owner pattern**: Hem Institution hem bağımsız öğretmen User
için snapshot tutulur. `owner_type` ('institution' | 'user') + XOR FK.
- Institution: 6 bileşen (orijinal Health v2)
- User: 5 bileşen (active_teacher kaldırılır, ağırlıklar 100'e yeniden ölçeklenir)

Tasarım kararları:
- UNIQUE (institution_id, snapshot_date) ve (user_id, snapshot_date) — her
  owner için günde 1 snapshot.
- Cron retansiyonu: 60 gün sonrası temizlik (opsiyonel).
- components_json: JSON string — band hesabı snapshot anında dondurulur.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


HEALTH_OWNER_TYPES = ("institution", "user")


HEALTH_BAND_LABELS_TR: dict[str, str] = {
    "champion": "Şampiyon",
    "healthy": "Sağlıklı",
    "at_risk": "Risk altında",
    "critical": "Kritik",
    "lost_imminent": "Kayıp eşiğinde",
}

HEALTH_BAND_COLORS: dict[str, str] = {
    "champion": "emerald",
    "healthy": "lime",
    "at_risk": "amber",
    "critical": "orange",
    "lost_imminent": "rose",
}

HEALTH_BAND_EMOJIS: dict[str, str] = {
    "champion": "🏆",
    "healthy": "🟢",
    "at_risk": "🟡",
    "critical": "🟠",
    "lost_imminent": "🔴",
}


def band_for_score(score: int) -> str:
    """0-100 user-facing skor → band."""
    if score >= 80:
        return "champion"
    if score >= 60:
        return "healthy"
    if score >= 40:
        return "at_risk"
    if score >= 20:
        return "critical"
    return "lost_imminent"


class HealthScoreSnapshot(Base):
    """Bir owner'ın (kurum veya bağımsız öğretmen) belirli tarihteki sağlık skoru."""

    __tablename__ = "health_score_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "institution_id", "snapshot_date",
            name="uq_health_snapshot_inst_date",
        ),
        UniqueConstraint(
            "user_id", "snapshot_date",
            name="uq_health_snapshot_user_date",
        ),
        Index(
            "ix_health_snapshot_inst_date",
            "institution_id", "snapshot_date",
        ),
        Index(
            "ix_health_snapshot_user_date",
            "user_id", "snapshot_date",
        ),
        CheckConstraint(
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
            name="ck_health_snapshots_owner_xor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'institution'"),
    )
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 0-100, yüksek = sağlıklı
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    band: Mapped[str] = mapped_column(String(20), nullable=False)
    # JSON: bileşen → {weight, value_pct, score_contribution}
    components_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Toplam aktif öğretmen/öğrenci sayısı (trigger algılaması için)
    active_teacher_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    active_student_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<HealthScoreSnapshot inst={self.institution_id} "
            f"{self.snapshot_date} score={self.score} band={self.band}>"
        )


__all__ = [
    "HEALTH_BAND_COLORS",
    "HEALTH_BAND_EMOJIS",
    "HEALTH_BAND_LABELS_TR",
    "HEALTH_OWNER_TYPES",
    "HealthScoreSnapshot",
    "band_for_score",
]
