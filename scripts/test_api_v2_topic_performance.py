"""API v2 Ders → Konu performansı smoke (P1).

Koç + öğrenci + veli 3 yüzey aynı agregasyonu kullanır. Senaryolar:
  1. Anonim → 401 (koç ucu)
  2. Koç GET → 200; Mat dersi + 2 konu (Türev/İntegral)
  3. Türev doğruluk %80 (40D/10Y), İntegral %67 (20D/10Y)
  4. Ders toplam doğruluk %75 (60D/20Y), çözülen test 8
  5. DENEME kitabı HARİÇ (genel deneme kalemi sayılmaz)
  6. Konular en çok çözülene göre sıralı (Türev 5 > İntegral 3)
  7. Başka koçun öğrencisi → 404
  8. Öğrenci kendi /student/topic-performance → 200 aynı veri
  9. Veli GET → 200 (bağlı çocuk)
 10. Veli başka çocuk → 404 (gizlilik)
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, ParentRelation, ParentStudentLink,
    Subject, Task, TaskBookItem, TaskStatus, TaskType, User, UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2tp{secrets.token_hex(3)}"
PASSWORD = "TopicPerf1!@xyz"
T_EMAIL = f"{PFX}_t@test.invalid"
T2_EMAIL = f"{PFX}_t2@test.invalid"
S_EMAIL = f"{PFX}_s@test.invalid"
S2_EMAIL = f"{PFX}_s2@test.invalid"
P_EMAIL = f"{PFX}_p@test.invalid"

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
    pwd = hash_password(PASSWORD)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        t = User(email=T_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        t2 = User(email=T2_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç2",
                  role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([t, t2]); db.flush()
        s = User(email=S_EMAIL, password_hash=pwd, full_name="Öğr",
                 role=UserRole.STUDENT, is_active=True, grade_level=12, teacher_id=t.id)
        s2 = User(email=S2_EMAIL, password_hash=pwd, full_name="Öğr2",
                  role=UserRole.STUDENT, is_active=True, grade_level=12, teacher_id=t2.id)
        p = User(email=P_EMAIL, password_hash=pwd, full_name="Veli",
                 role=UserRole.PARENT, is_active=True)
        db.add_all([s, s2, p]); db.flush()
        db.add(ParentStudentLink(parent_id=p.id, student_id=s.id,
                                 relation=ParentRelation.ANNE, is_primary=True))

        subj = Subject(teacher_id=t.id, name="Matematik", order=1)
        db.add(subj); db.flush()
        sb = Book(teacher_id=t.id, name="Mat SB", type=BookType.SORU_BANKASI, subject_id=subj.id)
        db.add(sb); db.flush()
        sec_turev = BookSection(book_id=sb.id, label="Türev", order=1, test_count=100)
        sec_integral = BookSection(book_id=sb.id, label="İntegral", order=2, test_count=100)
        db.add_all([sec_turev, sec_integral]); db.flush()
        # DENEME kitabı (hariç tutulmalı)
        dn = Book(teacher_id=t.id, name="Mat GD", type=BookType.GENEL_DENEME, subject_id=subj.id)
        db.add(dn); db.flush()
        dn_sec = BookSection(book_id=dn.id, label="Denemeler", order=1, test_count=40)
        db.add(dn_sec); db.flush()

        # Görevler + kalemler (Türev: 5 test, 40D/10Y · İntegral: 3 test, 20D/10Y)
        task = Task(student_id=s.id, date=date(2026, 5, 1), type=TaskType.TEST,
                    title="Mat", is_draft=False, status=TaskStatus.COMPLETED, completed_at=now)
        db.add(task); db.flush()
        db.add(TaskBookItem(task_id=task.id, book_id=sb.id, book_section_id=sec_turev.id,
                            planned_count=5, completed_count=5, correct_count=40, wrong_count=10))
        db.add(TaskBookItem(task_id=task.id, book_id=sb.id, book_section_id=sec_integral.id,
                            planned_count=3, completed_count=3, correct_count=20, wrong_count=10))
        # Deneme görevi (sayılmamalı)
        dtask = Task(student_id=s.id, date=date(2026, 5, 2), type=TaskType.TEST,
                     title="Deneme", is_draft=False, status=TaskStatus.COMPLETED, completed_at=now)
        db.add(dtask); db.flush()
        db.add(TaskBookItem(task_id=dtask.id, book_id=dn.id, book_section_id=dn_sec.id,
                            planned_count=2, completed_count=2, correct_count=5, wrong_count=35))

        out = {"s_id": s.id, "s2_id": s2.id}
        db.commit()
        return out


def _cleanup():
    with SessionLocal() as db:
        ids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}%")).all()]
        if ids:
            db.execute(sa_delete(TaskBookItem).where(
                TaskBookItem.task_id.in_(
                    db.query(Task.id).filter(Task.student_id.in_(ids)).subquery().select()
                )
            ))
            db.execute(sa_delete(Task).where(Task.student_id.in_(ids)))
            secs = db.query(BookSection.id).join(Book, Book.id == BookSection.book_id).filter(Book.teacher_id.in_(ids))
            db.execute(sa_delete(BookSection).where(BookSection.id.in_(secs.subquery().select())))
            db.execute(sa_delete(Book).where(Book.teacher_id.in_(ids)))
            db.execute(sa_delete(Subject).where(Subject.teacher_id.in_(ids)))
            db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(ids)))
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {email} {r.status_code} {r.text[:120]}")
    return c


def main():
    print(f"\n=== Ders→Konu performansı smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()
        tc = _login(T_EMAIL)
        t2c = _login(T2_EMAIL)
        sc = _login(S_EMAIL)
        pc = _login(P_EMAIL)
        sid, s2id = seed["s_id"], seed["s2_id"]

        r = TestClient(app).get(f"/api/v2/teacher/students/{sid}/topic-performance")
        check("1. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        r = tc.get(f"/api/v2/teacher/students/{sid}/topic-performance")
        j = r.json()
        check("2. Koç GET → 200", r.status_code == 200, f"status={r.status_code} {r.text[:140]}")
        subs = j.get("subjects", [])
        mat = next((x for x in subs if x["subject_name"] == "Matematik"), None)
        check("2b. Matematik dersi + 2 konu", mat is not None and len(mat["topics"]) == 2,
              f"{[s2['subject_name'] for s2 in subs]}")
        turev = next((t for t in (mat["topics"] if mat else []) if t["topic_name"] == "Türev"), None)
        integ = next((t for t in (mat["topics"] if mat else []) if t["topic_name"] == "İntegral"), None)
        check("3. Türev doğruluk %80", turev is not None and turev["accuracy_pct"] == 80, f"{turev}")
        check("3b. İntegral doğruluk %67", integ is not None and integ["accuracy_pct"] == 67, f"{integ}")
        check("4. Ders toplam doğruluk %75",
              mat is not None and mat["accuracy_pct"] == 75, f"acc={mat and mat['accuracy_pct']}")
        check("4b. Ders çözülen test = 8", mat is not None and mat["tests_solved"] == 8,
              f"tests={mat and mat['tests_solved']}")
        check("5. DENEME kitabı hariç (toplam D=60 Y=20)",
              mat is not None and mat["correct"] == 60 and mat["wrong"] == 20,
              f"D={mat and mat['correct']} Y={mat and mat['wrong']}")
        check("6. Konular en çok çözülene göre (Türev önce)",
              mat is not None and mat["topics"][0]["topic_name"] == "Türev", f"{mat and [t['topic_name'] for t in mat['topics']]}")
        ov = j.get("overall", {})
        check("6b. overall doğruluk %75 + topic_count 2",
              ov.get("accuracy_pct") == 75 and ov.get("topic_count") == 2, f"{ov}")

        r = t2c.get(f"/api/v2/teacher/students/{sid}/topic-performance")
        check("7. Başka koçun öğrencisi → 404", r.status_code == 404, f"status={r.status_code}")

        r = sc.get("/api/v2/student/topic-performance")
        j2 = r.json()
        mat2 = next((x for x in j2.get("subjects", []) if x["subject_name"] == "Matematik"), None)
        check("8. Öğrenci kendi performansı → 200 aynı veri",
              r.status_code == 200 and mat2 is not None and mat2["accuracy_pct"] == 75,
              f"status={r.status_code} {mat2}")

        r = pc.get(f"/api/v2/parent/students/{sid}/topic-performance")
        j3 = r.json()
        mat3 = next((x for x in j3.get("subjects", []) if x["subject_name"] == "Matematik"), None)
        check("9. Veli bağlı çocuk → 200", r.status_code == 200 and mat3 is not None, f"status={r.status_code}")

        r = pc.get(f"/api/v2/parent/students/{s2id}/topic-performance")
        check("10. Veli başka çocuk → 404 (gizlilik)", r.status_code == 404, f"status={r.status_code}")

    finally:
        _cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
