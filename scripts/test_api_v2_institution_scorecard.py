"""API v2 /institution/teacher-scorecard (Öğretmen Etkililik Karnesi) smoke (KP2).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. happy şekil (summary + teachers)
   4. yüksek uyumlu koç yüksek skor; düşük uyumlu koç düşük skor (sıralama)
   5. skor bileşenleri döner (completion_rate + accuracy + discipline + risk)
   6. weeks parametresi kabul
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

PFX = f"v2isc{secrets.token_hex(3)}"
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
T_GOOD_EMAIL = f"{PFX}_good@test.invalid"
T_BAD_EMAIL = f"{PFX}_bad@test.invalid"
PASSWORD = "ScPass1!@xyz"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed():
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
        t_good = User(email=T_GOOD_EMAIL, password_hash=pwd, full_name=f"{PFX} İyi Koç",
                      role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
                      password_changed_at=now, must_change_password=False, email_verified_at=now)
        t_bad = User(email=T_BAD_EMAIL, password_hash=pwd, full_name=f"{PFX} Zayıf Koç",
                     role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
                     password_changed_at=now, must_change_password=False, email_verified_at=now)
        db.add_all([admin, t_good, t_bad]); db.flush()
        sg = User(email=f"{PFX}_sg@t.invalid", password_hash=pwd, full_name="İyi Öğrenci",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=t_good.id, is_active=True)
        sb = User(email=f"{PFX}_sb@t.invalid", password_hash=pwd, full_name="Zayıf Öğrenci",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=t_bad.id, is_active=True)
        db.add_all([sg, sb]); db.flush()
        subj = Subject(name=f"{PFX} Mat", teacher_id=t_good.id); db.add(subj); db.flush()
        book = Book(teacher_id=t_good.id, subject_id=subj.id, name=f"{PFX} K", type="test")
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label=f"{PFX} Ü1"); db.add(sec); db.flush()
        # İyi koç öğrencisi: planned 100 completed 95 correct 90 wrong 5 → yüksek
        tg = Task(student_id=sg.id, date=ws, type=TaskType.TEST, title="P", is_draft=False, published_at=now)
        db.add(tg); db.flush()
        db.add(TaskBookItem(task_id=tg.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=100, completed_count=95, correct_count=90, wrong_count=5))
        # Zayıf koç öğrencisi: planned 100 completed 20 correct 5 wrong 15 → düşük
        tb = Task(student_id=sb.id, date=ws, type=TaskType.TEST, title="P", is_draft=False, published_at=now)
        db.add(tb); db.flush()
        db.add(TaskBookItem(task_id=tb.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=100, completed_count=20, correct_count=5, wrong_count=15))
        db.flush()
        out = {"inst_id": inst.id, "admin_id": admin.id,
               "t_good": t_good.id, "t_bad": t_bad.id, "s_ids": [sg.id, sb.id]}
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        uids = [seed["admin_id"], seed["t_good"], seed["t_bad"], *seed["s_ids"]]
        tasks = db.query(Task).filter(Task.student_id.in_(seed["s_ids"])).all()
        tids = [t.id for t in tasks]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        db.execute(sa_delete(Book).where(Book.teacher_id == seed["t_good"]))
        db.execute(sa_delete(Subject).where(Subject.teacher_id == seed["t_good"]))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code}")
    return c


def main():
    print(f"\n=== API v2 /institution/teacher-scorecard smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        ac = _login(ADMIN_EMAIL)
        tc = _login(T_GOOD_EMAIL)

        r = tc.get("/api/v2/institution/teacher-scorecard")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        r = TestClient(app).get("/api/v2/institution/teacher-scorecard")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        r = ac.get("/api/v2/institution/teacher-scorecard")
        j = r.json()
        ok = r.status_code == 200 and "summary" in j and "teachers" in j and len(j["teachers"]) >= 2
        check("3. happy şekil", ok, f"status={r.status_code} {r.text[:120]}")

        good = next((t for t in j["teachers"] if t["teacher_id"] == seed["t_good"]), None)
        bad = next((t for t in j["teachers"] if t["teacher_id"] == seed["t_bad"]), None)
        check("4. iyi koç skoru > zayıf koç skoru",
              good and bad and good["score"] > bad["score"],
              f"good={good['score'] if good else None} bad={bad['score'] if bad else None}")

        check("5. skor bileşenleri döner",
              good and good["completion_rate"] == 95 and good["accuracy"] == 95 and "discipline_pct" in good,
              f"{good}")

        # ilk sıra en yüksek skor
        check("5b. sıralama (skor azalan)", j["teachers"][0]["score"] >= j["teachers"][-1]["score"],
              f"first={j['teachers'][0]['score']} last={j['teachers'][-1]['score']}")

        r = ac.get("/api/v2/institution/teacher-scorecard?weeks=8")
        check("6. weeks=8 kabul", r.status_code == 200 and r.json()["summary"]["weeks"] == 8,
              f"status={r.status_code}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
