"""İskeleti başka öğrencilere kopyala (2026-09-27, kurum toplu kurulumu 3/4).

  1. copy-candidates: kaynak hariç koçun aktif öğrencileri + eksik kitaplar + mevcut dönem
  2. mode=new + assign: yeni dönem açılır, satırlar birebir, eksik kitap atanır
  3. day_capacity KOPYALANMAZ
  4. assign_missing_books=false: kitapsız satır, etiket = kitap adı
  5. mode=replace: hedefin bugünkü döneminin satırları değişir, dönem sayısı artmaz
  6. aynı başlangıçlı dönem varsa üstüne yazılır (ikinci dönem açılmaz)
  7. new modunda tarih yok → 422; yabancı öğrenci skipped_invalid; yabancı dönem 404
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject, User, UserRole,
)
from app.models.weekly_skeleton import WeeklySkeleton, WeeklySkeletonSlot
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"skc_{secrets.token_hex(3)}"
PWD = "SkelCopy!234xy"
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
                     full_name="İskelet Koç", role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Diğer", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()

        def st(n, t=coach):
            u = User(email=f"{PFX}_s{n}@test.invalid", password_hash=hash_password(PWD),
                     full_name=f"Öğrenci {n}", role=UserRole.STUDENT, is_active=True,
                     teacher_id=t.id, grade_level=10, class_group="10-A")
            db.add(u)
            db.flush()
            return u

        src, t1, t2, t3, x = st("src"), st("t1"), st("t2"), st("t3"), st("x", other)
        subj = db.query(Subject).filter(Subject.is_builtin.is_(True)).first()
        books = []
        for i in range(2):
            b = Book(name=f"Kaynak Kitap {i} {PFX}", subject_id=subj.id, teacher_id=coach.id,
                     type=BookType.SORU_BANKASI)
            db.add(b)
            db.flush()
            db.add(BookSection(book_id=b.id, label="Ü1", test_count=5, order=0))
            books.append(b)
        for b in books:
            db.add(StudentBook(student_id=src.id, book_id=b.id))
        db.add(StudentBook(student_id=t1.id, book_id=books[0].id))  # t1'de kitap1 eksik
        skel = WeeklySkeleton(student_id=src.id, coach_id=coach.id, name="Okul dönemi",
                              valid_from=date.today() - timedelta(days=10), day_capacity='{"0": 20}')
        db.add(skel)
        db.flush()
        skel.slots.append(WeeklySkeletonSlot(weekday=0, subject_id=subj.id, position=0,
                                             book_id=books[0].id, is_anchor=True))
        skel.slots.append(WeeklySkeletonSlot(weekday=1, subject_id=subj.id, position=0,
                                             book_id=books[1].id, is_routine=True, default_count=2,
                                             routine_mode="karma"))
        skel.slots.append(WeeklySkeletonSlot(weekday=2, subject_id=subj.id, position=0,
                                             label="Paragraf rutini"))
        # t3'ün mevcut (başlangıçsız) dönemi 1 satır
        t3sk = WeeklySkeleton(student_id=t3.id, coach_id=coach.id, name="Eski")
        db.add(t3sk)
        db.flush()
        t3sk.slots.append(WeeklySkeletonSlot(weekday=4, subject_id=subj.id, position=0))
        oth = WeeklySkeleton(student_id=x.id, coach_id=other.id, name="Yabancı")
        db.add(oth)
        db.commit()
        return {"coach": coach.id, "other": other.id, "email": coach.email, "src": src.id,
                "t1": t1.id, "t2": t2.id, "t3": t3.id, "x": x.id, "skel": skel.id, "oskel": oth.id,
                "books": [b.id for b in books], "b1name": books[1].name}


def cleanup(d):
    with SessionLocal() as db:
        sids = [d[k] for k in ("src", "t1", "t2", "t3", "x")]
        skids = [s.id for s in db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id.in_(sids))]
        db.execute(sa_delete(WeeklySkeletonSlot).where(WeeklySkeletonSlot.skeleton_id.in_(skids or [0])))
        db.execute(sa_delete(WeeklySkeleton).where(WeeklySkeleton.id.in_(skids or [0])))
        sbs = [s.id for s in db.query(StudentBook).filter(StudentBook.student_id.in_(sids))]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs or [0])))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(sids)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(d["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(d["books"])))
        db.execute(sa_delete(User).where(User.id.in_(sids + [d["coach"], d["other"]])))
        db.commit()


def skels_of(db, sid):
    return (db.query(WeeklySkeleton).filter(WeeklySkeleton.student_id == sid)
            .order_by(WeeklySkeleton.id).all())


def main() -> int:
    print(f"\n=== İskelet kopyala smoke — {PFX} ===\n")
    get_login_limiter().reset()
    d = seed()
    try:
        c = TestClient(app)
        assert c.post("/api/v2/auth/login", json={"email": d["email"], "password": PWD}).status_code == 200
        base = f"/api/v2/teacher/students/{d['src']}/skeleton"
        r = c.get(f"{base}/copy-candidates", params={"skeleton_id": d["skel"]})
        cand = r.json()
        by = {x["student_id"]: x for x in cand["candidates"]}
        check("1. adaylar: kaynak hariç 3 öğrenci", set(by) == {d["t1"], d["t2"], d["t3"]}, str(list(by)))
        check("2. eksik kitaplar (t1: 1, t2: 2)",
              len(by[d["t1"]]["missing_books"]) == 1 and len(by[d["t2"]]["missing_books"]) == 2)
        check("3. t3 mevcut dönemi görünür", by[d["t3"]]["current_period_name"] == "Eski"
              and by[d["t3"]]["current_slot_count"] == 1)

        start = (date.today() + timedelta(days=3)).isoformat()
        r = c.post(f"{base}/copy", json={"skeleton_id": d["skel"], "target_ids": [d["t1"], d["x"]],
                                        "mode": "new", "valid_from": start, "name": "Kurum dönemi"})
        res = r.json()["data"]
        check("4. yabancı öğrenci skipped_invalid", res["skipped_invalid_ids"] == [d["x"]], str(res))
        with SessionLocal() as db:
            ss = skels_of(db, d["t1"])
            new = ss[-1]
            check("5. yeni dönem açıldı (ad + başlangıç)", len(ss) == 1 and new.name == "Kurum dönemi"
                  and new.valid_from.isoformat() == start)
            sl = sorted(new.slots, key=lambda s: s.weekday)
            check("6. satırlar birebir (çapa, rutin karma, serbest metin)",
                  len(sl) == 3 and sl[0].is_anchor and sl[1].is_routine and sl[1].routine_mode == "karma"
                  and sl[1].default_count == 2 and sl[2].label == "Paragraf rutini")
            check("7. day_capacity kopyalanmadı", new.day_capacity is None)
            has = {x.book_id for x in db.query(StudentBook).filter(StudentBook.student_id == d["t1"])}
            check("8. eksik kitap atandı", set(d["books"]) <= has and res["students"][0]["books_assigned"] == 1)

        r = c.post(f"{base}/copy", json={"skeleton_id": d["skel"], "target_ids": [d["t2"]],
                                        "mode": "new", "valid_from": start, "assign_missing_books": False})
        with SessionLocal() as db:
            sl = sorted(skels_of(db, d["t2"])[-1].slots, key=lambda s: s.weekday)
            check("9. kitap atanmadan: satır kitapsız, etiket kitap adı",
                  sl[1].book_id is None and sl[1].label == d["b1name"] and sl[1].routine_mode is None
                  and r.json()["data"]["students"][0]["slots_without_book"] == 2)
            n = db.query(StudentBook).filter(StudentBook.student_id == d["t2"]).count()
            check("10. kitap atanmadı", n == 0, str(n))

        r = c.post(f"{base}/copy", json={"skeleton_id": d["skel"], "target_ids": [d["t3"]], "mode": "replace"})
        with SessionLocal() as db:
            ss = skels_of(db, d["t3"])
            check("11. replace: dönem sayısı aynı, satırlar değişti",
                  len(ss) == 1 and len(ss[0].slots) == 3 and ss[0].name == "Eski")

        r = c.post(f"{base}/copy", json={"skeleton_id": d["skel"], "target_ids": [d["t1"]],
                                        "mode": "new", "valid_from": start})
        with SessionLocal() as db:
            check("12. aynı başlangıçlı dönemin üstüne yazılır", len(skels_of(db, d["t1"])) == 1)

        r = c.post(f"{base}/copy", json={"skeleton_id": d["skel"], "target_ids": [d["t1"]], "mode": "new"})
        check("13. new modunda tarih yok → 422", r.status_code == 422)
        r = c.post(f"{base}/copy", json={"skeleton_id": d["oskel"], "target_ids": [d["t1"]], "mode": "replace"})
        check("14. başka öğrencinin dönemi → 404", r.status_code == 404, str(r.status_code))
        r = c.post(f"/api/v2/teacher/students/{d['x']}/skeleton/copy",
                   json={"skeleton_id": d["oskel"], "target_ids": [d["t1"]], "mode": "replace"})
        check("15. yabancı kaynak öğrenci → 404", r.status_code == 404)
    finally:
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
