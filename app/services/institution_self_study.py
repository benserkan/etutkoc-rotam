# -*- coding: utf-8 -*-
"""Kurum yöneticisi — Bağımsız çalışma girişleri raporu (Faz 2 görünürlük).

Kurumun koçlarının elle/bağımsız ilerleme girişlerini şeffaflaştırır:
kim, ne kadar, öğrenci beyanıyla mı yoksa koç tek taraflı mı. Kurum uyum/
karne metrikleri GÖREV-bazlıdır ve bu girişlerden etkilenmez; bu rapor
müfredat kapsaması + veli görünümlerini etkileyen elle girişlerin denetim
yüzeyidir (engelleme yok — görünürlük).

Dikkat işareti (advisory): dönem içinde koç tek taraflı işlenen test hem
hacimce yüksek (>= ATTENTION_MIN_TESTS) hem de toplam girişin büyük kısmı
(>= ATTENTION_DIRECT_SHARE) ise satır işaretlenir — "öğrenci beyanı olmadan
yüklü giriş" sinyali. Tatil dönüşü meşru olabilir; yönetici koçla konuşur.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased, joinedload

from app.models import (
    SS_SOURCE_COACH,
    SS_SOURCE_STUDENT,
    SS_STATUS_APPROVED,
    SS_STATUS_PENDING,
    SelfStudyEntry,
    StudentBook,
    User,
    UserRole,
)

ATTENTION_MIN_TESTS = 200
ATTENTION_DIRECT_SHARE = 0.8
RECENT_LIMIT = 50
MISMATCH_STUDENT_CAP = 100   # deneme çaprazı taranan öğrenci üst sınırı
MISMATCH_ROW_LIMIT = 50


def build_report(db: Session, institution_id: int, *, days: int = 30) -> dict:
    days = max(7, min(120, int(days or 30)))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    coaches = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id == institution_id,
        )
        .all()
    )
    coach_by_id = {c.id: c for c in coaches}
    coach_ids = list(coach_by_id.keys())

    if not coach_ids:
        return _empty(days)

    StudentUser = aliased(User)
    entries = (
        db.query(SelfStudyEntry, StudentUser)
        .options(
            joinedload(SelfStudyEntry.section),
            joinedload(SelfStudyEntry.student_book).joinedload(StudentBook.book),
        )
        .join(StudentUser, StudentUser.id == SelfStudyEntry.student_id)
        .filter(
            StudentUser.teacher_id.in_(coach_ids),
            SelfStudyEntry.created_at >= cutoff,
        )
        .order_by(SelfStudyEntry.created_at.desc(), SelfStudyEntry.id.desc())
        .all()
    )

    per_coach: dict[int, dict] = {}
    recent: list[dict] = []
    tot_entries = 0
    tot_applied = 0
    tot_direct_tests = 0
    tot_declared_tests = 0
    tot_pending = 0

    for e, student in entries:
        coach = coach_by_id.get(student.teacher_id or 0)
        if coach is None:
            continue
        row = per_coach.setdefault(coach.id, {
            "coach_id": coach.id,
            "coach_name": coach.full_name,
            "entries": 0,
            "applied_tests": 0,
            "coach_direct_entries": 0,
            "coach_direct_tests": 0,
            "student_declared_entries": 0,
            "student_declared_tests": 0,
            "pending_count": 0,
            "rejected_count": 0,
            "_students": set(),
        })
        row["entries"] += 1
        row["_students"].add(e.student_id)
        tot_entries += 1
        if e.status == SS_STATUS_APPROVED:
            row["applied_tests"] += e.applied_count
            tot_applied += e.applied_count
            if e.source == SS_SOURCE_COACH:
                row["coach_direct_entries"] += 1
                row["coach_direct_tests"] += e.applied_count
                tot_direct_tests += e.applied_count
            else:
                row["student_declared_entries"] += 1
                row["student_declared_tests"] += e.applied_count
                tot_declared_tests += e.applied_count
        elif e.status == SS_STATUS_PENDING:
            row["pending_count"] += 1
            tot_pending += 1
        else:
            row["rejected_count"] += 1

        if len(recent) < RECENT_LIMIT:
            book = e.student_book.book if e.student_book else None
            recent.append({
                "id": e.id,
                "created_at": e.created_at.isoformat() if e.created_at else "",
                "coach_name": coach.full_name,
                "student_name": student.full_name,
                "book_name": book.name if book else "—",
                "section_label": e.section.label if e.section else "—",
                "test_count": e.test_count,
                "applied_count": e.applied_count,
                "source": e.source,
                "status": e.status,
                "note": e.note,
            })

    coach_rows = []
    for row in per_coach.values():
        students = row.pop("_students")
        row["student_count"] = len(students)
        applied = row["applied_tests"]
        share = (row["coach_direct_tests"] / applied) if applied > 0 else 0.0
        row["coach_direct_share_pct"] = round(share * 100)
        row["attention"] = bool(
            row["coach_direct_tests"] >= ATTENTION_MIN_TESTS
            and share >= ATTENTION_DIRECT_SHARE
        )
        coach_rows.append(row)
    coach_rows.sort(key=lambda r: (-r["applied_tests"], r["coach_name"].lower()))

    # --- Deneme çaprazı (Faz 3): elle-AĞIRLIKLI işlenmiş konu + denemede düşük
    # doğruluk. Yalnız dönemde girişi olan öğrenciler taranır (bounded).
    mismatches = _exam_mismatches(db, entries, coach_by_id)

    return {
        "days": days,
        "summary": {
            "entries_total": tot_entries,
            "applied_tests_total": tot_applied,
            "coach_direct_tests": tot_direct_tests,
            "student_declared_tests": tot_declared_tests,
            "pending_total": tot_pending,
            "coaches_with_entries": len(coach_rows),
            "attention_count": sum(1 for r in coach_rows if r["attention"]),
            "mismatch_count": len(mismatches),
        },
        "coaches": coach_rows,
        "recent": recent,
        "mismatches": mismatches,
    }


def _exam_mismatches(db: Session, entries, coach_by_id: dict) -> list[dict]:
    """Dönemde girişi olan öğrencilerde elle-ağırlıklı deneme tutarsızlıkları.

    Pedagojik (görev-kaynaklı) tutarsızlık koç panelinde; buraya yalnız
    manual_heavy satırlar girer — "elle işlendi ama denemeler doğrulamıyor"
    denetim sinyali. Best-effort: hata raporu bloklamaz.
    """
    try:
        from app.services.exam_consistency import curriculum_exam_mismatches

        students: dict[int, tuple] = {}
        for e, student in entries:
            if student.id not in students:
                students[student.id] = (student, coach_by_id.get(student.teacher_id or 0))
        rows: list[dict] = []
        for student, coach in list(students.values())[:MISMATCH_STUDENT_CAP]:
            for f in curriculum_exam_mismatches(db, student.id):
                if not f["manual_heavy"]:
                    continue
                rows.append({
                    "student_id": student.id,
                    "student_name": student.full_name,
                    "coach_name": coach.full_name if coach else "—",
                    "subject_name": f["subject_name"],
                    "topic_name": f["topic_name"],
                    "completed": f["completed"],
                    "manual": f["manual"],
                    "manual_share_pct": f["manual_share_pct"],
                    "answered": f["answered"],
                    "accuracy_pct": f["accuracy_pct"],
                })
                if len(rows) >= MISMATCH_ROW_LIMIT:
                    return rows
        return rows
    except Exception:  # noqa: BLE001
        return []


def _empty(days: int) -> dict:
    return {
        "days": days,
        "summary": {
            "entries_total": 0,
            "applied_tests_total": 0,
            "coach_direct_tests": 0,
            "student_declared_tests": 0,
            "pending_total": 0,
            "coaches_with_entries": 0,
            "attention_count": 0,
            "mismatch_count": 0,
        },
        "coaches": [],
        "recent": [],
        "mismatches": [],
    }
