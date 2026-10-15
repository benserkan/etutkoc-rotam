"""Rehber günlük görüşme listesi (K48/K50, Adım 5, 2026-10-12).

Randevu modülüyle birlikte: bugünkü görüşmeler ÜSTTE (randevu + beklenen seans günü
bugün olan dönemler), ardından havuz öğrencileri sinyal şiddetine göre; öğrenci
başına 1 ana sinyal + katlanan ek sinyal sayısı; Gördüm/Ertele mevcut WarningState
mekanizmasıyla (koç kendi görünümünde `code` bazlı erteler). Gün-gün öğrencileri
bu listeye GİRMEZ (onlar pano uyarı akışında).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models import User, UserRole, WarningState
from app.models.appointment import APPT_STATUS_PENDING, APPT_STATUS_SCHEDULED, CoachingAppointment
from app.models.pool import PROGRAM_MODE_HAVUZ
from app.services import pool_mode as pm
from app.services.pool_flags import evaluate_pool_flags

LEVEL_RANK = {"red": 0, "amber": 1, "green": 2}


def _aw(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def build_daily_list(db: Session, *, coach: User, today: date | None = None, now: datetime | None = None) -> dict:
    today = today or date.today()
    now = now or datetime.now(timezone.utc)
    students = (db.query(User)
                .filter(User.teacher_id == coach.id, User.role == UserRole.STUDENT, User.is_active.is_(True),
                        User.program_mode == PROGRAM_MODE_HAVUZ)
                .order_by(User.full_name).all())
    appts = (db.query(CoachingAppointment).options(joinedload(CoachingAppointment.student))
             .filter(CoachingAppointment.coach_id == coach.id, CoachingAppointment.date == today,
                     CoachingAppointment.status.in_((APPT_STATUS_SCHEDULED, APPT_STATUS_PENDING)))
             .order_by(CoachingAppointment.start_time).all())
    appt_by_student: dict[int, CoachingAppointment] = {}
    for a in appts:
        appt_by_student.setdefault(a.student_id, a)
    states = {(w.student_id, w.code): w for w in
              db.query(WarningState).filter(WarningState.actor_id == coach.id).all()}

    rows: list[dict] = []
    for s in students:
        period = pm.get_open_period(db, s.id)
        rep = evaluate_pool_flags(db, s, today)
        primary = rep.primary[0] if rep.primary else None
        snoozed = False
        if primary is not None:
            st = states.get((s.id, primary.code))
            snz = _aw(st.snooze_until) if st else None
            snoozed = bool(snz and snz > now)
        appt = appt_by_student.get(s.id)
        expected_today = bool(period is not None and period.expected_next_on == today)
        summary = pm.period_summary(db, period, today) if period else None
        rows.append({
            "student_id": s.id, "student_name": s.full_name, "class_group": s.class_group,
            "session_today": appt is not None or expected_today,
            "appointment_time": appt.start_time if appt else None,
            "appointment_id": appt.id if appt else None,
            "period_id": period.id if period else None,
            "days_open": (today - period.opened_on).days if period else None,
            "expected_next_on": period.expected_next_on.isoformat() if period and period.expected_next_on else None,
            "pct": summary.pct if summary else None,
            "level": rep.level,
            "headline": rep.headline,
            "primary": _flag(primary) if primary else None,
            "primary_snoozed": snoozed,
            "extra": [_flag(w) for w in rep.secondary],
            "good": [_flag(w) for w in rep.good],
            "paper_student": any(w.code == "pool_paper" for w in rep.secondary),
        })
    rows.sort(key=lambda r: (0 if r["session_today"] else 1,
                             r["appointment_time"] or "99:99",
                             1 if r["primary_snoozed"] else 0,
                             LEVEL_RANK.get(r["level"], 9), r["student_name"].lower()))
    return {
        "today": today.isoformat(),
        "rows": rows,
        "counts": {
            "students": len(rows),
            "sessions_today": sum(1 for r in rows if r["session_today"]),
            "red": sum(1 for r in rows if r["level"] == "red" and not r["primary_snoozed"]),
            "amber": sum(1 for r in rows if r["level"] == "amber" and not r["primary_snoozed"]),
            "snoozed": sum(1 for r in rows if r["primary_snoozed"]),
        },
    }


def _flag(w) -> dict:
    return {"code": w.code, "level": w.level, "layer": getattr(w, "layer", ""), "title": w.title,
            "detail": w.detail, "evidence": [{"label": a, "value": b} for a, b in (w.evidence or [])],
            "coach_only": bool(getattr(w, "coach_only", False))}
