"""Öğretmen Etkililik Karnesi — kurum yöneticisi için (KP2, 2026-05-20).

"Kim sonuç alıyor?" — burnout (kim yoruldu) tamamlayıcısı. Her öğretmen için
4 bileşeni birleşik bir etkililik skoruna (0-100) indirger:

  • Tamamlama (%40)  — öğrencileri programa ne kadar uyuyor (compliance)
  • Doğruluk  (%25)  — yapılan soruların kalitesi (correct ÷ correct+wrong)
  • Disiplin  (%20)  — öğrenci başına haftalık planlanan soru (program yoğunluğu)
  • Düşük risk (%15) — risk altındaki öğrenci oranının tersi

Veri yapısı `institution_compliance` ile aynı (Task + TaskBookItem, is_draft=False)
+ `risk_analysis.bulk_risk_assessment`. Migration YOK. Gizlilik: öğretmen ADI
görünür, öğrenci detayı yok.

Yönetici bu karneyle en iyi pratiği yapan öğretmeni örnek gösterir, düşük
skorlu koçu yönlendirir.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.services.institution_compliance import _student_totals_for_week, _week_bounds, _rate, _accuracy
from app.services.risk_analysis import bulk_risk_assessment, filter_at_risk

# Disiplin normalizasyonu: öğrenci başına haftalık ~50 soru = tam puan
DISCIPLINE_TARGET_PER_WEEK = 50


def _score_color(score: int) -> str:
    if score >= 75:
        return "emerald"
    if score >= 50:
        return "sky"
    if score >= 30:
        return "amber"
    return "rose"


def _score_label(score: int) -> str:
    if score >= 75:
        return "Örnek"
    if score >= 50:
        return "İyi"
    if score >= 30:
        return "Gelişmeli"
    return "Dikkat"


def compute_teacher_scorecard(db: Session, *, institution_id: int, weeks: int = 4) -> dict:
    """Öğretmen başına etkililik karnesi (son N hafta)."""
    from datetime import date

    today = date.today()
    ws = _week_bounds(today, weeks - 1)[0]
    we = _week_bounds(today, 0)[1]

    teachers = (
        db.query(User.id, User.full_name, User.email)
        .filter(User.role == UserRole.TEACHER, User.institution_id == institution_id)
        .all()
    )
    teacher_name = {int(t.id): (t.full_name or t.email) for t in teachers}

    students = (
        db.query(User)
        .filter(
            User.role == UserRole.STUDENT,
            User.institution_id == institution_id,
            User.is_active.is_(True),
        )
        .all()
    )
    student_ids = [int(s.id) for s in students]
    student_teacher = {int(s.id): s.teacher_id for s in students}

    totals = _student_totals_for_week(db, student_ids=student_ids, ws=ws, we=we)

    # Risk: high+critical öğrenci sayısı (öğretmen başına)
    risk_by_teacher: dict[int | None, int] = {}
    if students:
        assessments = bulk_risk_assessment(db, students=students)
        for a in filter_at_risk(assessments, min_level="high"):
            tid = a.student.teacher_id
            risk_by_teacher[tid] = risk_by_teacher.get(tid, 0) + 1

    # Öğretmen başına topla
    agg: dict[int | None, dict] = {}
    for sid in student_ids:
        tid = student_teacher[sid]
        b = agg.setdefault(tid, {"planned": 0, "completed": 0, "correct": 0,
                                 "wrong": 0, "student_count": 0})
        b["student_count"] += 1
        t = totals.get(sid)
        if t:
            b["planned"] += t["planned"]
            b["completed"] += t["completed"]
            b["correct"] += t["correct"]
            b["wrong"] += t["wrong"]

    rows = []
    for tid, b in agg.items():
        sc = b["student_count"] or 1
        rate = _rate(b["planned"], b["completed"])
        accuracy = _accuracy(b["correct"], b["wrong"])
        per_student_week = b["planned"] / sc / weeks
        discipline_pct = int(round(min(per_student_week / DISCIPLINE_TARGET_PER_WEEK, 1.0) * 100))
        risk_count = risk_by_teacher.get(tid, 0)
        risk_ratio = risk_count / sc

        # Birleşik skor — eksik bileşenler nötr (50) sayılır
        c_rate = rate if rate is not None else 0
        c_acc = accuracy if accuracy is not None else 50
        c_low_risk = int(round((1 - min(risk_ratio, 1.0)) * 100))
        score = int(round(
            0.40 * c_rate + 0.25 * c_acc + 0.20 * discipline_pct + 0.15 * c_low_risk
        ))

        rows.append({
            "teacher_id": tid,
            "teacher_name": teacher_name.get(tid, "Koçu atanmamış") if tid else "Koçu atanmamış",
            "student_count": b["student_count"],
            "completion_rate": rate,
            "accuracy": accuracy,
            "discipline_per_student_week": int(round(per_student_week)),
            "discipline_pct": discipline_pct,
            "risk_students": risk_count,
            "score": score,
            "score_color": _score_color(score),
            "score_label": _score_label(score),
        })

    rows.sort(key=lambda r: -r["score"])

    scored = [r["score"] for r in rows] or [0]
    summary = {
        "teacher_count": len(rows),
        "avg_score": int(round(sum(scored) / len(scored))) if rows else 0,
        "top_name": rows[0]["teacher_name"] if rows else None,
        "top_score": rows[0]["score"] if rows else None,
        "weeks": weeks,
    }
    return {"summary": summary, "teachers": rows}
