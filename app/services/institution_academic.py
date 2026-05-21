"""Kurum Akademik Çıktı Panosu servisi — kurum yöneticisi için (KP4b, 2026-05-20).

KP4a'da öğretmenlerin girdiği deneme sonuçlarını (ExamResult) kurum düzeyinde
agregeler: "öğrencilerimiz denemelerde ne kadar net çıkarıyor, gidişat nasıl,
hangi koçun öğrencileri daha iyi, kim yükseliyor kim düşüyor?"

Net karşılaştırılabilirliği: ham net sınava göre değişir (LGS ~90 soru, TYT 120).
Bu yüzden kurum geneli/trend/koç karşılaştırması için **net başarı oranı**
(net ÷ soru sayısı, %) kullanılır — tüm sınav türlerinde karşılaştırılabilir.
Sınav türü kırılımında ham ortalama net de gösterilir (kendi içinde anlamlı).

Gizlilik: kurum yöneticisi öğretmen/öğrenci ADINI + oranını görür, öğrenci
detay sayfası YOK (at-risk/burnout/compliance gizlilik deseni).
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import EXAM_SECTION_LABELS, ExamResult, ExamSection, User, UserRole


def _pct_color(p: float | int | None) -> str:
    if p is None:
        return "slate"
    if p >= 70:
        return "emerald"
    if p >= 40:
        return "amber"
    return "rose"


def _net_pct(net: float, total_q: int) -> float | None:
    """Net başarı oranı: net ÷ soru sayısı (0-100). Karşılaştırılabilir metrik."""
    if total_q <= 0:
        return None
    return 100.0 * net / total_q


def _week_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def compute_academic(db: Session, *, institution_id: int, weeks: int = 8) -> dict:
    today = date.today()

    # Aktif öğrenciler + koç eşlemesi
    students = (
        db.query(User.id, User.full_name, User.email, User.teacher_id)
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
        )
        .all()
    )
    student_ids = [int(s.id) for s in students]
    student_meta = {
        int(s.id): {"name": s.full_name or s.email, "teacher_id": s.teacher_id}
        for s in students
    }

    teachers = (
        db.query(User.id, User.full_name, User.email)
        .filter(User.role == UserRole.TEACHER, User.institution_id == institution_id)
        .all()
    )
    teacher_name = {int(t.id): (t.full_name or t.email) for t in teachers}

    def tname(tid: int | None) -> str:
        if not tid:
            return "Koçu atanmamış"
        return teacher_name.get(int(tid), "Koçu atanmamış")

    # Tüm denemeler (kronolojik — gelişim/gerileme hesabı için)
    exams = []
    if student_ids:
        exams = (
            db.query(ExamResult)
            .filter(ExamResult.student_id.in_(student_ids))
            .order_by(ExamResult.exam_date.asc(), ExamResult.id.asc())
            .all()
        )

    total_exams = len(exams)
    students_with_exam = {int(e.student_id) for e in exams}
    all_net_pcts = [
        p for e in exams
        if (p := _net_pct(e.net, e.total_correct + e.total_wrong + e.total_blank)) is not None
    ]
    avg_net_pct = round(sum(all_net_pcts) / len(all_net_pcts)) if all_net_pcts else None

    cutoff_30 = today - timedelta(days=30)
    recent_exams = sum(1 for e in exams if e.exam_date >= cutoff_30)

    coverage_pct = (
        round(100 * len(students_with_exam) / len(student_ids)) if student_ids else None
    )

    # ---- Sınav türü (section) kırılımı ----
    by_section: dict[ExamSection, dict] = {}
    for e in exams:
        b = by_section.setdefault(e.section, {"nets": [], "pcts": [], "students": set()})
        b["nets"].append(e.net)
        p = _net_pct(e.net, e.total_correct + e.total_wrong + e.total_blank)
        if p is not None:
            b["pcts"].append(p)
        b["students"].add(int(e.student_id))
    section_rows = []
    for sec, b in by_section.items():
        avg_p = round(sum(b["pcts"]) / len(b["pcts"])) if b["pcts"] else None
        section_rows.append({
            "section": sec.value,
            "section_label": EXAM_SECTION_LABELS[sec],
            "exam_count": len(b["nets"]),
            "student_count": len(b["students"]),
            "avg_net": round(sum(b["nets"]) / len(b["nets"]), 2) if b["nets"] else 0.0,
            "avg_net_pct": avg_p,
            "net_pct_color": _pct_color(avg_p),
        })
    section_rows.sort(key=lambda r: -r["exam_count"])

    # ---- Haftalık trend (son N hafta, net başarı oranı) ----
    week_buckets: dict[date, list[float]] = {}
    for e in exams:
        p = _net_pct(e.net, e.total_correct + e.total_wrong + e.total_blank)
        if p is None:
            continue
        week_buckets.setdefault(_week_monday(e.exam_date), []).append(p)
    trend = []
    for wb in range(weeks - 1, -1, -1):
        ws = _week_monday(today) - timedelta(weeks=wb)
        pts = week_buckets.get(ws, [])
        trend.append({
            "week_start": ws.isoformat(),
            "avg_net_pct": round(sum(pts) / len(pts)) if pts else None,
            "exam_count": len(pts),
        })
    # Trend bazlı gelişim deltası (dolu ilk vs son hafta)
    filled = [t for t in trend if t["avg_net_pct"] is not None]
    delta = (filled[-1]["avg_net_pct"] - filled[0]["avg_net_pct"]) if len(filled) >= 2 else None

    # ---- Öğretmen kırılımı ----
    by_teacher: dict[int | None, dict] = {}
    for e in exams:
        tid = student_meta.get(int(e.student_id), {}).get("teacher_id")
        b = by_teacher.setdefault(tid, {"pcts": [], "students": set(), "exam_count": 0,
                                        "last_date": None})
        p = _net_pct(e.net, e.total_correct + e.total_wrong + e.total_blank)
        if p is not None:
            b["pcts"].append(p)
        b["students"].add(int(e.student_id))
        b["exam_count"] += 1
        if b["last_date"] is None or e.exam_date > b["last_date"]:
            b["last_date"] = e.exam_date
    teacher_rows = []
    for tid, b in by_teacher.items():
        avg_p = round(sum(b["pcts"]) / len(b["pcts"])) if b["pcts"] else None
        teacher_rows.append({
            "teacher_id": tid,
            "teacher_name": tname(tid),
            "student_count": len(b["students"]),
            "exam_count": b["exam_count"],
            "avg_net_pct": avg_p,
            "net_pct_color": _pct_color(avg_p),
            "last_exam_date": b["last_date"].isoformat() if b["last_date"] else None,
        })
    teacher_rows.sort(key=lambda r: (r["avg_net_pct"] is None, -(r["avg_net_pct"] or 0)))

    # ---- Öğrenci hareketi: en çok gelişen / gerileyen (≥2 deneme) ----
    per_student: dict[int, list[float]] = {}
    for e in exams:
        p = _net_pct(e.net, e.total_correct + e.total_wrong + e.total_blank)
        if p is None:
            continue
        per_student.setdefault(int(e.student_id), []).append(p)
    movers = []
    for sid, pcts in per_student.items():
        if len(pcts) < 2:
            continue
        meta = student_meta.get(sid, {})
        first_p, last_p = pcts[0], pcts[-1]
        movers.append({
            "student_name": meta.get("name", "—"),
            "teacher_name": tname(meta.get("teacher_id")),
            "first_net_pct": round(first_p),
            "last_net_pct": round(last_p),
            "delta": round(last_p - first_p),
            "exam_count": len(pcts),
        })
    improving = sorted([m for m in movers if m["delta"] > 0], key=lambda m: -m["delta"])[:10]
    declining = sorted([m for m in movers if m["delta"] < 0], key=lambda m: m["delta"])[:10]

    # ---- Deneme girmeyen öğrenciler (kapsama eksiği, koç kırılımlı) ----
    no_exam_by_teacher: dict[int | None, dict] = {}
    no_exam_total = 0
    for sid in student_ids:
        if sid in students_with_exam:
            continue
        no_exam_total += 1
        tid = student_meta[sid]["teacher_id"]
        e = no_exam_by_teacher.setdefault(tid, {"count": 0, "students": []})
        e["count"] += 1
        if len(e["students"]) < 10:
            e["students"].append(student_meta[sid]["name"])
    no_exam_rows = [
        {
            "teacher_id": tid,
            "teacher_name": tname(tid),
            "count": e["count"],
            "sample_students": e["students"],
        }
        for tid, e in no_exam_by_teacher.items()
    ]
    no_exam_rows.sort(key=lambda r: -r["count"])

    return {
        "summary": {
            "total_students": len(student_ids),
            "students_with_exam": len(students_with_exam),
            "coverage_pct": coverage_pct,
            "no_exam_count": no_exam_total,
            "total_exams": total_exams,
            "recent_exams": recent_exams,
            "avg_net_pct": avg_net_pct,
            "net_pct_color": _pct_color(avg_net_pct),
            "delta": delta,
            "weeks": weeks,
        },
        "sections": section_rows,
        "trend": trend,
        "teachers": teacher_rows,
        "improving": improving,
        "declining": declining,
        "no_exam_program": no_exam_rows,
    }
