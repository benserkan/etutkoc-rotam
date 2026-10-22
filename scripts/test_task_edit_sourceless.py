"""Smoke — "Görevi düzenle" kaynaksız kalem + kitaplı↔kaynaksız geçişler (2026-10-22).

PATCH /api/v2/teacher/tasks/{id}/single-item
  1  kaynaksız test görevi → sayfa + not + aralık (başlık, birim, adet aralıktan)
  2  kaynaksız → başka konu + soru (sayfa aralığı temizlenir)
  3  konusuz kaynaksız düzenleme 422 topic_required
  4  ters aralık 422
  5  kitaplı → kaynaksız: eski bölüm rezervi iade edilir
  6  kaynaksız → kitaplı: yeni bölüm rezervi açılır, kaynaksız alanlar temizlenir
  7  çözülen varken kaynaksız → kitaplı 422 · kitaplı → kaynaksız 422
  8  çözülen varken kaynaksız içinde sayı çözülenin altına inemez 422; üstü serbest
  9  başka koçun görevi 404
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Book,
    BookSection,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    SuspiciousIp,
    Task,
    TaskBookItem,
    User,
    UserRole,
)
from app.services import curriculum_progress as cp  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"tes_{secrets.token_hex(3)}"
PWD = "Koc!234567xyQwe"
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


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Düzen Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD), full_name="Öbür Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add_all([coach, other])
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Düzen Öğrenci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  grade_level=8)
        db.add(st)
        db.flush()
        fen = (db.query(Subject).filter(Subject.name == "Fen Bilimleri", Subject.is_builtin.is_(True),
                                        Subject.curriculum_model == "lgs").first())
        topics = cp.leaf_topics_for_student(db, st, coach.id, [fen.id]).by_subject[fen.id]
        book = Book(teacher_id=coach.id, subject_id=fen.id, name=f"{PFX} Fen SB", type=BookType.SORU_BANKASI)
        db.add(book)
        db.flush()
        sec = BookSection(book_id=book.id, label="Basınç", test_count=10, order=1, topic_id=topics[0].id)
        db.add(sec)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.commit()
        return {"coach": coach.id, "other": other.id, "st": st.id, "fen": fen.id, "book": book.id,
                "sec": sec.id, "sb": sb.id, "t1": topics[0].id, "t1name": topics[0].name,
                "t2": topics[1].id, "t2name": topics[1].name}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["st"], d["coach"], d["other"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id == d["sb"]))
        db.execute(sa_delete(StudentBook).where(StudentBook.id == d["sb"]))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == d["book"]))
        db.execute(sa_delete(Book).where(Book.id == d["book"]))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def reserved(d) -> int:
    with SessionLocal() as db:
        sp = (db.query(SectionProgress)
              .filter(SectionProgress.student_book_id == d["sb"], SectionProgress.book_section_id == d["sec"])
              .first())
        return int(sp.reserved_count) if sp else 0


def item_of(tid):
    with SessionLocal() as db:
        t = db.get(Task, tid)
        it = t.book_items[0]
        return t.title, {k: getattr(it, k) for k in (
            "book_id", "book_section_id", "topic_id", "label", "unit", "page_from", "page_to",
            "planned_count", "completed_count")}


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    today = date.today().isoformat()
    print(f"\n=== görevi düzenle — kaynaksız — {PFX} ===\n")
    try:
        c = TestClient(app)
        assert c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD}).status_code == 200
        base = f"/api/v2/teacher/students/{d['st']}"

        def create(item):
            r = c.post(f"{base}/tasks", json={"date": today, "type": "test", "title": "Görev",
                                              "is_draft": False, "items": [item]})
            assert r.status_code == 200, r.text
            with SessionLocal() as db:
                return db.query(Task).filter(Task.student_id == d["st"]).order_by(Task.id.desc()).first().id

        def patch(tid, **kw):
            body = {"date": today, "scheduled_hour": None, "type": "test", "period": None,
                    "planned_count": 1, "book_id": None, "section_id": None}
            body.update(kw)
            return c.patch(f"/api/v2/teacher/tasks/{tid}/single-item", json=body)

        # 1
        tid = create({"book_id": None, "section_id": None, "topic_id": d["t1"], "planned_count": 3})
        r = patch(tid, topic_id=d["t1"], label="Hız Fen", unit="sayfa", page_from=45, page_to=50, period="evening")
        title, it = item_of(tid)
        check("1 kaynaksız test → sayfa s.45–50 (adet 6, not, başlık)",
              r.status_code == 200 and it["unit"] == "sayfa" and it["page_from"] == 45 and it["page_to"] == 50
              and it["planned_count"] == 6 and it["label"] == "Hız Fen"
              and title == f"{d['t1name']} (Hız Fen): s. 45–50", f"{r.status_code} {title} {it}")
        # 2
        r = patch(tid, topic_id=d["t2"], unit="soru", planned_count=20, page_from=45, page_to=50)
        title, it = item_of(tid)
        check("2 başka konu + soru: aralık temizlendi, not yoksa konu adı",
              r.status_code == 200 and it["topic_id"] == d["t2"] and it["unit"] == "soru"
              and it["page_from"] is None and it["planned_count"] == 20 and title.startswith(d["t2name"]),
              f"{r.status_code} {title} {it}")
        # 3
        r = patch(tid, planned_count=2)
        check("3 konusuz kaynaksız → 422 topic_required", r.status_code == 422 and "topic_required" in r.text,
              r.text[:150])
        # 4
        r = patch(tid, topic_id=d["t2"], unit="sayfa", page_from=50, page_to=40)
        check("4 ters aralık → 422 invalid_page_range", r.status_code == 422 and "invalid_page_range" in r.text,
              r.text[:150])
        # 5 kitaplı → kaynaksız
        bt = create({"book_id": d["book"], "section_id": d["sec"], "planned_count": 4})
        r0 = reserved(d)
        r = patch(bt, topic_id=d["t1"], unit="test", planned_count=4)
        title, it = item_of(bt)
        check("5 kitaplı → kaynaksız: rezerv iade (4→0), kitap bağı koptu",
              r.status_code == 200 and r0 == 4 and reserved(d) == 0 and it["book_id"] is None
              and it["topic_id"] == d["t1"], f"{r.status_code} rez {r0}->{reserved(d)} {it}")
        # 6 kaynaksız → kitaplı
        r = patch(tid, book_id=d["book"], section_id=d["sec"], planned_count=3)
        title, it = item_of(tid)
        check("6 kaynaksız → kitaplı: rezerv 3, kaynaksız alanlar temizlendi",
              r.status_code == 200 and reserved(d) == 3 and it["book_id"] == d["book"]
              and it["topic_id"] is None and it["unit"] is None and it["label"] is None,
              f"{r.status_code} rez {reserved(d)} {it}")
        # 7 çözülen varken geçiş yok
        with SessionLocal() as db:
            x = db.get(Task, bt).book_items[0]
            x.completed_count = 2
            db.commit()
        r = patch(bt, book_id=d["book"], section_id=d["sec"], planned_count=4)
        check("7a çözülen varken kaynaksız → kitaplı 422",
              r.status_code == 422 and "source_change_with_completed" in r.text, r.text[:150])
        with SessionLocal() as db:
            x = db.get(Task, tid).book_items[0]
            x.completed_count = 1
            db.commit()
        r = patch(tid, topic_id=d["t1"], planned_count=3)
        check("7b çözülen varken kitaplı → kaynaksız 422",
              r.status_code == 422 and "source_change_with_completed" in r.text, r.text[:150])
        # 8 çözülenin altına inemez
        r = patch(bt, topic_id=d["t1"], planned_count=1)
        check("8a sayı çözülenin altına → 422 planned_below_completed",
              r.status_code == 422 and "planned_below_completed" in r.text, r.text[:150])
        r = patch(bt, topic_id=d["t1"], planned_count=5, unit="soru")
        title, it = item_of(bt)
        check("8b çözülenin üstü serbest (5 soru, çözülen 2 korunur)",
              r.status_code == 200 and it["planned_count"] == 5 and it["completed_count"] == 2,
              f"{r.status_code} {it}")
        # 9 başka koç
        c2 = TestClient(app)
        assert c2.post("/api/v2/auth/login", json={"email": f"{PFX}_o@test.invalid", "password": PWD}).status_code == 200
        r = c2.patch(f"/api/v2/teacher/tasks/{bt}/single-item",
                     json={"date": today, "scheduled_hour": None, "type": "test", "planned_count": 3,
                           "book_id": None, "section_id": None, "topic_id": d["t1"]})
        check("9 başka koçun görevi 404", r.status_code == 404, str(r.status_code))
    finally:
        cleanup(d)
    print(f"\n=== {passed} passed · {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
