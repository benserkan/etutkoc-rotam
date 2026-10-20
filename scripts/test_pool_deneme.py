"""Havuz deneme kalemleri D1b smoke (2026-10-20).

Kural: havuz deneme kalemi quantity = deneme adedi; kaba alınınca her deneme ayrı görev satırı
(1 satır = 1 deneme, planned 1) — programdaki deneme göreviyle aynı yapı.

   1. Koç havuza kaynaklı branş ekler (×3) → unit deneme, 6 soru, sıradaki bölüm
   2. Öğrenci kaba 2 alır → 2 satır DENEME 1, 2; deneme alanları; rezerv yok
   3. Öğrenci soru sayısında esnek: 6 soruluk denemede 7 doğru girebilir; kalem done 1
   4. Kap düzelt 3 → 3. satır DENEME 3 eklenir · 1'e indir → işaretlenmemişler silinir, görev tamam
   5. İkinci kap: daha önce alınanları atlar (DENEME 2, 3)
   6. Gün kapanışı: işaretlenmeyen deneme satırı silinir, görev tamam, kalan havuza döner
   7. Kaynaksız branş (×2, 20 soru, ad) → kapta 2 kitapsız dersli satır "Ad 1/2"
   8. Genel TYT → dersiz kalem "Genel deneme" · kapta tam_deneme · 120 soru
   9. Eski tip deneme kalemi (exam_kind boş, kitapsız) kapta 2 deneme satırı olur (eski "D+Y ≤ 2" hatası yok)
  10. Dönem özeti deneme adedini birim sayar
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

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
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, Task, TaskBookItem, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import gorev_stats, pool_mode  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"pdn_{secrets.token_hex(3)}"
PWD = "Ogrenci!234567xy"
today = date.today()
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": []}


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
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Rehber", role=UserRole.TEACHER, is_active=True)
        db.add(coach); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Havuz Öğrenci", role=UserRole.STUDENT, is_active=True, teacher_id=coach.id,
                  grade_level=12, track=Track.SAYISAL, program_mode="havuz", must_change_password=False)
        db.add(st); db.flush()
        bio = Subject(name="TYT Biyoloji", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(bio); db.flush()
        b = Book(teacher_id=coach.id, subject_id=bio.id, name=f"{PFX} Bio Branş", type=BookType.BRANS_DENEMESI)
        db.add(b); db.flush()
        secs = [BookSection(book_id=b.id, label=f"DENEME {i}", test_count=1, order=i) for i in range(1, 6)]
        db.add_all(secs); db.flush()
        db.add(StudentBook(student_id=st.id, book_id=b.id))
        p = pool_mode.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=1),
                                  expected_next_on=today + timedelta(days=6))
        db.commit()
        ids["users"] += [coach.id, st.id]
        ids["subjects"].append(bio.id)
        ids["books"].append(b.id)
        return {"coach": coach.id, "st": st.id, "bio": bio.id, "book": b.id, "pid": p.id,
                "secs": [x.id for x in secs]}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        from app.models import ExamResult as _ER  # D3 köprü kayıtları
        db.execute(sa_delete(_ER).where(_ER.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def rows(task_id: int):
    with SessionLocal() as db:
        t = db.get(Task, task_id)
        return t, sorted(t.book_items, key=lambda b: b.id) if t else []


def item_of(item_id: int) -> PoolItem:
    with SessionLocal() as db:
        it = db.get(PoolItem, item_id)
        db.expunge(it)
        return it


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    print(f"\n=== havuz deneme smoke — {PFX} ===\n")
    try:
        c = login(f"{PFX}_t@test.invalid")
        s = login(f"{PFX}_s@test.invalid")
        sid = d["st"]

        # 1
        r = c.post(f"/api/v2/teacher/students/{sid}/pool/deneme-items",
                   json={"kind": "brans", "book_id": d["book"], "count": 3})
        check("1a koç havuza kaynaklı deneme 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            it = db.query(PoolItem).filter(PoolItem.student_id == sid).order_by(PoolItem.id.desc()).first()
            i_book = it.id
            check("1b unit deneme · 3 adet · 6 soru · brans",
                  it.unit == "deneme" and it.quantity == 3 and it.question_count == 6 and it.exam_kind == "brans",
                  (it.unit, it.quantity, it.question_count, it.exam_kind))
            check("1c sıradaki bölüm DENEME 1", it.book_section_id == d["secs"][0])
        items_out = r.json()["data"]["period"]["items"] if r.status_code == 200 else []
        ob = next((x for x in items_out if x["id"] == i_book), {})
        check("1d paket kalemde deneme alanları", ob.get("exam_kind") == "brans" and ob.get("question_count") == 6, str(ob))

        # 2
        r = s.post("/api/v2/student/pool/cup", json={"item_id": i_book, "count": 2})
        check("2a kaba 2 deneme 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            t = db.query(Task).filter(Task.pool_item_id == i_book).first()
            tid = t.id
        t, rs = rows(tid)
        check("2b 2 satır DENEME 1, 2", [x.book_section_id for x in rs] == d["secs"][:2], str([x.book_section_id for x in rs]))
        check("2c satırlar deneme (planned 1, 6 soru, rezerv yok)",
              all(x.exam_kind == "brans" and x.planned_count == 1 and x.question_count == 6
                  and x.reservation_released_at is not None for x in rs))
        check("2d başlık deneme adları", "DENEME 1, DENEME 2" in t.title, t.title)

        # 3
        r = s.post(f"/api/v2/student/tasks/{tid}/items/{rs[0].id}/set-completed",
                   json={"completed": 1, "correct": 7, "wrong": 0, "blank": 0})
        check("3a 6 soruluk denemede 7 doğru girilebilir", r.status_code == 200, r.text[:300])
        r = s.get("/api/v2/student/pool")
        it = item_of(i_book)
        check("3b kalem tamamlanan 1", it.completed == 1, it.completed)

        # 4
        r = s.post(f"/api/v2/student/pool/cup/{tid}/resize", json={"count": 3})
        check("4a kap 3'e çıkar 200", r.status_code == 200, r.text[:300])
        t, rs = rows(tid)
        check("4b 3. satır DENEME 3", [x.book_section_id for x in rs] == d["secs"][:3], str([x.book_section_id for x in rs]))
        r = s.post(f"/api/v2/student/pool/cup/{tid}/resize", json={"count": 1})
        check("4c kap 1'e iner 200", r.status_code == 200, r.text[:300])
        t, rs = rows(tid)
        check("4d yalnız işaretli satır kaldı + görev tamam",
              len(rs) == 1 and rs[0].completed_count == 1 and t.status.value == "completed",
              (len(rs), t.status))
        r = s.post(f"/api/v2/student/pool/cup/{tid}/resize", json={"count": 0})
        check("4e 0 → 422", r.status_code == 422)

        # 5
        r = s.post("/api/v2/student/pool/cup", json={"item_id": i_book, "count": 2})
        check("5a ikinci kap 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            t2 = db.query(Task).filter(Task.pool_item_id == i_book, Task.id != tid).first()
            tid2 = t2.id
        t2, rs2 = rows(tid2)
        check("5b alınmış DENEME 1 atlandı → DENEME 2, 3",
              [x.book_section_id for x in rs2] == d["secs"][1:3], str([x.book_section_id for x in rs2]))

        # 6
        s.post(f"/api/v2/student/tasks/{tid2}/items/{rs2[0].id}/set-completed",
               json={"completed": 1, "correct": 4, "wrong": 1, "blank": 1})
        r = s.post("/api/v2/student/pool/close-day", json={})
        check("6a gün kapanışı 200", r.status_code == 200, r.text[:300])
        t2, rs2 = rows(tid2)
        check("6b işaretlenmeyen satır silindi, görev tamam",
              len(rs2) == 1 and t2.status.value == "completed", (len(rs2), t2.status))
        it = item_of(i_book)
        check("6c kalem 2/3, kalan 1", it.completed == 2 and it.remaining == 1, (it.completed, it.remaining))

        # 6d aynı kitaptan ikinci havuz kalemi alınmış denemeleri atlar
        r = c.post(f"/api/v2/teacher/students/{sid}/pool/deneme-items",
                   json={"kind": "brans", "book_id": d["book"], "count": 1})
        with SessionLocal() as db:
            i_book2 = db.query(PoolItem).filter(PoolItem.student_id == sid).order_by(PoolItem.id.desc()).first().id
        s.post("/api/v2/student/pool/cup", json={"item_id": i_book2, "count": 1})
        with SessionLocal() as db:
            tb2 = db.query(Task).filter(Task.pool_item_id == i_book2).first()
            secs_b2 = [x.book_section_id for x in tb2.book_items] if tb2 else []
        check("6d aynı kitaptan ikinci kalem çözülenleri atlar (DENEME 3 — gün sonunda havuza dönmüştü)", secs_b2 == [d["secs"][2]], str(secs_b2))

        # 7
        r = c.post(f"/api/v2/teacher/students/{sid}/pool/deneme-items",
                   json={"kind": "brans", "subject_id": d["bio"], "count": 2, "question_count": 20,
                         "name": "Özel ders biyoloji"})
        check("7a kaynaksız branş havuza 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            i_free = db.query(PoolItem).filter(PoolItem.student_id == sid).order_by(PoolItem.id.desc()).first().id
        r = s.post("/api/v2/student/pool/cup", json={"item_id": i_free, "count": 2})
        with SessionLocal() as db:
            tf = db.query(Task).filter(Task.pool_item_id == i_free).first()
            tfid = tf.id
        tf, rsf = rows(tfid)
        check("7b 2 kitapsız dersli satır, 20 soru",
              len(rsf) == 2 and all(x.book_id is None and x.subject_id == d["bio"] and x.question_count == 20 for x in rsf),
              str([(x.book_id, x.subject_id, x.question_count) for x in rsf]))
        check("7c etiketler 'Özel ders biyoloji 1/2'", rsf[0].label == "Özel ders biyoloji 1/2", rsf[0].label)

        # 8
        r = c.post(f"/api/v2/teacher/students/{sid}/pool/deneme-items",
                   json={"kind": "genel", "genel_key": "tyt", "count": 1})
        check("8a genel TYT havuza 200", r.status_code == 200, r.text[:300])
        g = next((x for x in r.json()["data"]["period"]["items"] if x.get("exam_kind") == "genel"), None) if r.status_code == 200 else None
        check("8b dersiz kalem 'Genel deneme' + 120 soru",
              g is not None and g["subject_id"] is None and g["subject_name"] == "Genel deneme"
              and g["question_count"] == 120, str(g))
        if g:
            s.post("/api/v2/student/pool/cup", json={"item_id": g["id"], "count": 1})
            with SessionLocal() as db:
                tg = db.query(Task).filter(Task.pool_item_id == g["id"]).first()
                check("8c kapta tam_deneme", tg is not None and gorev_stats.classify_gorev(tg) == "tam_deneme")
        r = s.get("/api/v2/student/pool")
        check("8d öğrenci havuz paketi 200 (dersiz kalemle)", r.status_code == 200, r.text[:200])

        # 9 eski tip deneme kalemi
        with SessionLocal() as db:
            p = db.get(StudyPeriod, d["pid"])
            stu = db.get(User, sid)
            subj = db.get(Subject, d["bio"])
            old = PoolItem(period_id=p.id, student_id=sid, subject_id=subj.id, label="Eski deneme",
                           quantity=2, unit="deneme")
            db.add(old); db.commit()
            i_old = old.id
        r = s.post("/api/v2/student/pool/cup", json={"item_id": i_old, "count": 2})
        check("9a eski tip kaba 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            to = db.query(Task).filter(Task.pool_item_id == i_old).first()
            toid = to.id
        to, rso = rows(toid)
        check("9b 2 deneme satırı (planned 1'er)", len(rso) == 2 and all(x.planned_count == 1 and x.exam_kind for x in rso),
              str([(x.planned_count, x.exam_kind) for x in rso]))
        r = s.post(f"/api/v2/student/tasks/{toid}/items/{rso[0].id}/set-completed",
                   json={"completed": 1, "correct": 15, "wrong": 3})
        check("9c 15 doğru girilebilir (eski 'D+Y ≤ 2' hatası yok)", r.status_code == 200, r.text[:300])

        # 10
        with SessionLocal() as db:
            p = db.get(StudyPeriod, d["pid"])
            sm = pool_mode.period_summary(db, p, today)
            # birimler: 3 + 1 (kitaplı) + 2 (kaynaksız) + 1 (genel) + 2 (eski) = 9
            check("10 dönem özeti deneme adedini birim sayar (9)", sm.total_units == 9, sm.total_units)
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
