"""Kitap kaynağı (katalog / şablon / elle) + atama listesi zenginleştirmesi (2026-09-27).

Koç: "kitap ata ekranında hangisi şablondan geliyor hangisi elle oluşturuldu
belli değil". Doğrular:
  * POST /books → katalog kaydından 'catalog', kişisel şablondan 'template',
    şablonsuz 'manual'; source_template_id dolar.
  * GET /teacher/books → kaynak etiketi, yayınevi, toplam test, kaç öğrencide,
    aynı adlı kitap sayısı, ?student_id ile sınıfa uygunluk.
  * GET /teacher/students/{id}/books satırında source_kind.
  * backfill betiği: NULL kaynaklı katalog kopyasını 'catalog', koç şablon
    kopyasını 'template', diğerini 'manual' yapar; idempotent.
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
    Book, BookSection, BookTemplate, BookTemplateSection, BookType, StudentBook, Subject, User, UserRole,
)
from app.services.book_catalog import normalized_key
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from scripts import backfill_book_source as bf

PFX = f"bsrc_{secrets.token_hex(3)}"
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
                     full_name="Kaynak Koç", role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Kaynak Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=10)
        db.add(st)
        subj = db.query(Subject).filter(Subject.is_builtin.is_(True)).first()
        cat = BookTemplate(name=f"Katalog Kitap {PFX}", type=BookType.SORU_BANKASI, subject_id=subj.id,
                           catalog_status="verified", source="admin_seed",
                           name_normalized=normalized_key(f"Katalog Kitap {PFX}"),
                           target_grade_min=9, target_grade_max=10)
        own = BookTemplate(teacher_id=coach.id, name=f"Benim Şablon {PFX}", type=BookType.SORU_BANKASI,
                           subject_id=subj.id)
        db.add_all([cat, own])
        db.flush()
        for t in (cat, own):
            for i in range(3):
                db.add(BookTemplateSection(template_id=t.id, label=f"Ünite {i + 1}",
                                           default_test_count=4, order=i))
        db.commit()
        return {"coach": coach.id, "student": st.id, "email": coach.email, "subject": subj.id,
                "cat": cat.id, "own": own.id}


def cleanup(d: dict) -> None:
    with SessionLocal() as db:
        bids = [b.id for b in db.query(Book).filter(Book.teacher_id == d["coach"]).all()]
        db.execute(sa_delete(StudentBook).where(StudentBook.book_id.in_(bids or [0])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids or [0])))
        db.execute(sa_delete(Book).where(Book.id.in_(bids or [0])))
        for tid in (d["cat"], d["own"]):
            db.execute(sa_delete(BookTemplateSection).where(BookTemplateSection.template_id == tid))
            db.execute(sa_delete(BookTemplate).where(BookTemplate.id == tid))
        db.execute(sa_delete(User).where(User.id.in_([d["student"], d["coach"]])))
        db.commit()


def main() -> int:
    print(f"\n=== Kitap kaynağı smoke — {PFX} ===\n")
    get_login_limiter().reset()
    d = seed()
    try:
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": d["email"], "password": PWD})
        assert r.status_code == 200, r.text

        def create(name, template_id=None, grade=None):
            body = {"name": name, "subject_id": d["subject"], "type": "soru_bankasi"}
            if template_id:
                body["template_id"] = template_id
            if grade:
                body["target_grade_min"], body["target_grade_max"] = grade
            r = c.post("/api/v2/teacher/library/books", json=body)
            assert r.status_code == 200, r.text
            return r.json()["data"]["id"]

        b_cat = create(f"Katalog Kitap {PFX}", d["cat"], (9, 10))
        b_own = create(f"Benim Şablon {PFX}", d["own"])
        b_man = create(f"Elle {PFX}", grade=(11, 12))
        b_dup = create(f"Elle {PFX}")
        with SessionLocal() as db:
            got = {b.id: (b.source_kind, b.source_template_id) for b in db.query(Book).filter(
                Book.id.in_([b_cat, b_own, b_man]))}
        check("1. katalogdan → catalog + şablon id", got[b_cat] == ("catalog", d["cat"]), str(got[b_cat]))
        check("2. kişisel şablondan → template", got[b_own] == ("template", d["own"]), str(got[b_own]))
        check("3. şablonsuz → manual", got[b_man] == ("manual", None), str(got[b_man]))

        c.post(f"/api/v2/teacher/students/{d['student']}/books", json={"book_id": b_cat})
        r = c.get("/api/v2/teacher/books", params={"student_id": d["student"]})
        items = {i["id"]: i for i in r.json()["items"]}
        ic, im = items[b_cat], items[b_man]
        check("4. liste: kaynak etiketi", ic["source_label"] == "Katalogdan" and im["source_label"] == "Elle oluşturuldu",
              f'{ic["source_label"]} / {im["source_label"]}')
        check("5. liste: toplam test + bölüm", ic["total_tests"] == 12 and ic["section_count"] == 3, str(ic))
        check("6. liste: kaç öğrencide", ic["assigned_student_count"] == 1 and im["assigned_student_count"] == 0)
        check("7. liste: 10. sınıfa uygunluk", ic["fits_student"] is True and im["fits_student"] is False,
              f'{ic["fits_student"]} {im["fits_student"]}')
        check("8. liste: aynı adlı kitap sayısı", items[b_dup]["same_name_count"] == 2 and ic["same_name_count"] == 1)
        check("9. liste: sınıf etiketi", ic["grade_label"] == "9-10. sınıf", str(ic["grade_label"]))
        r = c.get("/api/v2/teacher/books")
        check("10. student_id'siz fits_student yok", r.json()["items"][0]["fits_student"] is None)

        r = c.get(f"/api/v2/teacher/students/{d['student']}/books")
        row = next(i for i in r.json()["items"] if i["book_id"] == b_cat)
        check("11. öğrenci kitap satırında kaynak", row["source_kind"] == "catalog" and row["source_label"] == "Katalogdan")

        # backfill: kaynakları silip betiği çalıştır
        with SessionLocal() as db:
            for b in db.query(Book).filter(Book.teacher_id == d["coach"]):
                b.source_kind = None
                b.source_template_id = None
            db.commit()
            cat_by = {}
            own_by = {}
            for t in db.query(BookTemplate).filter(BookTemplate.id.in_([d["cat"], d["own"]])):
                if t.teacher_id is None:
                    cat_by.setdefault(t.name_normalized, []).append(t)
                else:
                    own_by.setdefault((t.teacher_id, normalized_key(t.name)), []).append(t)
            res = {}
            for b in db.query(Book).filter(Book.teacher_id == d["coach"]):
                res[b.id] = bf.classify(db, b, cat_by, own_by)[0]
        check("12. backfill katalog kopyası → catalog", res[b_cat] == "catalog", res[b_cat])
        check("13. backfill şablon kopyası → template", res[b_own] == "template", res[b_own])
        check("14. backfill diğer → manual", res[b_man] == "manual" and res[b_dup] == "manual")
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
