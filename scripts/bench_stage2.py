"""Stage 2 performans testi — 50 öğretmen × 500 öğrenci ile timing.

Hedefler:
- cohort_by_grade < 1.5s
- teacher_activity_heatmap (4 hafta) < 2.0s
- HTTP /institution/cohorts < 2.0s
- HTTP /institution/activity-heatmap < 3.0s

Test sonrası tüm bench verisi silinir.
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditAction,
    AuditLog,
    Institution,
    User,
    UserRole,
)
from app.services.cohort_analysis import (
    cohort_by_curriculum,
    cohort_by_exam_target,
    cohort_by_grade,
    cohort_by_track,
)
from app.services.teacher_activity import teacher_activity_heatmap
from app.services.security import hash_password


PFX = f"_bench_{secrets.token_hex(3)}"
PWD = "BenchTest!2345"
N_TEACHERS = 50
N_STUDENTS = 500


def main() -> int:
    print(f"\n=== SEED: {N_TEACHERS} öğretmen, {N_STUDENTS} öğrenci ===")
    t0 = time.perf_counter()
    teacher_ids: list[int] = []
    student_ids: list[int] = []
    audit_ids: list[int] = []
    inst_id: int | None = None
    admin_email: str | None = None

    with SessionLocal() as db:
        pwd_hash = hash_password(PWD)
        now = datetime.now(timezone.utc)

        inst = Institution(
            name=f"{PFX}_BENCH", slug=f"{PFX}-bench",
            contact_email=f"{PFX}@test.invalid", plan="free", is_active=True,
        )
        db.add(inst)
        db.flush()
        inst_id = inst.id

        admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash=pwd_hash,
            full_name="Bench Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add(admin)
        db.flush()
        admin_email = admin.email
        admin_id = admin.id

        # Öğretmenler
        for i in range(N_TEACHERS):
            t = User(
                email=f"{PFX}_t{i}@test.invalid", password_hash=pwd_hash,
                full_name=f"Bench Teacher {i:03d}", role=UserRole.TEACHER,
                institution_id=inst_id, is_active=True,
                password_changed_at=now, must_change_password=False,
                last_login_at=now - timedelta(days=i % 14),
            )
            db.add(t)
        db.flush()
        teacher_ids = [
            t.id for t in db.query(User).filter(
                User.institution_id == inst_id, User.role == UserRole.TEACHER
            ).all()
        ]

        # Öğrenciler — sınıflar 5-12 + bazı mezun, track çeşitliliği
        from app.models.user import Track, GraduateMode
        tracks = [Track.SAYISAL, Track.EA, Track.SOZEL, Track.DIL]
        for i in range(N_STUDENTS):
            grade = 5 + (i % 8)        # 5..12 dönüşümlü
            is_grad = (i % 50 == 0)    # her 50'de 1 mezun
            track = tracks[i % 4] if (grade >= 11 or is_grad) else None
            gmode = GraduateMode.DERSHANE if is_grad else None
            s = User(
                email=f"{PFX}_s{i}@test.invalid", password_hash=pwd_hash,
                full_name=f"Bench Student {i:03d}", role=UserRole.STUDENT,
                institution_id=inst_id,
                teacher_id=teacher_ids[i % N_TEACHERS],
                is_active=True, password_changed_at=now,
                must_change_password=False,
                grade_level=None if is_grad else grade,
                track=track, is_graduate=is_grad, graduate_mode=gmode,
                last_login_at=now - timedelta(days=i % 7),
            )
            db.add(s)
        db.flush()
        student_ids = [
            s.id for s in db.query(User).filter(
                User.institution_id == inst_id, User.role == UserRole.STUDENT
            ).all()
        ]

        # Audit logs — son 28 gün, her öğretmen rastgele günlerde login
        # Her öğretmene avg 10 login dağıt
        audit_batch = []
        for ti, tid in enumerate(teacher_ids):
            n_logins = 5 + (ti % 10)  # 5..14
            for k in range(n_logins):
                day_offset = k * (28 // max(1, n_logins))
                created_at = now - timedelta(days=day_offset, hours=ti % 24)
                audit_batch.append(AuditLog(
                    actor_id=tid, action=AuditAction.LOGIN_SUCCESS,
                    created_at=created_at,
                ))
        db.add_all(audit_batch)
        db.flush()
        audit_ids = [a.id for a in audit_batch]

        db.commit()
    seed_time = time.perf_counter() - t0
    print(f"  seed: {seed_time:.2f}s")

    print(f"\n=== Service-level timing ===")
    bench_results = []

    def bench(label: str, target_s: float, fn) -> None:
        t = time.perf_counter()
        result = fn()
        dt = time.perf_counter() - t
        ok = dt < target_s
        marker = "[PASS]" if ok else "[SLOW]"
        n = len(result) if result is not None else 0
        bench_results.append((label, dt, target_s, ok))
        print(f"  {marker} {label}: {dt*1000:.0f}ms (target < {target_s*1000:.0f}ms) — {n} kohort/teacher")

    with SessionLocal() as db:
        bench("cohort_by_grade", 1.5,
              lambda: cohort_by_grade(db, institution_id=inst_id))
        bench("cohort_by_track", 1.5,
              lambda: cohort_by_track(db, institution_id=inst_id))
        bench("cohort_by_curriculum", 1.5,
              lambda: cohort_by_curriculum(db, institution_id=inst_id))
        bench("cohort_by_exam_target", 1.5,
              lambda: cohort_by_exam_target(db, institution_id=inst_id))
        bench("teacher_activity_heatmap (4h)", 2.0,
              lambda: teacher_activity_heatmap(db, institution_id=inst_id, weeks=4))
        bench("teacher_activity_heatmap (12h)", 3.0,
              lambda: teacher_activity_heatmap(db, institution_id=inst_id, weeks=12))

    print(f"\n=== HTTP-level timing ===")
    # Reset admin password
    with SessionLocal() as db:
        admin = db.get(User, admin_id)
        admin.password_hash = hash_password(PWD)
        admin.locked_until = None
        admin.failed_login_count = 0
        admin.must_change_password = False
        admin.password_changed_at = datetime.now(timezone.utc)
        db.commit()

    c = TestClient(app)
    r = c.post("/login", data={"email": admin_email, "password": PWD},
               follow_redirects=False)
    if r.status_code != 303:
        print(f"  [WARN] login fail status={r.status_code}, HTTP bench atlandı")
    else:
        for tab in ("grade", "track", "curriculum", "exam_target"):
            t = time.perf_counter()
            r = c.get(f"/institution/cohorts?tab={tab}")
            dt = time.perf_counter() - t
            ok = dt < 2.0 and r.status_code == 200
            marker = "[PASS]" if ok else "[SLOW/FAIL]"
            bench_results.append((f"HTTP cohorts {tab}", dt, 2.0, ok))
            print(f"  {marker} HTTP /institution/cohorts?tab={tab}: {dt*1000:.0f}ms (status={r.status_code})")

        for w in (4, 12):
            t = time.perf_counter()
            r = c.get(f"/institution/activity-heatmap?weeks={w}")
            dt = time.perf_counter() - t
            target = 3.0 if w == 4 else 5.0
            ok = dt < target and r.status_code == 200
            marker = "[PASS]" if ok else "[SLOW/FAIL]"
            bench_results.append((f"HTTP heatmap w={w}", dt, target, ok))
            print(f"  {marker} HTTP /institution/activity-heatmap?weeks={w}: {dt*1000:.0f}ms")

    # CLEANUP
    print(f"\n=== CLEANUP ===")
    t = time.perf_counter()
    with SessionLocal() as db:
        all_user_ids = teacher_ids + student_ids + [admin_id]
        if audit_ids:
            db.query(AuditLog).filter(
                AuditLog.id.in_(audit_ids)
            ).delete(synchronize_session=False)
        if all_user_ids:
            db.query(AuditLog).filter(
                AuditLog.actor_id.in_(all_user_ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(all_user_ids)).delete(
                synchronize_session=False
            )
        db.query(Institution).filter(Institution.id == inst_id).delete()
        db.commit()
    print(f"  cleanup: {(time.perf_counter() - t):.2f}s")

    # ÖZET
    print(f"\n=== ÖZET ===")
    failed = [r for r in bench_results if not r[3]]
    print(f"  Toplam test: {len(bench_results)}, hedefi tutturan: {len(bench_results) - len(failed)}")
    for label, dt, target, ok in bench_results:
        marker = "[PASS]" if ok else "[SLOW]"
        print(f"  {marker} {label}: {dt*1000:.0f}ms (target {target*1000:.0f}ms)")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
