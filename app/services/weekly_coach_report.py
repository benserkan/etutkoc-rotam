# -*- coding: utf-8 -*-
"""Haftalık koç raporu — TEK MERKEZ (2026-08-19).

"Haftalık rapor oluştur" butonunun arkasındaki algoritma:
  1. `default_window`  — programın işlendiği son güne kadar geriye 7 gün.
  2. `collect`         — o pencere için tüm analizler (mevcut servislerden; JSON'a
                         yazılabilir sözlük). Hiçbir yazma yapmaz.
  3. `build_agenda`    — KURAL MOTORU: veriden seans gündemi maddeleri (kredisiz,
                         daima var). Her madde bir karar ya da soru içerir.
  4. `render_html`     — raporun HTML görünümü (tek dosya, açık/koyu tema). Format
                         scripts/build_weekly_report_html.py ile birebir.
  5. `create_report`   — CoachingReport satırı (data_json + agenda_json; aynı hafta
                         yeniden üretilirse version+1).
  6. `insight_bundle`  — KS4 AI içgörüsüne verilen yoğunlaştırılmış paket (akıcı,
                         rakamlı "Seans gündemi" → ai_agenda_json; kredili, endpoint'te).

Seans bağı: koç rapordaki gündem maddelerini seçip "Yeni seans" açar → seans
`report_id` + `agenda_items` taşır (router).
"""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Book, BookSection, CoachingReport, ExamResult, SectionProgress, StudentBook,
    Subject, Task, Topic, User,
)

DEFAULT_DAYS = 7
TYT_PENALTY = 4  # TYT/AYT: 4 yanlış 1 doğruyu götürür

TR_DAYS = {"Monday": "Pzt", "Tuesday": "Sal", "Wednesday": "Çar", "Thursday": "Per",
           "Friday": "Cum", "Saturday": "Cmt", "Sunday": "Paz"}
TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
             "Eylül", "Ekim", "Kasım", "Aralık"]
SUBJ_ORDER = ["TYT Matematik", "AYT Matematik", "TYT Geometri", "AYT Geometri", "TYT Türkçe",
              "TYT Fizik", "TYT Kimya", "TYT Biyoloji", "AYT Fizik", "AYT Kimya", "AYT Biyoloji"]


# ============================================================================
# yardımcılar
# ============================================================================
def _j(o):
    """json.dumps default: dataclass/enum/datetime/nesne güvenli."""
    if is_dataclass(o) and not isinstance(o, type):
        return asdict(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if hasattr(o, "value"):
        return o.value
    if hasattr(o, "__dict__"):
        return {k: v for k, v in vars(o).items() if not k.startswith("_")}
    return str(o)


def to_jsonable(o: Any) -> Any:
    """Sözlüğü JSON-güvenli hâle getir (dataclass → dict vb.)."""
    return json.loads(json.dumps(o, ensure_ascii=False, default=_j))


def _safe(out: dict, name: str, fn) -> None:
    try:
        out[name] = fn()
    except Exception as e:  # noqa: BLE001 — bir blok düşerse rapor düşmesin
        out[name] = {"_error": f"{type(e).__name__}: {e}"}


def d_tr(s: str, with_day: bool = True) -> str:
    d = date.fromisoformat(str(s)[:10])
    wd = TR_DAYS[d.strftime("%A")]
    return f"{d.day} {TR_MONTHS[d.month - 1]}" + (f" {wd}" if with_day else "")


def pct(a, b):
    return round(100 * a / b) if b else None


def _band(p):
    if p is None:
        return "none"
    return "good" if p >= 85 else ("warn" if p >= 70 else "bad")


# ============================================================================
# 1) pencere
# ============================================================================
def default_window(db: Session, student: User, *, days: int = DEFAULT_DAYS,
                   today: date | None = None) -> tuple[date, date]:
    """Programın işlendiği son gün (yayınlanmış en son görev tarihi ≤ bugün) → geriye 7 gün."""
    today = today or date.today()
    last = (
        db.query(func.max(Task.date))
        .filter(Task.student_id == student.id, Task.is_draft == False, Task.date <= today)  # noqa: E712
        .scalar()
    )
    week_end = last or today
    return week_end - timedelta(days=days - 1), week_end


# ============================================================================
# 2) veri toplama
# ============================================================================
def collect(db: Session, student: User, week_start: date, week_end: date) -> dict:
    """Pencere için tüm analizler — JSON'a yazılabilir sözlük. Salt-okuma."""
    since, until = week_start, week_end
    days = (until - since).days + 1
    coach = db.get(User, student.teacher_id) if student.teacher_id else None
    out: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"since": since.isoformat(), "until": until.isoformat(), "days": days},
    }

    def profil():
        return {
            "id": student.id, "full_name": student.full_name, "email": student.email,
            "grade_level": student.grade_level, "track": getattr(student, "track", None),
            "study_mode": getattr(student, "study_mode", None),
            "curriculum_model": student.effective_curriculum_model,
            "is_paused": getattr(student, "is_paused", None),
            "created_at": student.created_at, "last_login_at": student.last_login_at,
            "coach": {"id": coach.id, "full_name": coach.full_name} if coach else None,
        }
    _safe(out, "student", profil)

    def kitaplar():
        rows = (db.query(StudentBook).options(selectinload(StudentBook.book))
                .filter(StudentBook.student_id == student.id).all())
        res = []
        for sb in rows:
            b = sb.book
            subj = db.get(Subject, b.subject_id) if b.subject_id else None
            secs = db.query(BookSection).filter(BookSection.book_id == b.id).order_by(BookSection.id).all()
            progs = {p.book_section_id: p for p in db.query(SectionProgress)
                     .filter(SectionProgress.student_book_id == sb.id).all()}
            sec_rows = []
            for sc in secs:
                p = progs.get(sc.id)
                tp = db.get(Topic, sc.topic_id) if sc.topic_id else None
                sec_rows.append({
                    "section_id": sc.id, "label": sc.label, "test_count": sc.test_count,
                    "topic": tp.name if tp else None,
                    "completed": (p.completed_count if p else 0), "reserved": (p.reserved_count if p else 0),
                    "manual": (getattr(p, "manual_count", 0) if p else 0),
                })
            tot = sum(s["test_count"] or 0 for s in sec_rows)
            done = sum(s["completed"] for s in sec_rows)
            rez = sum(s["reserved"] for s in sec_rows)
            res.append({
                "student_book_id": sb.id, "book_id": b.id, "book": b.name,
                "publisher": getattr(b, "publisher", None),
                "type": getattr(b, "type", None), "subject": subj.name if subj else None,
                "subject_id": b.subject_id, "assigned_at": getattr(sb, "assigned_at", None),
                "test_total": tot, "completed": done, "reserved": rez,
                "pct": pct(done, tot), "sections": sec_rows,
            })
        return res
    _safe(out, "books", kitaplar)

    from app.services import analytics as an
    _safe(out, "subject_breakdown_tests_only", lambda: an.subject_breakdown(db, student.id, tests_only=True))

    from app.services import curriculum_progress as cp
    _safe(out, "curriculum", lambda: cp.compute_curriculum_progress(db, student, student.teacher_id))
    _safe(out, "recent_units", lambda: cp.recently_covered_units(db, student, days=days))

    from app.services import topic_performance as tpf
    _safe(out, "topic_performance", lambda: tpf.compute_topic_performance(db, student.id))

    from app.services import gorev_stats as gs

    def gorevler():
        tasks = (db.query(Task).options(selectinload(Task.book_items))
                 .filter(Task.student_id == student.id, Task.date >= since, Task.date <= until,
                         Task.is_draft == False)  # noqa: E712
                 .order_by(Task.date.asc(), Task.id.asc()).all())
        cache: dict = {}

        def get(model, pk):
            k = (model.__name__, pk)
            if k not in cache:
                cache[k] = db.get(model, pk) if pk else None
            return cache[k]

        by_day: dict[str, list] = defaultdict(list)
        rows = []
        for t in tasks:
            items = []
            for it in t.book_items:
                b = get(Book, it.book_id)
                sc = get(BookSection, it.book_section_id)
                tp = get(Topic, sc.topic_id) if (sc and sc.topic_id) else None
                sj = get(Subject, b.subject_id) if (b and b.subject_id) else None
                items.append({
                    "book": b.name if b else None, "book_type": (getattr(b, "type", None) if b else None),
                    "subject": sj.name if sj else None,
                    "section": sc.label if sc else None, "topic": tp.name if tp else None, "label": it.label,
                    "planned": it.planned_count, "completed": it.completed_count,
                    "correct": it.correct_count, "wrong": it.wrong_count, "blank": it.blank_count,
                })
            rows.append({
                "id": t.id, "date": t.date, "title": t.title, "type": t.type, "status": t.status,
                "period": t.period, "category": gs.classify_gorev(t), "done": gs.gorev_done(t),
                "solved_count": t.solved_count, "work_block_id": t.work_block_id,
                "completed_at": t.completed_at, "items": items,
            })
            by_day[t.date.isoformat()].append(t)
        summary = gs.summarize(tasks)
        per_day = {}
        for i in range(days):
            d = since + timedelta(days=i)
            ts = by_day.get(d.isoformat(), [])
            s = gs.summarize(ts) if ts else None
            per_day[d.isoformat()] = ({
                "weekday": d.strftime("%A"), "gorev_total": s.gorev_total, "gorev_done": s.gorev_done,
                "test_planned": s.test_planned, "test_completed": s.test_completed,
                "deneme_planned": s.deneme_planned, "deneme_completed": s.deneme_completed,
            } if s else {"weekday": d.strftime("%A"), "gorev_total": 0, "gorev_done": 0,
                         "test_planned": 0, "test_completed": 0, "deneme_planned": 0, "deneme_completed": 0})
        agg = defaultdict(lambda: {"planned": 0, "completed": 0, "correct": 0, "wrong": 0, "blank": 0})
        for r in rows:
            for it in r["items"]:
                key = (it["subject"] or "—", it["topic"] or it["section"] or it["label"] or "—", it["book_type"])
                a = agg[key]
                a["planned"] += it["planned"] or 0
                a["completed"] += it["completed"] or 0
                a["correct"] += it["correct"] or 0
                a["wrong"] += it["wrong"] or 0
                a["blank"] += it["blank"] or 0
        by_subject_topic = [
            {"subject": k[0], "topic": k[1], "book_type": k[2], **v}
            for k, v in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1]))
        ]
        # gelecek hafta programı var mı?
        next_count = (
            db.query(func.count(Task.id))
            .filter(Task.student_id == student.id, Task.date > until, Task.is_draft == False)  # noqa: E712
            .scalar() or 0
        )
        return {"summary": summary, "per_day": per_day, "tasks": rows,
                "by_subject_topic": by_subject_topic, "next_week_task_count": int(next_count)}
    _safe(out, "tasks_window", gorevler)

    def gorev_all():
        tasks = (db.query(Task).options(selectinload(Task.book_items))
                 .filter(Task.student_id == student.id, Task.is_draft == False).all())  # noqa: E712
        s = gs.summarize(tasks)
        return {"summary": s, "first_task_date": min((t.date for t in tasks), default=None),
                "last_task_date": max((t.date for t in tasks), default=None), "count": len(tasks)}
    _safe(out, "tasks_all", gorev_all)

    def denemeler():
        exams = (db.query(ExamResult).options(selectinload(ExamResult.questions))
                 .filter(ExamResult.student_id == student.id)
                 .order_by(ExamResult.exam_date.asc(), ExamResult.id.asc()).all())
        res = []
        for e in exams:
            qs = e.questions or []
            by = defaultdict(lambda: {"dogru": 0, "yanlis": 0, "bos": 0, "n": 0})
            for q in qs:
                sname = (db.get(Subject, q.subject_id).name if q.subject_id else (q.subject_name_raw or "—"))
                tname = (db.get(Topic, q.topic_id).name if q.topic_id else (q.topic_label_raw or "—"))
                key = (sname, tname)
                by[key]["n"] += 1
                if q.result == "dogru":
                    by[key]["dogru"] += 1
                elif q.result == "yanlis":
                    by[key]["yanlis"] += 1
                else:
                    by[key]["bos"] += 1
            res.append({
                "id": e.id, "title": e.title, "exam_date": e.exam_date, "section": e.section,
                "total_correct": e.total_correct, "total_wrong": e.total_wrong,
                "total_blank": e.total_blank, "net": e.net, "subject_nets": e.subject_nets,
                "import_source": getattr(e, "import_source", None), "questions_count": len(qs),
                "by_topic": [{"subject": k[0], "topic": k[1], **v}
                             for k, v in sorted(by.items(), key=lambda kv: (kv[0][0], -kv[1]["yanlis"]))],
            })
        return res
    _safe(out, "exams", denemeler)

    from app.services import exam_topic_analysis as eta
    _safe(out, "exam_insight_summary", lambda: eta.exam_insight_summary(db, student))

    from app.models.wrong_question import WrongQuestion
    from app.services import wrong_question_service as wqs

    def ysa():
        rows = (db.query(WrongQuestion).filter(WrongQuestion.student_id == student.id)
                .order_by(WrongQuestion.created_at.asc()).all())
        items = [{
            "id": w.id, "created_at": w.created_at, "status": w.status, "source": w.source_kind,
            "subject": (db.get(Subject, w.subject_id).name if w.subject_id else None),
            "topic": (db.get(Topic, w.topic_id).name if w.topic_id else None),
            "error_type": w.error_type, "correct_streak": getattr(w, "correct_streak", None),
        } for w in rows]
        return {"items": items, "coach_summary": wqs.coach_summary(db, student.id)}
    _safe(out, "wrong_questions", ysa)

    _safe(out, "snapshot", lambda: an.student_snapshot(db, student, until))

    def prefill():
        from app.routes.api_v2.teacher import _compute_session_prefill  # döngüsel import'u önlemek için tembel
        return _compute_session_prefill(db, student)
    _safe(out, "session_prefill", prefill)

    def seanslar():
        from app.models.coaching_session import CoachingInsight, CoachingSession
        ss = (db.query(CoachingSession).filter(CoachingSession.student_id == student.id)
              .order_by(CoachingSession.session_date.desc()).limit(6).all())
        ins = db.query(CoachingInsight).filter(CoachingInsight.student_id == student.id).first()
        return {
            "sessions": [{"id": s.id, "date": s.session_date, "status": s.status, "agenda": s.agenda,
                          "coach_note": s.coach_note, "next_change": s.next_change, "mood": s.mood}
                         for s in ss],
            "insight": ({"summary": ins.summary, "agenda": ins.agenda_suggestions, "tips": ins.psychological_tips,
                         "watch": ins.watch_outs, "is_stale": ins.is_stale, "generated_at": ins.generated_at}
                        if ins else None),
        }
    _safe(out, "coaching", seanslar)

    def dna():
        from app.services import study_dna
        p = study_dna.compute_profile(db, student_id=student.id, window_days=28)
        d = to_jsonable(p)
        d.pop("heatmap", None)
        return d
    _safe(out, "study_dna", dna)

    def notlar():
        from app.models.student_day_note import StudentDayNote
        rows = (db.query(StudentDayNote).filter(StudentDayNote.student_id == student.id,
                                                  StudentDayNote.date >= since, StudentDayNote.date <= until)
                .order_by(StudentDayNote.date.asc()).all())
        return [{"date": r.date, "note": getattr(r, "note", None) or getattr(r, "text", None)} for r in rows]
    _safe(out, "day_notes", notlar)

    def talepler():
        from app.models.task_request import TaskRequest
        rows = (db.query(TaskRequest).filter(TaskRequest.student_id == student.id)
                .order_by(TaskRequest.created_at.asc()).all())
        return [{k: getattr(r, k, None) for k in ("id", "created_at", "kind", "status", "message",
                                                    "response", "task_id", "requested_count")} for r in rows]
    _safe(out, "task_requests", talepler)

    def selfstudy():
        from app.models.self_study import SelfStudyEntry
        rows = db.query(SelfStudyEntry).filter(SelfStudyEntry.student_id == student.id).all()
        return [{k: getattr(r, k, None) for k in ("id", "created_at", "status", "test_count",
                                                    "applied_count", "note", "book_section_id")} for r in rows]
    _safe(out, "self_study", selfstudy)

    def mism():
        from app.services import exam_consistency as ec
        return ec.curriculum_exam_mismatches(db, student.id)
    _safe(out, "exam_curriculum_mismatch", mism)

    return to_jsonable(out)


# ============================================================================
# 3) türetilmiş ölçüler (render + kural motoru ortak)
# ============================================================================
def derive(d: dict) -> dict:
    """Ham dökümden rapor/kural motorunun kullandığı türetilmiş ölçüler."""
    tw = d.get("tasks_window") or {}
    summ = tw.get("summary") or {}
    tasks = tw.get("tasks") or []
    win = d.get("window") or {}
    first, last = win.get("since"), win.get("until")
    D = Y = B = 0
    for r in tw.get("by_subject_topic") or []:
        D += r.get("correct") or 0
        Y += r.get("wrong") or 0
        B += r.get("blank") or 0
    days = [(k, v) for k, v in (tw.get("per_day") or {}).items() if first <= k <= last]
    worked_days = sum(1 for _, v in days if (v.get("gorev_done") or 0) > 0)
    planned_days = sum(1 for _, v in days if (v.get("gorev_total") or 0) > 0)
    day_dy: dict = defaultdict(lambda: {"D": 0, "Y": 0, "B": 0})
    for t in tasks:
        for it in t.get("items") or []:
            day_dy[t["date"]]["D"] += it.get("correct") or 0
            day_dy[t["date"]]["Y"] += it.get("wrong") or 0
            day_dy[t["date"]]["B"] += it.get("blank") or 0
    subj: dict = {}
    for s in summ.get("subjects") or []:
        subj[s["subject_name"]] = {"gorev_total": s["gorev_total"], "gorev_done": s["gorev_done"],
                                   "test_planned": s["test_planned"], "test_completed": s["test_completed"],
                                   "D": 0, "Y": 0, "B": 0}
    for r in tw.get("by_subject_topic") or []:
        if r.get("book_type") == "brans_denemesi":
            continue
        s = subj.setdefault(r["subject"], {"gorev_total": 0, "gorev_done": 0, "test_planned": 0,
                                           "test_completed": 0, "D": 0, "Y": 0, "B": 0})
        s["D"] += r.get("correct") or 0
        s["Y"] += r.get("wrong") or 0
        s["B"] += r.get("blank") or 0
    for s in subj.values():
        s["acc"] = pct(s["D"], s["D"] + s["Y"])
    denemeler = []
    for t in tasks:
        if t.get("category") != "deneme":
            continue
        it = (t.get("items") or [{}])[0]
        dd, yy = it.get("correct") or 0, it.get("wrong") or 0
        n = dd + yy + (it.get("blank") or 0)
        net = (dd - yy / TYT_PENALTY) if n else None
        denemeler.append({"date": t["date"], "subject": it.get("subject") or "—",
                          "planned": it.get("planned") or 0, "completed": it.get("completed") or 0,
                          "done": t.get("done"), "D": dd, "Y": yy, "n": n, "net": net,
                          "net_pct": (pct(net, n) if n else None)})
    topics = [dict(r) for r in (tw.get("by_subject_topic") or []) if r.get("book_type") != "brans_denemesi"]
    for r in topics:
        r["answered"] = (r.get("correct") or 0) + (r.get("wrong") or 0)
        r["acc"] = pct(r.get("correct") or 0, r["answered"])
    topics_sorted = sorted(topics, key=lambda r: ((r["acc"] if r["acc"] is not None else 999), -(r.get("wrong") or 0)))
    wrong_by_subject: dict = defaultdict(int)
    for r in tw.get("by_subject_topic") or []:
        wrong_by_subject[r["subject"]] += r.get("wrong") or 0
    total_wrong = sum(wrong_by_subject.values())
    wrong_topics = sorted([r for r in (tw.get("by_subject_topic") or []) if (r.get("wrong") or 0) > 0],
                          key=lambda r: -r["wrong"])
    pending = [t for t in tasks if not t.get("done")]
    no_dy = [t for t in tasks if t.get("done") and t.get("category") in ("test", "deneme")
             and any((it.get("completed") or 0) > 0 and it.get("correct") is None and it.get("wrong") is None
                     for it in (t.get("items") or []))]
    baseline_tests = sum((e.get("applied_count") or 0) for e in (d.get("self_study") or [])
                         if isinstance(e, dict) and e.get("status") == "approved")
    cur = d.get("curriculum") if isinstance(d.get("curriculum"), dict) else {"subjects": []}
    cur_subj = [s for s in cur.get("subjects") or []
                if (s.get("total_topics", 0) - s.get("no_resource_topics", 0)) > 0 or s.get("started_topics", 0) > 0]
    books = sorted(d.get("books") or [], key=lambda b: (SUBJ_ORDER.index(b["subject"]) if b.get("subject") in SUBJ_ORDER else 99, b.get("book") or ""))
    reqs = d.get("task_requests") if isinstance(d.get("task_requests"), list) else []
    dna = d.get("study_dna") if isinstance(d.get("study_dna"), dict) else None
    pre = d.get("session_prefill") if isinstance(d.get("session_prefill"), dict) else {}
    wq = (d.get("wrong_questions") or {}).get("coach_summary") or {}
    wq_total = ((wq.get("counts") or {}).get("total")) or 0
    gp = pct(summ.get("gorev_done") or 0, summ.get("gorev_total") or 0)
    return {
        "first": first, "last": last, "D": D, "Y": Y, "B": B, "acc_all": pct(D, D + Y),
        "days": days, "worked_days": worked_days, "planned_days": planned_days, "day_dy": day_dy,
        "subj": subj, "denemeler": denemeler, "topics_sorted": topics_sorted,
        "wrong_by_subject": wrong_by_subject, "total_wrong": total_wrong, "wrong_topics": wrong_topics,
        "pending": pending, "no_dy": no_dy, "baseline_tests": baseline_tests,
        "cur": cur, "cur_subj": cur_subj, "books": books, "reqs": reqs, "dna": dna, "pre": pre,
        "wq_total": wq_total, "gorev_pct": gp, "summ": summ,
        "exam_count": len(d.get("exams") or []) if isinstance(d.get("exams"), list) else 0,
        "next_week_task_count": tw.get("next_week_task_count") or 0,
    }


# ============================================================================
# 4) KURAL MOTORU — seans gündemi
# ============================================================================
_KW_ENERGY = ("enerji", "yorgun", "yoruldum", "bitkin", "çok zor", "zorlandım", "zordu")
_KW_RESOURCE = ("kalmamış", "kalmadı", "çözülmüş", "çözülü", "bitti", "bitmiş")


def _fmt_topic(r: dict) -> str:
    return f"{r.get('subject')} — {r.get('topic')}"


def build_agenda(d: dict, m: dict | None = None) -> list[dict]:
    """Veriden seans gündemi maddeleri. Her madde: {key, title, detail, severity}.
    severity: high | medium | info. Kredisiz, deterministik."""
    m = m or derive(d)
    items: list[dict] = []
    summ, subj = m["summ"], m["subj"]
    st = d.get("student") or {}
    name = (st.get("full_name") or "Öğrenci").split(" ")[0]

    # 1) Haftanın özeti
    best = max([(v.get("acc") or 0, k) for k, v in subj.items() if (v["D"] + v["Y"]) >= 20] or [(0, None)])
    parts = [f"{summ.get('gorev_done', 0)}/{summ.get('gorev_total', 0)} görev (%{m['gorev_pct'] if m['gorev_pct'] is not None else 0})",
             f"{m['worked_days']}/{m['planned_days'] or len(m['days'])} gün çalışıldı",
             f"{summ.get('test_completed', 0)} test (plan {summ.get('test_planned', 0)})"]
    if m["acc_all"] is not None:
        parts.append(f"genel doğruluk %{m['acc_all']} ({m['D']} D / {m['Y']} Y)")
    if best[1]:
        parts.append(f"en güçlü ders {best[1]} %{best[0]}")
    sev = "info" if (m["gorev_pct"] or 0) >= 85 else ("medium" if (m["gorev_pct"] or 0) >= 60 else "high")
    items.append({"key": "summary", "severity": sev,
                  "title": "Haftanın özeti" + (" — güçlü hafta" if sev == "info" else " — düşük tamamlama" if sev == "high" else ""),
                  "detail": "; ".join(parts) + ". " + ("Takdir et, ritmin korunacağı mesajını ver." if sev == "info" else "Nedenini birlikte konuşun.")})

    # 2) Düşük günler + açık görevler + enerji sinyali
    low_days = [(k, v) for k, v in m["days"] if (v.get("gorev_total") or 0) > 0
                and pct(v.get("gorev_done") or 0, v.get("gorev_total") or 0) < 75]
    energy_msgs = [r for r in m["reqs"] if any(k in (r.get("message") or "").lower() for k in _KW_ENERGY)]
    if low_days or m["pending"] or energy_msgs:
        det = []
        if low_days:
            det.append("Düşük günler: " + ", ".join(f"{d_tr(k)} ({v.get('gorev_done')}/{v.get('gorev_total')})" for k, v in low_days) + ".")
        if m["pending"]:
            det.append(f"Yapılmayan {len(m['pending'])} görev: " + "; ".join(
                f"{d_tr(t['date'], False)} {t['title']}" for t in m["pending"][:4]) + (" …" if len(m["pending"]) > 4 else "") + ".")
        if energy_msgs:
            det.append("Mesajlarda zorlanma/enerji sinyali: " + " | ".join(f"“{r['message'][:70]}”" for r in energy_msgs[:2]) + ".")
        avg_tasks = round(sum((v.get("gorev_total") or 0) for _, v in m["days"]) / max(1, m["planned_days"]), 1)
        det.append(f"Günlük yük ≈ {avg_tasks} görev. Sor: hangi gün/saat/ders yordu? Karar: yük mü hafiflesin, dağılım mı değişsin?")
        items.append({"key": "load", "severity": "high" if (len(low_days) >= 2 or energy_msgs) else "medium",
                      "title": "Yük ve enerji", "detail": " ".join(det)})

    # 3) Zayıf konular
    weak = [r for r in m["topics_sorted"] if r["acc"] is not None and r["acc"] < 80 and r["answered"] >= 20]
    top_wrong = m["wrong_topics"][0] if m["wrong_topics"] else None
    if weak or top_wrong:
        det = []
        if weak:
            det.append("Doğruluğu %80'in altındaki konular: " + ", ".join(
                f"{_fmt_topic(r)} %{r['acc']} ({r['wrong']} Y)" for r in weak[:4]) + ".")
        if top_wrong:
            det.append(f"En çok yanlış: {_fmt_topic(top_wrong)} ({top_wrong['wrong']} Y).")
        det.append("Karar: konu tekrarı mı, kaynak/zorluk ayarı mı, yanlış analizi mi?")
        items.append({"key": "weak_topics", "severity": "high" if len(weak) >= 2 else "medium",
                      "title": "Zayıf konular — yanlışların yoğunlaştığı yer", "detail": " ".join(det)})

    # 4) Ders odağı — doğruluğu en düşük ders (≥30 cevaplı) + açık kalan + D/Y girilmemiş
    cands = [(v["acc"], k) for k, v in subj.items() if v.get("acc") is not None and (v["D"] + v["Y"]) >= 30]
    if cands or m["no_dy"]:
        det = []
        s_name = None
        if cands:
            acc_min, s_name = min(cands)
            s = subj[s_name]
            share = round(100 * m["wrong_by_subject"].get(s_name, 0) / (m["total_wrong"] or 1))
            det.append(f"{s_name}: doğruluk %{acc_min} ({s['D']} D / {s['Y']} Y), haftanın yanlışlarındaki payı %{share}.")
            pend_s = [t for t in m["pending"] if any((it.get("subject") == s_name) for it in t.get("items") or [])]
            if pend_s:
                det.append(f"Bu derste {len(pend_s)} görev açık kaldı.")
        if m["no_dy"]:
            det.append("D/Y girilmeyen kalem: " + "; ".join(f"{d_tr(t['date'], False)} {t['title'][:60]}" for t in m["no_dy"][:3]) + ".")
        items.append({"key": "subject_focus", "severity": "medium",
                      "title": f"Ders odağı: {s_name}" if s_name else "Eksik D/Y girişleri", "detail": " ".join(det)})

    # 5) Branş deneme trendi
    by_s: dict = defaultdict(list)
    for x in m["denemeler"]:
        if x["n"]:
            by_s[x["subject"]].append(x)
    dets = []
    sev = "info"
    for sname, xs in by_s.items():
        if len(xs) >= 2:
            a, b = xs[0], xs[-1]
            delta = b["net"] - a["net"]
            arrow = "↑" if delta > 0.5 else ("↓" if delta < -0.5 else "→")
            txt = f"{sname}: {a['net']:.2f} → {b['net']:.2f} net {arrow}"
            if delta <= -2:
                txt += " (belirgin düşüş)"
                sev = "high"
            dets.append(txt)
        elif xs:
            dets.append(f"{sname}: {xs[0]['net']:.2f} net (tek set)")
        low = [x for x in xs if (x["net_pct"] or 0) < 60]
        if low and len(low) == len(xs):
            dets.append(f"{sname} net oranı düşük (%{min(x['net_pct'] or 0 for x in xs)}–%{max(x['net_pct'] or 0 for x in xs)})")
            sev = "high" if sev != "high" else sev
    missing_sb = []
    for sname in by_s:
        sb = [b for b in m["books"] if b.get("subject") == sname and b.get("type") == "soru_bankasi"]
        if not sb or all((b.get("completed") or 0) == 0 for b in sb):
            missing_sb.append(sname)
    if dets:
        det = "; ".join(dets) + "."
        if missing_sb:
            det += f" {', '.join(missing_sb)} için soru bankası çalışması yok — deneme öncesi konu çalışması planla."
        items.append({"key": "deneme_trend", "severity": sev, "title": "Branş denemeleri", "detail": det})

    # 6) Kaynak & atama hijyeni
    res_msgs = [r for r in m["reqs"] if any(k in (r.get("message") or "").lower() for k in _KW_RESOURCE)]
    unstarted = [b for b in m["books"] if b.get("type") == "soru_bankasi" and (b.get("completed") or 0) == 0]
    if res_msgs or unstarted:
        det = []
        if res_msgs:
            det.append("Öğrenci mesajlarında 'kalmamış/çözülmüş/bitti' sinyalleri: " + " | ".join(f"“{r['message'][:60]}”" for r in res_msgs[:2])
                       + " → kitapların 'önceden çözülmüş test' işaretlerini güncelle, atarken kalan kapasiteyi kontrol et.")
        if unstarted:
            det.append("Hiç başlanmamış soru bankaları: " + ", ".join(f"{b['book']} ({b.get('subject')})" for b in unstarted[:4]) + ".")
        items.append({"key": "resources", "severity": "medium" if res_msgs else "info",
                      "title": "Kaynak ve atama hijyeni", "detail": " ".join(det)})

    # 7) Bekleyen talepler
    pend_req = [r for r in m["reqs"] if r.get("status") == "pending"]
    if pend_req:
        items.append({"key": "pending_requests", "severity": "high", "title": "Yanıt bekleyen öğrenci mesajı",
                      "detail": " | ".join(f"{d_tr(str(r.get('created_at'))[:10])}: “{r.get('message')}”" for r in pend_req[:3]) + " — seans öncesi kapat."})

    # 8) Boş sistemler
    empties = []
    if m["wq_total"] == 0 and m["Y"] > 0:
        empties.append(f"Yanlış Soru Arşivi boş — bu hafta {m['Y']} yanlış yapıldı ama hiçbiri arşive girmedi; günde 2–3 yanlışı fotoğrafla eklemesini iste (AI ipucu + aralıklı tekrar).")
    if m["exam_count"] == 0:
        empties.append("Sisteme girilmiş genel deneme yok — ilk genel denemeyi tarihle; karne PDF'i aktarılınca konu×deneme analizi açılır.")
    if empties:
        items.append({"key": "empty_systems", "severity": "medium", "title": "Kullanılmayan araçlar", "detail": " ".join(empties)})

    # 9) Çalışma ritmi
    dna = m["dna"] or {}
    tot = sum((dna.get(k) or 0) for k in ("morning_count", "afternoon_count", "evening_count", "night_count"))
    night = dna.get("night_count") or 0
    if tot >= 10 and night / tot >= 0.5:
        items.append({"key": "rhythm", "severity": "info", "title": "Çalışma ritmi: gece ağırlıklı",
                      "detail": f"İşaretlemelerin %{round(100 * night / tot)}'i gece (22–06). Gerçekten geç mi çalışıyor, yoksa günün işini gece toplu mu işaretliyor? Uyku/ritim sorusu."})

    # 10) Gelecek hafta
    focus = [f"{_fmt_topic(r)}" for r in weak[:2]]
    nxt = [f"{s['name']}: sırada {s.get('next_topic_name')}" for s in m["cur_subj"] if s.get("next_topic_name")][:3]
    det = ("Gelecek hafta için program henüz yok — oluştur. " if not m["next_week_task_count"] else f"Gelecek hafta {m['next_week_task_count']} görev planlı. ")
    if focus:
        det += "Odak: " + ", ".join(focus) + ". "
    if nxt:
        det += "Müfredat: " + "; ".join(nxt) + ". "
    if unstarted:
        det += f"Başlanmamış kaynak: {unstarted[0]['book']}."
    items.append({"key": "next_week", "severity": "info", "title": "Gelecek haftanın programı", "detail": det.strip()})
    return items


# ============================================================================
# 5) HTML
# ============================================================================
def _esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=False)


def _bar(p, cls="acc", label=None):
    p = 0 if p is None else max(0, min(100, p))
    lab = _esc(label if label is not None else f"%{p}")
    fill = _band(p) if cls == "acc" else "neutral"
    return (f'<span class="bar {cls}"><span class="fill b-{fill}" style="width:{p}%"></span></span>'
            f'<span class="num">{lab}</span>')


def _chip(text, kind="neutral"):
    return f'<span class="chip c-{kind}">{_esc(text)}</span>'


def render_html(d: dict, agenda: list[dict], ai_agenda: list[dict] | None = None, *,
                report_id: int | None = None, version: int = 1, session_url: str | None = None) -> str:
    """Rapor HTML'i (tek dosya). `ai_agenda` varsa gündem bölümünde AI metni,
    altında kural motoru maddeleri katlanır; yoksa kural maddeleri."""
    m = derive(d)
    st = d.get("student") or {}
    summ = m["summ"]
    first, last = m["first"], m["last"]
    week_label = f"{d_tr(first, False)} – {d_tr(last, False)} {date.fromisoformat(last).year}"
    grade = st.get("grade_level")
    track = str(st.get("track") or "")
    grade_txt = (f"{grade}. sınıf" if grade else "Mezun") + (f" · {track.capitalize()}" if track else "")
    H: list[str] = []

    def stat(label, value, sub="", kind="neutral"):
        return (f'<div class="stat s-{kind}"><div class="stat-l">{_esc(label)}</div><div class="stat-v">{value}</div>'
                f'<div class="stat-s">{_esc(sub)}</div></div>')

    H.append(f"""
<header class="top">
  <div class="eyebrow">Haftalık Koçluk Raporu{(' · sürüm ' + str(version)) if version > 1 else ''}</div>
  <h1>{_esc(st.get('full_name'))}</h1>
  <div class="meta">
    <span>{_esc(grade_txt)}</span><span class="dot">·</span>
    <span>Program haftası: <b>{_esc(week_label)}</b></span><span class="dot">·</span>
    <span>Koç: {_esc((st.get('coach') or {}).get('full_name', ''))}</span><span class="dot">·</span>
    <span>Rapor tarihi: {_esc(d_tr((d.get('generated_at') or '')[:10], False))}</span>
  </div>
</header>""")

    gp = m["gorev_pct"]
    H.append('<section class="stats">')
    H.append(stat("Görev tamamlama", f'<b>%{gp if gp is not None else 0}</b>', f'{summ.get("gorev_done", 0)} / {summ.get("gorev_total", 0)} görev', _band(gp)))
    H.append(stat("Çözülen test", f'<b>{summ.get("test_completed", 0)}</b>', f'planlanan {summ.get("test_planned", 0)} · soru bankası',
                  "good" if (summ.get("test_completed", 0) >= summ.get("test_planned", 0) and summ.get("test_planned", 0)) else "warn"))
    H.append(stat("Branş denemesi", f'<b>{summ.get("deneme_completed", 0)}</b> / {summ.get("deneme_planned", 0)}',
                  " · ".join(sorted({x["subject"] for x in m["denemeler"]})) or "bu hafta yok",
                  _band(pct(summ.get("deneme_completed", 0), summ.get("deneme_planned", 0)))))
    H.append(stat("Genel doğruluk", f'<b>%{m["acc_all"] if m["acc_all"] is not None else "—"}</b>',
                  f'{m["D"]} doğru · {m["Y"]} yanlış · {m["B"]} boş', _band(m["acc_all"])))
    H.append(stat("Çalışılan gün", f'<b>{m["worked_days"]}</b> / {len(m["days"])}',
                  "her gün görev kapatıldı" if m["worked_days"] == len(m["days"]) else "boş gün var",
                  "good" if m["worked_days"] == len(m["days"]) else "warn"))
    H.append(stat("Yanlış soru arşivi", f'<b>{m["wq_total"]}</b>', "kayıt yok — henüz kullanmıyor" if m["wq_total"] == 0 else "kayıt",
                  "warn" if m["wq_total"] == 0 else "neutral"))
    H.append('</section>')

    # haftanın seyri
    low_days = [(k, v) for k, v in m["days"] if (v.get("gorev_total") or 0) > 0 and pct(v.get("gorev_done") or 0, v.get("gorev_total") or 0) < 75]
    note = (" Düşük gün: " + ", ".join(f"{d_tr(k)} ({v.get('gorev_done')}/{v.get('gorev_total')})" for k, v in low_days) + ".") if low_days else ""
    rows = []
    for k, v in m["days"]:
        gt, gd = v.get("gorev_total") or 0, v.get("gorev_done") or 0
        p = pct(gd, gt)
        dy = m["day_dy"][k]
        acc = pct(dy["D"], dy["D"] + dy["Y"])
        rows.append(f"""<tr><td class="day">{_esc(d_tr(k))}</td><td class="num">{gd} / {gt}</td>
  <td class="barcell">{_bar(p, 'acc', f'%{p}' if p is not None else '—')}</td>
  <td class="num">{v.get('test_completed', 0)} / {v.get('test_planned', 0)}</td>
  <td class="num">{v.get('deneme_completed', 0)} / {v.get('deneme_planned', 0)}</td>
  <td class="num">{dy['D']} / <span class="red">{dy['Y']}</span>{(' / ' + str(dy['B'])) if dy['B'] else ''}</td>
  <td class="barcell">{_bar(acc, 'acc', f'%{acc}' if acc is not None else '—')}</td></tr>""")
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Haftanın seyri</h2><p>Gün gün görev kapanışı, çözülen test/deneme ve o günün doğru-yanlışı.{_esc(note)}</p></div>
  <div class="tablewrap"><table class="t">
    <thead><tr><th>Gün</th><th class="num">Görev</th><th>Kapanış</th><th class="num">Test</th><th class="num">Deneme</th><th class="num">D / Y / B</th><th>Doğruluk</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table></div>
</section>""")

    # ders bazlı
    tw_total = m["total_wrong"] or 1
    rows = []
    for name in sorted(m["subj"].keys(), key=lambda n: SUBJ_ORDER.index(n) if n in SUBJ_ORDER else 99):
        if name == "—":
            continue  # derssiz kalemler — genel toplamda zaten sayılı
        s = m["subj"][name]
        rows.append(f"""<tr><td class="lbl">{_esc(name)}</td><td class="num">{s['gorev_done']} / {s['gorev_total']}</td>
  <td class="num">{s['test_completed']} / {s['test_planned']}</td><td class="num">{s['D']}</td><td class="num red">{s['Y']}</td><td class="num">{s['B'] or '—'}</td>
  <td class="barcell">{_bar(s['acc'], 'acc', f"%{s['acc']}" if s['acc'] is not None else '—')}</td>
  <td class="num muted">%{round(100 * s['Y'] / tw_total) if m['total_wrong'] else 0}</td></tr>""")
    den_sub: dict = defaultdict(lambda: {"D": 0, "Y": 0, "n": 0, "c": 0, "p": 0})
    for x in m["denemeler"]:
        ds = den_sub[x["subject"]]
        ds["D"] += x["D"]; ds["Y"] += x["Y"]; ds["n"] += x["n"]; ds["c"] += x["completed"]; ds["p"] += x["planned"]
    for name, ds in sorted(den_sub.items(), key=lambda kv: SUBJ_ORDER.index(kv[0]) if kv[0] in SUBJ_ORDER else 99):
        acc = pct(ds["D"], ds["D"] + ds["Y"])
        rows.append(f"""<tr><td class="lbl">{_esc(name)} <span class="tag">branş denemesi</span></td><td class="num">—</td>
  <td class="num">{ds['c']} / {ds['p']} deneme</td><td class="num">{ds['D']}</td><td class="num red">{ds['Y']}</td><td class="num">—</td>
  <td class="barcell">{_bar(acc, 'acc', f'%{acc}' if acc is not None else '—')}</td>
  <td class="num muted">%{round(100 * ds['Y'] / tw_total) if m['total_wrong'] else 0}</td></tr>""")
    top2 = sorted(m["wrong_by_subject"].items(), key=lambda kv: -kv[1])[:2]
    share_note = (f" Yanlışların <b>%{round(100 * sum(v for _, v in top2) / tw_total)}</b>'i {' + '.join(k for k, _ in top2)} derslerinden." if top2 and m["total_wrong"] else "")
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Ders bazlı performans</h2><p>Soru bankası testleri ve branş denemeleri ayrı okunur (birim farkı). Son sütun: haftanın toplam yanlışı içindeki pay.{share_note}</p></div>
  <div class="tablewrap"><table class="t">
    <thead><tr><th>Ders</th><th class="num">Görev</th><th class="num">Test</th><th class="num">Doğru</th><th class="num">Yanlış</th><th class="num">Boş</th><th>Doğruluk</th><th class="num">Yanlış payı</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table></div>
</section>""")

    # konu bazlı
    rows = []
    for r in m["topics_sorted"]:
        st_chip = (_chip('zayıf', 'bad') if (r['acc'] is not None and r['acc'] < 80)
                   else (_chip('dikkat', 'warn') if (r['acc'] is not None and r['acc'] < 85) else _chip('iyi', 'good')))
        rows.append(f"""<tr><td class="lbl"><span class="sub">{_esc(r['subject'])}</span>{_esc(r['topic'])}</td>
  <td class="num">{r['completed']} / {r['planned']}</td><td class="num">{r['correct']}</td><td class="num red">{r['wrong']}</td><td class="num">{r['blank'] or '—'}</td>
  <td class="barcell">{_bar(r['acc'], 'acc', f"%{r['acc']}" if r['acc'] is not None else '—')}</td><td>{st_chip}</td></tr>""")
    wrows = []
    for r in m["wrong_topics"][:10]:
        share = round(100 * r["wrong"] / tw_total)
        wrows.append(f'<tr><td class="lbl"><span class="sub">{_esc(r["subject"])}</span>{_esc(r["topic"])}</td><td class="num red">{r["wrong"]}</td><td class="barcell">{_bar(share, "share", f"%{share}")}</td></tr>')
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Konu bazlı doğru / yanlış</h2><p>Bu hafta çözülen soru bankası testleri, doğruluğa göre (en düşük üstte). Eşikler: %85+ iyi · %70–84 dikkat · altı zayıf. Sayılar öğrencinin girdiği D/Y'den.</p></div>
  <div class="tablewrap"><table class="t">
    <thead><tr><th>Ders · Konu</th><th class="num">Test</th><th class="num">D</th><th class="num">Y</th><th class="num">B</th><th>Doğruluk</th><th>Durum</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="7" class="muted">Bu hafta D/Y girilmiş test yok.</td></tr>'}</tbody></table></div>
  <h3>Yanlışların dağılımı <span class="muted">({m['total_wrong']} yanlış · branş denemeleri dahil)</span></h3>
  <div class="tablewrap"><table class="t compact"><thead><tr><th>Ders · Konu</th><th class="num">Yanlış</th><th>Pay</th></tr></thead>
    <tbody>{''.join(wrows) or '<tr><td colspan="3" class="muted">—</td></tr>'}</tbody></table></div>
</section>""")

    # branş denemeleri
    rows = []
    for x in m["denemeler"]:
        if not x["n"]:
            rows.append(f'<tr class="dim"><td>{_esc(d_tr(x["date"]))}</td><td class="lbl">{_esc(x["subject"])}</td><td class="num">{x["completed"]} / {x["planned"]}</td><td colspan="4" class="muted">{"yapılmadı" if not x["done"] else "D/Y girilmedi"}</td></tr>')
            continue
        rows.append(f"""<tr><td>{_esc(d_tr(x['date']))}</td><td class="lbl">{_esc(x['subject'])}</td><td class="num">{x['completed']} / {x['planned']}</td>
  <td class="num">{x['n']}</td><td class="num">{x['D']} / <span class="red">{x['Y']}</span></td><td class="num"><b>{x['net']:.2f}</b></td>
  <td class="barcell">{_bar(x['net_pct'], 'acc', f"%{x['net_pct']}")}</td></tr>""")
    trend = []
    by_s: dict = defaultdict(list)
    for x in m["denemeler"]:
        if x["n"]:
            by_s[x["subject"]].append(x)
    for sname, xs in by_s.items():
        if len(xs) >= 2:
            a, b = xs[0], xs[-1]
            delta = b["net"] - a["net"]
            arrow = "↑" if delta > 0.5 else ("↓" if delta < -0.5 else "→")
            trend.append(f"<li><b>{_esc(sname)}</b>: {a['net']:.2f} → {b['net']:.2f} net ({arrow} {delta:+.2f}); {xs[0]['n']} soruluk set başına.</li>")
    exam_note = ("Henüz sisteme girilmiş <b>genel deneme / karne yok</b> — net trendi ve konu×deneme analizi bunun için bekliyor."
                 if m["exam_count"] == 0 else f"Sistemde {m['exam_count']} genel deneme kayıtlı.")
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Branş denemeleri</h2><p>Her satır bir günün branş deneme seti (TYT/AYT: {TYT_PENALTY} yanlış 1 doğruyu götürür). {exam_note}</p></div>
  <div class="tablewrap"><table class="t">
    <thead><tr><th>Gün</th><th>Ders</th><th class="num">Deneme</th><th class="num">Soru</th><th class="num">D / Y</th><th class="num">Net</th><th>Net oranı</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="7" class="muted">Bu hafta branş denemesi yok.</td></tr>'}</tbody></table></div>
  <ul class="notes">{''.join(trend)}</ul>
</section>""")

    # müfredat
    rows = []
    for s in sorted(m["cur_subj"], key=lambda s: SUBJ_ORDER.index(s["name"]) if s["name"] in SUBJ_ORDER else 99):
        chips = []
        for t in s.get("topics") or []:
            if t.get("status") == "tamamlandi":
                chips.append(_chip(t["name"], "good"))
            elif t.get("status") in ("devam", "planlandi"):
                chips.append(_chip(f'{t["name"]} · {t.get("completed", 0)}/{t.get("test_total", 0)}', "warn"))
        rows.append(f"""<div class="cur">
  <div class="cur-h"><b>{_esc(s['name'])}</b> <span class="muted">{s['started_topics']} / {s['total_topics']} konuya başlandı · {s['completed_topics']} tamamlandı{(' · kaynağı olmayan konu: ' + str(s['no_resource_topics'])) if s.get('no_resource_topics') else ''}</span>
    <span class="cur-bar">{_bar(s['coverage_pct'], 'prog', f"%{s['coverage_pct']}")}</span></div>
  <div class="cur-next">Sırada: <b>{_esc(s.get('next_topic_name') or '—')}</b>{(' · son işlenen: ' + _esc(s['last_topic_name'])) if s.get('last_topic_name') else ''}</div>
  <div class="chips">{''.join(chips) if chips else '<span class="muted">başlanan konu yok</span>'}</div>
</div>""")
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Müfredat kapsama (ders bazlı)</h2><p>Resmi konu sırasına göre hangi konulara başlandı/tamamlandı. <b>Kapsama</b> = en az bir test çözülen konu oranı. Koçluk öncesi "önceden çözülmüş" işaretlenen <b>{m['baseline_tests']} test</b> de sayıma dahildir. Müfredat konularına eşlenmemiş kitaplar burada görünmez.</p></div>
  {''.join(rows) or '<p class="muted">Müfredata eşli kaynak yok.</p>'}
</section>""")

    # kitaplar
    rows = []
    for b in m["books"]:
        p = b.get("pct")
        rows.append(f"""<tr><td class="lbl"><span class="sub">{_esc(b.get('subject'))}</span>{_esc(b.get('book'))} <span class="tag">{'branş denemesi' if b.get('type') == 'brans_denemesi' else 'soru bankası'}</span></td>
  <td class="num">{b.get('completed')} / {b.get('test_total')}</td><td class="num muted">{b.get('reserved') or '—'}</td>
  <td class="barcell">{_bar(p, 'prog', f'%{p}' if p is not None else '—')}</td></tr>""")
    unstarted = sum(1 for b in m["books"] if (b.get("completed") or 0) == 0)
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Kitap ilerlemesi</h2><p>{len(m['books'])} kitap · çözülen / toplam test. "Rezerv" = gelecek güne atanmış ama henüz çözülmemiş test.{(' ' + str(unstarted) + ' kitapta hiç başlanmadı.') if unstarted else ''}</p></div>
  <div class="tablewrap"><table class="t"><thead><tr><th>Kitap</th><th class="num">Test</th><th class="num">Rezerv</th><th>İlerleme</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="4" class="muted">Atanmış kitap yok.</td></tr>'}</tbody></table></div>
</section>""")

    # açık kalanlar
    li = [f"<li><b>{_esc(d_tr(t['date']))}</b> — {_esc(t['title'])} <span class='muted'>({(t.get('items') or [{}])[0].get('completed', 0)}/{(t.get('items') or [{}])[0].get('planned', 0)})</span></li>" for t in m["pending"]]
    li2 = [f"<li><b>{_esc(d_tr(t['date']))}</b> — {_esc(t['title'])}</li>" for t in m["no_dy"]]
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Açık kalanlar</h2><p>Yapılmayan görevler ve doğru/yanlışı girilmeden kapatılan kalemler.</p></div>
  <div class="two">
    <div><h3>Yapılmadı ({len(m['pending'])})</h3><ul class="notes">{''.join(li) or '<li>—</li>'}</ul></div>
    <div><h3>D/Y girilmedi ({len(m['no_dy'])})</h3><ul class="notes">{''.join(li2) or '<li>—</li>'}</ul></div>
  </div>
</section>""")

    # mesajlar
    title_by_id = {t["id"]: t["title"] for t in (d.get("tasks_window") or {}).get("tasks") or []}
    rows = []
    for r in m["reqs"]:
        ts = str(r.get("created_at") or "")
        try:
            when = d_tr(ts[:10]) + " " + datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M")
        except ValueError:
            when = ts[:16]
        ctx = title_by_id.get(r.get("task_id"))
        status = {"resolved": "çözüldü", "approved": "onaylandı", "withdrawn": "geri çekti", "pending": "BEKLİYOR",
                  "rejected": "reddedildi"}.get(r.get("status"), r.get("status") or "")
        rows.append(f'<tr><td class="day">{_esc(when)}</td><td>“{_esc(r.get("message"))}”{("<div class=muted>↳ " + _esc(ctx) + "</div>") if ctx else ""}</td><td>{_chip(status, "warn" if r.get("status") == "pending" else "neutral")}</td></tr>')
    n_pending_req = sum(1 for r in m["reqs"] if r.get("status") == "pending")
    H.append(f"""
<section class="card">
  <div class="card-h"><h2>Öğrenci mesajları (görev talepleri)</h2><p>{len(m['reqs'])} mesaj — zorlanma, enerji ve kaynak-bitti sinyalleri buradan okunur{('; ' + str(n_pending_req) + ' mesaj yanıt bekliyor') if n_pending_req else ''}.</p></div>
  <div class="tablewrap"><table class="t compact"><thead><tr><th>Zaman</th><th>Mesaj</th><th>Durum</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="3" class="muted">Mesaj yok.</td></tr>'}</tbody></table></div>
</section>""")

    # ritim
    dna = m["dna"]
    if dna:
        tot = sum((dna.get(k) or 0) for k in ("morning_count", "afternoon_count", "evening_count", "night_count"))

        def seg(label, n):
            p = pct(n, tot) or 0
            return f'<div class="seg"><span class="seg-l">{_esc(label)}</span>{_bar(p, "share", f"{n} işaret · %{p}")}</div>'
        H.append(f"""
<section class="card">
  <div class="card-h"><h2>Çalışma ritmi (işaretleme saatleri)</h2><p>Görevlerin tamamlandı işaretlendiği saatler — son 28 gün. Gece yoğunluğu iki şey olabilir: gerçekten geç çalışıyor ya da günün tamamını gece toplu işaretliyor.</p></div>
  <div class="segs">{seg('Sabah (06–12)', dna.get('morning_count') or 0)}{seg('Öğle (12–17)', dna.get('afternoon_count') or 0)}{seg('Akşam (17–22)', dna.get('evening_count') or 0)}{seg('Gece (22–06)', dna.get('night_count') or 0)}</div>
  <p class="muted small">Zirve gün: <b>{_esc(dna.get('peak_day_name'))}</b> · hafta içi {dna.get('weekday_count')} / hafta sonu {dna.get('weekend_count')} işaret · son 7 gün hızı: <b>{m['pre'].get('recent_rate')}</b> test/gün.</p>
</section>""")

    # seans gündemi
    sev_chip = {"high": ("öncelikli", "bad"), "medium": ("konuşulmalı", "warn"), "info": ("bilgi", "neutral")}
    if ai_agenda:
        items_html = "".join(f"<li><b>{_esc(a.get('title'))}</b> — {_esc(a.get('detail'))}</li>" for a in ai_agenda)
        rule_html = "".join(f"<li><b>{_esc(a.get('title'))}</b> {_chip(*sev_chip.get(a.get('severity'), ('bilgi', 'neutral')))}<br>{_esc(a.get('detail'))}</li>" for a in agenda)
        body = (f'<ol class="agenda-list">{items_html}</ol>'
                f'<details class="rules"><summary>Kural motorunun ham maddeleri ({len(agenda)})</summary><ol class="agenda-list small">{rule_html}</ol></details>')
        lead = "Yapay zekâ, haftanın verisinden seans için öncelik sırasıyla yazdı. Her madde bir karar ya da soru içerir."
    else:
        items_html = "".join(f"<li><b>{_esc(a.get('title'))}</b> {_chip(*sev_chip.get(a.get('severity'), ('bilgi', 'neutral')))}<br>{_esc(a.get('detail'))}</li>" for a in agenda)
        body = f'<ol class="agenda-list">{items_html}</ol>'
        lead = "Veriden çıkan, seansta konuşmaya değer başlıklar — öncelik sırasıyla (kural motoru). Her madde bir karar ya da soru içerir."
    open_link = f'<p class="cta"><a href="{_esc(session_url)}">Bu gündemle seans aç →</a></p>' if session_url else ""
    H.append(f"""
<section class="card agenda" id="gundem">
  <div class="card-h"><h2>Seans gündemi — veriden çıkan başlıklar</h2><p>{lead}</p></div>
  {body}{open_link}
</section>""")

    H.append(f"""
<section class="card notesbox">
  <div class="card-h"><h2>Veri notları</h2></div>
  <ul class="notes small">
    <li>Kaynak: Rotam veritabanı, {_esc((d.get('generated_at') or '')[:16].replace('T', ' '))} UTC anlık görüntüsü; yalnız yayınlanmış görevler (taslaklar hariç).</li>
    <li>Doğru/yanlış sayıları öğrencinin görev kapatırken girdiği değerlerdir; girilmeyen kalemler doğruluk hesabına girmez.</li>
    <li>"Test" = soru bankası testi; "deneme" = branş denemesi seti (adet). İkisi birbirine sayılmaz.</li>
    <li>Kitap/müfredat ilerlemesi koçluk öncesi beyan edilen {m['baseline_tests']} testi de içerir; haftalık tablolar yalnız bu haftayı sayar.</li>
  </ul>
</section>""")
    title = f"{_esc(st.get('full_name'))} · {_esc(d_tr(first, False))}–{_esc(d_tr(last, False))}"
    return _TEMPLATE.replace("{{TITLE}}", title).replace("{{BODY}}", "\n".join(H))


_TEMPLATE = """<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{TITLE}}</title>
<style>
:root{--bg:#F4F6F8;--surface:#FFFFFF;--ink:#13262F;--ink-2:#3E5560;--muted:#6A7C86;--line:#DCE3E8;--accent:#0E7490;--accent-soft:#E3F2F6;--amber:#B9760A;--amber-soft:#FBF0DA;--good:#1E7F56;--good-soft:#DFF2E8;--warn:#B26A00;--warn-soft:#FCEFD8;--bad:#B3362B;--bad-soft:#F9E2DF;--bar-track:#E6ECF0;--neutral-fill:#5C8FA3}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0F181E;--surface:#16232B;--ink:#E8EEF1;--ink-2:#C3D0D7;--muted:#91A3AD;--line:#2A3942;--accent:#5BC3D9;--accent-soft:#12303A;--amber:#F0B54D;--amber-soft:#3A2C12;--good:#5AD19A;--good-soft:#173527;--warn:#F2B25A;--warn-soft:#3C2C10;--bad:#F08A7C;--bad-soft:#43211D;--bar-track:#233038;--neutral-fill:#7FB6CA}}
:root[data-theme="dark"]{--bg:#0F181E;--surface:#16232B;--ink:#E8EEF1;--ink-2:#C3D0D7;--muted:#91A3AD;--line:#2A3942;--accent:#5BC3D9;--accent-soft:#12303A;--amber:#F0B54D;--amber-soft:#3A2C12;--good:#5AD19A;--good-soft:#173527;--warn:#F2B25A;--warn-soft:#3C2C10;--bad:#F08A7C;--bad-soft:#43211D;--bar-track:#233038;--neutral-fill:#7FB6CA}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,Roboto,sans-serif;font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{max-width:980px;margin:0 auto;padding:28px 18px 64px}
.top{padding:10px 4px 22px}
.eyebrow{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-family:"Segoe UI Variable Display","Segoe UI",system-ui,sans-serif;font-size:34px;line-height:1.1;margin:6px 0 10px;letter-spacing:-.01em;text-wrap:balance}
.meta{color:var(--ink-2);font-size:14px;display:flex;flex-wrap:wrap;gap:6px 8px}.meta .dot{color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(138px,1fr));gap:10px;margin:6px 0 16px}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px;position:relative;overflow:hidden}
.stat::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--line)}
.stat.s-good::before{background:var(--good)}.stat.s-warn::before{background:var(--warn)}.stat.s-bad::before{background:var(--bad)}
.stat-l{font-size:12px;color:var(--muted);letter-spacing:.04em;text-transform:uppercase;font-weight:600}
.stat-v{font-size:26px;line-height:1.15;margin-top:4px;font-variant-numeric:tabular-nums;color:var(--ink)}.stat-v b{font-weight:800}
.stat-s{font-size:12.5px;color:var(--ink-2);margin-top:2px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px 20px 16px;margin:14px 0}
.card-h h2{font-size:19px;margin:0 0 4px;letter-spacing:-.005em}.card-h p{margin:0 0 12px;color:var(--ink-2);font-size:14px;max-width:72ch}
h3{font-size:14.5px;margin:16px 0 8px;color:var(--ink)}
.tablewrap{overflow-x:auto}
table.t{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}
table.t th{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);font-weight:700;white-space:nowrap}
table.t td{padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:middle}table.t tr:last-child td{border-bottom:none}
table.t .num{text-align:right;white-space:nowrap}table.t th.num{text-align:right}table.t .lbl{font-weight:600}table.t .day{white-space:nowrap;font-weight:600}
table.t .sub{display:block;font-size:11px;color:var(--muted);font-weight:600;letter-spacing:.03em;text-transform:uppercase}
table.compact td{padding:5px 8px}tr.dim td{color:var(--muted)}
.red{color:var(--bad);font-weight:600}.muted{color:var(--muted)}.small{font-size:13px}
.tag{display:inline-block;font-size:11px;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:0 7px;margin-left:6px;font-weight:500;vertical-align:middle}
.barcell{min-width:150px;white-space:nowrap}
.bar{display:inline-block;width:96px;height:8px;border-radius:4px;background:var(--bar-track);vertical-align:middle;overflow:hidden;margin-right:8px}.bar .fill{display:block;height:100%;border-radius:4px}
.fill.b-good{background:var(--good)}.fill.b-warn{background:var(--warn)}.fill.b-bad{background:var(--bad)}.fill.b-none{background:transparent}.fill.b-neutral{background:var(--neutral-fill)}
.bar.share{width:140px}.num{font-variant-numeric:tabular-nums}
.chip{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:2px 9px;margin:2px 4px 2px 0;white-space:nowrap;border:1px solid transparent}
.c-good{background:var(--good-soft);color:var(--good)}.c-warn{background:var(--warn-soft);color:var(--warn)}.c-bad{background:var(--bad-soft);color:var(--bad)}.c-neutral{background:var(--accent-soft);color:var(--accent)}
.notes{margin:6px 0 0 18px;padding:0;color:var(--ink-2)}.notes li{margin:4px 0}
.two{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:640px){.two{grid-template-columns:1fr}}
.cur{padding:12px 0;border-top:1px solid var(--line)}.cur:first-of-type{border-top:none}
.cur-h{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}.cur-bar{margin-left:auto}
.cur-next{font-size:13.5px;color:var(--ink-2);margin:4px 0 6px}.chips{display:flex;flex-wrap:wrap}
.segs{display:grid;gap:8px;max-width:560px}.seg{display:flex;align-items:center;gap:10px}.seg-l{width:130px;font-size:13.5px;color:var(--ink-2)}
.agenda{border-color:var(--amber);background:linear-gradient(0deg,var(--amber-soft),var(--amber-soft)),var(--surface)}
.agenda .card-h h2{color:var(--amber)}
.agenda-list{margin:6px 0 0 20px;padding:0}.agenda-list li{margin:8px 0;color:var(--ink)}
.agenda .rules{margin-top:12px}.agenda .rules summary{cursor:pointer;color:var(--ink-2);font-size:13.5px}
.cta{margin:14px 0 0}.cta a{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;font-weight:700;padding:8px 14px;border-radius:8px}
.notesbox{background:transparent;border-style:dashed}
@media print{body{background:#fff}.card{break-inside:avoid;border-color:#ccc}.wrap{padding:0}.cta{display:none}}
</style></head><body><div class="wrap">
{{BODY}}
</div></body></html>
"""


# ============================================================================
# 6) rapor kaydı + KS4 paketi
# ============================================================================
def create_report(db: Session, coach: User, student: User, *, week_start: date | None = None,
                  week_end: date | None = None) -> CoachingReport:
    """Raporu üret ve CoachingReport olarak ekle (flush; commit çağıranda)."""
    if week_end is None or week_start is None:
        ws, we = default_window(db, student)
        week_start = week_start or ws
        week_end = week_end or we
    data = collect(db, student, week_start, week_end)
    agenda = build_agenda(data)
    prev = (db.query(func.max(CoachingReport.version))
            .filter(CoachingReport.student_id == student.id, CoachingReport.week_start == week_start,
                    CoachingReport.week_end == week_end).scalar()) or 0
    r = CoachingReport(
        student_id=student.id, coach_id=coach.id, week_start=week_start, week_end=week_end,
        version=prev + 1,
        data_json=json.dumps(data, ensure_ascii=False, default=_j),
        agenda_json=json.dumps(agenda, ensure_ascii=False),
    )
    db.add(r)
    db.flush()
    return r


def load_data(r: CoachingReport) -> dict:
    try:
        return json.loads(r.data_json or "{}")
    except (ValueError, TypeError):
        return {}


def load_agenda(r: CoachingReport) -> list[dict]:
    try:
        return [a for a in json.loads(r.agenda_json or "[]") if isinstance(a, dict)]
    except (ValueError, TypeError):
        return []


def load_ai_agenda(r: CoachingReport) -> list[dict] | None:
    """ai_agenda_json ya düz liste ya {"agenda": [...], ...} sözlüğü olabilir."""
    if not r.ai_agenda_json:
        return None
    try:
        v = json.loads(r.ai_agenda_json)
    except (ValueError, TypeError):
        return None
    if isinstance(v, dict):
        v = v.get("agenda") or []
    return [a for a in v if isinstance(a, dict)] or None


def insight_bundle(data: dict, agenda: list[dict]) -> dict:
    """KS4 AI'ya verilen yoğun paket: rakamlı özet + kural maddeleri + mesajlar."""
    m = derive(data)
    return {
        "window": data.get("window"),
        "totals": {"gorev_done": m["summ"].get("gorev_done"), "gorev_total": m["summ"].get("gorev_total"),
                   "gorev_pct": m["gorev_pct"], "worked_days": m["worked_days"], "days": len(m["days"]),
                   "test_completed": m["summ"].get("test_completed"), "test_planned": m["summ"].get("test_planned"),
                   "deneme_completed": m["summ"].get("deneme_completed"), "deneme_planned": m["summ"].get("deneme_planned"),
                   "correct": m["D"], "wrong": m["Y"], "blank": m["B"], "accuracy_pct": m["acc_all"]},
        "per_day": [{"date": k, "done": v.get("gorev_done"), "total": v.get("gorev_total"),
                     "tests": v.get("test_completed"), "planned_tests": v.get("test_planned")} for k, v in m["days"]],
        "subjects": [{"subject": k, "gorev": f"{v['gorev_done']}/{v['gorev_total']}", "tests": f"{v['test_completed']}/{v['test_planned']}",
                      "correct": v["D"], "wrong": v["Y"], "accuracy_pct": v["acc"]} for k, v in m["subj"].items()],
        "topics": [{"subject": r["subject"], "topic": r["topic"], "tests": r["completed"], "correct": r["correct"],
                    "wrong": r["wrong"], "accuracy_pct": r["acc"]} for r in m["topics_sorted"][:14]],
        "branch_exams": [{"date": x["date"], "subject": x["subject"], "questions": x["n"], "correct": x["D"], "wrong": x["Y"],
                          "net": round(x["net"], 2) if x["net"] is not None else None, "net_pct": x["net_pct"], "done": x["done"]}
                         for x in m["denemeler"]],
        "pending_tasks": [f"{t['date']} {t['title']}" for t in m["pending"][:6]],
        "no_dy_tasks": [f"{t['date']} {t['title']}" for t in m["no_dy"][:4]],
        "curriculum": [{"subject": s["name"], "coverage_pct": s.get("coverage_pct"), "started": s.get("started_topics"),
                        "total": s.get("total_topics"), "next": s.get("next_topic_name")} for s in m["cur_subj"]],
        "unstarted_books": [f"{b['book']} ({b.get('subject')})" for b in m["books"] if (b.get("completed") or 0) == 0][:6],
        "student_messages": [{"date": str(r.get("created_at") or "")[:16], "status": r.get("status"), "message": r.get("message")}
                             for r in m["reqs"][-12:]],
        "wrong_archive_total": m["wq_total"], "exam_count": m["exam_count"],
        "rhythm": ({k: (m["dna"] or {}).get(k) for k in ("morning_count", "afternoon_count", "evening_count", "night_count", "peak_day_name")}
                   if m["dna"] else None),
        "next_week_task_count": m["next_week_task_count"],
        "rule_agenda": [{"title": a.get("title"), "detail": a.get("detail"), "severity": a.get("severity")} for a in agenda],
    }
