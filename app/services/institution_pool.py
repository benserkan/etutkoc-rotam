"""Kurum — haftalık havuz panosu (K54/K55, Adım 5, 2026-10-12; genişletildi 2026-10-13).

K54: şube × son dönem havuz yüzdesi · seansı geciken öğrenci (beklenen gün 3+ geçti ya da
     14 gün seanssız) · rehber başına kırmızı sinyal.
K55: rehber yükü (bugünkü görüşme + geciken seans) kuruma görünür.

2026-10-13 — koç ve öğrenci ekranlarında üretilen verinin kuruma yansıması (hepsi mevcut
servislerden, ayrı hesap yazılmaz):
  · öğrenci katılımı — bugün kap kuran / işaretleyen (kap görevleri), 3+ gün dokunmayan
    (pool_idle_streak), kağıt öğrencisi (is_paper_student)
  · tempo — öğrencinin Havuzum ekranındaki cümlenin aynısı (pool_student._pace)
  · kayıt kaynağı — açık dönemde biten birimin öğrenci kaydı (completed) vs rehber seans işareti
  · kalem yapısı — rehber editörü: kitaplı / konulu (kaynaksız) / serbest; öğretmen ödevi; devir;
    öğrencinin eklediği → onay bekleyen (rehber iş yükü)
  · sinyal dağılımı — pool_flags kod aileleri (katılım/tempo/doğruluk/deneme/kaçınma/toplu işaret/seans)
  · ders bazında ilerleme — açık dönem kalemleri ders adıyla birleşik
  · eğilim — son 4 hafta kapanan dönemlerin ortalama %'si (tatil hariç)

Düzeltmeler (2026-10-13 doğrulama): "son dönem %" artık ARA (tatil) dönemlerini saymaz (K42 baseline
ile aynı); bugünkü görüşme, öğrencinin randevusu varsa beklenen seans gününü İKİNCİ kez saymaz;
şube satırına sarı (dikkat) sayısı eklendi.

Gizlilik: öğrenci detay sayfası YOK (D4 deseni); öğrenci adı + rehber adı görünür.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Subject, Task, TaskStatus, User, UserRole
from app.models.appointment import APPT_STATUS_PENDING, APPT_STATUS_SCHEDULED, CoachingAppointment
from app.models.pool import (
    APPROVAL_PENDING, APPROVAL_REJECTED, PERIOD_BREAK, PERIOD_NO_SESSION_RED_DAYS, PERIOD_OPEN,
    PROGRAM_MODE_HAVUZ, SOURCE_CARRY, SOURCE_STUDENT, UNIT_ETKINLIK, ClassGroup, StudyPeriod,
)
from app.services import pool_mode as pm
from app.services.pool_flags import SESSION_LATE_DAYS, evaluate_pool_flags, is_paper_student

TREND_WEEKS = 4

# Sinyal aileleri (pool_flags kodları → kuruma sade ad + açıklama). Sıra = panodaki sıra.
SIGNAL_FAMILIES: list[tuple[str, tuple[str, ...], str, str]] = [
    ("seans", ("pool_session_overdue", "pool_session_late"), "Seans gecikti",
     "Beklenen seans günü 3+ gün geçti ya da 14 gündür seans yok."),
    ("donem", ("pool_no_period", "pool_empty"), "Havuz yok / boş",
     "Açık dönem yok ya da dönem açık ama havuzda kalem yok."),
    ("katilim", ("pool_idle_streak", "pool_no_cup", "pool_no_tick"), "Havuza dokunmuyor",
     "2-3 gündür giriş/kap/işaret yok, ya da kap kurup işaretlemiyor."),
    ("tempo", ("pool_behind",), "Tempo geride",
     "Kalan birim için günde gereken, son dönemlerdeki alışkanlığının 1,5 katını aşıyor."),
    ("dogruluk", ("pool_accuracy_",), "Düşük doğruluk",
     "Bir derste en az 2 test kaleminde doğruluk %50'nin altında."),
    ("deneme", ("pool_exam_cross",), "Çalıştığı konuda denemede yanlış",
     "Bu dönem havuzda çalışılan konudan denemede yanlış var."),
    ("kacinma", ("pool_avoided",), "Kaçınılan kalem",
     "Kaba girip geri dönen, 3. kez devredilen ya da 4 gündür alınmayan kalem."),
    ("toplu", ("pool_bulk_mark",), "Toplu işaretleme",
     "Kısa sürede çok sayıda test 'yaptım' işaretlendi — rehber seansta kitaptan kontrol eder."),
]


@dataclass
class PoolOverview:
    students: int = 0
    coaches: int = 0
    open_periods: int = 0
    avg_last_pct: int | None = None
    avg_open_pct: int | None = None
    avg_expected_pct: int | None = None   # açık dönemlerde geçen gün oranı (yüzde bu kadar olmalı)
    late_sessions: int = 0
    red_students: int = 0
    amber_students: int = 0
    groups: list[dict] = field(default_factory=list)
    late: list[dict] = field(default_factory=list)
    coach_rows: list[dict] = field(default_factory=list)
    participation: dict = field(default_factory=dict)
    pace: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    items: dict = field(default_factory=dict)
    signals: list[dict] = field(default_factory=list)
    subjects: list[dict] = field(default_factory=list)
    trend: list[dict] = field(default_factory=list)


def _last_closed(db: Session, student_id: int) -> StudyPeriod | None:
    """En son kapanmış dönem — ARA (tatil) hariç (K42 baseline ile aynı kural)."""
    return (db.query(StudyPeriod).options(joinedload(StudyPeriod.items))
            .filter(StudyPeriod.student_id == student_id, StudyPeriod.status != PERIOD_OPEN,
                    StudyPeriod.status != PERIOD_BREAK)
            .order_by(StudyPeriod.closed_on.desc(), StudyPeriod.id.desc()).first())


def _last_closed_pct(db: Session, student_id: int, today: date) -> int | None:
    p = _last_closed(db, student_id)
    if p is None:
        return None
    s = pm.period_summary(db, p, today)
    return s.pct if s.total_units else None


def _avg(xs: list[int]) -> int | None:
    return int(round(sum(xs) / len(xs))) if xs else None


def _family(code: str) -> str | None:
    for key, codes, _l, _h in SIGNAL_FAMILIES:
        if any(code == c or (c.endswith("_") and code.startswith(c)) for c in codes):
            return key
    return None


def build_overview(db: Session, *, institution_id: int, today: date | None = None) -> PoolOverview:
    from app.routes.api_v2.pool_student import _pace  # öğrencinin gördüğü tempo cümlesiyle AYNI kural

    today = today or date.today()
    coaches = (db.query(User)
               .filter(User.institution_id == institution_id, User.role == UserRole.TEACHER, User.is_active.is_(True))
               .order_by(User.full_name).all())
    coach_ids = [c.id for c in coaches]
    if not coach_ids:
        return PoolOverview()
    students = (db.query(User)
                .filter(User.teacher_id.in_(coach_ids), User.role == UserRole.STUDENT, User.is_active.is_(True),
                        User.program_mode == PROGRAM_MODE_HAVUZ)
                .order_by(User.full_name).all())
    ov = PoolOverview(students=len(students), coaches=len(coaches))
    blank_coach = {"students": 0, "red": 0, "amber": 0, "late_sessions": 0, "today_sessions": 0, "load": 0,
                   "pending_approval": 0, "bulk": 0, "paper": 0, "avg_open_pct": None}
    if not students:
        ov.coach_rows = [{"coach_id": c.id, "coach_name": c.full_name, **blank_coach} for c in coaches]
        return ov
    sids = [s.id for s in students]

    # bugünkü görüşmeler (randevu modülü) — öğrenci bazında (beklenen seans günüyle çift sayılmasın)
    appt_students: dict[int, set[int]] = {}
    for cid, sid in (db.query(CoachingAppointment.coach_id, CoachingAppointment.student_id)
                     .filter(CoachingAppointment.coach_id.in_(coach_ids), CoachingAppointment.date == today,
                             CoachingAppointment.status.in_((APPT_STATUS_SCHEDULED, APPT_STATUS_PENDING))).all()):
        appt_students.setdefault(int(cid), set()).add(int(sid) if sid is not None else -1)

    # bugünün kap görevleri (öğrenci katılımı)
    cup_today: dict[int, list[Task]] = {}
    for t in (db.query(Task).options(joinedload(Task.book_items))
              .filter(Task.student_id.in_(sids), Task.date == today, Task.pool_item_id.isnot(None)).all()):
        cup_today.setdefault(t.student_id, []).append(t)

    # şube ders programı girilmiş mi (scope coach:{id})
    lessons_set: set[tuple[int, str]] = set()
    for cg in db.query(ClassGroup).filter(ClassGroup.scope_key.in_([f"coach:{i}" for i in coach_ids])).all():
        if any(v for v in cg.lessons.values()):
            lessons_set.add((int(cg.scope_key.split(":", 1)[1]), cg.name))

    groups: dict[str, dict] = {}
    per_coach: dict[int, dict] = {c.id: {"coach_id": c.id, "coach_name": c.full_name, **blank_coach,
                                         "today_sessions": 0, "_open": [], "_seen_today": set()}
                                  for c in coaches}
    for cid, sset in appt_students.items():
        if cid in per_coach:
            per_coach[cid]["today_sessions"] = len(sset)
            per_coach[cid]["_seen_today"] = set(sset)
    last_pcts: list[int] = []
    open_pcts: list[int] = []
    expected_pcts: list[int] = []
    part = {"cup_today": 0, "ticked_today": 0, "idle": 0, "paper": 0}
    pace = {"onde": 0, "yolunda": 0, "geride": 0, "belirsiz": 0}
    src = {"student_units": 0, "coach_units": 0, "done_units": 0, "total_units": 0}
    items_ = {"total": 0, "book": 0, "topic": 0, "free": 0, "teacher_homework": 0, "carried": 0,
              "pending_approval": 0, "rejected": 0, "student_added": 0}
    sig_count: dict[str, dict] = {k: {"red": 0, "amber": 0, "info": 0, "students": 0} for k, *_ in SIGNAL_FAMILIES}
    subj: dict[int, dict] = {}

    for s in students:
        cname = per_coach.get(s.teacher_id, {}).get("coach_name", "—")
        row = per_coach.get(s.teacher_id)
        if row is not None:
            row["students"] += 1
        gname = s.class_group or "Şubesiz"
        g = groups.setdefault(gname, {"class_group": gname, "students": 0, "last": [], "open": [], "late": 0,
                                      "red": 0, "amber": 0, "lessons_set": False})
        g["students"] += 1
        if s.class_group and (s.teacher_id, s.class_group) in lessons_set:
            g["lessons_set"] = True
        lp = _last_closed_pct(db, s.id, today)
        if lp is not None:
            g["last"].append(lp)
            last_pcts.append(lp)

        # katılım (öğrenci ekranı: kap + işaret)
        cups = cup_today.get(s.id, [])
        if cups:
            part["cup_today"] += 1
            if any(t.status == TaskStatus.COMPLETED or sum(int(bi.completed_count or 0) for bi in t.book_items) > 0
                   for t in cups):
                part["ticked_today"] += 1

        period = pm.get_open_period(db, s.id)
        if period is not None:
            ov.open_periods += 1
            sm = pm.period_summary(db, period, today)
            if sm.total_units:
                g["open"].append(sm.pct)
                open_pcts.append(sm.pct)
                if row is not None:
                    row["_open"].append(sm.pct)
            if period.expected_next_on and period.expected_next_on > period.opened_on:
                span = (period.expected_next_on - period.opened_on).days
                expected_pcts.append(min(100, int(round(100 * (today - period.opened_on).days / span))))
            pace[_pace(sm, pm.days_without_session(period, today))[0]] += 1
            days_open = (today - period.opened_on).days
            late_days = (today - period.expected_next_on).days if period.expected_next_on else 0
            if days_open >= PERIOD_NO_SESSION_RED_DAYS or late_days >= SESSION_LATE_DAYS:
                ov.late_sessions += 1
                g["late"] += 1
                if row is not None:
                    row["late_sessions"] += 1
                ov.late.append({"student_id": s.id, "student_name": s.full_name, "coach_name": cname,
                                "class_group": s.class_group, "opened_on": period.opened_on.isoformat(),
                                "expected_next_on": period.expected_next_on.isoformat() if period.expected_next_on else None,
                                "days_open": days_open, "late_days": max(0, late_days),
                                "level": "red" if days_open >= PERIOD_NO_SESSION_RED_DAYS else "amber",
                                "pct": sm.pct if sm.total_units else None})
            # beklenen seans günü bugün — randevusu zaten sayılmadıysa (çift sayım yok)
            if period.expected_next_on == today and row is not None and s.id not in row["_seen_today"]:
                row["today_sessions"] += 1
                row["_seen_today"].add(s.id)

            # kalem yapısı + kayıt kaynağı + ders bazında
            for it in period.items:
                if it.removed_at is not None:
                    continue
                items_["total"] += 1
                if it.source == SOURCE_STUDENT:
                    items_["student_added"] += 1
                    if it.approval == APPROVAL_PENDING:
                        items_["pending_approval"] += 1
                        if row is not None:
                            row["pending_approval"] += 1
                    elif it.approval == APPROVAL_REJECTED:
                        items_["rejected"] += 1
                if it.book_id:
                    items_["book"] += 1
                elif it.topic_id:
                    items_["topic"] += 1
                else:
                    items_["free"] += 1
                if it.teacher_homework:
                    items_["teacher_homework"] += 1
                if it.source == SOURCE_CARRY:
                    items_["carried"] += 1
                if not it.counts_toward_pool:
                    continue
                units = 1 if it.unit == UNIT_ETKINLIK else int(it.quantity or 0)
                done = it.done_units
                stu = min(done, int(it.completed or 0))
                src["student_units"] += stu
                src["coach_units"] += max(0, done - stu)
                src["done_units"] += done
                src["total_units"] += units
                if it.subject_id:
                    sr = subj.setdefault(it.subject_id, {"done": 0, "total": 0, "students": set()})
                    sr["done"] += min(done, units)
                    sr["total"] += units
                    sr["students"].add(s.id)

        rep = evaluate_pool_flags(db, s, today)
        if rep.level == "red":
            ov.red_students += 1
            g["red"] += 1
            if row is not None:
                row["red"] += 1
        elif rep.level == "amber":
            ov.amber_students += 1
            g["amber"] += 1
            if row is not None:
                row["amber"] += 1
        fams_seen: set[str] = set()
        for w in rep.primary + rep.secondary:
            fam = _family(w.code)
            if fam is None:
                continue
            lvl = w.level if w.level in ("red", "amber") else "info"
            sig_count[fam][lvl] += 1
            if fam not in fams_seen:
                sig_count[fam]["students"] += 1
                fams_seen.add(fam)
            if w.code == "pool_idle_streak":
                part["idle"] += 1
            if w.code == "pool_bulk_mark" and row is not None:
                row["bulk"] += 1
        if is_paper_student(db, s, period):
            part["paper"] += 1
            if row is not None:
                row["paper"] += 1

    ov.avg_last_pct = _avg(last_pcts)
    ov.avg_open_pct = _avg(open_pcts)
    ov.avg_expected_pct = _avg(expected_pcts)
    ov.groups = sorted(
        [{"class_group": g["class_group"], "students": g["students"], "last_pct": _avg(g["last"]),
          "open_pct": _avg(g["open"]), "late_sessions": g["late"], "red": g["red"], "amber": g["amber"],
          "lessons_set": g["lessons_set"]} for g in groups.values()],
        key=lambda r: (r["class_group"] == "Şubesiz", r["class_group"]))
    ov.late.sort(key=lambda r: (0 if r["level"] == "red" else 1, -r["days_open"]))
    for row in per_coach.values():
        row["load"] = row["today_sessions"] + row["late_sessions"] + row["red"]  # K55: rehber yükü
        row["avg_open_pct"] = _avg(row.pop("_open"))
        row.pop("_seen_today", None)
    ov.coach_rows = sorted(per_coach.values(), key=lambda r: (-r["load"], r["coach_name"]))
    ov.participation = {**part, "students": len(students)}
    ov.pace = pace
    ov.sources = src
    ov.items = items_
    ov.signals = [{"key": k, "label": label, "hint": hint, **sig_count[k]} for k, _c, label, hint in SIGNAL_FAMILIES]
    names = {x.id: x.name for x in db.query(Subject).filter(Subject.id.in_(list(subj))).all()} if subj else {}
    merged: dict[str, dict] = {}
    for sid, r in subj.items():
        m = merged.setdefault(names.get(sid, "—"), {"done": 0, "total": 0, "students": set()})
        m["done"] += r["done"]
        m["total"] += r["total"]
        m["students"] |= r["students"]
    ov.subjects = sorted(
        [{"name": n, "done": m["done"], "total": m["total"], "students": len(m["students"]),
          "pct": int(round(100 * m["done"] / m["total"])) if m["total"] else 0} for n, m in merged.items()],
        key=lambda r: -r["total"])
    ov.trend = _trend(db, sids, today)
    return ov


def _trend(db: Session, student_ids: list[int], today: date) -> list[dict]:
    """Son TREND_WEEKS haftada (Pzt-Paz) kapanan dönemlerin ortalama %'si — tatil (ara) hariç."""
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=TREND_WEEKS - 1)
    rows = (db.query(StudyPeriod).options(joinedload(StudyPeriod.items))
            .filter(StudyPeriod.student_id.in_(student_ids), StudyPeriod.status != PERIOD_OPEN,
                    StudyPeriod.status != PERIOD_BREAK, StudyPeriod.closed_on >= start).all())
    buckets: dict[date, list[int]] = {start + timedelta(weeks=i): [] for i in range(TREND_WEEKS)}
    for p in rows:
        s = pm.period_summary(db, p, today)
        if not s.total_units or p.closed_on is None:
            continue
        wk = p.closed_on - timedelta(days=p.closed_on.weekday())
        if wk in buckets:
            buckets[wk].append(s.pct)
    return [{"week_start": wk.isoformat(), "avg_pct": _avg(v), "periods": len(v)} for wk, v in sorted(buckets.items())]
