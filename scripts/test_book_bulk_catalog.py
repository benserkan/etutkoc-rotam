"""Toplu kataloğdan ünite ekleme + atama baseline smoke test.

Senaryolar:
1. Hazır subject + topic oluştur
2. Boş kitap oluştur (soru bankası)
3. POST /sections/bulk-from-catalog → 5 topic seçili, 3'ünü gönder, 12 test/her biri
4. BookSection 3 adet eklenmiş, label = topic.name, test_count = 12
5. Aynı endpoint tekrar çağır, aynı 3 topic + yeni 1 topic → sadece 1 yeni eklendi
6. Atanmış öğrenci varken bulk-from-catalog yeni ünite eklerse SectionProgress da açılmış mı
7. Atama modal — önceden çözülmüş baseline girişi: completed_count = baseline
8. Baseline > section.test_count clamp test
9. Negatif baseline → 0
10. Modal HTML'inde baseline input alanı render edilmiş mi
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_teacher
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    Topic,
    User,
    UserRole,
)


PFX = f"_bk_{secrets.token_hex(3)}"
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


def main() -> int:
    now = datetime.now(timezone.utc)
    client = TestClient(app)

    with SessionLocal() as db:
        teacher = User(
            email=f"{PFX}_t@test.invalid", password_hash="x" * 60,
            full_name="Bulk Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        db.add(teacher); db.flush()

        student = User(
            email=f"{PFX}_s@test.invalid", password_hash="x" * 60,
            full_name="Bulk Student", role=UserRole.STUDENT,
            teacher_id=teacher.id,
            is_active=True, password_changed_at=now,
        )
        db.add(student); db.flush()

        subject = Subject(
            name=f"{PFX} AYT Mat",
            order=99, is_builtin=False, teacher_id=teacher.id,
        )
        db.add(subject); db.flush()

        topic_names = ["Limit", "Türev", "İntegral", "Trigonometri", "Logaritma"]
        topics: list[Topic] = []
        for i, n in enumerate(topic_names):
            t = Topic(
                subject_id=subject.id, name=n, order=i,
                is_builtin=False, teacher_id=teacher.id,
            )
            db.add(t); topics.append(t)
        db.flush()

        book = Book(
            teacher_id=teacher.id, subject_id=subject.id,
            name=f"{PFX} Test Bankası",
            type=BookType.SORU_BANKASI,
            avg_questions_per_test=10,
        )
        db.add(book); db.flush()

        sb = StudentBook(student_id=student.id, book_id=book.id)
        db.add(sb)
        db.commit()

        teacher_id, student_id = teacher.id, student.id
        book_id = book.id
        topic_ids = [t.id for t in topics]

    def teacher_override():
        with SessionLocal() as _db:
            u = (
                _db.query(User)
                .options(joinedload(User.institution))
                .filter(User.id == teacher_id)
                .first()
            )
            if u is not None:
                if u.institution is not None:
                    _db.expunge(u.institution)
                _db.expunge(u)
            return u

    app.dependency_overrides[require_teacher] = teacher_override
    app.dependency_overrides[get_current_user] = teacher_override

    # ============ STEP 1: GET book detail page renders catalog block ============
    print("\n=== STEP 1: book_detail render — toplu kataloğ kartı ===")
    r = client.get(f"/teacher/books/{book_id}")
    check("book_detail 200", r.status_code == 200, f"got {r.status_code}")
    body = r.text
    check("toplu katalog başlığı", "Müfredat kataloğundan toplu ekle" in body)
    check("topic checkbox 5 adet", body.count('name="topic_ids"') == 5)
    check("default test count input", 'name="test_count_' in body)

    # ============ STEP 2: POST 3 topic ile bulk add ============
    print("\n=== STEP 2: 3 topic toplu ekle ===")
    selected = topic_ids[:3]
    payload: dict = {"topic_ids": [str(tid) for tid in selected]}
    for tid in selected:
        payload[f"test_count_{tid}"] = "12"
    r = client.post(
        f"/teacher/books/{book_id}/sections/bulk-from-catalog",
        data=payload, follow_redirects=False,
    )
    check("bulk POST 303", r.status_code == 303, f"got {r.status_code}")
    check("redirect içerir 'eklendi'", "eklendi" in r.headers.get("location", ""))

    with SessionLocal() as db:
        sections = (
            db.query(BookSection)
            .filter(BookSection.book_id == book_id)
            .order_by(BookSection.order)
            .all()
        )
        check("3 BookSection oluştu", len(sections) == 3, f"got {len(sections)}")
        labels = [s.label for s in sections]
        check("label = topic.name (Limit)", "Limit" in labels)
        check("label = topic.name (Türev)", "Türev" in labels)
        check("test_count = 12", all(s.test_count == 12 for s in sections))
        check("topic_id set", all(s.topic_id in selected for s in sections))

        # SectionProgress atanmış öğrenciye açılmış mı
        progresses = (
            db.query(SectionProgress)
            .join(StudentBook, SectionProgress.student_book_id == StudentBook.id)
            .filter(StudentBook.book_id == book_id, StudentBook.student_id == student_id)
            .all()
        )
        check("3 SectionProgress (atanmış öğrenci)", len(progresses) == 3, f"got {len(progresses)}")

    # ============ STEP 3: Tekrar ekle, eski 3 atlansın, 1 yeni eklensin ============
    print("\n=== STEP 3: 4 topic tekrar gönder (3 zaten var, 1 yeni) ===")
    selected2 = topic_ids[:4]  # 0..3, biri yeni (index 3)
    payload2: dict = {"topic_ids": [str(tid) for tid in selected2]}
    for tid in selected2:
        payload2[f"test_count_{tid}"] = "8"
    r = client.post(
        f"/teacher/books/{book_id}/sections/bulk-from-catalog",
        data=payload2, follow_redirects=False,
    )
    check("ikinci bulk POST 303", r.status_code == 303)
    loc = r.headers.get("location", "")
    check("mesajda 'atlandı'", "atland" in loc, f"loc={loc}")

    with SessionLocal() as db:
        sections = db.query(BookSection).filter(BookSection.book_id == book_id).all()
        check("toplam 4 section", len(sections) == 4, f"got {len(sections)}")
        # En son eklenen test_count = 8 olmalı
        new_section = next(
            (s for s in sections if s.topic_id == topic_ids[3]), None
        )
        check("yeni eklenen var", new_section is not None)
        check("yeni section test_count=8", new_section.test_count == 8 if new_section else False)

    # ============ STEP 4: Boş seçim → err ============
    print("\n=== STEP 4: Hiç seçim yok → err redirect ===")
    r = client.post(
        f"/teacher/books/{book_id}/sections/bulk-from-catalog",
        data=[], follow_redirects=False,
    )
    check("boş seçim 303", r.status_code == 303)
    check("err mesajı", "err=" in r.headers.get("location", ""))

    # ============ STEP 5: Yetki — başka teacher'ın kitabı 404 ============
    print("\n=== STEP 5: Başka teacher kitabı 404 ===")
    with SessionLocal() as db:
        other_teacher = User(
            email=f"{PFX}_o@test.invalid", password_hash="x" * 60,
            full_name="Other Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now,
        )
        db.add(other_teacher); db.commit()
        other_id = other_teacher.id

    def other_override():
        with SessionLocal() as _db:
            u = (
                _db.query(User)
                .options(joinedload(User.institution))
                .filter(User.id == other_id)
                .first()
            )
            if u is not None:
                if u.institution is not None:
                    _db.expunge(u.institution)
                _db.expunge(u)
            return u

    app.dependency_overrides[require_teacher] = other_override
    app.dependency_overrides[get_current_user] = other_override
    r = client.post(
        f"/teacher/books/{book_id}/sections/bulk-from-catalog",
        data={"topic_ids": [str(topic_ids[0])]}, follow_redirects=False,
    )
    check("cross-teacher 404", r.status_code == 404, f"got {r.status_code}")
    app.dependency_overrides.clear()

    # ============ STEP 6: Atama baseline akışı ============
    print("\n=== STEP 6: Atama modal — baseline (önceden çözülmüş) ===")
    app.dependency_overrides[require_teacher] = teacher_override
    app.dependency_overrides[get_current_user] = teacher_override

    # Yeni bir öğrenci ve yeni bir kitap (hiç atanmamış) oluştur
    with SessionLocal() as db:
        new_student = User(
            email=f"{PFX}_s2@test.invalid", password_hash="x" * 60,
            full_name="Baseline Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, is_active=True, password_changed_at=now,
        )
        db.add(new_student); db.flush()
        new_student_id = new_student.id

        new_book = Book(
            teacher_id=teacher_id, subject_id=db.query(Subject).filter(
                Subject.teacher_id == teacher_id
            ).first().id,
            name=f"{PFX} Baseline Kitap",
            type=BookType.SORU_BANKASI,
        )
        db.add(new_book); db.flush()
        # 3 ünite, her biri 10 test
        sec1 = BookSection(book_id=new_book.id, label="Ünite 1", test_count=10, order=0)
        sec2 = BookSection(book_id=new_book.id, label="Ünite 2", test_count=10, order=1)
        sec3 = BookSection(book_id=new_book.id, label="Ünite 3", test_count=10, order=2)
        db.add_all([sec1, sec2, sec3])
        db.commit()
        new_book_id = new_book.id
        sec1_id, sec2_id, sec3_id = sec1.id, sec2.id, sec3.id

    # GET student detail — modal HTML render baseline input'u içeriyor mu
    r = client.get(f"/teacher/students/{new_student_id}")
    check("student_detail 200", r.status_code == 200, f"got {r.status_code}")
    body = r.text
    check("baseline_X_Y input render edildi",
          f'name="baseline_{new_book_id}_{sec1_id}"' in body,
          "modal'da kitap için section baseline alanı yok")
    check("baseline expand label gözüküyor",
          "önceden çalışmış mı" in body)

    # POST atama: baseline 3, 5, 0 (3. ünite önceden çözülmemiş)
    payload = {
        "book_ids": [str(new_book_id)],
        f"baseline_{new_book_id}_{sec1_id}": "3",
        f"baseline_{new_book_id}_{sec2_id}": "5",
        f"baseline_{new_book_id}_{sec3_id}": "0",
    }
    r = client.post(
        f"/teacher/students/{new_student_id}/books/assign",
        data=payload, follow_redirects=False,
    )
    check("baseline POST 303", r.status_code == 303, f"got {r.status_code}")

    with SessionLocal() as db:
        sb = (
            db.query(StudentBook)
            .filter(StudentBook.student_id == new_student_id, StudentBook.book_id == new_book_id)
            .first()
        )
        check("StudentBook oluştu", sb is not None)
        progresses = (
            db.query(SectionProgress)
            .filter(SectionProgress.student_book_id == sb.id)
            .all()
        )
        by_section = {p.book_section_id: p for p in progresses}
        check("3 SectionProgress", len(progresses) == 3, f"got {len(progresses)}")
        check("sec1 baseline=3", by_section[sec1_id].completed_count == 3,
              f"got {by_section[sec1_id].completed_count}")
        check("sec2 baseline=5", by_section[sec2_id].completed_count == 5)
        check("sec3 baseline=0 (default)", by_section[sec3_id].completed_count == 0)

    # ============ STEP 7: Baseline clamping ve geçersiz ============
    print("\n=== STEP 7: Baseline clamp ve geçersiz değer ===")
    # Yeni kitap + öğrenci (önceki StudentBook silmemek için ayrı)
    with SessionLocal() as db:
        student2 = User(
            email=f"{PFX}_s3@test.invalid", password_hash="x" * 60,
            full_name="Clamp Student", role=UserRole.STUDENT,
            teacher_id=teacher_id, is_active=True, password_changed_at=now,
        )
        db.add(student2); db.commit()
        student2_id = student2.id

    # baseline > test_count → clamp 10
    # baseline negatif → 0
    # baseline non-numeric → 0
    payload = {
        "book_ids": [str(new_book_id)],
        f"baseline_{new_book_id}_{sec1_id}": "999",   # clamp to 10
        f"baseline_{new_book_id}_{sec2_id}": "-3",    # clamp to 0
        f"baseline_{new_book_id}_{sec3_id}": "abc",   # invalid → 0
    }
    r = client.post(
        f"/teacher/students/{student2_id}/books/assign",
        data=payload, follow_redirects=False,
    )
    check("clamp POST 303", r.status_code == 303)

    with SessionLocal() as db:
        sb2 = (
            db.query(StudentBook)
            .filter(StudentBook.student_id == student2_id, StudentBook.book_id == new_book_id)
            .first()
        )
        progresses = (
            db.query(SectionProgress)
            .filter(SectionProgress.student_book_id == sb2.id)
            .all()
        )
        by_section = {p.book_section_id: p for p in progresses}
        check("baseline clamp >test_count → 10", by_section[sec1_id].completed_count == 10,
              f"got {by_section[sec1_id].completed_count}")
        check("baseline negatif → 0", by_section[sec2_id].completed_count == 0)
        check("baseline non-numeric → 0", by_section[sec3_id].completed_count == 0)

    app.dependency_overrides.clear()

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_students = [student_id, new_student_id, student2_id]
        # Tüm StudentBook'lar ve SectionProgress'ler
        sb_ids = [
            sid for (sid,) in db.query(StudentBook.id).filter(
                StudentBook.student_id.in_(all_students)
            ).all()
        ]
        if sb_ids:
            db.query(SectionProgress).filter(
                SectionProgress.student_book_id.in_(sb_ids)
            ).delete(synchronize_session=False)
            db.query(StudentBook).filter(StudentBook.id.in_(sb_ids)).delete(synchronize_session=False)
        db.query(BookSection).filter(BookSection.book_id.in_([book_id, new_book_id])).delete(synchronize_session=False)
        db.query(Book).filter(Book.id.in_([book_id, new_book_id])).delete(synchronize_session=False)
        db.query(Topic).filter(Topic.id.in_(topic_ids)).delete(synchronize_session=False)
        db.execute(delete(Subject).where(Subject.teacher_id == teacher_id))
        db.execute(
            delete(User).where(User.id.in_(all_students + [teacher_id, other_id]))
        )
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
