"""Hata düzeltme doğrulama — tek kitap-kalemli görev oluşturunca başlık otomatik
üretilir ('Görev' placeholder'ı KALMAZ; 'Kitap — Bölüm: N test' olur).

Kullanıcı bulgusu (2026-05-25): görev ekleyince satır 'Görev' yazıyordu; ancak
düzenle→güncelle sonrası 'Kitap — Bölüm: N test' oluyordu (tutarsızlık). Create
artık tek-kalem düzenleme ile aynı başlığı üretir.

Senaryolar:
   1. Tek-kalem test görevi oluştur → title = 'Kitap — Bölüm: 5 test' (Görev DEĞİL)
   2. Aynı görevi tek-kalem düzenle (sayı 8) → title = '... : 8 test' (tutarlı)
   3. Kitapsız deneme görevi → title 'Görev/Kitap—' OLMAZ, deneme label'ı korunur
"""
from __future__ import annotations

import sys
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
    AuditLog, Book, BookSection, BookType, SectionProgress, StudentBook,
    Subject, Task, TaskBookItem, User, UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"ttl{secrets.token_hex(3)}"
PASSWORD = "TitlePass1!@xyz"
TEACHER = f"{PFX}_t@test.invalid"

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


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        teacher = User(email=TEACHER, password_hash=pwd, full_name="Koç", role=UserRole.TEACHER,
                       is_active=True, password_changed_at=now, must_change_password=False,
                       email_verified_at=now)
        db.add(teacher); db.flush()
        student = User(email=f"{PFX}_s@test.invalid", password_hash=pwd, full_name="Öğr",
                       role=UserRole.STUDENT, is_active=True, grade_level=8, teacher_id=teacher.id,
                       password_changed_at=now, must_change_password=False)
        db.add(student); db.flush()
        subj = Subject(name=f"{PFX} Fen", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        book = Book(name="LGS Örnek Sorular Fen Bilimleri", subject_id=subj.id,
                    type=BookType.SORU_BANKASI, teacher_id=teacher.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Örnek Sorular Fen Bilimleri", test_count=50, order=0)
        db.add(sec); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb); db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               reserved_count=0, completed_count=0))
        out = {"teacher_id": teacher.id, "student_id": student.id, "subj_id": subj.id,
               "book_id": book.id, "section_id": sec.id, "book_name": book.name,
               "section_label": sec.label}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        sids = [seed["student_id"]]
        task_ids = [t.id for t in db.query(Task).filter(Task.student_id.in_(sids)).all()]
        if task_ids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(task_ids)))
            db.execute(sa_delete(Task).where(Task.id.in_(task_ids)))
        sb_ids = db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids)).scalar_subquery()
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sb_ids)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(sids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == seed["book_id"]))
        db.execute(sa_delete(Book).where(Book.id == seed["book_id"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subj_id"]))
        uids = [seed["teacher_id"], seed["student_id"]]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.commit()


def _login() -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": TEACHER, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login {r.status_code} {r.text[:120]}")
    return c


def main() -> int:
    print(f"\n=== Görev başlığı otomatik üretim smoke — {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    sid = seed["student_id"]
    expected1 = f"{seed['book_name']} — {seed['section_label']}: 5 test"
    expected2 = f"{seed['book_name']} — {seed['section_label']}: 8 test"
    try:
        tc = _login()
        # 1. Oluştur — frontend gibi title='Görev' gönder
        r = tc.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": date.today().isoformat(), "type": "test", "title": "Görev",
            "items": [{"book_id": seed["book_id"], "section_id": seed["section_id"], "planned_count": 5}],
        })
        j = r.json().get("data", {}) if r.status_code == 200 else {}
        check("1. Oluşturmada başlık otomatik ('Görev' değil)",
              r.status_code == 200 and j.get("title") == expected1,
              f"status={r.status_code} title={j.get('title')!r} beklenen={expected1!r}")
        task_id = j.get("id")

        # 2. Tek-kalem düzenle (sayı 8) → başlık tutarlı yeniden üretilir
        r = tc.patch(f"/api/v2/teacher/tasks/{task_id}/single-item", json={
            "date": date.today().isoformat(), "scheduled_hour": None, "type": "test",
            "book_id": seed["book_id"], "section_id": seed["section_id"],
            "planned_count": 8, "notes": None,
        })
        jt = r.json().get("data", {}) if r.status_code == 200 else {}
        check("2. Düzenlemede başlık tutarlı (8 test)",
              r.status_code == 200 and jt.get("title") == expected2,
              f"status={r.status_code} title={jt.get('title')!r} beklenen={expected2!r}")

        # 3. Kitapsız deneme görevi → deneme label'ı korunur (Kitap—/Görev değil)
        r = tc.post(f"/api/v2/teacher/students/{sid}/tasks", json={
            "date": date.today().isoformat(), "type": "other", "title": "LGS Tam Deneme 7",
            "items": [{"book_id": None, "section_id": None, "label": "LGS Tam Deneme 7", "planned_count": 90}],
        })
        jd = r.json().get("data", {}) if r.status_code == 200 else {}
        check("3. Kitapsız deneme başlığı korunur (otomatik üretilmez)",
              r.status_code == 200 and jd.get("title") == "LGS Tam Deneme 7",
              f"status={r.status_code} title={jd.get('title')!r}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
