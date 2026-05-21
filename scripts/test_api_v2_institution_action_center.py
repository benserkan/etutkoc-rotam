"""API v2 /institution/action-center (Müdahale Merkezi) smoke (KP1, 2026-05-20).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. happy şekil (summary + items)
   4. boş program kartı üretilir (program girilmemiş öğrenci)
   5. düşük uyum koç kartı üretilir (rate < 40)
   6. kartlar önceliklendirilir (critical önce)
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
    AuditLog, Book, BookSection, Institution, Subject, Task, TaskBookItem,
    TaskType, User, UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2iac{secrets.token_hex(3)}"
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "AcPass1!@xyz"

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


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    ws = date.today() - timedelta(days=date.today().weekday())
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} K", slug=f"{PFX}-k", contact_email=f"{PFX}@t.invalid",
                           plan="free", is_active=True)
        db.add(inst); db.flush()
        admin = User(email=ADMIN_EMAIL, password_hash=pwd, full_name=f"{PFX} Admin",
                     role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id, is_active=True,
                     password_changed_at=now, must_change_password=False, email_verified_at=now)
        teacher = User(email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç",
                       role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
                       password_changed_at=now, must_change_password=False, email_verified_at=now)
        db.add_all([admin, teacher]); db.flush()
        # s1: düşük uyum (rate 20), s2 + s3: boş program
        s1 = User(email=f"{PFX}_s1@t.invalid", password_hash=pwd, full_name="Öğrenci Bir",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=teacher.id, is_active=True)
        s2 = User(email=f"{PFX}_s2@t.invalid", password_hash=pwd, full_name="Öğrenci İki",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=teacher.id, is_active=True)
        s3 = User(email=f"{PFX}_s3@t.invalid", password_hash=pwd, full_name="Öğrenci Üç",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=teacher.id, is_active=True)
        db.add_all([s1, s2, s3]); db.flush()
        subj = Subject(name=f"{PFX} Mat", teacher_id=teacher.id); db.add(subj); db.flush()
        book = Book(teacher_id=teacher.id, subject_id=subj.id, name=f"{PFX} Kitap", type="test")
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label=f"{PFX} Ü1"); db.add(sec); db.flush()
        # s1: planned 100 completed 20 → rate 20 (düşük uyum)
        t1 = Task(student_id=s1.id, date=ws, type=TaskType.TEST, title="P", is_draft=False, published_at=now)
        db.add(t1); db.flush()
        db.add(TaskBookItem(task_id=t1.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=100, completed_count=20, correct_count=10, wrong_count=10))
        # s2, s3: hiç görev (boş program → 2 öğrenci)
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
        raise RuntimeError(f"login fail {r.status_code}")
    return c


def main() -> int:
    print(f"\n=== API v2 /institution/action-center smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        ac = _login(ADMIN_EMAIL)
        tc = _login(TEACHER_EMAIL)

        r = tc.get("/api/v2/institution/action-center")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        r = TestClient(app).get("/api/v2/institution/action-center")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        r = ac.get("/api/v2/institution/action-center")
        j = r.json()
        ok = r.status_code == 200 and "summary" in j and "items" in j and isinstance(j["items"], list)
        check("3. happy şekil", ok, f"status={r.status_code} {r.text[:120]}")

        cats = {i["category"] for i in j["items"]}
        check("4. boş program kartı var", "empty_program" in cats, f"cats={cats}")
        check("5. düşük uyum kartı var", "low_compliance" in cats, f"cats={cats}")

        # boş program 2 öğrenci → count 2; düşük uyum rate 20 → critical
        empty = next((i for i in j["items"] if i["category"] == "empty_program"), None)
        check("4b. boş program count=2", empty is not None and empty["count"] == 2, f"{empty}")
        low = next((i for i in j["items"] if i["category"] == "low_compliance"), None)
        check("5b. düşük uyum critical (rate 20 < 25)", low is not None and low["severity"] == "critical", f"{low}")

        # önceliklendirme: ilk item critical (varsa)
        if j["items"]:
            sev_order = {"critical": 0, "warn": 1, "info": 2}
            ranks = [sev_order.get(i["severity"], 9) for i in j["items"]]
            check("6. kartlar önceliklendirilmiş (critical önce)", ranks == sorted(ranks), f"ranks={ranks}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
