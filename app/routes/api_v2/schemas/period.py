"""Dönem filtresi ortak şemaları (P3, 2026-09-04).

Konu performansı · deneme listesi/trendi · deneme konu analizi · analitik
yüzeylerinin hepsi aynı meta bloğunu döner; UI tek bir dönem seçicisi çizer.
"""
from __future__ import annotations

from pydantic import BaseModel


class PeriodOption(BaseModel):
    id: int
    label: str                 # "9. Sınıf (2026-2027)"
    grade_label: str           # "9. Sınıf"
    started_on: str
    ended_on: str | None = None
    is_current: bool


class PeriodFilterMeta(BaseModel):
    """Görünümün hangi döneme göre süzüldüğü + seçenekler.

    `applied=False` → süzme YOK (dönem kaydı yok ya da 'tüm zamanlar' seçildi);
    bu durumda UI seçiciyi göstermez, eski davranış birebir korunur.
    """
    applied: bool = False
    active_key: str = "all"            # "all" | "<period_id>"
    active_label: str | None = None
    started_on: str | None = None
    ended_on: str | None = None
    options: list[PeriodOption] = []
