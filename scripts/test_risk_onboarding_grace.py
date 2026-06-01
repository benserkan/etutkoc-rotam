"""Risk göstergesi onboarding-grace smoke.

Yeni eklenen öğrenci (hesap < 3 gün), programı kurulu + %0 tamamlama olsa bile
'düşük haftalık tamamlama' ve 'N gün üst üste boş' UYARISI ALMAMALI (yanlış-pozitif;
kullanıcı 2026-06-01: dün eklenen öğrenci "14 gün üst üste boş" alıyordu). 3+ günlük
öğrencide gerçek sinyaller KORUNUR.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Task, TaskBookItem, TaskStatus, TaskType, User, UserRole
from app.services.risk_analysis import compute_risk_score

PFX = f"riskgrace_{_secrets.token_hex(3)}"
passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _mk_student(db, *, email: str, teacher_id: int, created_at: datetime) -> int:
    s = User(
        email=email, password_hash="x", full_name=f"{PFX} {email[:6]}",
        role=UserRole.STUDENT, teacher_id=teacher_id, grade_level=12,
        is_active=True, created_at=created_at, password_changed_at=created_at,
        must_change_password=False,
    )
    db.add(s)
    db.flush()
    t = Task(
        student_id=s.id, date=date.today(), type=TaskType.OTHER,
        title="Deneme", status=TaskStatus.PENDING, is_draft=False,
    )
    db.add(t)
    db.flush()
    # id-reuse orphan temizliği — yeni task id'sine yapışmış eski kalemleri at
    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id == t.id))
    db.add(TaskBookItem(
        task_id=t.id, book_id=None, book_section_id=None,
        label="Deneme", planned_count=15, completed_count=0,
    ))
    return s.id


def main() -> int:
    print(f"\n=== risk onboarding-grace smoke — prefix: {PFX} ===\n")
    now = datetime.now(timezone.utc)
    ids: list[int] = []
    with SessionLocal() as db:
        teacher = User(
            email=f"{PFX}_t@test.invalid", password_hash="x",
            full_name=f"{PFX} Teacher", role=UserRole.TEACHER, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add(teacher)
        db.flush()
        new_id = _mk_student(db, email=f"{PFX}_new@t.invalid", teacher_id=teacher.id, created_at=now)
        old_id = _mk_student(db, email=f"{PFX}_old@t.invalid", teacher_id=teacher.id, created_at=now - timedelta(days=6))
        db.commit()
        ids = [teacher.id, new_id, old_id]

    try:
        with SessionLocal() as db:
            new = db.get(User, new_id)
            ra = compute_risk_score(db, student=new)
            codes = {i.code for i in ra.indicators}
            check("1. YENİ öğrenci (hesap 0g): low_completion YOK", "low_completion" not in codes, str(codes))
            check("2. YENİ öğrenci: consecutive_empty YOK", "consecutive_empty" not in codes, str(codes))
            check("3. YENİ öğrenci: score düşük (uyarısız)", ra.score == 0, f"score={ra.score} codes={codes}")

            old = db.get(User, old_id)
            ra2 = compute_risk_score(db, student=old)
            codes2 = {i.code for i in ra2.indicators}
            check("4. ESKİ öğrenci (6g): low_completion VAR", "low_completion" in codes2, str(codes2))
            check("5. ESKİ öğrenci: consecutive_empty VAR", "consecutive_empty" in codes2, str(codes2))
            ce = next((i for i in ra2.indicators if i.code == "consecutive_empty"), None)
            check("6. ESKİ: boş gün hesap yaşıyla sınırlı (≤6, 14 değil)",
                  ce is not None and "6 gün" in ce.title, ce.title if ce else "yok")
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(TaskBookItem).where(
                TaskBookItem.task_id.in_(
                    [t.id for t in db.query(Task.id).filter(Task.student_id.in_([new_id, old_id])).all()]
                )
            ))
            db.execute(sa_delete(Task).where(Task.student_id.in_([new_id, old_id])))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
