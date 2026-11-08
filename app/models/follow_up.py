"""Ölçüm geçmişi + takip listesi (2026-11-08).

İki parça, tek amaç: "2-3 hafta sonra bakılacak" işler unutulmasın.

- `MetricSnapshot` — ölçüm listesi. Her gün, tanımlı her ölçü için (sistem
  geneli ve/veya koç başına) bir değer yazılır. Ölçüm kimsenin bir betik
  koşmasını beklemez; geçmiş kendiliğinden birikir.
- `FollowUp` — takip listesi. Tarihli yapılacak. Vadesi gelince süper admine
  panelde rozet + e-posta + push gider. Bir ölçüye bağlıysa (check_kind) vade
  günü sistem ölçümü kendisi değerlendirir ve sonucu kayda yazar; insan yalnız
  karar verir.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# --------------------------------------------------------------- ölçüm sahibi
METRIC_OWNER_SYSTEM = "system"  # sistem geneli (owner_id = 0)
METRIC_OWNER_COACH = "coach"    # koç başına (owner_id = koç kullanıcı id)

# --------------------------------------------------------------- takip
FU_STATUS_OPEN = "open"
FU_STATUS_DONE = "done"
FU_STATUS_CANCELLED = "cancelled"
FU_STATUSES = (FU_STATUS_OPEN, FU_STATUS_DONE, FU_STATUS_CANCELLED)

FU_CATEGORIES = {
    "olcum": "Ölçüm",
    "urun": "Ürün",
    "veri": "Veri düzeltme",
    "musteri": "Müşteri",
    "pazarlama": "Pazarlama",
    "altyapi": "Altyapı",
    "diger": "Diğer",
}
FU_PRIORITIES = {"high": "Önemli", "normal": "Normal"}

# Vadesi geçmiş ama kapanmamış iş: her gün değil, bu aralıkla yeniden hatırlat
# (her gün aynı e-posta = alarm körlüğü).
FU_OVERDUE_REMIND_DAYS = 3
# Yaklaşan işler özette kaç gün önceden görünsün
FU_UPCOMING_DAYS = 7


class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    __table_args__ = (
        UniqueConstraint("metric_key", "owner_type", "owner_id", "measured_on",
                         name="uq_metric_snapshot_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(String(16), nullable=False, default=METRIC_OWNER_SYSTEM)
    owner_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    measured_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Değerin dayandığı örnek sayısı (ör. ölçülen kalem) — az örnekli değer
    # arayüzde soluk gösterilir, karar bunlardan çıkarılmaz.
    sample_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Tohum kayıtlar için kararlı anahtar (idempotent seed). Elle girilende boş.
    key: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(24), nullable=False, default="diger")
    priority: Mapped[str] = mapped_column(String(8), nullable=False, default="normal")
    due_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    snoozed_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default=FU_STATUS_OPEN, index=True)
    # Tamamlanınca N gün sonrasına aynı iş yeniden açılır (None = tek seferlik)
    recurrence_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Otomatik değerlendirme: "metric_trend" (ölçüye bağlı) ya da None (elle)
    check_kind: Mapped[str | None] = mapped_column(String(48), nullable=True)
    check_params_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ölçüm karşılaştırmasının başlangıç günü ("o günden bu yana ne değişti")
    baseline_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bildirim tekrarını sınırlar (aynı gün iki kez gönderilmez)
    notified_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    result_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Tekrarlayan işte önceki kayıt (zincir)
    previous_id: Mapped[int | None] = mapped_column(
        ForeignKey("follow_ups.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    @property
    def effective_due(self) -> date:
        if self.snoozed_until and self.snoozed_until > self.due_on:
            return self.snoozed_until
        return self.due_on
