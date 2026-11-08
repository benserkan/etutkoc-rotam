"""API v2 — Süper Admin: Takip listesi + Ölçüm listesi (2026-11-08).

Takip listesi: tarihli yapılacaklar; ölçüye bağlı olanlarda vade günü sistem
sonucu kendisi hesaplar. Ölçüm listesi: tanımlı ölçülerin günlük geçmişi
(sistem geneli + koç kırılımı).
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_db
from app.models import FollowUp, User
from app.models.follow_up import (
    FU_CATEGORIES, FU_PRIORITIES, FU_STATUS_OPEN, FU_UPCOMING_DAYS,
    METRIC_OWNER_COACH, METRIC_OWNER_SYSTEM,
)
from app.routes.api_v2.admin import _require_super_admin
from app.services import follow_up_service as fus
from app.services import metrics_registry as mr

router = APIRouter(prefix="/admin", tags=["v2-admin-follow-ups"])

_INV = ["admin:follow-ups", "admin:badges"]


# ----------------------------------------------------------------- şemalar


class CheckParams(BaseModel):
    metric_key: str
    owner_type: str = METRIC_OWNER_SYSTEM
    min_change: float = Field(3, ge=0.5, le=50)


class FollowUpBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=4000)
    due_on: date
    category: str = "diger"
    priority: str = "normal"
    recurrence_days: int | None = None
    check: CheckParams | None = None
    baseline_on: date | None = None


class FollowUpPatchBody(BaseModel):
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=4000)
    due_on: date | None = None
    category: str | None = None
    priority: str | None = None
    recurrence_days: int | None = None
    clear_recurrence: bool = False
    check: CheckParams | None = None
    clear_check: bool = False
    baseline_on: date | None = None


class CompleteBody(BaseModel):
    note: str | None = Field(None, max_length=4000)
    next_due: date | None = None


class SnoozeBody(BaseModel):
    days: int | None = Field(None, ge=1, le=365)
    until: date | None = None


class CancelBody(BaseModel):
    note: str | None = Field(None, max_length=4000)


class ReopenBody(BaseModel):
    due_on: date | None = None


# ----------------------------------------------------------------- yardımcılar


def _err(e: fus.FollowUpError):
    raise HTTPException(status_code=422, detail={"error": "follow_up", "code": e.code, "message": e.message})


def _get(db: Session, fid: int) -> FollowUp:
    it = db.get(FollowUp, fid)
    if it is None:
        raise HTTPException(status_code=404, detail={"error": "follow_up", "code": "not_found", "message": "Kayıt yok."})
    return it


def _item(db: Session, it: FollowUp, today: date, names: dict) -> dict:
    eff = it.effective_due
    p = fus.params_of(it)
    md = mr.METRICS.get(p.get("metric_key")) if it.check_kind else None

    def _name(uid):
        if not uid:
            return None
        if uid not in names:
            u = db.get(User, uid)
            names[uid] = u.full_name if u else None
        return names[uid]

    return {
        "id": it.id,
        "key": it.key,
        "title": it.title,
        "description": it.description,
        "category": it.category,
        "category_label": FU_CATEGORIES.get(it.category, it.category),
        "priority": it.priority,
        "status": it.status,
        "bucket": fus.bucket(it, today),
        "due_on": it.due_on.isoformat(),
        "snoozed_until": it.snoozed_until.isoformat() if it.snoozed_until else None,
        "effective_due": eff.isoformat(),
        "days_left": (eff - today).days,
        "recurrence_days": it.recurrence_days,
        "check_kind": it.check_kind,
        "check": ({"metric_key": p.get("metric_key"), "metric_label": md.label if md else p.get("metric_key"),
                   "owner_type": p.get("owner_type", METRIC_OWNER_SYSTEM),
                   "min_change": p.get("min_change", 3)} if it.check_kind else None),
        "baseline_on": it.baseline_on.isoformat() if it.baseline_on else None,
        "report": fus.report_of(it),
        "last_checked_at": it.last_checked_at.isoformat() if it.last_checked_at else None,
        "notified_on": it.notified_on.isoformat() if it.notified_on else None,
        "completed_at": it.completed_at.isoformat() if it.completed_at else None,
        "completed_by_name": _name(it.completed_by_id),
        "result_note": it.result_note,
        "previous_id": it.previous_id,
        "created_by_name": _name(it.created_by_id),
        "created_at": it.created_at.isoformat() if it.created_at else None,
    }


def _metric_meta() -> list[dict]:
    return [
        {"key": m.key, "label": m.label, "unit": m.unit, "description": m.description,
         "owners": list(m.owners), "higher_is_better": m.higher_is_better,
         "min_sample": m.min_sample}
        for m in mr.METRICS.values()
    ]


# ----------------------------------------------------------------- takip listesi


@router.get("/follow-ups")
def list_follow_ups(
    status: str = Query("open", pattern="^(open|closed|all)$"),
    user: User = Depends(_require_super_admin),
    db: Session = Depends(get_db),
):
    today = date.today()
    names: dict = {}
    items = [_item(db, it, today, names) for it in fus.list_items(db, status=status)]
    return {
        "items": items,
        "counts": fus.counts(db, today),
        "today": today.isoformat(),
        "upcoming_days": FU_UPCOMING_DAYS,
        "meta": {
            "categories": FU_CATEGORIES,
            "priorities": FU_PRIORITIES,
            "metrics": _metric_meta(),
            "owner_types": {METRIC_OWNER_SYSTEM: "Sistem geneli", METRIC_OWNER_COACH: "Koç bazında"},
        },
    }


@router.post("/follow-ups")
def create_follow_up(body: FollowUpBody, user: User = Depends(_require_super_admin),
                     db: Session = Depends(get_db)):
    try:
        it = fus.create(
            db, actor_id=user.id, title=body.title, description=body.description,
            due_on=body.due_on, category=body.category, priority=body.priority,
            recurrence_days=body.recurrence_days,
            check_kind="metric_trend" if body.check else None,
            check_params=body.check.model_dump() if body.check else None,
            baseline_on=body.baseline_on,
        )
        if it.check_kind:
            fus.evaluate(db, it)
    except fus.FollowUpError as e:
        db.rollback()
        _err(e)
    db.commit()
    return {"data": _item(db, it, date.today(), {}), "invalidate": _INV}


@router.post("/follow-ups/{fid}")
def update_follow_up(fid: int, body: FollowUpPatchBody, user: User = Depends(_require_super_admin),
                     db: Session = Depends(get_db)):
    it = _get(db, fid)
    fields: dict = {}
    for k in ("title", "description", "due_on", "category", "priority", "baseline_on"):
        v = getattr(body, k)
        if v is not None:
            fields[k] = v
    if body.clear_recurrence:
        fields["recurrence_days"] = None
    elif body.recurrence_days is not None:
        fields["recurrence_days"] = body.recurrence_days
    if body.clear_check:
        fields["check_kind"] = None
        fields["check_params"] = None
    elif body.check is not None:
        fields["check_kind"] = "metric_trend"
        fields["check_params"] = body.check.model_dump()
    try:
        fus.update(db, it, **fields)
        if it.check_kind:
            fus.evaluate(db, it)
    except fus.FollowUpError as e:
        db.rollback()
        _err(e)
    db.commit()
    return {"data": _item(db, it, date.today(), {}), "invalidate": _INV}


@router.post("/follow-ups/{fid}/complete")
def complete_follow_up(fid: int, body: CompleteBody, user: User = Depends(_require_super_admin),
                       db: Session = Depends(get_db)):
    it = _get(db, fid)
    try:
        nxt = fus.complete(db, it, actor_id=user.id, note=body.note, next_due=body.next_due)
    except fus.FollowUpError as e:
        db.rollback()
        _err(e)
    db.commit()
    names: dict = {}
    return {"data": {"item": _item(db, it, date.today(), names),
                     "next": _item(db, nxt, date.today(), names) if nxt else None},
            "invalidate": _INV}


@router.post("/follow-ups/{fid}/snooze")
def snooze_follow_up(fid: int, body: SnoozeBody, user: User = Depends(_require_super_admin),
                     db: Session = Depends(get_db)):
    it = _get(db, fid)
    until = body.until or (date.today() + timedelta(days=body.days or 3))
    try:
        fus.snooze(it, until=until)
    except fus.FollowUpError as e:
        _err(e)
    db.commit()
    return {"data": _item(db, it, date.today(), {}), "invalidate": _INV}


@router.post("/follow-ups/{fid}/cancel")
def cancel_follow_up(fid: int, body: CancelBody, user: User = Depends(_require_super_admin),
                     db: Session = Depends(get_db)):
    it = _get(db, fid)
    try:
        fus.cancel(it, note=body.note)
    except fus.FollowUpError as e:
        _err(e)
    db.commit()
    return {"data": _item(db, it, date.today(), {}), "invalidate": _INV}


@router.post("/follow-ups/{fid}/reopen")
def reopen_follow_up(fid: int, body: ReopenBody, user: User = Depends(_require_super_admin),
                     db: Session = Depends(get_db)):
    it = _get(db, fid)
    try:
        fus.reopen(it, due_on=body.due_on)
    except fus.FollowUpError as e:
        _err(e)
    db.commit()
    return {"data": _item(db, it, date.today(), {}), "invalidate": _INV}


@router.post("/follow-ups/{fid}/check")
def check_follow_up(fid: int, user: User = Depends(_require_super_admin),
                    db: Session = Depends(get_db)):
    """Ölçüm değerlendirmesini ŞİMDİ koşar (vadeyi beklemeden)."""
    it = _get(db, fid)
    if not it.check_kind:
        raise HTTPException(status_code=422, detail={"error": "follow_up", "code": "no_check",
                                                      "message": "Bu iş bir ölçüye bağlı değil."})
    fus.evaluate(db, it)
    db.commit()
    return {"data": _item(db, it, date.today(), {}), "invalidate": ["admin:follow-ups"]}


@router.post("/follow-ups/{fid}/delete")
def delete_follow_up(fid: int, user: User = Depends(_require_super_admin),
                     db: Session = Depends(get_db)):
    """Yalnız kapalı (tamamlanmış/iptal) iş silinir — açık iş önce iptal edilir."""
    it = _get(db, fid)
    if it.status == FU_STATUS_OPEN:
        raise HTTPException(status_code=422, detail={"error": "follow_up", "code": "still_open",
                                                      "message": "Açık iş silinmez; önce iptal et."})
    db.delete(it)
    db.commit()
    return {"data": {"deleted": True}, "invalidate": _INV}


# ----------------------------------------------------------------- ölçüm listesi


@router.get("/metrics")
def list_metrics(user: User = Depends(_require_super_admin), db: Session = Depends(get_db)):
    """Her ölçünün sistem geneli son değeri + 7/30 gün önceye göre değişim + son 60 gün."""
    today = date.today()
    out = []
    for md in mr.METRICS.values():
        last = mr.latest(db, md.key, METRIC_OWNER_SYSTEM, 0)
        pts = mr.series(db, md.key, METRIC_OWNER_SYSTEM, 0, today - timedelta(days=60))
        d7 = mr.value_at(db, md.key, METRIC_OWNER_SYSTEM, 0, today - timedelta(days=7))
        d30 = mr.value_at(db, md.key, METRIC_OWNER_SYSTEM, 0, today - timedelta(days=30))

        def _delta(ref):
            if not last or not ref or ref.measured_on >= last.measured_on:
                return None
            return round((last.value or 0) - (ref.value or 0), 1)

        coach_n = sum(1 for t, _ in mr.owners_of(db, md.key) if t == METRIC_OWNER_COACH)
        out.append({
            **next(m for m in _metric_meta() if m["key"] == md.key),
            "latest_value": last.value if last else None,
            "latest_on": last.measured_on.isoformat() if last else None,
            "sample_n": last.sample_n if last else None,
            "delta_7d": _delta(d7),
            "delta_30d": _delta(d30),
            "coach_count": coach_n,
            "points": [{"on": p.measured_on.isoformat(), "value": p.value} for p in pts],
        })
    first = None
    from app.models import MetricSnapshot
    row = db.query(MetricSnapshot.measured_on).order_by(MetricSnapshot.measured_on).first()
    if row:
        first = row[0].isoformat()
    return {"metrics": out, "today": today.isoformat(), "history_since": first}


@router.get("/metrics/{metric_key}")
def metric_detail(metric_key: str, days: int = Query(90, ge=7, le=730),
                  user: User = Depends(_require_super_admin), db: Session = Depends(get_db)):
    md = mr.METRICS.get(metric_key)
    if md is None:
        raise HTTPException(status_code=404, detail={"error": "follow_up", "code": "not_found", "message": "Ölçü yok."})
    today = date.today()
    since = today - timedelta(days=days)
    names: dict = {}
    owners = []
    for t, oid in mr.owners_of(db, metric_key):
        pts = mr.series(db, metric_key, t, oid, since)
        if not pts:
            continue
        last = pts[-1]
        ref = mr.value_at(db, metric_key, t, oid, today - timedelta(days=21))
        owners.append({
            "owner_type": t, "owner_id": oid,
            "owner_label": mr.owner_label(db, t, oid, names),
            "latest_value": last.value, "latest_on": last.measured_on.isoformat(),
            "sample_n": last.sample_n,
            "enough_sample": (last.sample_n or 0) >= md.min_sample or md.min_sample == 0,
            "delta_21d": (round((last.value or 0) - (ref.value or 0), 1)
                          if ref and ref.measured_on < last.measured_on and last.value is not None
                          and ref.value is not None else None),
            "points": [{"on": p.measured_on.isoformat(), "value": p.value, "n": p.sample_n} for p in pts],
        })
    owners.sort(key=lambda o: (o["owner_type"] != METRIC_OWNER_SYSTEM, -(o["sample_n"] or 0)))
    meta = next(m for m in _metric_meta() if m["key"] == metric_key)
    linked = [
        {"id": it.id, "title": it.title, "effective_due": it.effective_due.isoformat()}
        for it in db.query(FollowUp).filter(FollowUp.status == FU_STATUS_OPEN,
                                            FollowUp.check_kind.isnot(None)).all()
        if fus.params_of(it).get("metric_key") == metric_key
    ]
    return {"metric": meta, "days": days, "owners": owners, "linked_follow_ups": linked}


@router.post("/metrics/collect")
def collect_metrics_now(user: User = Depends(_require_super_admin), db: Session = Depends(get_db)):
    """Bugünün ölçümünü ŞİMDİ al (gece işini beklemeden; aynı gün üzerine yazar)."""
    summary = mr.collect_all(db, date.today())
    return {"data": summary, "invalidate": ["admin:metrics", "admin:follow-ups"]}
