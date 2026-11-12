"""Haftalık yönetici özeti — veri güvenilirliği (2026-11-12).

Kurum yöneticisine giden sayılar stratejik önemde. Kural (kullanıcı kararı):
fark bulunursa bölüm ATILMAZ; sorun giderilir (bağımsız hesap esas alınır) ve
verinin son hâli için bir GÜVENİLİRLİK SKORU hesaplanır. Skor ve her kontrolün
sonucu özet kaydına (`admin_weekly_digests.payload_json["reliability"]`) yazılır,
arşiv ekranında görünür.

İki katman:
  1. Tutarlılık kontrolleri — panel servisinin verdiği sayı, AYRI bir kod yolundan
     (ham görev kalemleri, Python tarafı `completion.item_counts`) yeniden hesaplanır.
     Eşleşmezse bağımsız hesap esas alınır ve kontrol "düzeltildi" olarak kaydedilir.
  2. Veri kalitesi — sayılar doğru olsa da ne kadar dayanıklı: program kapsaması,
     doğru/yanlış girişi, işaretleme düzeni, deneme kapsaması.

Skor = 0,4 × tutarlılık + 0,6 × veri kalitesi (0–100).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session, selectinload

from app.models import Task, TaskBookItem
from app.services import completion


@dataclass
class Check:
    key: str
    label: str
    status: str            # ok | fixed | warn
    detail: str

    def as_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "status": self.status, "detail": self.detail}


@dataclass
class Component:
    key: str
    label: str
    score: int | None      # 0–100; None = ölçülemedi (skora girmez)
    detail: str

    def as_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "score": self.score, "detail": self.detail}


@dataclass
class Reliability:
    checks: list[Check] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)

    def consistency(self) -> int:
        pen = sum(5 if c.status == "fixed" else 15 if c.status == "warn" else 0 for c in self.checks)
        return max(0, 100 - pen)

    def quality(self) -> int | None:
        vals = [c.score for c in self.components if c.score is not None]
        return round(sum(vals) / len(vals)) if vals else None

    def score(self) -> int:
        q = self.quality()
        if q is None:
            return self.consistency()
        return round(0.4 * self.consistency() + 0.6 * q)

    def as_dict(self) -> dict:
        s = self.score()
        level = "high" if s >= 80 else "medium" if s >= 60 else "low"
        return {
            "score": s,
            "level": level,
            "level_label": {"high": "Yüksek", "medium": "Orta", "low": "Düşük"}[level],
            "consistency": self.consistency(),
            "quality": self.quality(),
            "checks": [c.as_dict() for c in self.checks],
            "components": [c.as_dict() for c in self.components],
            "fixed_count": sum(1 for c in self.checks if c.status == "fixed"),
        }


def independent_totals(db: Session, student_ids: list[int], start: date, end: date) -> dict[int, list[int]]:
    """Bağımsız hesap: görev kalemleri Python'da `item_counts` ile süzülür (SQL süzgecinden
    farklı kod yolu). Dönüş: öğrenci → [planlanan, çözülen, doğru, yanlış, sonuçlu_test]."""
    out: dict[int, list[int]] = {}
    if not student_ids:
        return out
    tasks = (db.query(Task)
             .options(selectinload(Task.book_items).joinedload(TaskBookItem.book))
             .filter(Task.student_id.in_(student_ids), Task.is_draft.is_(False),
                     Task.date >= start, Task.date <= end)
             .all())
    for t in tasks:
        acc = out.setdefault(int(t.student_id), [0, 0, 0, 0, 0])
        for it in t.book_items:
            if not completion.item_counts(it):
                continue
            c = int(it.completed_count or 0)
            acc[0] += int(it.planned_count or 0)
            acc[1] += c
            acc[2] += int(it.correct_count or 0)
            acc[3] += int(it.wrong_count or 0)
            if c and (it.correct_count is not None or it.wrong_count is not None):
                acc[4] += c
    return out


def marking_ratio(db: Session, student_ids: list[int], today: date) -> tuple[int, int]:
    """(toplu işaretleme uyarısı OLMAYAN öğrenci, değerlendirilen öğrenci) — öğrenci
    özetindeki kuralla aynı (son 14 gün)."""
    from app.services.student_overview import RELIAB_DAYS, reliability

    if not student_ids:
        return 0, 0
    since = today - timedelta(days=RELIAB_DAYS)
    tasks = (db.query(Task)
             .options(selectinload(Task.book_items).joinedload(TaskBookItem.book))
             .filter(Task.student_id.in_(student_ids), Task.is_draft.is_(False),
                     Task.date >= since, Task.date <= today)
             .all())
    by: dict[int, list[Task]] = {}
    for t in tasks:
        by.setdefault(int(t.student_id), []).append(t)
    judged = clean = 0
    # reliability() "bugün"ü dışlar; özet Pazar akşamına göre → today + 1
    for sid, ts in by.items():
        warns = reliability(ts, today + timedelta(days=1))
        keys = {w["key"] for w in warns}
        if not keys & {"bulk", "next_day", "marking_ok"}:
            continue          # yeterli işaretleme yok — değerlendirmeye girmez
        judged += 1
        if "bulk" not in keys:
            clean += 1
    return clean, judged
