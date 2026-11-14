"""Veli haftalık rapor e-postası — sürüm 2 (2026-11-12).

TEK KAYNAK: sayılar `parent_weekly_report.build_weekly_report` ile aynı (velinin
uygulamadaki "Haftalık Rapor" ekranı). Mail o hesabın üstüne şunları ekler:
  - deneme serileri (tam denemeler tür türü: TYT, AYT…) + hedef — `student_overview`
  - en çok net kazandıracak 3 konu — `exam_overview` (deneme konu analizi)
  - gelecek haftanın programı (ders dağılımı)
  - kurum ve koç kimliği, Rota (sesli yorum) bağlantısı

Hafta: Pazartesi–Pazar; her Pazartesi 19:00 TR gönderilir (cron `parent_weekly_report`).
Veliye GİTMEYENLER: koça özel uyarılar (toplu işaretleme, doğru/yanlış girilmiyor),
konu bazında doğru/yanlış dökümü, öğrenci–koç yazışmaları.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import Task, User

TR_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
             "Eylül", "Ekim", "Kasım", "Aralık"]
TR_MON_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def num(v: float | None) -> str:
    """Türkçe sayı: 98.5 → "98,5", 64.0 → "64"."""
    if v is None:
        return "—"
    r = round(float(v), 2)
    s = f"{r:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


def short(d: date) -> str:
    return f"{d.day} {TR_MON_SHORT[d.month - 1]}"


def range_label(ws: date, we: date) -> str:
    if ws.month == we.month:
        return f"{ws.day}–{we.day} {TR_MONTHS[we.month - 1]} {we.year}"
    return f"{ws.day} {TR_MONTHS[ws.month - 1]} – {we.day} {TR_MONTHS[we.month - 1]} {we.year}"


_VOW = "aıoueiöüAIOUEİÖÜ"


def genitive(name: str) -> str:
    """Kesme işaretli tamlayan eki: Emir → Emir'in, Ayşe → Ayşe'nin, Ali → Ali'nin, Umut → Umut'un."""
    w = (name or "").strip()
    if not w:
        return "Öğrencinin"
    last_v = next((c for c in reversed(w.lower()) if c in "aıoueiöü"), "e")
    v = {"a": "ı", "ı": "ı", "o": "u", "u": "u", "e": "i", "i": "i", "ö": "ü", "ü": "ü"}[last_v]
    return f"{w}'{'n' if w[-1] in _VOW else ''}{v}n"


def report_week(today: date | None = None) -> date:
    """Raporlanan haftanın Pazartesi'si: bugünden önceki son tamamlanmış Pzt–Paz."""
    today = today or date.today()
    return today - timedelta(days=today.weekday() + 7)


def _series(db: Session, student: User, ref: date) -> tuple[list[dict], list[dict]]:
    """Tam deneme serileri (veli diliyle) + raporlanan haftanın branş denemeleri."""
    from app.models.exam_result import ExamResult
    from app.services import exam_scope
    from app.services.student_overview import exam_overview

    ov = exam_overview(db, student, ref)
    targets = {t["series_key"]: t for t in (ov.get("targets") or [])}
    rows = (db.query(ExamResult).filter(ExamResult.student_id == student.id,
                                        ExamResult.exam_date <= ref)
            .order_by(ExamResult.exam_date.asc(), ExamResult.id.asc()).all())
    by_key: dict[str, list] = {}
    for r in rows:
        by_key.setdefault(exam_scope.series_key(r), []).append(r)
    series = []
    for e in ov.get("exams") or []:
        ser = by_key.get(e["series_key"]) or []
        last = ser[-1] if ser else None
        qn = (last.total_correct + last.total_wrong + last.total_blank) if last else None
        label = e["series_label"].replace(" (genel deneme)", "")
        item = {
            "label": label, "count": e["count"], "last_net": num(e["last_net"]),
            "last_title": last.title if last else None,
            "last_date": short(date.fromisoformat(e["last_date"])),
            "questions": qn, "diff": e["diff"], "diff_text": None, "avg3": num(e["avg_last3"]),
            "target": None,
        }
        if e["diff"] is not None:
            item["diff_text"] = (f"öncekine göre +{num(e['diff'])}" if e["diff"] > 0
                                 else f"öncekine göre −{num(abs(e['diff']))}" if e["diff"] < 0
                                 else "öncekiyle aynı")
        t = targets.get(e["series_key"])
        if t:
            gap = t["gap"]
            item["target"] = (f"Hedef {num(t['target_net'])} net"
                              + (f" → {num(gap)} net kaldı" if gap > 0 else " → hedef tuttu"))
        series.append(item)
    # raporlanan hafta içindeki branş / oturum denemeleri (tam denemeyle kıyaslanmaz)
    ws = ref - timedelta(days=6)
    grouped: dict[str, list[str]] = {}
    for r in rows:
        if ws <= r.exam_date <= ref and exam_scope.classify(r) != "genel":
            sc = exam_scope.exam_scope(r)
            label = sc.series_label.replace(" branş", "").replace(" · ", " ")
            grouped.setdefault(label, []).append(num(r.net))
    branch = [{"label": k, "nets": " · ".join(v), "count": len(v)} for k, v in grouped.items()]
    return series, branch


def _topics(db: Session, student: User) -> dict | None:
    """En çok net kazandıracak 3 konu (öğrencinin ana tam deneme serisinden)."""
    from app.services.exam_overview import build_exam_overview

    try:
        ov = build_exam_overview(db, student)
    except Exception:
        return None
    if not ov or not ov.get("is_general") or (ov.get("count") or 0) < 2:
        return None
    opp = ((ov.get("topics") or {}).get("opportunities") or [])[:3]
    if not opp:
        return None
    return {
        "series": (ov.get("series_label") or "").replace(" (genel deneme)", ""),
        "count": ov.get("count"),
        "loss_note": (ov.get("loss") or {}).get("note"),
        "items": [{"topic": o["topic_name"], "subject": o["subject_name"],
                   "gain": num(o["net_gain_per_exam"])} for o in opp],
        "subjects": [o["subject_name"] for o in opp],
    }


def _next_week(db: Session, student_id: int, mon: date) -> dict | None:
    from app.services.gorev_stats import primary_subject

    nm = mon + timedelta(days=7)
    tasks = (db.query(Task).filter(Task.student_id == student_id, Task.is_draft.is_(False),
                                   Task.date >= nm, Task.date <= nm + timedelta(days=6)).all())
    if not tasks:
        return None
    cnt: Counter = Counter()
    for t in tasks:
        try:
            s = primary_subject(t)
        except Exception:
            s = None
        name = getattr(s, "name", None)
        if name:
            for p in ("TYT ", "AYT ", "LGS "):
                if name.startswith(p):
                    name = name[len(p):]
            cnt[name] += 1
    return {"label": f"{short(nm)}–{short(nm + timedelta(days=6))}", "tasks": len(tasks),
            "top": [{"subject": s, "count": n} for s, n in cnt.most_common(3)]}


def build_mail_payload(db: Session, parent: User | None, student: User, *, today: date | None = None) -> dict[str, Any]:
    from app.routes.api_v2.parent import _parent_insight_gate
    from app.services import branding
    from app.services.parent_weekly_report import build_weekly_report

    today = today or date.today()
    mon = report_week(today)
    sun = mon + timedelta(days=6)
    if parent is not None:
        rep = build_weekly_report(db, parent, student.id, mon, today=today)
    else:  # koçun gönderdiği veli bağlantısı — erişim çağıranda denetlendi
        from app.services.parent_weekly_report import build_weekly_report_for_student
        rep = build_weekly_report_for_student(db, student, mon, today=today)

    coach = db.get(User, student.teacher_id) if student.teacher_id else None
    brand = branding.brand_for_user(db, student)
    exam_date = getattr(student, "effective_exam_date", None)
    days_left = (exam_date - sun).days if exam_date and exam_date > sun else None

    normal = rep.get("normal") or {}
    hist = [{"label": short(date.fromisoformat(w["start"]) + timedelta(days=6)), "pct": w["pct"]}
            for w in (normal.get("weeks") or [])]
    hist.append({"label": "Bu hafta", "pct": rep["completion_pct"]})

    series, branch = _series(db, student, sun)
    topics = _topics(db, student)
    nxt = _next_week(db, student.id, mon)
    if nxt and topics:
        overlap = [t["subject"] for t in nxt["top"]
                   if any(t["subject"] in s or s.endswith(t["subject"]) for s in topics["subjects"])]
        nxt["focus_note"] = (f"{overlap[0]} dersine ayrılan pay, en çok net kazandıracak konularla örtüşüyor."
                             if overlap else None)

    _coach, rota_on, _why = _parent_insight_gate(db, student)
    lagging = [s for s in rep["subjects"] if s["planned"] > 0 and s["pct"] < 70]
    lagging.sort(key=lambda s: s["pct"])
    done_all = [s for s in rep["subjects"] if s["planned"] > 0 and s["completed"] >= s["planned"]]

    first = (student.full_name or "").split()[0] if student.full_name else "Öğrenci"
    return {
        "__template": "parent_weekly_report",
        "version": 2,
        "student_id": student.id,
        "student_name": student.full_name,
        "student_first": first,
        "student_gen": genitive(first),
        "week_start": mon.isoformat(),
        "week_end": sun.isoformat(),
        "week_label": range_label(mon, sun),
        "coach_name": coach.full_name if coach else None,
        "institution_name": brand.name if brand else None,
        "days_to_exam": days_left,
        "verdict_level": rep["verdict_level"],
        "verdict_text": rep["verdict_text"],
        "gorev_done": rep["gorev_done"], "gorev_total": rep["gorev_total"],
        "completion_pct": rep["completion_pct"],
        "test_completed": rep["test_completed"], "test_planned": rep["test_planned"],
        "question_completed": rep["question_completed"],
        "active_days": rep["active_days"],
        "comparison": rep["comparison"],
        "normal": {k: normal.get(k) for k in ("pct_low", "pct_high", "tests_low", "tests_high")},
        "history": hist,
        "lagging": lagging[:3],
        "done_all": [s["subject_name"] for s in done_all],
        "series": series,
        "branch": branch,
        "topics": topics,
        "next_week": nxt,
        "teacher_notes": rep["teacher_notes"][:2],
        # veli bağlantılı rapor sayfası (2026-11-14) — tüm dersler + gün gün
        "subjects_all": rep["subjects"],
        "daily": rep["daily"],
        "rota": bool(rota_on),
        # geriye uyum (WhatsApp şablonu + eski alanlar)
        "completed": rep["test_completed"], "planned": rep["test_planned"],
        "rate_pct": rep["completion_pct"],
    }
