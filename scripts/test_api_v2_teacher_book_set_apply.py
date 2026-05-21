"""API v2 öğretmen 5d.3 smoke — bulk assign + book-set student aggregation.

Senaryolar (12):
   1. POST /students/{id}/books/bulk happy (3 kitap → 3 atanır)
   2. POST /students/{id}/books/bulk idempotent (aynı 3 kitap → 0 atanır, 3 skipped_already)
   3. POST /students/{id}/books/bulk başkasının kitabı → skipped_invalid'da
   4. POST /students/{id}/books/bulk başkasının öğrencisi → 404
   5. POST /students/{id}/books/bulk boş liste → 200 / 0 atama
   6. GET /library/book-sets → set'in student_count=1
   7. GET /library/book-sets → grade_distribution doluu (8. sınıf:1)
   8. GET /library/book-sets/{id} → assigned_students listesinde öğrenci var
   9. GET /library/book-sets/{id} → assigned_book_count = set boyutu
  10. İkinci öğrenciye atama sonrası student_count=2
  11. Cross-tenant: başka öğretmenin set'i → 404
  12. Atanmamış kitap (set dışı) → assigned_students yine etkilenmez (sadece bu set'in kitapları sayılır)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookSet,
    BookSetItem,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2_5d3_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
STUDENT2_EMAIL = f"{PFX}_s2@test.invalid"
OTHER_STUDENT_EMAIL = f"{PFX}_os@test.invalid"
PASSWORD = "TestPass123!@xyz"

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
    with SessionLocal() as db:
        # İki öğretmen + üç öğrenci (1 ve 2 ana öğretmenin; 3 başka öğretmenin)
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 5d3 Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer 5d3", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        db.add_all([teacher, other_teacher]); db.flush()
        student1 = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Öğrenci A {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=teacher.id,
        )
        student2 = User(
            email=STUDENT2_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Öğrenci B {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=7, teacher_id=teacher.id,
        )
        other_student = User(
            email=OTHER_STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Diğer Öğrenci {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=other_teacher.id,
        )
        db.add_all([student1, student2, other_student])
        db.flush()

        # Subject: builtin "Matematik" zaten var, ona göre id alalım. Yoksa oluştur.
        subj = db.query(Subject).filter(Subject.name == "Matematik").first()
        if not subj:
            subj = Subject(name="Matematik", is_builtin=True)
            db.add(subj); db.flush()

        # Üç kitap (teacher) + 1 kitap (other_teacher), her birinin 1 section'ı
        teacher_books = []
        for i in range(3):
            b = Book(
                teacher_id=teacher.id, subject_id=subj.id,
                name=f"Kitap-{PFX}-{i}", type=BookType.SORU_BANKASI,
            )
            db.add(b); db.flush()
            db.add(BookSection(book_id=b.id, label=f"Bölüm {i+1}", test_count=10, order=1))
            teacher_books.append(b)
        other_book = Book(
            teacher_id=other_teacher.id, subject_id=subj.id,
            name=f"OtherKitap-{PFX}", type=BookType.SORU_BANKASI,
        )
        db.add(other_book); db.flush()
        db.add(BookSection(book_id=other_book.id, label="Bölüm 1", test_count=10, order=1))

        # Set (teacher) — 3 kitabı set içine al
        bs = BookSet(teacher_id=teacher.id, name=f"Set-{PFX}")
        db.add(bs); db.flush()
        for i, b in enumerate(teacher_books):
            db.add(BookSetItem(set_id=bs.id, book_id=b.id, order=i))

        # Başka öğretmenin de bir seti olsun (cross-tenant 404 test'i için)
        other_bs = BookSet(teacher_id=other_teacher.id, name=f"OtherSet-{PFX}")
        db.add(other_bs)

        db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_id": student1.id,
            "student2_id": student2.id,
            "other_student_id": other_student.id,
            "subject_id": subj.id,
            "book_ids": [b.id for b in teacher_books],
            "other_book_id": other_book.id,
            "set_id": bs.id,
            "other_set_id": other_bs.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        # Section progress → student books → book set items → books → sets → users
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id.in_(
                db.query(StudentBook.id).filter(
                    StudentBook.student_id.in_([
                        seed["student_id"], seed["student2_id"], seed["other_student_id"],
                    ])
                ).subquery().element
            )
        ))
        db.execute(sa_delete(StudentBook).where(
            StudentBook.student_id.in_([
                seed["student_id"], seed["student2_id"], seed["other_student_id"],
            ])
        ))
        db.execute(sa_delete(BookSetItem).where(
            BookSetItem.set_id.in_([seed["set_id"], seed["other_set_id"]])
        ))
        db.execute(sa_delete(BookSet).where(
            BookSet.id.in_([seed["set_id"], seed["other_set_id"]])
        ))
        db.execute(sa_delete(BookSection).where(
            BookSection.book_id.in_(seed["book_ids"] + [seed["other_book_id"]])
        ))
        db.execute(sa_delete(Book).where(
            Book.id.in_(seed["book_ids"] + [seed["other_book_id"]])
        ))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["teacher_id"], seed["other_teacher_id"],
            seed["student_id"], seed["student2_id"], seed["other_student_id"],
        ])))
        db.commit()


def _login(client: TestClient, email: str) -> int:
    return client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD}).status_code


def main() -> int:
    print(f"\n=== API v2 /teacher 5d.3 (bulk assign + book-set student agg) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()

    try:
        client = TestClient(app)
        assert _login(client, TEACHER_EMAIL) == 200

        sid = seed["student_id"]
        sid2 = seed["student2_id"]
        oid = seed["other_student_id"]
        bids = seed["book_ids"]
        other_bid = seed["other_book_id"]
        set_id = seed["set_id"]
        other_set_id = seed["other_set_id"]

        # 1) Happy bulk → 3 atandı
        r = client.post(
            f"/api/v2/teacher/students/{sid}/books/bulk",
            json={"book_ids": bids},
        )
        data = r.json().get("data", {}) if r.text else {}
        ok = (
            r.status_code == 200
            and data.get("assigned_count") == 3
            and data.get("skipped_already_ids") == []
            and data.get("skipped_invalid_ids") == []
        )
        check("1. bulk assign happy (3 kitap)", ok,
              f"status={r.status_code} count={data.get('assigned_count')}")

        # 2) Idempotent
        r = client.post(
            f"/api/v2/teacher/students/{sid}/books/bulk",
            json={"book_ids": bids},
        )
        data = r.json().get("data", {})
        ok = (
            r.status_code == 200
            and data.get("assigned_count") == 0
            and sorted(data.get("skipped_already_ids", [])) == sorted(bids)
            and data.get("skipped_invalid_ids") == []
        )
        check("2. bulk assign idempotent", ok,
              f"already={data.get('skipped_already_ids')}")

        # 3) Başkasının kitabı → skipped_invalid
        r = client.post(
            f"/api/v2/teacher/students/{sid2}/books/bulk",
            json={"book_ids": [other_bid, bids[0]]},
        )
        data = r.json().get("data", {})
        ok = (
            r.status_code == 200
            and other_bid in (data.get("skipped_invalid_ids") or [])
            and data.get("assigned_count") == 1  # bids[0] atandı (öğrenci2 için yeni)
        )
        check("3. bulk assign başkasının kitabı → skipped_invalid", ok,
              f"invalid={data.get('skipped_invalid_ids')} count={data.get('assigned_count')}")

        # 4) Başkasının öğrencisi → 404
        r = client.post(
            f"/api/v2/teacher/students/{oid}/books/bulk",
            json={"book_ids": bids},
        )
        ok = r.status_code == 404
        check("4. bulk assign başkasının öğrencisi → 404", ok,
              f"status={r.status_code}")

        # 5) Boş liste → 200/0
        r = client.post(
            f"/api/v2/teacher/students/{sid}/books/bulk",
            json={"book_ids": []},
        )
        data = r.json().get("data", {})
        ok = r.status_code == 200 and data.get("assigned_count") == 0
        check("5. bulk assign boş liste", ok, f"status={r.status_code}")

        # 6-7) GET /book-sets — student_count + grade_distribution
        r = client.get("/api/v2/teacher/library/book-sets")
        items = (r.json() or {}).get("items", []) if r.text else []
        my_set = next((it for it in items if it["id"] == set_id), None)
        ok = (
            r.status_code == 200
            and my_set is not None
            and my_set.get("student_count") == 2  # öğrenci 1 (3 kitap) + öğrenci 2 (1 kitap)
        )
        check("6. /book-sets student_count=2", ok,
              f"got={my_set.get('student_count') if my_set else None}")

        gd = (my_set or {}).get("grade_distribution") or []
        grade_map = {(b["grade_level"], b["is_graduate"]): b["student_count"] for b in gd}
        ok = (
            grade_map.get((8, False)) == 1
            and grade_map.get((7, False)) == 1
        )
        check("7. /book-sets grade_distribution (7:1, 8:1)", ok, f"map={grade_map}")

        # 8-9) GET /book-sets/{id} — assigned_students + assigned_book_count
        r = client.get(f"/api/v2/teacher/library/book-sets/{set_id}")
        body = r.json() if r.text else {}
        assigned = body.get("assigned_students", [])
        student_a = next((a for a in assigned if a["student_id"] == sid), None)
        student_b = next((a for a in assigned if a["student_id"] == sid2), None)
        ok = (
            r.status_code == 200
            and len(assigned) == 2
            and student_a is not None
            and student_b is not None
        )
        check("8. /book-sets/{id} assigned_students içerir", ok,
              f"len={len(assigned)} a={bool(student_a)} b={bool(student_b)}")

        ok = (
            student_a and student_a.get("assigned_book_count") == 3
            and student_b and student_b.get("assigned_book_count") == 1
        )
        check("9. assigned_book_count doğru (A=3, B=1)", ok,
              f"a={student_a and student_a.get('assigned_book_count')} b={student_b and student_b.get('assigned_book_count')}")

        # 10) Öğrenci B'ye kalan 2 kitabı da bulk ile uygula → student_count yine 2
        r = client.post(
            f"/api/v2/teacher/students/{sid2}/books/bulk",
            json={"book_ids": bids},  # bids[0] zaten atalı; bids[1], bids[2] yeni
        )
        data = r.json().get("data", {})
        ok = (
            r.status_code == 200
            and data.get("assigned_count") == 2
            and bids[0] in (data.get("skipped_already_ids") or [])
        )
        check("10. Öğrenci B kalan kitapları al → 2 yeni", ok,
              f"count={data.get('assigned_count')} already={data.get('skipped_already_ids')}")

        # 11) Cross-tenant: başka öğretmenin set'i → 404
        r = client.get(f"/api/v2/teacher/library/book-sets/{other_set_id}")
        ok = r.status_code == 404
        check("11. Cross-tenant set → 404", ok, f"status={r.status_code}")

        # 12) Set'in kitaplarını tam alan öğrenci B → assigned_book_count=3
        r = client.get(f"/api/v2/teacher/library/book-sets/{set_id}")
        body = r.json()
        assigned = body.get("assigned_students", [])
        student_b = next((a for a in assigned if a["student_id"] == sid2), None)
        ok = student_b is not None and student_b.get("assigned_book_count") == 3
        check("12. Set tamamı alındığında assigned_book_count=3", ok,
              f"b={student_b and student_b.get('assigned_book_count')}")

    finally:
        _cleanup(seed)
        print("\n  cleanup OK\n")

    total = passed + len(failed)
    print(f"\n=== SONUÇ: {passed}/{total} PASS ===")
    if failed:
        for f in failed:
            print(f"  ✗ {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
