"""Ölçüm listesi — tanımlı ölçüler + günlük toplayıcı + geçmiş okuma (2026-11-08).

YENİ ÖLÇÜ EKLEMEK = `METRICS`'e bir satır + bir toplayıcı fonksiyon. Gece işi
(`metrics_snapshot_daily`, 02:30 UTC) her ölçüyü toplar ve günün değerini
yazar (aynı gün tekrar koşulursa üzerine yazar — idempotent). Takip listesi
(follow_up_service) bu geçmişten "o günden bu yana ne değişti" raporu çıkarır.

Değerler YÜZDE (0-100) ya da sayı olarak saklanır; birim tanımda yazar.
Az örnekli değer (sample_n < min_sample) arayüzde soluk gösterilir ve trend
kararına katılmaz — 12 kalemlik bir koçun %80'i ile 600 kalemlik koçun %80'i
aynı güvende değildir.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.models import MetricSnapshot, User
from app.models.follow_up import METRIC_OWNER_COACH, METRIC_OWNER_SYSTEM

logger = logging.getLogger(__name__)


@dataclass
class Reading:
    owner_type: str
    owner_id: int
    value: float | None
    sample_n: int | None = None
    details: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MetricDef:
    key: str
    label: str
    unit: str            # "%" | "sayı"
    higher_is_better: bool
    description: str     # her zaman görünür açıklama (ne ölçülür, nereden)
    owners: tuple[str, ...]
    min_sample: int
    collect: Callable[[Session], list[Reading]]


# ----------------------------------------------------------------- toplayıcılar


def _weighted(readings: list[Reading], min_sample: int) -> Reading | None:
    ok = [r for r in readings if r.value is not None and (r.sample_n or 0) >= min_sample]
    total = sum(r.sample_n or 0 for r in ok)
    if not total:
        return None
    val = sum((r.value or 0) * (r.sample_n or 0) for r in ok) / total
    return Reading(METRIC_OWNER_SYSTEM, 0, round(val, 1), total, {"coaches": len(ok)})


def _rec_collect(field_default: str, field_learned: str, min_sample: int) -> Callable:
    def collect(db: Session) -> list[Reading]:
        from app.models import CoachRecWeights
        from app.models.rec_weights import REC_STATUS_INSUFFICIENT, REC_STATUS_LEARNED

        out: list[Reading] = []
        for row in db.query(CoachRecWeights).all():
            if row.status == REC_STATUS_INSUFFICIENT:
                continue
            # Koçta gerçekten kullanılan ağırlığın isabeti
            raw = getattr(row, field_learned) if row.status == REC_STATUS_LEARNED else getattr(row, field_default)
            if raw is None:
                continue
            out.append(Reading(METRIC_OWNER_COACH, row.coach_id, round(raw * 100, 1),
                               row.n_items, {"status": row.status}))
        sysr = _weighted(out, min_sample)
        if sysr:
            out.append(sysr)
        return out
    return collect


def _skeleton_acceptance(db: Session) -> list[Reading]:
    from app.models import SkeletonGhostAction
    from app.services.skeleton_suggest import acceptance_report

    since = date.today() - timedelta(days=30)
    coach_ids = [
        cid for (cid,) in db.query(SkeletonGhostAction.coach_id)
        .filter(SkeletonGhostAction.date >= since).distinct()
        if cid
    ]
    out: list[Reading] = []
    for cid in coach_ids:
        rep = acceptance_report(db, coach_id=cid, days=30)
        if rep["actions"]:
            out.append(Reading(METRIC_OWNER_COACH, cid, rep["acceptance_pct"], rep["actions"],
                               {"accepted": rep["accepted"], "other": rep["other"],
                                "dismissed": rep["dismissed"]}))
    rep = acceptance_report(db, days=30)
    if rep["actions"]:
        out.append(Reading(METRIC_OWNER_SYSTEM, 0, rep["acceptance_pct"], rep["actions"],
                           {"accepted": rep["accepted"]}))
    return out


def _email_delivery(db: Session) -> list[Reading]:
    from app.models.communication_log import (
        CHANNEL_EMAIL, FAILURE_STATUSES, SUCCESS_STATUSES, CommunicationLog,
    )

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = (
        db.query(CommunicationLog.status)
        .filter(CommunicationLog.channel == CHANNEL_EMAIL, CommunicationLog.created_at >= since)
        .all()
    )
    ok = sum(1 for (s,) in rows if s in SUCCESS_STATUSES)
    bad = sum(1 for (s,) in rows if s in FAILURE_STATUSES)
    if not ok + bad:
        return []
    return [Reading(METRIC_OWNER_SYSTEM, 0, round(100 * ok / (ok + bad), 1), ok + bad,
                    {"ok": ok, "failed": bad})]


def _active_coaches(db: Session) -> list[Reading]:
    """Son 7 günde en az bir öğrencisine görev yayınlamış koç sayısı."""
    from app.models import Task

    since = date.today() - timedelta(days=7)
    n = (
        db.query(User.teacher_id)
        .join(Task, Task.student_id == User.id)
        .filter(Task.date >= since, Task.is_draft.is_(False), User.teacher_id.isnot(None))
        .distinct()
        .count()
    )
    return [Reading(METRIC_OWNER_SYSTEM, 0, float(n), None)]


METRICS: dict[str, MetricDef] = {
    "rec.shown": MetricDef(
        key="rec.shown",
        label="Öneri isabeti — ekranda",
        unit="%",
        higher_is_better=True,
        description=(
            "Koçun gerçekten verdiği bölüm, önerilerde ekranda gösterilenler arasında mı? "
            "Son 12 haftanın ayrılmış son günlerinde ölçülür (gece öneri öğrenimi hesaplar)."
        ),
        owners=(METRIC_OWNER_SYSTEM, METRIC_OWNER_COACH),
        min_sample=80,
        collect=_rec_collect("shown_default", "shown_learned", 80),
    ),
    "rec.top3": MetricDef(
        key="rec.top3",
        label="Öneri isabeti — ilk 3",
        unit="%",
        higher_is_better=True,
        description="Koçun verdiği bölüm önerilerin ilk üçünde mi? (aynı ölçüm, daha sıkı)",
        owners=(METRIC_OWNER_SYSTEM, METRIC_OWNER_COACH),
        min_sample=80,
        collect=_rec_collect("top3_default", "top3_learned", 80),
    ),
    "skeleton.acceptance": MetricDef(
        key="skeleton.acceptance",
        label="İskelet çip kabulü",
        unit="%",
        higher_is_better=True,
        description=(
            "Son 30 günde koçun iskelet önerilerinde işlediği satırların yüzde kaçında "
            "önerilen çipi kabul ettiği. Hedef ≥%60."
        ),
        owners=(METRIC_OWNER_SYSTEM, METRIC_OWNER_COACH),
        min_sample=10,
        collect=_skeleton_acceptance,
    ),
    "email.delivery": MetricDef(
        key="email.delivery",
        label="E-posta teslim başarısı",
        unit="%",
        higher_is_better=True,
        description="Son 24 saatte gönderilmeye çalışılan e-postaların sağlayıcıya ulaşan payı.",
        owners=(METRIC_OWNER_SYSTEM,),
        min_sample=5,
        collect=_email_delivery,
    ),
    "coaches.active": MetricDef(
        key="coaches.active",
        label="Aktif koç",
        unit="sayı",
        higher_is_better=True,
        description="Son 7 günde en az bir öğrencisine yayınlanmış görevi olan koç sayısı.",
        owners=(METRIC_OWNER_SYSTEM,),
        min_sample=0,
        collect=_active_coaches,
    ),
}


# ----------------------------------------------------------------- yazma


def record(db: Session, key: str, readings: list[Reading], day: date) -> int:
    """Günün değerlerini yazar (aynı gün + sahip varsa günceller)."""
    n = 0
    for r in readings:
        row = (
            db.query(MetricSnapshot)
            .filter(MetricSnapshot.metric_key == key, MetricSnapshot.owner_type == r.owner_type,
                    MetricSnapshot.owner_id == r.owner_id, MetricSnapshot.measured_on == day)
            .one_or_none()
        )
        if row is None:
            row = MetricSnapshot(metric_key=key, owner_type=r.owner_type, owner_id=r.owner_id,
                                 measured_on=day)
            db.add(row)
        row.value = r.value
        row.sample_n = r.sample_n
        row.details_json = json.dumps(r.details, ensure_ascii=False) if r.details else None
        db.flush()
        n += 1
    return n


def collect_all(db: Session, day: date | None = None, keys: list[str] | None = None) -> dict:
    """Tüm ölçüleri toplar. Bir ölçünün hatası diğerlerini durdurmaz."""
    day = day or date.today()
    out: dict[str, int | str] = {}
    for key, md in METRICS.items():
        if keys and key not in keys:
            continue
        try:
            out[key] = record(db, key, md.collect(db), day)
            db.commit()
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.exception("metric collect failed: %s", key)
            out[key] = f"hata: {type(e).__name__}"
    return out


# ----------------------------------------------------------------- okuma


def owner_label(db: Session, owner_type: str, owner_id: int, cache: dict | None = None) -> str:
    if owner_type == METRIC_OWNER_SYSTEM:
        return "Sistem geneli"
    if cache is not None and owner_id in cache:
        return cache[owner_id]
    u = db.get(User, owner_id)
    label = u.full_name if u else f"Silinmiş kullanıcı (#{owner_id})"
    if cache is not None:
        cache[owner_id] = label
    return label


def series(db: Session, key: str, owner_type: str, owner_id: int, since: date) -> list[MetricSnapshot]:
    return (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.metric_key == key, MetricSnapshot.owner_type == owner_type,
                MetricSnapshot.owner_id == owner_id, MetricSnapshot.measured_on >= since)
        .order_by(MetricSnapshot.measured_on)
        .all()
    )


def value_at(db: Session, key: str, owner_type: str, owner_id: int, on: date) -> MetricSnapshot | None:
    """`on` gününde ya da öncesindeki en yakın ölçüm; yoksa sonraki ilk ölçüm."""
    base = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.metric_key == key, MetricSnapshot.owner_type == owner_type,
                MetricSnapshot.owner_id == owner_id, MetricSnapshot.measured_on <= on,
                MetricSnapshot.value.isnot(None))
        .order_by(MetricSnapshot.measured_on.desc())
        .first()
    )
    if base is not None:
        return base
    return (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.metric_key == key, MetricSnapshot.owner_type == owner_type,
                MetricSnapshot.owner_id == owner_id, MetricSnapshot.measured_on >= on,
                MetricSnapshot.value.isnot(None))
        .order_by(MetricSnapshot.measured_on)
        .first()
    )


def latest(db: Session, key: str, owner_type: str, owner_id: int) -> MetricSnapshot | None:
    return (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.metric_key == key, MetricSnapshot.owner_type == owner_type,
                MetricSnapshot.owner_id == owner_id, MetricSnapshot.value.isnot(None))
        .order_by(MetricSnapshot.measured_on.desc())
        .first()
    )


def owners_of(db: Session, key: str) -> list[tuple[str, int]]:
    rows = (
        db.query(MetricSnapshot.owner_type, MetricSnapshot.owner_id)
        .filter(MetricSnapshot.metric_key == key)
        .distinct()
        .all()
    )
    return [(t, i) for t, i in rows]
