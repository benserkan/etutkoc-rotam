"""Kitap/bölüm silme — görev geçmişi FK ihlali düzeltmesi smoke (2026-08-14).

Saha reprosu: koç kitabı öğrenciye atar → görev oluşur → atamayı KALDIRIR
(SectionProgress CASCADE gider) → kitabı/bölümü silmeye çalışır. Eski davranış:
progress guard'ları geçer, task_book_items FK'sı patlar → 500 (11 hata grubu).
Yeni davranış: kalemler koparılır (label doldurulur, FK NULL, görev
block_detached) → silme 200, görev geçmişi görünür kalır.

Senaryolar (10):
   1. REPRO: atama kaldırıldıktan sonra tekil bölüm DELETE → 200 (eskiden 500)
   2. ...kalem koparıldı: label='Kitap — Bölüm', book_id/section_id NULL
   3. ...görev block_detached=True ('Diğer' sınıfı — deneme sayılmaz)
   4. clear-sections → 200 (kalan bölümler + kalemleri koparılır)
   5. kitap DELETE → 200
   6. Öğrenci gün görünümü 200 + görev hâlâ listede (geçmiş kaybolmadı)
   7. AKTİF rezervli kitapta silme hâlâ 409 has_progress (guard bozulmadı)
   8. clear-sections aktif progress'te 409
   9. Koparılan kalem sayısı doğru döner (helper birim)
  10. Yabancı koç kitabı silemez (404)
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
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"bdel_{secrets.token_hex(3)}"
PASSWORD = "TestPass123!@xyz"
T1 = f"{PFX}_t1@test.invalid"
T2 = f"{PFX}_t2@test.invalid"
S1 = f"{PFX}_s1@test.invalid"

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
    today = date.today()
    with SessionLocal() as db:
        t1 = User(email=T1, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} Koç1", role=UserRole.TEACHER, is_active=True)
        t2 = User(email=T2, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} Koç2", role=UserRole.TEACHER, is_active=True)
        db.add_all([t1, t2])
        db.flush()
        s1 = User(email=S1, password_hash=hash_password(PASSWORD),
                  full_name=f"{PFX} Öğr", role=UserRole.STUDENT,
                  teacher_id=t1.id, is_active=True, grade_level=8)
        db.add(s1)
        db.flush()
        subj = Subject(name=f"{PFX} Fizik", teacher_id=t1.id)
        db.add(subj)
        db.flush()

        def mk_book(name):
            b = Book(name=name, subject_id=subj.id, teacher_id=t1.id,
                     type=BookType.SORU_BANKASI)
            db.add(b)
            db.flush()
            out = []
            for i in (1, 2):
                sec = BookSection(book_id=b.id, label=f"Bölüm {i}", order=i, test_count=10)
                db.add(sec)
                db.flush()
                out.append(sec.id)
            return b.id, out

        # Kitap A: repro kitabı — görev + TAMAMLANMIŞ kalem, sonra atama KALDIRILIR
        book_a, secs_a = mk_book(f"{PFX} Repro Kitabı")
        sb = StudentBook(student_id=s1.id, book_id=book_a)
        db.add(sb)
        db.flush()
        task = Task(student_id=s1.id, title=f"{PFX} Repro Kitabı — Bölüm 1: 4 test",
                    type=TaskType.TEST, date=today, status=TaskStatus.COMPLETED,
                    is_draft=False)
        db.add(task)
        db.flush()
        db.add(TaskBookItem(task_id=task.id, book_id=book_a,
                            book_section_id=secs_a[0], planned_count=4,
                            completed_count=4))
        # Saha durumu: atama kaldırılmış → StudentBook + SectionProgress YOK
        db.delete(sb)
        db.flush()

        # Kitap B: AKTİF rezervli (guard testi)
        book_b, secs_b = mk_book(f"{PFX} Aktif Kitap")
        sb2 = StudentBook(student_id=s1.id, book_id=book_b)
        db.add(sb2)
        db.flush()
        db.add(SectionProgress(student_book_id=sb2.id, book_section_id=secs_b[0],
                               reserved_count=3, completed_count=0))
        db.commit()
        return {"t1": t1.id, "t2": t2.id, "s1": s1.id, "subj": subj.id,
                "book_a": book_a, "secs_a": secs_a,
                "book_b": book_b, "secs_b": secs_b,
                "task": task.id, "today": today}


def _cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uids = [ids["t1"], ids["t2"], ids["s1"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(uids)).all()]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        sb_ids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(uids)).all()]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sb_ids)))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sb_ids)))
        bids = [r[0] for r in db.query(Book.id).filter(Book.teacher_id.in_(uids)).all()]
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids)))
        db.execute(sa_delete(Book).where(Book.id.in_(bids)))
        db.execute(sa_delete(Subject).where(Subject.teacher_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def main() -> int:
    ids = _seed()
    client = TestClient(app)
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": T1, "password": PASSWORD})
    assert r.status_code == 200, f"login {r.status_code}"
    base = "/api/v2/teacher/library"

    try:
        # ---- 1-3: tekil bölüm silme (repro)
        r = client.delete(f"{base}/books/{ids['book_a']}/sections/{ids['secs_a'][0]}")
        check("1. REPRO — ataması kaldırılmış kitapta bölüm DELETE → 200",
              r.status_code == 200, f"{r.status_code}: {r.text[:200]}")
        with SessionLocal() as db:
            it = db.query(TaskBookItem).filter(TaskBookItem.task_id == ids["task"]).first()
            check("2. kalem koparıldı: label dolu + FK'lar NULL",
                  it is not None and it.book_id is None
                  and it.book_section_id is None
                  and it.label and "Bölüm 1" in it.label,
                  f"label={it.label if it else None} book={it.book_id if it else '?'}")
            t = db.get(Task, ids["task"])
            check("3. görev block_detached=True", bool(t.block_detached), str(t.block_detached))

        # ---- 4: clear-sections (kalan Bölüm 2)
        r = client.post(f"{base}/books/{ids['book_a']}/clear-sections")
        check("4. clear-sections → 200", r.status_code == 200, f"{r.status_code}: {r.text[:150]}")

        # ---- 5: kitap silme
        r = client.delete(f"{base}/books/{ids['book_a']}")
        check("5. kitap DELETE → 200", r.status_code == 200, f"{r.status_code}: {r.text[:150]}")

        # ---- 6: öğrenci geçmişi duruyor
        r = client.get(f"/api/v2/teacher/students/{ids['s1']}/day?date={ids['today'].isoformat()}")
        ok = r.status_code == 200 and any(
            t["id"] == ids["task"] for t in r.json().get("tasks", []))
        check("6. gün görünümü 200 + görev geçmişte duruyor", ok,
              f"{r.status_code}")

        # ---- 7-8: aktif rezervli kitapta guard'lar bozulmadı
        r = client.delete(f"{base}/books/{ids['book_b']}/sections/{ids['secs_b'][0]}")
        check("7. aktif rezervli bölüm DELETE → 409 has_progress",
              r.status_code == 409, str(r.status_code))
        r = client.post(f"{base}/books/{ids['book_b']}/clear-sections")
        check("8. aktif rezervli clear-sections → 409", r.status_code == 409, str(r.status_code))

        # ---- 9: helper koparılan sayısı (birim)
        from app.routes.api_v2.library import _detach_task_items_for_sections
        with SessionLocal() as db:
            b = db.get(Book, ids["book_b"])
            n = _detach_task_items_for_sections(db, b, list(b.sections or []))
            db.rollback()
            check("9. helper: kalemsiz kitapta 0 döner", n == 0, str(n))

        # ---- 10: yabancı koç
        get_login_limiter().reset()
        r = client.post("/api/v2/auth/login", json={"email": T2, "password": PASSWORD})
        assert r.status_code == 200
        r = client.delete(f"{base}/books/{ids['book_b']}")
        check("10. yabancı koç kitabı silemez (404)", r.status_code == 404, str(r.status_code))
    finally:
        _cleanup(ids)

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print("  FAIL:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
