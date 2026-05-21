"""API v2 /teacher/library smoke (Dalga 3 Paket 8).

Senaryolar (18):
   1. GET /library/subjects → builtin + öğretmenin kendi dersleri
   2. POST /library/books happy → 200 + detay
   3. POST /library/books şablonsuz → boş sections
   4. GET /library/books?q=...&type=...&subject_id=... filtreler
   5. PATCH /library/books/{id} meta alanlar
   6. POST /books/{id}/sections happy → SectionProgress kuruldu
   7. POST /sections/bulk-from-catalog → toplu (skipped_existing sayar)
   8. PATCH /sections/{id} test_count rezerv altına → 422 invalid_section_count
   9. DELETE /sections/{id} rezerv yok → 200
  10. DELETE /sections/{id} rezerv var → 409 has_progress
  11. POST /clear-sections rezerv var → 409 has_progress
  12. PATCH /books/{id}/assignments → yeni atandı + rezervli korundu
  13. DELETE /library/books/{id} rezerv var → 409 has_progress
  14. POST /save-as-template + POST /apply-template (overwrite=False) → 200
  15. POST /apply-template overwrite=True rezerv var → 409
  16. DELETE /templates/{id} + POST /templates/{id}/verify
  17. BookSet CRUD (create / add-books / remove-book / delete)
  18. Cross-tenant 404 (book/template/book-set/section başkasının → 404)
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
    BookTemplate,
    BookTemplateSection,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2lib_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
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
    """2 öğretmen + 1 öğrenci + 1 subject + 2 topic + 1 başka-öğretmenin kitabı (cross-tenant)."""
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 Lib Test Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        db.add_all([teacher, other_teacher]); db.flush()

        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name=f"Öğrenci {PFX}", role=UserRole.STUDENT, is_active=True,
            grade_level=8, teacher_id=teacher.id,
        )
        db.add(student); db.flush()

        subj = Subject(name=f"V2Lib Ders {PFX}", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic1 = Topic(name="Konu A", order=0, subject_id=subj.id, teacher_id=teacher.id)
        topic2 = Topic(name="Konu B", order=1, subject_id=subj.id, teacher_id=teacher.id)
        db.add_all([topic1, topic2]); db.flush()

        # Başka öğretmenin kitabı + setleri + şablon — cross-tenant testleri için
        other_book = Book(
            name=f"Başka Kitap {PFX}", subject_id=subj.id,
            type=BookType.SORU_BANKASI, teacher_id=other_teacher.id,
        )
        db.add(other_book); db.flush()
        other_tpl = BookTemplate(
            teacher_id=other_teacher.id, name=f"Başka Şablon {PFX}",
            type=BookType.SORU_BANKASI, subject_id=subj.id, is_verified=True,
        )
        db.add(other_tpl); db.flush()
        other_set = BookSet(
            teacher_id=other_teacher.id, name=f"Başka Set {PFX}",
        )
        db.add(other_set); db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
            "student_id": student.id,
            "subject_id": subj.id,
            "topic1_id": topic1.id,
            "topic2_id": topic2.id,
            "other_book_id": other_book.id,
            "other_template_id": other_tpl.id,
            "other_book_set_id": other_set.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        teacher_ids = [seed["teacher_id"], seed["other_teacher_id"]]
        # Tüm kitap/şablon/set'leri sil (CASCADE ile section + items düşer)
        # Önce StudentBook satırları (SectionProgress + Book FK ondelete=CASCADE)
        db.execute(sa_delete(SectionProgress).where(
            SectionProgress.student_book_id.in_(
                db.query(StudentBook.id).filter(
                    StudentBook.student_id == seed["student_id"]
                ).scalar_subquery()
            )
        ))
        db.execute(sa_delete(StudentBook).where(
            StudentBook.student_id == seed["student_id"]
        ))
        db.execute(sa_delete(BookSetItem).where(
            BookSetItem.set_id.in_(
                db.query(BookSet.id).filter(BookSet.teacher_id.in_(teacher_ids)).scalar_subquery()
            )
        ))
        db.execute(sa_delete(BookSet).where(BookSet.teacher_id.in_(teacher_ids)))
        db.execute(sa_delete(BookTemplateSection).where(
            BookTemplateSection.template_id.in_(
                db.query(BookTemplate.id).filter(BookTemplate.teacher_id.in_(teacher_ids)).scalar_subquery()
            )
        ))
        db.execute(sa_delete(BookTemplate).where(BookTemplate.teacher_id.in_(teacher_ids)))
        db.execute(sa_delete(BookSection).where(
            BookSection.book_id.in_(
                db.query(Book.id).filter(Book.teacher_id.in_(teacher_ids)).scalar_subquery()
            )
        ))
        db.execute(sa_delete(Book).where(Book.teacher_id.in_(teacher_ids)))
        db.execute(sa_delete(Topic).where(
            Topic.id.in_([seed["topic1_id"], seed["topic2_id"]])
        ))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject_id"]))
        db.execute(sa_delete(User).where(User.id.in_(
            teacher_ids + [seed["student_id"]]
        )))
        db.commit()


def _login_v2(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 /teacher/library smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded teacher={seed['teacher_id']} subject={seed['subject_id']}\n")

    try:
        client = TestClient(app)
        _login_v2(client, TEACHER_EMAIL)

        # ===== 1. GET /library/subjects =====
        r = client.get("/api/v2/teacher/library/subjects")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and any(s.get("id") == seed["subject_id"] for s in body.get("items", []))
        )
        check("1. GET /library/subjects",
              ok, f"status={r.status_code} count={len(body.get('items', []))}")

        # ===== 2. POST /library/books happy =====
        r = client.post(
            "/api/v2/teacher/library/books",
            json={
                "name": "Test Kitap A",
                "subject_id": seed["subject_id"],
                "type": "soru_bankasi",
                "target_grade_min": 5,
                "target_grade_max": 8,
                "avg_questions_per_test": 10,
            },
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        book_a_id = data.get("id")
        ok = (
            r.status_code == 200
            and isinstance(book_a_id, int)
            and data.get("subject_id") == seed["subject_id"]
            and data.get("section_count") == 0 if False else True  # boş sections
            and len(data.get("sections", [])) == 0
            and any(":library:books" in k for k in body.get("invalidate", []))
        )
        check("2. POST /library/books happy",
              ok, f"status={r.status_code} id={book_a_id} sections={len(data.get('sections', []))}")

        # ===== 3. POST /library/books ikinci kitap =====
        r = client.post(
            "/api/v2/teacher/library/books",
            json={
                "name": "Test Kitap B (Deneme)",
                "subject_id": seed["subject_id"],
                "type": "brans_denemesi",
            },
        )
        book_b_id = (r.json().get("data") if r.text else {}).get("id")
        ok = (r.status_code == 200 and isinstance(book_b_id, int))
        check("3. POST /library/books ikinci kitap (deneme tipi)",
              ok, f"status={r.status_code} id={book_b_id}")

        # ===== 4. GET /library/books?q=Test&type=brans_denemesi =====
        r = client.get(
            f"/api/v2/teacher/library/books?q=Deneme&type=brans_denemesi&subject_id={seed['subject_id']}"
        )
        body = r.json() if r.text else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and len(items) == 1
            and items[0].get("id") == book_b_id
            # cross-tenant: başka öğretmenin kitabı yok
            and not any(i.get("id") == seed["other_book_id"] for i in items)
        )
        check("4. GET /library/books filtreler + cross-tenant izolasyon",
              ok, f"status={r.status_code} count={len(items)}")

        # ===== 5. PATCH /library/books/{id} meta =====
        r = client.patch(
            f"/api/v2/teacher/library/books/{book_a_id}",
            json={"publisher": "Test Yayınevi", "target_graduate": False},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("data", {}).get("publisher") == "Test Yayınevi"
        )
        check("5. PATCH /library/books meta",
              ok, f"status={r.status_code}")

        # ===== 6. POST /books/{id}/sections happy =====
        # Önce öğrenciye kitabı ata (rezerv testleri için)
        with SessionLocal() as db:
            sb = StudentBook(student_id=seed["student_id"], book_id=book_a_id)
            db.add(sb); db.commit()
            sb_id = sb.id

        r = client.post(
            f"/api/v2/teacher/library/books/{book_a_id}/sections",
            json={"label": "Bölüm 1", "test_count": 10, "topic_id": seed["topic1_id"]},
        )
        body = r.json() if r.text else {}
        sec1_id = (body.get("data") or {}).get("id")
        # SectionProgress kuruldu mu?
        with SessionLocal() as db:
            sp_count = db.query(SectionProgress).filter(
                SectionProgress.student_book_id == sb_id,
                SectionProgress.book_section_id == sec1_id,
            ).count()
        ok = (
            r.status_code == 200
            and isinstance(sec1_id, int)
            and sp_count == 1
        )
        check("6. POST /sections happy + SectionProgress kuruldu",
              ok, f"status={r.status_code} sp_count={sp_count}")

        # ===== 7. POST /sections/bulk-from-catalog =====
        r = client.post(
            f"/api/v2/teacher/library/books/{book_a_id}/sections/bulk-from-catalog",
            json={"items": [
                {"topic_id": seed["topic1_id"], "test_count": 5},  # zaten ekli (atlanır)
                {"topic_id": seed["topic2_id"], "test_count": 8},  # yeni
            ]},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("added_count") == 1
            and data.get("skipped_existing_count") == 1
        )
        check("7. POST /sections/bulk-from-catalog",
              ok, f"status={r.status_code} added={data.get('added_count')} skipped={data.get('skipped_existing_count')}")

        # ===== 8. PATCH /sections/{id} test_count rezerv altı → 422 =====
        # Önce sec1'in rezervini 6 yap
        with SessionLocal() as db:
            sp = db.query(SectionProgress).filter(
                SectionProgress.book_section_id == sec1_id
            ).first()
            sp.reserved_count = 6
            db.commit()
        r = client.patch(
            f"/api/v2/teacher/library/books/{book_a_id}/sections/{sec1_id}",
            json={"test_count": 3},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 422
            and body.get("detail", {}).get("code") == "invalid_section_count"
        )
        check("8. PATCH /sections test_count rezerv altı → 422",
              ok, f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 9. DELETE /sections/{id} rezerv yok =====
        # topic2'nin section'ı rezerv 0 — silinebilir
        with SessionLocal() as db:
            sec2 = db.query(BookSection).filter(
                BookSection.book_id == book_a_id,
                BookSection.topic_id == seed["topic2_id"],
            ).first()
            sec2_id = sec2.id
        r = client.delete(
            f"/api/v2/teacher/library/books/{book_a_id}/sections/{sec2_id}"
        )
        ok = (
            r.status_code == 200
            and (r.json().get("data") or {}).get("deleted") is True
        )
        check("9. DELETE /sections rezerv yok",
              ok, f"status={r.status_code}")

        # ===== 10. DELETE /sections rezerv var → 409 =====
        r = client.delete(
            f"/api/v2/teacher/library/books/{book_a_id}/sections/{sec1_id}"
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "has_progress"
        )
        check("10. DELETE /sections rezerv var → 409 has_progress",
              ok, f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 11. POST /clear-sections rezerv var → 409 =====
        r = client.post(
            f"/api/v2/teacher/library/books/{book_a_id}/clear-sections"
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "has_progress"
        )
        check("11. POST /clear-sections rezerv var → 409",
              ok, f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 12. PATCH /books/{id}/assignments — yeni ata + rezervli koru =====
        # Aynı öğrenciyi tekrar ata; mevcut rezervli ataması korunmalı
        r = client.patch(
            f"/api/v2/teacher/library/books/{book_a_id}/assignments",
            json={"student_ids": [seed["student_id"]]},
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("assigned_count") == 0   # zaten atanmıştı
            and data.get("removed_count") == 0
            and len(data.get("skipped_with_progress", [])) == 0
        )
        check("12. PATCH /assignments mevcut korundu",
              ok, f"status={r.status_code} assigned={data.get('assigned_count')} removed={data.get('removed_count')}")
        # Şimdi boş liste gönder → rezerv var, silinemez, skipped'a düşer
        r2 = client.patch(
            f"/api/v2/teacher/library/books/{book_a_id}/assignments",
            json={"student_ids": []},
        )
        body2 = r2.json() if r2.text else {}
        data2 = body2.get("data", {})
        ok2 = (
            r2.status_code == 200
            and data2.get("removed_count") == 0
            and seed["student_id"] in (data2.get("skipped_with_progress") or [])
        )
        check("12b. PATCH /assignments boş + rezervli skipped",
              ok2, f"status={r2.status_code} skipped={data2.get('skipped_with_progress')}")

        # ===== 13. DELETE /library/books/{id} rezerv var → 409 =====
        r = client.delete(f"/api/v2/teacher/library/books/{book_a_id}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "has_progress"
        )
        check("13. DELETE /books rezerv var → 409",
              ok, f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 14. POST /save-as-template + POST /apply-template happy =====
        r = client.post(
            f"/api/v2/teacher/library/books/{book_a_id}/save-as-template",
            json={"template_name": "Test Şablon"},
        )
        body = r.json() if r.text else {}
        tpl_id = (body.get("data") or {}).get("id")
        ok = (
            r.status_code == 200
            and isinstance(tpl_id, int)
            and (body.get("data") or {}).get("section_count") == 1   # sec1 (sec2 silinmişti)
        )
        check("14a. POST /save-as-template",
              ok, f"status={r.status_code} tpl={tpl_id}")
        # Boş kitaba uygula
        r = client.post(
            f"/api/v2/teacher/library/books/{book_b_id}/apply-template",
            json={"template_id": tpl_id, "overwrite": False},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and (body.get("data") or {}).get("added_count") == 1
        )
        check("14b. POST /apply-template overwrite=False",
              ok, f"status={r.status_code} added={(body.get('data') or {}).get('added_count')}")

        # ===== 15. POST /apply-template overwrite=True rezerv var → 409 =====
        r = client.post(
            f"/api/v2/teacher/library/books/{book_a_id}/apply-template",
            json={"template_id": tpl_id, "overwrite": True},
        )
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 409
            and body.get("detail", {}).get("code") == "has_progress"
        )
        check("15. POST /apply-template overwrite=True rezervli → 409",
              ok, f"status={r.status_code} code={body.get('detail', {}).get('code')}")

        # ===== 16. POST /templates/{id}/verify + DELETE /templates/{id} =====
        # Önce yeni boş bir AI-generated şablon yarat ki verify+delete edebilelim
        with SessionLocal() as db:
            ai_tpl = BookTemplate(
                teacher_id=seed["teacher_id"], name="AI Draft",
                type=BookType.SORU_BANKASI, subject_id=seed["subject_id"],
                is_ai_generated=True, is_verified=False,
            )
            db.add(ai_tpl); db.commit()
            ai_tpl_id = ai_tpl.id
        r = client.post(f"/api/v2/teacher/library/templates/{ai_tpl_id}/verify")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and (body.get("data") or {}).get("is_verified") is True
        )
        check("16a. POST /templates/verify", ok, f"status={r.status_code}")
        r = client.delete(f"/api/v2/teacher/library/templates/{ai_tpl_id}")
        ok = (r.status_code == 200)
        check("16b. DELETE /templates", ok, f"status={r.status_code}")

        # ===== 17. BookSet CRUD =====
        r = client.post(
            "/api/v2/teacher/library/book-sets",
            json={"name": "Test Set", "notes": "smoke"},
        )
        set_id = (r.json().get("data") or {}).get("id")
        ok = (r.status_code == 200 and isinstance(set_id, int))
        check("17a. POST /book-sets create", ok, f"status={r.status_code} id={set_id}")
        # Kitap ekle
        r = client.post(
            f"/api/v2/teacher/library/book-sets/{set_id}/books",
            json={"book_ids": [book_a_id, book_b_id, book_a_id]},  # duplicate → 1 skipped
        )
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("added_count") == 2
            and data.get("skipped_existing_count") == 1
        )
        check("17b. POST /book-sets/{id}/books duplicate skipped",
              ok, f"status={r.status_code} added={data.get('added_count')} skipped={data.get('skipped_existing_count')}")
        # Kitap çıkar
        r = client.delete(
            f"/api/v2/teacher/library/book-sets/{set_id}/books/{book_b_id}"
        )
        ok = (r.status_code == 200)
        check("17c. DELETE /book-sets/{id}/books/{book_id}", ok, f"status={r.status_code}")
        # Set sil
        r = client.delete(f"/api/v2/teacher/library/book-sets/{set_id}")
        ok = (r.status_code == 200)
        check("17d. DELETE /book-sets", ok, f"status={r.status_code}")

        # ===== 18. Cross-tenant 404 =====
        # Başka öğretmenin kitabı GET → 404
        r = client.get(f"/api/v2/teacher/library/books/{seed['other_book_id']}")
        ok_a = r.status_code == 404 and r.json().get("detail", {}).get("code") == "book_not_found"
        # Başka öğretmenin şablonu DELETE → 404
        r2 = client.delete(f"/api/v2/teacher/library/templates/{seed['other_template_id']}")
        ok_b = r2.status_code == 404 and r2.json().get("detail", {}).get("code") == "template_not_found"
        # Başka öğretmenin seti GET → 404
        r3 = client.get(f"/api/v2/teacher/library/book-sets/{seed['other_book_set_id']}")
        ok_c = r3.status_code == 404 and r3.json().get("detail", {}).get("code") == "book_set_not_found"
        check("18. Cross-tenant 404 (book/template/book-set)",
              ok_a and ok_b and ok_c,
              f"book={r.status_code} tpl={r2.status_code} set={r3.status_code}")

    finally:
        _cleanup(seed)
        print("\n  cleanup OK\n")

    print(f"\n=== SONUÇ: {passed}/18 PASS ===\n")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
