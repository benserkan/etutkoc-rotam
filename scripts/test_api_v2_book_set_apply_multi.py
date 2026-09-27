"""Kitap setini birden çok öğrenciye uygula (2026-09-27, kurum toplu kurulumu 2/4).

  1. apply-candidates: aktif öğrenciler + şube + sınıf uygunluğu + zaten atalı sayısı
  2. apply: 3 öğrenci → setin 2 kitabı her birine; SectionProgress 0-baseline
  3. zaten atalı kitap atlanır (already), arşivli kitap arşivden çıkar
  4. idempotent — ikinci basış 0 yeni atama
  5. başka koçun öğrencisi skipped_invalid; başka koçun seti 404
  6. invalidate öğrenci öneklerini içerir
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookSet, BookSetItem, BookType, SectionProgress, StudentBook, Subject,
    User, UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"bsam_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Set Koç", role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Diğer", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()

        def st(name, grade, grp, teacher=coach, grad=False):
            u = User(email=f"{PFX}_{name}@test.invalid", password_hash=hash_password(PWD),
                     full_name=name, role=UserRole.STUDENT, is_active=True,
                     teacher_id=teacher.id, grade_level=grade, class_group=grp, is_graduate=grad)
            db.add(u)
            db.flush()
            return u

        a, b, c = st("A", 10, "10-A"), st("B", 10, "10-A"), st("C", 11, "11-B")
        m = st("M", None, "Mezun", grad=True)
        x = st("X", 10, None, teacher=other)
        subj = db.query(Subject).filter(Subject.is_builtin.is_(True)).first()
        books = []
        for i in range(2):
            bk = Book(name=f"Set Kitap {i} {PFX}", subject_id=subj.id, teacher_id=coach.id,
                      type=BookType.SORU_BANKASI)
            db.add(bk)
            db.flush()
            for j in range(3):
                db.add(BookSection(book_id=bk.id, label=f"Ü{j}", test_count=5, order=j))
            books.append(bk)
        bs = BookSet(teacher_id=coach.id, name=f"10. sınıf seti {PFX}",
                     target_grade_min=9, target_grade_max=10)
        obs = BookSet(teacher_id=other.id, name=f"Yabancı {PFX}")
        db.add_all([bs, obs])
        db.flush()
        for i, bk in enumerate(books):
            db.add(BookSetItem(set_id=bs.id, book_id=bk.id, order=i))
        db.flush()
        # B'ye kitap0 zaten atalı; C'ye kitap1 ARŞİVLİ atalı
        db.add(StudentBook(student_id=b.id, book_id=books[0].id))
        db.add(StudentBook(student_id=c.id, book_id=books[1].id,
                           archived_at=datetime.now(timezone.utc)))
        db.commit()
        return {"coach": coach.id, "other": other.id, "email": coach.email,
                "a": a.id, "b": b.id, "c": c.id, "m": m.id, "x": x.id,
                "books": [bk.id for bk in books], "set": bs.id, "oset": obs.id}


def cleanup(d):
    with SessionLocal() as db:
        sids = [d[k] for k in ("a", "b", "c", "m", "x")]
        sbs = [s.id for s in db.query(StudentBook).filter(StudentBook.student_id.in_(sids))]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs or [0])))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(sids)))
        db.execute(sa_delete(BookSetItem).where(BookSetItem.set_id.in_([d["set"], d["oset"]])))
        db.execute(sa_delete(BookSet).where(BookSet.id.in_([d["set"], d["oset"]])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(d["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(d["books"])))
        db.execute(sa_delete(User).where(User.id.in_(sids + [d["coach"], d["other"]])))
        db.commit()


def main() -> int:
    print(f"\n=== Seti çok öğrenciye uygula — {PFX} ===\n")
    get_login_limiter().reset()
    d = seed()
    try:
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": d["email"], "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/library/book-sets/{d['set']}"
        r = c.get(f"{base}/apply-candidates")
        cand = r.json()
        rows = {s["student_id"]: s for s in cand["students"]}
        check("1. aday listesi yalnız koçun öğrencileri (4)", set(rows) == {d["a"], d["b"], d["c"], d["m"]},
              str(list(rows)))
        check("2. şube + sınıf uygunluğu",
              rows[d["a"]]["class_group"] == "10-A" and rows[d["a"]]["fits_grade"]
              and not rows[d["c"]]["fits_grade"] and not rows[d["m"]]["fits_grade"], str(rows[d["c"]]))
        check("3. zaten atalı sayısı (B=1, C arşivli=0)",
              rows[d["b"]]["already_count"] == 1 and rows[d["c"]]["already_count"] == 0
              and cand["set_book_count"] == 2)

        r = c.post(f"{base}/apply", json={"student_ids": [d["a"], d["b"], d["c"], d["x"]]})
        res = r.json()
        by = {s["student_id"]: s for s in res["data"]["students"]}
        check("4. A'ya 2 kitap atandı", by[d["a"]]["assigned_count"] == 2, str(by.get(d["a"])))
        check("5. B: 1 atandı + 1 zaten vardı",
              by[d["b"]]["assigned_count"] == 1 and by[d["b"]]["already_count"] == 1)
        check("6. C: 1 atandı + 1 arşivden çıktı",
              by[d["c"]]["assigned_count"] == 1 and by[d["c"]]["unarchived_count"] == 1)
        check("7. başka koçun öğrencisi skipped_invalid", res["data"]["skipped_invalid_ids"] == [d["x"]])
        check("8. invalidate öğrenci önekini içerir",
              f"teacher:{d['coach']}:students:{d['a']}" in res["invalidate"])
        with SessionLocal() as db:
            sb = db.query(StudentBook).filter(StudentBook.student_id == d["a"],
                                              StudentBook.book_id == d["books"][0]).one()
            n = db.query(SectionProgress).filter(SectionProgress.student_book_id == sb.id).count()
            check("9. SectionProgress 0-baseline (3 bölüm)", n == 3, str(n))
            arch = db.query(StudentBook).filter(StudentBook.student_id == d["c"],
                                                StudentBook.book_id == d["books"][1]).one()
            check("10. arşivli atama açıldı", arch.archived_at is None)
        r = c.post(f"{base}/apply", json={"student_ids": [d["a"], d["b"], d["c"]]})
        check("11. idempotent — ikinci basış 0 atama", r.json()["data"]["assigned_total"] == 0)
        r = c.post(f"/api/v2/teacher/library/book-sets/{d['oset']}/apply", json={"student_ids": [d["a"]]})
        check("12. başka koçun seti 404", r.status_code == 404, str(r.status_code))
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
