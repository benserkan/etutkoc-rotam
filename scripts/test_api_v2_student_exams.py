"""API v2 — Öğrenci deneme listesi (GET /student/exams) smoke.

Öğrenci kendi deneme sonuçlarını salt-okuma görür (koç girer). Senaryolar:
  1. login + GET → 200 + summary (count/avg/best/last/first/trend) + rows DESC
  2. net hesabı + trend_delta (son - ilk)
  3. ders kırılımı (subject_nets) parse
  4. başka öğrencinin denemesi listede YOK (izolasyon)
  5. denemesi olmayan öğrenci → count 0, rows []
"""
from __future__ import annotations

import sys
try:
    sys.path.insert(0, ".")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import ExamResult, User, UserRole
from app.models.curriculum import ExamSection
from app.models.exam_result import compute_net
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"sex_{secrets.token_hex(3)}"
PWDH = "Exam!23456"
PWD = hash_password(PWDH)
now = datetime.now(timezone.utc)
ctx: dict = {}
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def mk_exam(db, student_id, coach_id, *, title, d, correct, wrong, blank, subjects=None):
    section = ExamSection.LGS
    sn = json.dumps(subjects) if subjects else None
    db.add(ExamResult(
        student_id=student_id, created_by_id=coach_id, title=title,
        exam_date=d, section=section,
        total_correct=correct, total_wrong=wrong, total_blank=blank,
        net=compute_net(correct, wrong, section), subject_nets=sn, note=None,
    ))


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_coach@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Koç", role=UserRole.TEACHER, institution_id=None,
                     is_active=True, plan="solo_pro", password_changed_at=now,
                     must_change_password=False)
        db.add(coach); db.flush()
        stu = User(email=f"{PFX}_stu@test.invalid", password_hash=PWD,
                   full_name=f"{PFX} Öğrenci", role=UserRole.STUDENT, teacher_id=coach.id,
                   is_active=True, password_changed_at=now, must_change_password=False)
        other = User(email=f"{PFX}_other@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Diğer", role=UserRole.STUDENT, teacher_id=coach.id,
                     is_active=True, password_changed_at=now, must_change_password=False)
        empty = User(email=f"{PFX}_empty@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Boş", role=UserRole.STUDENT, teacher_id=coach.id,
                     is_active=True, password_changed_at=now, must_change_password=False)
        db.add(stu); db.add(other); db.add(empty); db.flush()
        ctx.update(coach=coach.id, stu=stu.id, other=other.id, empty=empty.id)
        # stu: 2 deneme (eski + yeni); yeni'ye ders kırılımı
        mk_exam(db, stu.id, coach.id, title="LGS Deneme 1", d=date(2026, 5, 1),
                correct=60, wrong=9, blank=21)  # net = 60 - 9/3 = 57.0
        mk_exam(db, stu.id, coach.id, title="LGS Deneme 2", d=date(2026, 5, 15),
                correct=70, wrong=6, blank=14,  # net = 70 - 2 = 68.0
                subjects=[{"name": "Matematik", "correct": 18, "wrong": 3, "blank": 0, "net": 17.0}])
        # other: 1 deneme (izolasyon kontrolü)
        mk_exam(db, other.id, coach.id, title="Diğer LGS", d=date(2026, 5, 10),
                correct=40, wrong=0, blank=50)
        db.commit()


def cleanup():
    with SessionLocal() as db:
        ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
        if ids:
            db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def login(suffix):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {suffix}: {r.status_code} {r.text[:120]}")
    return c


def main() -> int:
    print(f"\n=== ÖĞRENCİ DENEMELER — {PFX} ===\n")
    setup()
    try:
        c = login("stu")
        r = c.get("/api/v2/student/exams")
        ok = r.status_code == 200
        d = r.json() if ok else {}
        check("1. GET /student/exams → 200", ok, f"{r.status_code} {r.text[:140]}")

        s = d.get("summary", {})
        rows = d.get("rows", [])
        check("2a. summary count=2", s.get("count") == 2, f"{s}")
        check("2b. avg/best/last/first/trend",
              abs(s.get("avg_net", 0) - 62.5) < 0.01 and abs(s.get("best_net", 0) - 68.0) < 0.01
              and abs(s.get("last_net", 0) - 68.0) < 0.01 and abs(s.get("first_net", 0) - 57.0) < 0.01
              and abs(s.get("trend_delta", 0) - 11.0) < 0.01,
              f"{s}")
        check("3a. rows DESC (ilk = en yeni 'LGS Deneme 2')",
              len(rows) == 2 and rows[0].get("title") == "LGS Deneme 2", f"{[x.get('title') for x in rows]}")
        check("3b. net + total_questions doğru (yeni: 68 net / 90 soru)",
              len(rows) and abs(rows[0].get("net", 0) - 68.0) < 0.01
              and rows[0].get("total_questions") == 90, f"{rows[0] if rows else None}")
        check("3c. ders kırılımı parse (Matematik 1 satır)",
              len(rows) and len(rows[0].get("subjects", [])) == 1
              and rows[0]["subjects"][0]["name"] == "Matematik", f"{rows[0].get('subjects') if rows else None}")

        # 4. izolasyon — "Diğer LGS" listede olmamalı
        titles = [x.get("title") for x in rows]
        check("4. başka öğrencinin denemesi yok (izolasyon)", "Diğer LGS" not in titles, f"{titles}")

        # 5. boş öğrenci
        ce = login("empty")
        r = ce.get("/api/v2/student/exams")
        de = r.json() if r.status_code == 200 else {}
        check("5. denemesi olmayan → count 0, rows []",
              r.status_code == 200 and de.get("summary", {}).get("count") == 0
              and de.get("rows") == [], f"{r.status_code} {de.get('summary')}")
    finally:
        cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
