"""M5 — Demo Ekosistem Oluştur smoke.

Senaryolar (12):
   1. POST /admin/demo-seed kind=institution → 200, kurum + 4 kullanıcı
   2. credentials liste: 4 rol (admin, koç, öğrenci, veli) + her birinde email/şifre
   3. Login: admin → 200 (Demo123!@ ile)
   4. Login: koç → 200
   5. Login: öğrenci → 200
   6. Login: veli → 200
   7. Tutarlılık: koç↔öğrenci teacher_id eşleşir; veli↔öğrenci ParentStudentLink
   8. Örnek veri: en az 1 görev + 1 deneme yaratılmış
   9. kind=solo_coach → 200, 5 kullanıcı (koç + 2 öğr + 2 veli)
  10. kind=institution_teacher → 200, 3 kullanıcı (öğretmen + öğr + veli)
  11. kind=invalid → 422 invalid_kind
  12. anon → 401; TEACHER → 403 role_required
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    Institution,
    ParentStudentLink,
    SectionProgress,
    StudentBook,
    Subject,
    SuspiciousIp,
    Task,
    TaskBookItem,
    Topic,
    User,
    UserRole,
)
from app.models.coach_billing import CoachStudentRate
from app.models.coaching_session import CoachingSession
from app.models.exam_result import ExamResult
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2ds_{secrets.token_hex(3)}"
ADMIN_EMAIL = f"{PFX}_a@test.invalid"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
PASSWORD = "TestPass123!@xyz"
DEMO_PWD = "Demo123!@"

passed = 0
failed: list[str] = []
created_user_ids: list[int] = []
created_inst_ids: list[int] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed_admin() -> dict:
    """Süper admin + TEACHER hesabı (role guard testi için)."""
    with SessionLocal() as db:
        admin = User(
            email=ADMIN_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Demo Test Admin", role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Demo Test Koç", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        db.add_all([admin, teacher])
        db.commit()
        return {"admin_id": admin.id, "teacher_id": teacher.id}


def _cleanup_demo_users_and_data() -> None:
    """Demo seed sonucunda yaratılan tüm objeleri sil — temizlik."""
    with SessionLocal() as db:
        if created_user_ids:
            # Cascade ile bağlı veriler temizlenir; ama bazı SQLite cascades
            # güvenilmez → manuel temizlik
            db.execute(sa_delete(ExamResult).where(
                ExamResult.student_id.in_(created_user_ids)))
            db.execute(sa_delete(CoachingSession).where(
                CoachingSession.student_id.in_(created_user_ids)))
            db.execute(sa_delete(CoachingSession).where(
                CoachingSession.coach_id.in_(created_user_ids)))
            db.execute(sa_delete(CoachStudentRate).where(
                CoachStudentRate.student_id.in_(created_user_ids)))

            # Task → TaskBookItem cascade
            task_ids = [
                tid for (tid,) in db.query(Task.id)
                .filter(Task.student_id.in_(created_user_ids)).all()
            ]
            if task_ids:
                db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids)))
                db.execute(sa_delete(Task).where(Task.id.in_(task_ids)))

            # ParentStudentLink temizle
            db.execute(sa_delete(ParentStudentLink).where(
                ParentStudentLink.student_id.in_(created_user_ids)))
            db.execute(sa_delete(ParentStudentLink).where(
                ParentStudentLink.parent_id.in_(created_user_ids)))

            # StudentBook + SectionProgress
            sb_ids = [sid for (sid,) in db.query(StudentBook.id)
                      .filter(StudentBook.student_id.in_(created_user_ids)).all()]
            if sb_ids:
                db.execute(sa_delete(SectionProgress).where(
                    SectionProgress.student_book_id.in_(sb_ids)))
                db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sb_ids)))

            # Müfredat: BookSection → Topic → Subject → Book — koçun teacher_id'sine bağlı
            book_ids = [bid for (bid,) in db.query(Book.id)
                        .filter(Book.teacher_id.in_(created_user_ids)).all()]
            if book_ids:
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(book_ids)))
                db.execute(sa_delete(Book).where(Book.id.in_(book_ids)))
            topic_ids = []
            subject_ids = [sid for (sid,) in db.query(Subject.id)
                           .filter(Subject.teacher_id.in_(created_user_ids)).all()]
            if subject_ids:
                topic_ids = [tid for (tid,) in db.query(Topic.id)
                             .filter(Topic.subject_id.in_(subject_ids)).all()]
                if topic_ids:
                    db.execute(sa_delete(Topic).where(Topic.id.in_(topic_ids)))
                db.execute(sa_delete(Subject).where(Subject.id.in_(subject_ids)))

            db.execute(sa_delete(User).where(User.id.in_(created_user_ids)))

        if created_inst_ids:
            db.execute(sa_delete(Institution).where(Institution.id.in_(created_inst_ids)))

        # Admin + test koçunu sil
        db.execute(sa_delete(User).where(User.email.in_([ADMIN_EMAIL, TEACHER_EMAIL])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(client: TestClient, email: str, password: str) -> int:
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": email, "password": password})
    return r.status_code


def main() -> int:
    print(f"\n=== M5 demo seed smoke — prefix: {PFX} ===\n")
    seed = _seed_admin()

    try:
        client = TestClient(app)
        # Süper admin login
        assert _login(client, ADMIN_EMAIL, PASSWORD) == 200

        # ===== 1. kind=institution =====
        r = client.post("/api/v2/admin/demo-seed", json={"kind": "institution"})
        body = r.json() if r.text else {}
        creds_inst = body.get("credentials", [])
        # User ID'leri temizlik için topla
        for c in creds_inst:
            created_user_ids.append(c["user_id"])
        if body.get("institution_id"):
            created_inst_ids.append(body["institution_id"])

        ok = (
            r.status_code == 200
            and body.get("kind") == "institution"
            and body.get("institution_id") is not None
            and len(creds_inst) == 4
        )
        check("1. POST kind=institution → 200, 4 kullanıcı",
              ok, f"status={r.status_code} creds={len(creds_inst)}")

        # ===== 2. Roller doğru =====
        role_labels = sorted(c["role_label"] for c in creds_inst)
        expected = sorted(["Kurum Yöneticisi", "Koç", "Öğrenci", "Veli"])
        ok = role_labels == expected
        check("2. credentials 4 rol (Yönetici/Koç/Öğrenci/Veli)",
              ok, f"got={role_labels}")

        # ===== 3-6. Her kullanıcı Demo123!@ ile login =====
        for c in creds_inst:
            new_client = TestClient(app)
            sc = _login(new_client, c["email"], DEMO_PWD)
            role = c["role_label"]
            check(f"3-6. login {role} ({c['email']}) → 200",
                  sc == 200, f"status={sc}")

        # ===== 7. Tutarlılık: teacher_id + ParentStudentLink =====
        with SessionLocal() as db:
            student_cred = next(c for c in creds_inst if c["role_label"] == "Öğrenci")
            coach_cred = next(c for c in creds_inst if c["role_label"] == "Koç")
            parent_cred = next(c for c in creds_inst if c["role_label"] == "Veli")
            student = db.get(User, student_cred["user_id"])
            link = db.query(ParentStudentLink).filter_by(
                parent_id=parent_cred["user_id"],
                student_id=student_cred["user_id"],
            ).first()
            ok = (
                student.teacher_id == coach_cred["user_id"]
                and link is not None
            )
            check("7. teacher_id + ParentStudentLink bağı doğru",
                  ok, f"t_id={student.teacher_id} expected={coach_cred['user_id']} link={link is not None}")

            # ===== 8. Örnek veri: en az 1 görev + 1 deneme =====
            task_count = db.query(Task).filter_by(student_id=student.id).count()
            exam_count = db.query(ExamResult).filter_by(student_id=student.id).count()
            ok = task_count >= 1 and exam_count >= 1
            check("8. örnek veri: ≥1 görev + ≥1 deneme",
                  ok, f"tasks={task_count} exams={exam_count}")

        # ===== 9. kind=solo_coach =====
        r = client.post("/api/v2/admin/demo-seed", json={"kind": "solo_coach"})
        body = r.json() if r.text else {}
        creds_solo = body.get("credentials", [])
        for c in creds_solo:
            created_user_ids.append(c["user_id"])

        ok = (
            r.status_code == 200
            and body.get("kind") == "solo_coach"
            and body.get("institution_id") is None  # bağımsız koç
            and len(creds_solo) == 5  # koç + 2 öğr + 2 veli
        )
        check("9. kind=solo_coach → 200, 5 kullanıcı (1 koç + 2 öğr + 2 veli)",
              ok, f"status={r.status_code} creds={len(creds_solo)} inst={body.get('institution_id')}")

        # ===== 10. kind=institution_teacher =====
        r = client.post("/api/v2/admin/demo-seed", json={"kind": "institution_teacher"})
        body = r.json() if r.text else {}
        creds_it = body.get("credentials", [])
        for c in creds_it:
            created_user_ids.append(c["user_id"])
        if body.get("institution_id"):
            created_inst_ids.append(body["institution_id"])

        role_labels_it = sorted(c["role_label"] for c in creds_it)
        ok = (
            r.status_code == 200
            and body.get("kind") == "institution_teacher"
            and len(creds_it) == 3
            and role_labels_it == sorted(["Koç", "Öğrenci", "Veli"])
        )
        check("10. kind=institution_teacher → 200, 3 kullanıcı",
              ok, f"status={r.status_code} creds={len(creds_it)} roles={role_labels_it}")

        # ===== 11. kind=invalid =====
        r = client.post("/api/v2/admin/demo-seed", json={"kind": "garbage"})
        # Pydantic Literal validation 422 üretir
        ok = r.status_code in (400, 422)
        check("11. kind=invalid → 422",
              ok, f"status={r.status_code}")

        # ===== 12. role guard =====
        anon_client = TestClient(app)
        r = anon_client.post("/api/v2/admin/demo-seed", json={"kind": "institution"})
        ok_anon = r.status_code == 401

        teacher_client = TestClient(app)
        assert _login(teacher_client, TEACHER_EMAIL, PASSWORD) == 200
        r = teacher_client.post("/api/v2/admin/demo-seed", json={"kind": "institution"})
        body = r.json() if r.text else {}
        ok_teacher = (
            r.status_code == 403
            and body.get("detail", {}).get("code") == "role_required"
        )
        check("12. anon→401 + TEACHER→403 role_required",
              ok_anon and ok_teacher, f"anon={ok_anon} teacher={r.status_code}")

    finally:
        _cleanup_demo_users_and_data()

    total = passed + len(failed)
    print(f"\n=== Sonuç: {passed}/{total} geçti ===\n")
    if failed:
        print("Başarısız senaryolar:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
