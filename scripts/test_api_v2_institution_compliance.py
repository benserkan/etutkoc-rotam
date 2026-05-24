"""API v2 /institution/compliance (Program Uyum Panosu) smoke (2026-05-20).

Senaryolar:
   1. Teacher → 403 (rol kapısı)
   2. Anonim → 401
   3. compliance happy — summary + trend + teachers + attention + empty_program şekli
   4. kurum tamamlama oranı doğru hesaplanır (planned/completed → rate)
   5. doğruluk oranı (correct/wrong → accuracy) doğru
   6. öğretmen kırılımı: koç başına satır + boş öğrenci sayısı
   7. boş program: planı olmayan öğrenci empty_program'da
   8. öğrenci dikkat listesi: planı olan öğrenci + en düşük üstte
   9. weeks parametresi trend uzunluğunu belirler
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    Book,
    BookSection,
    Institution,
    Subject,
    Task,
    TaskBookItem,
    TaskType,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2icomp{secrets.token_hex(3)}"
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "CompPass1!@xyz"

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


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    ws = _monday(date.today())
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k",
                           contact_email=f"{PFX}@t.invalid", plan="free", is_active=True)
        db.add(inst)
        db.flush()
        admin = User(email=ADMIN_EMAIL, password_hash=pwd, full_name=f"{PFX} Admin",
                     role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id, is_active=True,
                     password_changed_at=now, must_change_password=False, email_verified_at=now)
        teacher = User(email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç",
                       role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
                       password_changed_at=now, must_change_password=False, email_verified_at=now)
        db.add_all([admin, teacher])
        db.flush()
        # 3 öğrenci: s1 (uyumlu), s2 (düşük), s3 (boş program).
        # created_at eski (10g) → boş-program onboarding grace'inden etkilenmesin.
        old = datetime.now(timezone.utc) - timedelta(days=10)
        s1 = User(email=f"{PFX}_s1@t.invalid", password_hash=pwd, full_name="Öğrenci Bir",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=teacher.id, is_active=True, created_at=old)
        s2 = User(email=f"{PFX}_s2@t.invalid", password_hash=pwd, full_name="Öğrenci İki",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=teacher.id, is_active=True, created_at=old)
        s3 = User(email=f"{PFX}_s3@t.invalid", password_hash=pwd, full_name="Öğrenci Üç",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=teacher.id, is_active=True, created_at=old)
        db.add_all([s1, s2, s3])
        db.flush()
        # Kitap (TaskBookItem.book_id zorunlu)
        subj = Subject(name=f"{PFX} Matematik", teacher_id=teacher.id)
        db.add(subj); db.flush()
        book = Book(teacher_id=teacher.id, subject_id=subj.id, name=f"{PFX} Test Kitabı", type="test")
        db.add(book); db.flush()
        section = BookSection(book_id=book.id, label=f"{PFX} Ünite 1")
        db.add(section); db.flush()
        # s1: planned 100, completed 90, correct 80, wrong 10 → rate 90, acc ~89
        t1 = Task(student_id=s1.id, date=ws, type=TaskType.TEST, title="P", is_draft=False, published_at=now)
        db.add(t1); db.flush()
        db.add(TaskBookItem(task_id=t1.id, book_id=book.id, book_section_id=section.id, planned_count=100, completed_count=90, correct_count=80, wrong_count=10))
        # s2: planned 100, completed 30, correct 15, wrong 15 → rate 30
        t2 = Task(student_id=s2.id, date=ws, type=TaskType.TEST, title="P", is_draft=False, published_at=now)
        db.add(t2); db.flush()
        db.add(TaskBookItem(task_id=t2.id, book_id=book.id, book_section_id=section.id, planned_count=100, completed_count=30, correct_count=15, wrong_count=15))
        # s3: hiç görev yok (boş program)
        db.flush()
        out = {"inst_id": inst.id, "admin_id": admin.id, "teacher_id": teacher.id,
               "s_ids": [s1.id, s2.id, s3.id]}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["admin_id"], seed["teacher_id"], *seed["s_ids"]]
        tasks = db.query(Task).filter(Task.student_id.in_(seed["s_ids"])).all()
        tids = [t.id for t in tasks]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        db.execute(sa_delete(Book).where(Book.teacher_id == seed["teacher_id"]))
        db.execute(sa_delete(Subject).where(Subject.teacher_id == seed["teacher_id"]))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.commit()


def _login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /institution/compliance smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded inst={seed['inst_id']}\n")

    try:
        ac = _login(ADMIN_EMAIL)
        tc = _login(TEACHER_EMAIL)

        # 1. teacher → 403
        r = tc.get("/api/v2/institution/compliance")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 2. anonim → 401
        r = TestClient(app).get("/api/v2/institution/compliance")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. happy şekil
        r = ac.get("/api/v2/institution/compliance")
        j = r.json()
        ok = (
            r.status_code == 200
            and "summary" in j and "trend" in j and "teachers" in j
            and "attention_students" in j and "empty_program" in j
        )
        check("3. compliance happy şekil", ok, f"status={r.status_code} {r.text[:120]}")

        s = j["summary"]
        # 4. kurum rate: planned 200, completed 120 → 60
        check("4. kurum tamamlama oranı (200/120 → 60)",
              s["planned"] == 200 and s["completed"] == 120 and s["rate"] == 60,
              f"planned={s['planned']} completed={s['completed']} rate={s['rate']}")

        # 5. doğruluk: correct 95, wrong 25 → 79
        check("5. doğruluk oranı (95/(95+25) → 79)", s["accuracy"] == 79, f"accuracy={s['accuracy']}")

        # 5b. empty_count = 1 (s3)
        check("5c. boş program sayısı = 1", s["empty_count"] == 1, f"empty_count={s['empty_count']}")

        # 6. öğretmen kırılımı
        trow = next((t for t in j["teachers"] if t["teacher_id"] == seed["teacher_id"]), None)
        ok = trow is not None and trow["student_count"] == 3 and trow["empty_students"] == 1 and trow["rate"] == 60
        check("6. öğretmen kırılımı (3 öğrenci, 1 boş, rate 60)", ok, f"{trow}")

        # 7. boş program listesi
        erow = next((e for e in j["empty_program"] if e["teacher_id"] == seed["teacher_id"]), None)
        check("7. boş program: koç + count 1 + sample", erow is not None and erow["count"] == 1 and len(erow["sample_students"]) == 1,
              f"{erow}")

        # 8. öğrenci dikkat: planı olan 2 öğrenci, en düşük (s2=30) üstte
        att = j["attention_students"]
        check("8. dikkat listesi: 2 öğrenci + en düşük üstte",
              len(att) == 2 and att[0]["rate"] == 30, f"len={len(att)} first_rate={att[0]['rate'] if att else None}")

        # 9. weeks param
        r = ac.get("/api/v2/institution/compliance?weeks=4")
        check("9. weeks=4 → trend 4 hafta", r.status_code == 200 and len(r.json()["trend"]) == 4,
              f"trend_len={len(r.json()['trend'])}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
