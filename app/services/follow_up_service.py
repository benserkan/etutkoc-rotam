"""Takip listesi — tarihli yapılacaklar + otomatik ölçüm değerlendirmesi (2026-11-08).

Akış:
1. İş açılır (elle ya da tohum betiğiyle): başlık + vade + kategori; ölçüme
   bağlıysa `check_kind="metric_trend"` + {metric_key, owner_type}.
2. Gece `follow_up_daily` (09:00 TR): vadesi gelen/geçen açık işler için
   - ölçüye bağlıysa değerlendirme koşulur, rapor kayda yazılır
     ("başlangıçtan bu yana hangi koç düştü/yükseldi");
   - süper admine TEK özet e-posta + push gider (vade günü bir kez, gecikmişse
     3 günde bir — her gün aynı e-posta alarm körlüğü yaratır).
3. İnsan karar verir: Tamamla (sonuç notu) · Ertele · İptal. Tekrarlayan iş
   tamamlanınca bir sonraki kendiliğinden açılır (yeni başlangıç = bugün).

Panel rozeti (`count_due`) vadesi gelmiş açık iş sayısıdır — işleyince azalır.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import FollowUp, User
from app.models.follow_up import (
    FU_CATEGORIES,
    FU_OVERDUE_REMIND_DAYS,
    FU_PRIORITIES,
    FU_STATUS_CANCELLED,
    FU_STATUS_DONE,
    FU_STATUS_OPEN,
    FU_UPCOMING_DAYS,
    METRIC_OWNER_COACH,
    METRIC_OWNER_SYSTEM,
)
from app.services import metrics_registry as mr

logger = logging.getLogger(__name__)

CHECK_KINDS = {"metric_trend": "Ölçüm eğilimi"}


class FollowUpError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ----------------------------------------------------------------- yardımcılar


def _today() -> date:
    return date.today()


def params_of(item: FollowUp) -> dict:
    try:
        return json.loads(item.check_params_json) if item.check_params_json else {}
    except Exception:  # noqa: BLE001
        return {}


def report_of(item: FollowUp) -> dict | None:
    try:
        return json.loads(item.last_report_json) if item.last_report_json else None
    except Exception:  # noqa: BLE001
        return None


def bucket(item: FollowUp, today: date | None = None) -> str:
    """overdue | today | upcoming | later | done | cancelled"""
    today = today or _today()
    if item.status == FU_STATUS_DONE:
        return "done"
    if item.status == FU_STATUS_CANCELLED:
        return "cancelled"
    eff = item.effective_due
    if eff < today:
        return "overdue"
    if eff == today:
        return "today"
    if eff <= today + timedelta(days=FU_UPCOMING_DAYS):
        return "upcoming"
    return "later"


def _validate(*, category: str, priority: str, check_kind: str | None, params: dict | None,
              recurrence_days: int | None) -> None:
    if category not in FU_CATEGORIES:
        raise FollowUpError("invalid_category", "Geçersiz kategori.")
    if priority not in FU_PRIORITIES:
        raise FollowUpError("invalid_priority", "Geçersiz öncelik.")
    if recurrence_days is not None and not (1 <= recurrence_days <= 365):
        raise FollowUpError("invalid_recurrence", "Tekrar aralığı 1-365 gün olmalı.")
    if check_kind:
        if check_kind not in CHECK_KINDS:
            raise FollowUpError("invalid_check", "Geçersiz otomatik kontrol.")
        key = (params or {}).get("metric_key")
        if key not in mr.METRICS:
            raise FollowUpError("invalid_metric", "Bağlanan ölçü tanımlı değil.")
        owner = (params or {}).get("owner_type", METRIC_OWNER_SYSTEM)
        if owner not in mr.METRICS[key].owners:
            raise FollowUpError("invalid_metric_owner", "Bu ölçü bu kapsamda tutulmuyor.")


# ----------------------------------------------------------------- yazma


def create(db: Session, *, actor_id: int | None, title: str, due_on: date,
           description: str | None = None, category: str = "diger", priority: str = "normal",
           recurrence_days: int | None = None, check_kind: str | None = None,
           check_params: dict | None = None, baseline_on: date | None = None,
           key: str | None = None) -> FollowUp:
    title = (title or "").strip()
    if not title:
        raise FollowUpError("title_required", "Başlık boş olamaz.")
    _validate(category=category, priority=priority, check_kind=check_kind,
              params=check_params, recurrence_days=recurrence_days)
    item = FollowUp(
        key=key, title=title[:200], description=(description or "").strip() or None,
        category=category, priority=priority, due_on=due_on, status=FU_STATUS_OPEN,
        recurrence_days=recurrence_days, check_kind=check_kind or None,
        check_params_json=json.dumps(check_params, ensure_ascii=False) if check_kind else None,
        # Ölçüm karşılaştırması: başlangıç verilmediyse kayıt günü
        baseline_on=(baseline_on or _today()) if check_kind else None,
        created_by_id=actor_id,
    )
    db.add(item)
    db.flush()
    return item


def update(db: Session, item: FollowUp, **fields) -> FollowUp:
    if "title" in fields and fields["title"] is not None:
        t = fields["title"].strip()
        if not t:
            raise FollowUpError("title_required", "Başlık boş olamaz.")
        item.title = t[:200]
    if "description" in fields:
        item.description = (fields["description"] or "").strip() or None
    if fields.get("due_on"):
        item.due_on = fields["due_on"]
        item.snoozed_until = None
        item.notified_on = None
    category = fields.get("category") or item.category
    priority = fields.get("priority") or item.priority
    recurrence = fields["recurrence_days"] if "recurrence_days" in fields else item.recurrence_days
    check_kind = fields["check_kind"] if "check_kind" in fields else item.check_kind
    params = fields["check_params"] if "check_params" in fields else params_of(item)
    _validate(category=category, priority=priority, check_kind=check_kind or None,
              params=params, recurrence_days=recurrence)
    item.category, item.priority, item.recurrence_days = category, priority, recurrence
    if "check_kind" in fields or "check_params" in fields:
        item.check_kind = check_kind or None
        item.check_params_json = json.dumps(params, ensure_ascii=False) if item.check_kind else None
        if item.check_kind and not item.baseline_on:
            item.baseline_on = _today()
        if not item.check_kind:
            item.last_report_json = None
    if fields.get("baseline_on"):
        item.baseline_on = fields["baseline_on"]
    return item


def complete(db: Session, item: FollowUp, *, actor_id: int | None, note: str | None,
             next_due: date | None = None) -> FollowUp | None:
    """Kapatır. Tekrarlayan işte (ya da next_due verildiyse) sıradakini açar."""
    if item.status != FU_STATUS_OPEN:
        raise FollowUpError("not_open", "Bu iş zaten kapalı.")
    item.status = FU_STATUS_DONE
    item.completed_at = datetime.now(timezone.utc)
    item.completed_by_id = actor_id
    item.result_note = (note or "").strip() or None
    nxt = next_due or (
        _today() + timedelta(days=item.recurrence_days) if item.recurrence_days else None
    )
    if nxt is None:
        return None
    if nxt <= _today():
        raise FollowUpError("next_in_past", "Sonraki tarih bugünden sonra olmalı.")
    new = FollowUp(
        title=item.title, description=item.description, category=item.category,
        priority=item.priority, due_on=nxt, status=FU_STATUS_OPEN,
        recurrence_days=item.recurrence_days, check_kind=item.check_kind,
        check_params_json=item.check_params_json,
        baseline_on=_today() if item.check_kind else None,
        previous_id=item.id, created_by_id=actor_id,
    )
    db.add(new)
    db.flush()
    return new


def snooze(item: FollowUp, *, until: date) -> FollowUp:
    if item.status != FU_STATUS_OPEN:
        raise FollowUpError("not_open", "Kapalı iş ertelenemez.")
    if until <= _today():
        raise FollowUpError("snooze_in_past", "Erteleme tarihi bugünden sonra olmalı.")
    item.snoozed_until = until
    item.notified_on = None
    return item


def cancel(item: FollowUp, *, note: str | None) -> FollowUp:
    if item.status != FU_STATUS_OPEN:
        raise FollowUpError("not_open", "Bu iş zaten kapalı.")
    item.status = FU_STATUS_CANCELLED
    item.completed_at = datetime.now(timezone.utc)
    item.result_note = (note or "").strip() or item.result_note
    return item


def reopen(item: FollowUp, *, due_on: date | None = None) -> FollowUp:
    if item.status == FU_STATUS_OPEN:
        raise FollowUpError("already_open", "İş zaten açık.")
    item.status = FU_STATUS_OPEN
    item.completed_at = None
    item.completed_by_id = None
    item.snoozed_until = None
    item.notified_on = None
    if due_on:
        item.due_on = due_on
    return item


# ----------------------------------------------------------------- değerlendirme


def evaluate(db: Session, item: FollowUp, today: date | None = None) -> dict | None:
    """Ölçüye bağlı işin raporunu üretir + kayda yazar. Elle işte None."""
    if item.check_kind != "metric_trend":
        return None
    today = today or _today()
    p = params_of(item)
    key = p.get("metric_key")
    md = mr.METRICS.get(key)
    if md is None:
        return None
    owner_type = p.get("owner_type", METRIC_OWNER_SYSTEM)
    min_change = float(p.get("min_change", 3))
    base_on = item.baseline_on or today
    sign = 1 if md.higher_is_better else -1

    owners = [(t, i) for t, i in mr.owners_of(db, key) if t == owner_type]
    if owner_type == METRIC_OWNER_COACH:
        # Koç kırılımının yanında sistem geneli de görünsün
        owners += [(t, i) for t, i in mr.owners_of(db, key) if t == METRIC_OWNER_SYSTEM]
    names: dict = {}
    rows = []
    for t, oid in owners:
        base = mr.value_at(db, key, t, oid, base_on)
        last = mr.latest(db, key, t, oid)
        enough = bool(last and ((last.sample_n or 0) >= md.min_sample or md.min_sample == 0))
        delta = None
        verdict = "no_data"
        if base is not None and last is not None and base.measured_on < last.measured_on:
            delta = round((last.value or 0) - (base.value or 0), 1)
            if not enough:
                verdict = "few_samples"
            elif sign * delta >= min_change:
                verdict = "improved"
            elif sign * delta <= -min_change:
                verdict = "declined"
            else:
                verdict = "stable"
        elif last is not None:
            verdict = "single_point"
        rows.append({
            "owner_type": t, "owner_id": oid,
            "owner_label": mr.owner_label(db, t, oid, names),
            "base_value": base.value if base else None,
            "base_on": base.measured_on.isoformat() if base else None,
            "latest_value": last.value if last else None,
            "latest_on": last.measured_on.isoformat() if last else None,
            "sample_n": last.sample_n if last else None,
            "delta": delta, "verdict": verdict,
        })
    order = {"declined": 0, "improved": 1, "stable": 2, "few_samples": 3, "single_point": 4, "no_data": 5}
    rows.sort(key=lambda r: (r["owner_type"] != METRIC_OWNER_SYSTEM, order[r["verdict"]],
                             -(r["sample_n"] or 0)))

    declined = [r for r in rows if r["verdict"] == "declined"]
    improved = [r for r in rows if r["verdict"] == "improved"]
    measured = [r for r in rows if r["delta"] is not None]
    sys_row = next((r for r in rows if r["owner_type"] == METRIC_OWNER_SYSTEM), None)
    unit = "puan" if md.unit == "%" else ""
    parts = []
    if not measured:
        verdict = "no_data"
        days = (today - base_on).days
        if sys_row and sys_row["latest_value"] is not None:
            parts.append(f"Şu anki değer: sistem geneli {_fmt(sys_row['latest_value'], md.unit)}.")
        parts.append(
            f"Karşılaştırma için en az iki gün ölçüm gerekir (başlangıç "
            f"{base_on.strftime('%d.%m.%Y')}, {days} gün önce). Ölçüm her gece birikir."
        )
    else:
        if sys_row and sys_row["delta"] is not None:
            parts.append(
                f"Sistem geneli {_fmt(sys_row['base_value'], md.unit)} → "
                f"{_fmt(sys_row['latest_value'], md.unit)} ({_signed(sys_row['delta'])} {unit})."
            )
        if declined:
            parts.append(
                "Düşen: " + ", ".join(
                    f"{r['owner_label']} ({_signed(r['delta'])})" for r in declined[:5]
                ) + "."
            )
        if improved:
            parts.append(
                "Yükselen: " + ", ".join(
                    f"{r['owner_label']} ({_signed(r['delta'])})" for r in improved[:5]
                ) + "."
            )
        if not declined and not improved:
            parts.append(f"Belirgin değişim yok (eşik ±{min_change:g} {unit}).")
        verdict = "declined" if declined else ("improved" if improved else "stable")
    report = {
        "metric_key": key, "metric_label": md.label, "unit": md.unit,
        "owner_type": owner_type, "baseline_on": base_on.isoformat(),
        "evaluated_on": today.isoformat(), "min_change": min_change,
        "verdict": verdict, "summary": " ".join(parts), "rows": rows,
    }
    item.last_report_json = json.dumps(report, ensure_ascii=False)
    item.last_checked_at = datetime.now(timezone.utc)
    return report


def _fmt(v, unit: str) -> str:
    if v is None:
        return "—"
    return f"%{v:g}" if unit == "%" else f"{v:g}"


def _signed(v) -> str:
    return f"{v:+g}" if v is not None else "—"


# ----------------------------------------------------------------- okuma


def list_items(db: Session, *, status: str = "open") -> list[FollowUp]:
    q = db.query(FollowUp)
    if status == "open":
        q = q.filter(FollowUp.status == FU_STATUS_OPEN)
    elif status == "closed":
        q = q.filter(FollowUp.status != FU_STATUS_OPEN)
    items = q.all()
    if status == "open":
        items.sort(key=lambda i: (i.effective_due, i.priority != "high", i.id))
    else:
        items.sort(key=lambda i: i.completed_at or i.updated_at, reverse=True)
    return items


def counts(db: Session, today: date | None = None) -> dict:
    today = today or _today()
    out = {"overdue": 0, "today": 0, "upcoming": 0, "later": 0}
    for it in db.query(FollowUp).filter(FollowUp.status == FU_STATUS_OPEN).all():
        out[bucket(it, today)] += 1
    out["closed"] = db.query(FollowUp).filter(FollowUp.status != FU_STATUS_OPEN).count()
    return out


def count_due(db: Session, today: date | None = None) -> int:
    c = counts(db, today)
    return c["overdue"] + c["today"]


# ----------------------------------------------------------------- gece işi


def _needs_notice(item: FollowUp, today: date) -> bool:
    eff = item.effective_due
    if eff > today:
        return False
    if item.notified_on is None or item.notified_on < eff:
        return True
    return (today - item.notified_on).days >= FU_OVERDUE_REMIND_DAYS


def run_daily(db: Session, today: date | None = None, *, send: bool = True) -> dict:
    """Vadesi gelenleri değerlendir + işaretle (commit) → sonra bildir.

    Bildirim AÇIK DB işlemi dışında gönderilir (uzun dış çağrı kuralı).
    """
    today = today or _today()
    open_items = db.query(FollowUp).filter(FollowUp.status == FU_STATUS_OPEN).all()
    # Ölçüye bağlı açık işlerin raporu her gün tazelenir (panel güncel kalsın)
    for it in open_items:
        if it.check_kind:
            try:
                evaluate(db, it, today)
            except Exception:  # noqa: BLE001
                logger.exception("follow_up evaluate failed id=%s", it.id)
    notice = [it for it in open_items if _needs_notice(it, today)]
    if not notice:
        db.commit()
        return {"due": 0, "notified": 0}
    lines = []
    for it in sorted(notice, key=lambda i: (i.effective_due, i.priority != "high")):
        rep = report_of(it)
        lines.append({
            "id": it.id, "title": it.title,
            "category": FU_CATEGORIES.get(it.category, it.category),
            "priority": it.priority,
            "due": it.effective_due.strftime("%d.%m.%Y"),
            "late_days": (today - it.effective_due).days,
            "summary": rep.get("summary") if rep else None,
            "verdict": rep.get("verdict") if rep else None,
        })
        it.notified_on = today
    upcoming = [
        {"title": it.title, "due": it.effective_due.strftime("%d.%m.%Y")}
        for it in sorted(open_items, key=lambda i: i.effective_due)
        if today < it.effective_due <= today + timedelta(days=3)
    ]
    db.commit()
    result = {"due": len(lines), "notified": 0}
    if send:
        result.update(_send_digest(db, lines, upcoming))
    return result


def _send_digest(db: Session, lines: list[dict], upcoming: list[dict]) -> dict:
    from app.models import UserRole
    from app.services.alarm_engine import _alarm_email_recipients
    from app.services.email_service import send_email
    from app.services.push_notifications import send_push_to_user

    late = sum(1 for ln in lines if ln["late_days"] > 0)
    ctx = {"items": lines, "upcoming": upcoming, "count": len(lines), "late": late}
    ok = 0
    recipients = _alarm_email_recipients(db)
    for addr in recipients:
        try:
            if send_email(addr, "follow_up_digest", ctx):
                ok += 1
        except Exception:  # noqa: BLE001
            logger.exception("follow_up digest email fail to=%s", addr)
    pushed = 0
    title = f"Takip listesi: {len(lines)} iş bekliyor" + (f" ({late} gecikmiş)" if late else "")
    body = lines[0]["title"] + (f" ve {len(lines) - 1} iş daha" if len(lines) > 1 else "")
    for a in db.query(User).filter(User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True)):
        try:
            pushed += send_push_to_user(db, user_id=a.id, title=title, body=body,
                                        data={"type": "admin_follow_up", "screen": "follow_ups"})
        except Exception:  # noqa: BLE001
            logger.warning("follow_up push fail user=%s", a.id, exc_info=True)
    return {"notified": len(lines), "email_ok": ok, "email_total": len(recipients), "push": pushed}
