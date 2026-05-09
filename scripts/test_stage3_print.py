"""Stage 3 Part B — print template smoke test."""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    Institution,
    User,
    UserRole,
)
from app.services.security import hash_password


PFX = f"_print_{secrets.token_hex(3)}"
PWD = "TestPass!234567"

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
    print("\n=== SEED ===")
    with SessionLocal() as db:
        pwd_hash = hash_password(PWD)
        now = datetime.now(timezone.utc)

        inst = Institution(
            name=f"{PFX}_inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="free", is_active=True,
        )
        db.add(inst); db.flush()
        inst_id = inst.id

        admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash=pwd_hash,
            full_name="Print Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=f"{PFX}_t@test.invalid", password_hash=pwd_hash,
            full_name="Print Teacher", role=UserRole.TEACHER,
            institution_id=inst_id, is_active=True,
            password_changed_at=now, must_change_password=False,
            last_login_at=now,
        )
        db.add_all([admin, teacher]); db.flush()
        admin_id, admin_email = admin.id, admin.email
        teacher_id = teacher.id

        # 2 öğrenci, biri risk altında olacak
        s1 = User(
            email=f"{PFX}_s1@test.invalid", password_hash=pwd_hash,
            full_name="Print Student 1", role=UserRole.STUDENT,
            institution_id=inst_id, teacher_id=teacher_id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            last_login_at=now - datetime.now().replace(year=now.year-1).utcoffset() if False else now - (now - now),  # bugün
        )
        # Risk altında: hiç giriş yok + program yok
        s2 = User(
            email=f"{PFX}_s2@test.invalid", password_hash=pwd_hash,
            full_name="Print Student 2", role=UserRole.STUDENT,
            institution_id=inst_id, teacher_id=teacher_id,
            grade_level=11, is_active=True,
            password_changed_at=now, must_change_password=False,
            last_login_at=None,
        )
        db.add_all([s1, s2]); db.flush()
        student_ids = [s1.id, s2.id]
        db.commit()
    print(f"  inst={inst_id} admin={admin_id} teacher={teacher_id} students={student_ids}")

    # ============ HTTP ============
    print("\n=== Login ===")
    c = TestClient(app)
    r = c.post("/login", data={"email": admin_email, "password": PWD},
               follow_redirects=False)
    check("admin login", r.status_code == 303, f"got {r.status_code}")

    print("\n=== Print routes ===")
    for path, expected in [
        ("/institution/cohorts/print", ["Kohort Karşılaştırma Raporu", "Sınıf seviyesi"]),
        ("/institution/at-risk/print", ["Risk Altındaki Öğrenciler"]),
        ("/institution/activity-heatmap/print", ["Aktivite Raporu", "Print Teacher"]),
    ]:
        r = c.get(path)
        check(f"GET {path} -> 200", r.status_code == 200, f"got {r.status_code}")
        for term in expected:
            check(f"  {path} içerir '{term}'", term in r.text,
                  f"'{term}' yok in response")

    print("\n=== Print routes — weeks query ===")
    r = c.get("/institution/activity-heatmap/print?weeks=12")
    check("weeks=12 200", r.status_code == 200)
    r = c.get("/institution/activity-heatmap/print?weeks=99")
    check("weeks=99 invalid -> 200 fallback", r.status_code == 200)

    print("\n=== Anonim ===")
    anon = TestClient(app)
    for path in ("/institution/cohorts/print", "/institution/at-risk/print",
                 "/institution/activity-heatmap/print"):
        r = anon.get(path, follow_redirects=False)
        check(f"anon {path} -> 303", r.status_code == 303,
              f"got {r.status_code}")

    print("\n=== Cross-tenant ===")
    # Başka kurum admin'i bu kurumun verilerini görmemeli
    with SessionLocal() as db:
        other_inst = Institution(
            name=f"{PFX}_other", slug=f"{PFX}-other",
            contact_email=f"{PFX}_other@test.invalid", plan="free", is_active=True,
        )
        db.add(other_inst); db.flush()
        other_admin = User(
            email=f"{PFX}_other_admin@test.invalid", password_hash=hash_password(PWD),
            full_name="Other Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=other_inst.id, is_active=True,
            password_changed_at=datetime.now(timezone.utc),
            must_change_password=False,
        )
        db.add(other_admin); db.flush()
        other_inst_id = other_inst.id
        other_admin_id = other_admin.id
        other_admin_email = other_admin.email
        db.commit()

    c2 = TestClient(app)
    c2.post("/login", data={"email": other_admin_email, "password": PWD},
            follow_redirects=False)
    r = c2.get("/institution/at-risk/print")
    check("other admin at-risk/print 200", r.status_code == 200)
    check("other admin Print Student GÖRMEZ",
          "Print Student" not in r.text,
          "veri sızdı")
    check("other admin Print Teacher GÖRMEZ",
          "Print Teacher" not in r.text,
          "öğretmen sızdı")

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_ids = [admin_id, teacher_id, other_admin_id] + student_ids
        db.query(AuditLog).filter(
            AuditLog.actor_id.in_(all_ids)
        ).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(all_ids)).delete(
            synchronize_session=False
        )
        db.query(Institution).filter(
            Institution.id.in_([inst_id, other_inst_id])
        ).delete(synchronize_session=False)
        db.commit()
        print("  test verisi temizlendi")

    print(f"\n=== SONUC ===")
    print(f"  gecen: {passed}, basarisiz: {len(failed)}")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    print("  [OK] Stage 3 print template testi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
