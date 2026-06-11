"""Panel hızlı erişim — davranıştan öğrenen kartlar (QA-1).

İki tablo:
  - PanelVisitEvent: ham ziyaret olayı. Ham URL SAKLANMAZ — yalnız rota
    kataloğundan geçen normalize route_key + entity_id (KVKK: gezinti
    geçmişi değil, katalog anahtarı). 180 gün saklanır; panel_events_purge
    cron'u eskileri siler. Kullanıcı yüzeyini BESLEMEZ — analiz hammaddesi.
  - PanelRouteStat: kullanıcı + route_key + entity_id başına TEK satır
    agregat. EWMA skor (yarılanma ~14 gün) + sayaçlar + kullanıcı kararları
    (sabitle / kaldır). Hızlı erişim kartlarını besleyen tek kaynak.

entity_id=0 = entity'siz (sayfa-düzeyi) satır. UNIQUE constraint'te NULL'lar
eşit sayılmadığından NULL yerine 0 kullanılır.

Yaşam döngüsü (panel_behavior servisi):
  ADAY → (skor ≥ eşik VE ≥3 farklı gün) → ÖNERİLEN
  ÖNERİLEN → (karta 3 tıklama VEYA elle sabitle) → KALICI
  Kaldırılan rota dismissed_until (90 gün) boyunca önerilmez.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class PanelVisitEvent(Base):
    __tablename__ = "panel_visit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    route_key: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dwell_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="web")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PanelVisitEvent u={self.user_id} {self.route_key} e={self.entity_id}>"


class PanelRouteStat(Base):
    __tablename__ = "panel_route_stats"
    __table_args__ = (
        UniqueConstraint("user_id", "route_key", "entity_id", name="uq_panel_route_stat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    route_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # 0 = entity'siz (sayfa-düzeyi)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    days_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dwell_ms_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_visit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_visit_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Kart kararları
    card_clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pinned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PanelRouteStat u={self.user_id} {self.route_key} e={self.entity_id} s={self.score:.2f}>"
