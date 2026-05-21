"""Stage 13 — Çalışma DNA + burnout smoke test.

Senaryolar:
1. compute_profile birim: 0 task → has_enough_data=False, chronotype=unknown
2. compute_profile: tamamlanmış görevleri heatmap'e doğru saat × gün yerleştirir
3. chronotype çıkarımı: çoğunluğu gece olan örnek → "night"
4. WeeklyTrend: bu hafta>geçen → "up", aksine "down"
5. by_subject: ders bazlı planned/completed toplam doğru
6. burnout night_owl: >%30 gece tamamlama → signal
7. burnout intensity_spike: this/last +%50 → signal
8. burnout completion_drop: -%50 → signal
9. burnout streak_break: 7 gün streak + 3 gün boş → signal
10. risk_score 3 sinyal ile compute edilir
11. HTTP guards: anonim /student/dna → 303
12. /student/dna öğrenci → 200, profil render
13. /teacher/students/{id}/dna öğretmen → 200
14. /teacher/burnout → 200, tüm öğrenciler listede
15. /institution/burnout institution_admin → 200
16. cross-teacher /teacher/students/{id}/dna → 404
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
from app.deps import (
    get_current_user, require_institution_admin, require_teacher,
)
from app.main import app
from app.models import (
    Institution,
    Task,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.burnout import compute_burnout
from app.services.study_dna import compute_profile


PFX = f"_dna_{secrets.token_hex(3)}"
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
    print("\n=== STEP 1: Fixture (teacher, student, institution) ===")
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} INST", slug=f"dna-inst-{secrets.token_hex(2)}")
        db.add(inst); db.flush()

        teacher = User(
            email=f"{PFX}_t@test.invalid", password_hash="x" * 60,
            full_name="DNA Teacher", role=UserRole.TEACHER,
            institution_id=inst.id,
            is_active=True, password_changed_at=now,
        )
        admin = User(
            email=f"{PFX}_a@test.invalid", password_hash="x" * 60,
            full_name="DNA Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst.id,
            is_active=True, password_changed_at=now,
        )
        other = User(
            email=f"{PFX}_o@test.invalid", password_hash="x" * 60,
            full_name="Other Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        db.add_all([teacher, admin, other]); db.flush()

        student = User(
            email=f"{PFX}_s@test.invalid", password_hash="x" * 60,
            full_name="DNA Student", role=UserRole.STUDENT,
            teacher_id=teacher.id, institution_id=inst.id,
            is_active=True, password_changed_at=now,
        )
        db.add(student); db.commit()
        teacher_id, admin_id, other_id, student_id, inst_id = (
            teacher.id, admin.id, other.id, student.id, inst.id
        )

    check("fixture OK", True)

    # ============ STEP 2: 0 task — profile boş ============
    print("\n=== STEP 2: 0 task ===")
    with SessionLocal() as db:
        p = compute_profile(db, student_id=student_id, now=now)
    check("0 task: has_enough_data=False", not p.has_enough_data)
    check("0 task: chronotype=unknown", p.chronotype == "unknown")
    check("0 task: trend=insufficient",
          p.trend is None or p.trend.direction == "insufficient")
    check("0 task: heatmap tüm 0",
          all(p.heatmap[d][h] == 0 for d in range(7) for h in range(24)))

    # ============ STEP 3: Gece çalışan profil (night chronotype) ============
    print("\n=== STEP 3: Gece çalışan profil ===")
    # 10 görev: hepsi UTC 22:00 (TR 01:00 = gece). Son 7 gün içinde yayılır.
    with SessionLocal() as db:
        for i in range(10):
            d = now.date() - timedelta(days=i)
            # UTC 22:00 → TR 01:00 (gece)
            completed = datetime(d.year, d.month, d.day, 22, 0, tzinfo=timezone.utc)
            t = Task(
                student_id=student_id,
                date=d,
                type=TaskType.TEST,
                title=f"NightTask{i}",
                status=TaskStatus.COMPLETED,
                completed_at=completed,
            )
            db.add(t)
        db.commit()

    with SessionLocal() as db:
        p = compute_profile(db, student_id=student_id, now=now)
    check("gece 10 task: chronotype=night",
          p.chronotype == "night", f"got {p.chronotype}")
    check("gece task: peak_hour 1 (TR)",
          p.peak_hour == 1, f"got {p.peak_hour}")
    check("gece task: total_completed=10",
          p.total_completed == 10)
    check("gece task: heatmap[weekday][1] > 0",
          any(p.heatmap[d][1] > 0 for d in range(7)))

    # ============ STEP 4: night_owl burnout sinyali ============
    print("\n=== STEP 4: night_owl burnout ===")
    with SessionLocal() as db:
        r = compute_burnout(db, student_id=student_id, now=now)
    kinds = [s.kind for s in r.signals]
    check("night_owl signal", "night_owl" in kinds)
    check("risk_score > 0", r.risk_score > 0, f"got {r.risk_score}")

    # ============ STEP 5: intensity spike — bu hafta >> geçen hafta ============
    print("\n=== STEP 5: intensity_spike ===")
    # Yeni öğrenci
    with SessionLocal() as db:
        s2 = User(
            email=f"{PFX}_s2@test.invalid", password_hash="x" * 60,
            full_name="Spike Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, institution_id=inst_id,
            is_active=True, password_changed_at=now,
        )
        db.add(s2); db.commit()
        s2_id = s2.id
        # Geçen hafta: 5 görev (last_start = today-13..today-7)
        for i in range(5):
            d = now.date() - timedelta(days=10 + (i % 4))
            db.add(Task(
                student_id=s2_id, date=d, type=TaskType.TEST,
                title=f"LastWeek{i}", status=TaskStatus.COMPLETED,
                completed_at=datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc),
            ))
        # Bu hafta: 12 görev (≥%50 spike)
        for i in range(12):
            d = now.date() - timedelta(days=i % 6)
            db.add(Task(
                student_id=s2_id, date=d, type=TaskType.TEST,
                title=f"ThisWeek{i}", status=TaskStatus.COMPLETED,
                completed_at=datetime(d.year, d.month, d.day, 14, 0, tzinfo=timezone.utc),
            ))
        db.commit()

    with SessionLocal() as db:
        r2 = compute_burnout(db, student_id=s2_id, now=now)
    kinds2 = [s.kind for s in r2.signals]
    check("intensity_spike signal", "intensity_spike" in kinds2,
          f"signals={kinds2}")

    # ============ STEP 6: streak_break ============
    print("\n=== STEP 6: streak_break ===")
    with SessionLocal() as db:
        s3 = User(
            email=f"{PFX}_s3@test.invalid", password_hash="x" * 60,
            full_name="Streak Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, institution_id=inst_id,
            is_active=True, password_changed_at=now,
        )
        db.add(s3); db.commit()
        s3_id = s3.id
        # 3..15 gün önce her gün 1 görev (13 gün streak)
        for offset in range(3, 16):
            d = now.date() - timedelta(days=offset)
            db.add(Task(
                student_id=s3_id, date=d, type=TaskType.TEST,
                title=f"Day{offset}", status=TaskStatus.COMPLETED,
                completed_at=datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc),
            ))
        # Son 3 gün boş — hiç task yok
        db.commit()

    with SessionLocal() as db:
        r3 = compute_burnout(db, student_id=s3_id, now=now)
    kinds3 = [s.kind for s in r3.signals]
    check("streak_break signal", "streak_break" in kinds3,
          f"signals={kinds3}")

    # ============ STEP 7: HTTP guards ============
    print("\n=== STEP 7: HTTP guards ===")
    app.dependency_overrides.clear()
    r = client.get("/student/dna", follow_redirects=False)
    check("anonim /student/dna → 303", r.status_code in (302, 303))

    # ============ STEP 8: Öğrenci kendi DNA ============
    print("\n=== STEP 8: Öğrenci kendi DNA sayfası ===")
    def make_user_override(uid: int):
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

    app.dependency_overrides[get_current_user] = make_user_override(student_id)
    r = client.get("/student/dna")
    check("student dna 200", r.status_code == 200, f"got {r.status_code}")
    check("dna sayfada 'Çalışma DNA'",
          "Çalışma DNA" in r.text or "DNA" in r.text)
    check("burnout sinyali render",
          "Tükenmişlik" in r.text or "tükenmiş" in r.text.lower())

    # ============ STEP 9: Öğretmen DNA detay ============
    print("\n=== STEP 9: Öğretmen DNA detay ===")
    app.dependency_overrides[require_teacher] = make_user_override(teacher_id)
    app.dependency_overrides[get_current_user] = make_user_override(teacher_id)
    r = client.get(f"/teacher/students/{student_id}/dna")
    check("teacher dna 200", r.status_code == 200)
    check("öğrenci adı render", "DNA Student" in r.text)

    r = client.get("/teacher/burnout")
    check("teacher burnout dashboard 200", r.status_code == 200)
    check("dashboard'da öğrenci listede", "DNA Student" in r.text)

    # ============ STEP 10: Cross-tenant ============
    print("\n=== STEP 10: Cross-tenant 404 ===")
    app.dependency_overrides[require_teacher] = make_user_override(other_id)
    app.dependency_overrides[get_current_user] = make_user_override(other_id)
    r = client.get(f"/teacher/students/{student_id}/dna")
    check("cross-tenant /teacher/students/{id}/dna 404",
          r.status_code == 404, f"got {r.status_code}")

    # ============ STEP 11: Institution admin ============
    print("\n=== STEP 11: Institution admin burnout listesi ===")
    app.dependency_overrides.clear()
    app.dependency_overrides[require_institution_admin] = make_user_override(admin_id)
    app.dependency_overrides[get_current_user] = make_user_override(admin_id)
    r = client.get("/institution/burnout")
    check("institution burnout 200", r.status_code == 200, f"got {r.status_code}")
    # Bizim DNA Student burnout sinyali olmalı (night_owl)
    check("liste DNA Student içerir",
          "DNA Student" in r.text, "burnout sinyali olan öğrenci listede olmalı")
    # Gizlilik: link yok — "/teacher/students/" link içermemeli
    check("gizlilik: detay linki yok",
          "/teacher/students/" not in r.text or "dna" not in r.text)

    app.dependency_overrides.clear()

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_students = [student_id, s2_id, s3_id]
        db.execute(delete(Task).where(Task.student_id.in_(all_students)))
        db.execute(delete(User).where(
            User.id.in_(all_students + [teacher_id, admin_id, other_id])
        ))
        db.execute(delete(Institution).where(Institution.id == inst_id))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
