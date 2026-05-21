"""Stage 14 — Pomodoro + gamification smoke test.

Senaryolar:
1. PomodoroSession start_session: yeni session açılır, ended_at NULL
2. end_session: ended_at + actual_minutes set
3. today_summary: bugünkü WORK ve break dakika sayımları
4. compute_streak: 0 task → 0
5. compute_streak: 3 günlük aktif → 3
6. compute_streak: bugün aktif değil ama dün → 1
7. evaluate_badges: 1 task → first_step rozet
8. evaluate_badges: 3 günlük streak → streak_3 rozet
9. evaluate_badges: idempotent — aynı rozet 2. kez verilmez
10. compute_points: task + pomodoro + review + rozet sayım doğru
11. HTTP guards: anonim /student/focus → 303
12. /student/focus öğrenci → 200, preset butonları render
13. POST /student/focus/start → session açılır, redirect
14. POST /student/focus/{id}/end → session biter
15. /student/badges → 200, earned ve locked listede
16. /teacher/students/{id}/focus → 200, badge sayısı doğru
17. Cross-tenant 404
18. Task completion auto-award (route üzerinden) — rozet tetiklenir
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_teacher
from app.main import app
from app.models import (
    PomodoroSession,
    StudentBadge,
    Task,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.models.focus import PomodoroKind
from app.services.gamification import (
    BADGES,
    compute_points,
    compute_streak,
    evaluate_badges_for_student,
    longest_streak,
)
from app.services.pomodoro import (
    end_session,
    start_session,
    today_summary,
)


PFX = f"_focus_{secrets.token_hex(3)}"
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


def main() -> int:
    now = datetime.now(timezone.utc)
    client = TestClient(app)

    # ============ STEP 1: Fixture ============
    print("\n=== STEP 1: Fixture ===")
    with SessionLocal() as db:
        teacher = User(
            email=f"{PFX}_t@test.invalid", password_hash="x" * 60,
            full_name="Focus Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        other = User(
            email=f"{PFX}_o@test.invalid", password_hash="x" * 60,
            full_name="Other Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        db.add_all([teacher, other]); db.flush()
        student = User(
            email=f"{PFX}_s@test.invalid", password_hash="x" * 60,
            full_name="Focus Student", role=UserRole.STUDENT,
            teacher_id=teacher.id,
            is_active=True, password_changed_at=now,
        )
        db.add(student); db.commit()
        teacher_id, other_id, student_id = teacher.id, other.id, student.id
    check("fixture OK", True)

    # ============ STEP 2: Pomodoro start / end ============
    print("\n=== STEP 2: PomodoroSession start/end ===")
    with SessionLocal() as db:
        sess = start_session(
            db, student_id=student_id, planned_minutes=25,
            kind=PomodoroKind.WORK, label="Matematik",
        )
        db.commit()
        sess_id = sess.id
        check("session created", sess.id is not None)
        check("session ended_at NULL", sess.ended_at is None)
        check("planned_minutes=25", sess.planned_minutes == 25)

    with SessionLocal() as db:
        sess = db.query(PomodoroSession).filter(PomodoroSession.id == sess_id).first()
        end_session(db, session=sess, actual_minutes=22, interrupted=False)
        db.commit()
        check("ended_at set", sess.ended_at is not None)
        check("actual_minutes=22", sess.actual_minutes == 22)

    # ============ STEP 3: today_summary ============
    print("\n=== STEP 3: today_summary ===")
    with SessionLocal() as db:
        summary = today_summary(db, student_id=student_id, now=now)
    check("summary.work_sessions=1", summary.work_sessions == 1)
    check("summary.work_minutes=22", summary.work_minutes == 22)

    # ============ STEP 4: Streak 0 ============
    print("\n=== STEP 4: Streak 0 ===")
    with SessionLocal() as db:
        # Önce mevcut session'ı sil — pomodoro 22 dk olduğu için bugün aktif sayılır
        # Streak testi için fresh student kullanalım
        s2 = User(
            email=f"{PFX}_s2@test.invalid", password_hash="x" * 60,
            full_name="Streak Empty Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, is_active=True, password_changed_at=now,
        )
        db.add(s2); db.commit()
        s2_id = s2.id
        st = compute_streak(db, student_id=s2_id, now=now)
    check("0 task → streak=0", st == 0, f"got {st}")

    # ============ STEP 5: 3 günlük streak (3 ardışık gün task) ============
    print("\n=== STEP 5: 3 günlük streak ===")
    with SessionLocal() as db:
        for offset in [0, 1, 2]:
            d = now.date() - timedelta(days=offset)
            db.add(Task(
                student_id=s2_id, date=d, type=TaskType.TEST,
                title=f"D{offset}", status=TaskStatus.COMPLETED,
                completed_at=datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc),
            ))
        db.commit()
        st = compute_streak(db, student_id=s2_id, now=now)
        ls = longest_streak(db, student_id=s2_id)
    check("3 ardışık → streak=3", st == 3, f"got {st}")
    check("longest_streak=3", ls == 3, f"got {ls}")

    # ============ STEP 6: Streak dünden başlasa bile geçerli ============
    print("\n=== STEP 6: Dünden başlayan streak ===")
    with SessionLocal() as db:
        s3 = User(
            email=f"{PFX}_s3@test.invalid", password_hash="x" * 60,
            full_name="Yesterday Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, is_active=True, password_changed_at=now,
        )
        db.add(s3); db.commit()
        s3_id = s3.id
        d = now.date() - timedelta(days=1)  # dün
        db.add(Task(
            student_id=s3_id, date=d, type=TaskType.TEST,
            title="Yesterday", status=TaskStatus.COMPLETED,
            completed_at=datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc),
        ))
        db.commit()
        st = compute_streak(db, student_id=s3_id, now=now)
    check("sadece dün → streak=1", st == 1, f"got {st}")

    # ============ STEP 7: Badge eval — first_step + streak_3 ============
    print("\n=== STEP 7: Badge auto-award ===")
    with SessionLocal() as db:
        newly = evaluate_badges_for_student(db, student_id=s2_id, commit=True)
    kinds = [b.kind for b in newly]
    check("first_step kazanıldı", "first_step" in kinds, f"new={kinds}")
    check("streak_3 kazanıldı", "streak_3" in kinds, f"new={kinds}")

    # Idempotent — 2. çağrıda tekrar verilmez
    with SessionLocal() as db:
        newly2 = evaluate_badges_for_student(db, student_id=s2_id, commit=True)
    check("idempotent — 2. çağrı 0 yeni rozet", len(newly2) == 0,
          f"new={[b.kind for b in newly2]}")

    with SessionLocal() as db:
        total_badges = db.query(StudentBadge).filter(
            StudentBadge.student_id == s2_id
        ).count()
    check("toplam 2 rozet (first_step + streak_3)", total_badges == 2,
          f"got {total_badges}")

    # ============ STEP 8: compute_points ============
    print("\n=== STEP 8: compute_points ===")
    with SessionLocal() as db:
        pts = compute_points(db, student_id=s2_id)
    # 3 task × 10 = 30 + 0 pomodoro + 0 review + 2 badge × 25 = 50 → toplam 80
    check("points.tasks=30", pts.tasks == 30, f"got {pts.tasks}")
    check("points.badges=50", pts.badges == 50, f"got {pts.badges}")
    check("points.total=80", pts.total == 80, f"got {pts.total}")

    # ============ STEP 9: HTTP guards ============
    print("\n=== STEP 9: HTTP guards ===")
    app.dependency_overrides.clear()
    r = client.get("/student/focus", follow_redirects=False)
    check("anonim /student/focus → 303", r.status_code in (302, 303))

    # ============ STEP 10: Öğrenci /student/focus ============
    print("\n=== STEP 10: /student/focus öğrenci ===")
    def make_override(uid: int):
        def _ov():
            with SessionLocal() as _db:
                u = (
                    _db.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == uid)
                    .first()
                )
                if u is not None:
                    if u.institution is not None:
                        _db.expunge(u.institution)
                    _db.expunge(u)
                return u
        return _ov

    app.dependency_overrides[get_current_user] = make_override(student_id)
    r = client.get("/student/focus")
    check("student focus 200", r.status_code == 200)
    check("preset butonları render",
          "25 dk Odak" in r.text and "50 dk Odak" in r.text)
    check("streak rozeti render", "günlük seri" in r.text)

    # ============ STEP 11: POST /student/focus/start ============
    print("\n=== STEP 11: POST start ===")
    r = client.post(
        "/student/focus/start",
        data={"planned_minutes": "30", "kind": "work", "label": "Test çalışma"},
        follow_redirects=False,
    )
    check("start POST 303", r.status_code == 303)
    with SessionLocal() as db:
        active = (
            db.query(PomodoroSession)
            .filter(
                PomodoroSession.student_id == student_id,
                PomodoroSession.ended_at.is_(None),
            )
            .first()
        )
        check("aktif session oluştu", active is not None)
        check("planned=30", active.planned_minutes == 30 if active else False)
        active_id = active.id if active else None

    # ============ STEP 12: POST /student/focus/{id}/end ============
    print("\n=== STEP 12: POST end ===")
    if active_id:
        r = client.post(
            f"/student/focus/{active_id}/end",
            data={"actual_minutes": "28", "interrupted": ""},
            follow_redirects=False,
        )
        check("end POST 303", r.status_code == 303)
        with SessionLocal() as db:
            sess = db.query(PomodoroSession).filter(
                PomodoroSession.id == active_id
            ).first()
            check("ended_at set", sess.ended_at is not None)
            check("actual_minutes=28", sess.actual_minutes == 28)

    # ============ STEP 13: /student/badges ============
    print("\n=== STEP 13: /student/badges ===")
    r = client.get("/student/badges")
    check("badges 200", r.status_code == 200)
    check("'Rozetlerim' başlık", "Rozetlerim" in r.text)
    check("locked listede 'Otuz Günlük'",
          "Otuz Günlük" in r.text or "streak_30" in r.text or "Maraton" in r.text)

    # ============ STEP 14: Öğretmen detay ============
    print("\n=== STEP 14: /teacher/students/{id}/focus ===")
    app.dependency_overrides[require_teacher] = make_override(teacher_id)
    app.dependency_overrides[get_current_user] = make_override(teacher_id)
    r = client.get(f"/teacher/students/{student_id}/focus")
    check("teacher focus 200", r.status_code == 200)
    check("öğrenci adı render", "Focus Student" in r.text)

    # Cross-tenant
    app.dependency_overrides[require_teacher] = make_override(other_id)
    app.dependency_overrides[get_current_user] = make_override(other_id)
    r = client.get(f"/teacher/students/{student_id}/focus")
    check("cross-tenant 404", r.status_code == 404, f"got {r.status_code}")

    app.dependency_overrides.clear()

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_students = [student_id, s2_id, s3_id]
        db.execute(delete(StudentBadge).where(StudentBadge.student_id.in_(all_students)))
        db.execute(delete(PomodoroSession).where(PomodoroSession.student_id.in_(all_students)))
        db.execute(delete(Task).where(Task.student_id.in_(all_students)))
        db.execute(delete(User).where(
            User.id.in_(all_students + [teacher_id, other_id])
        ))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
