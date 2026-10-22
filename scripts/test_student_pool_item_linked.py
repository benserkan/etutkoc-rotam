"""Öğrenci "Havuza kalem ekle" — müfredat/kitap eşleşmeli kalem (2026-10-22).

Öğrenci koçun ekleme akışını yaşar: ders → kitabın bölümü ya da müfredat konusu → miktar.
Kalem konuya/kitaba BAĞLI eklenir, onay bekler; koç onaylayınca yüzdeye + müfredat sinyaline girer.

Çalıştır: PYTHONPATH=. python scripts/test_student_pool_item_linked.py
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
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Topic, Track,
    User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"spl_{secrets.token_hex(3)}"
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
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Rehber",
                     role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD), full_name="Başka",
                     role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Öğrenci",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                  track=Track.SAYISAL, program_mode="havuz")
        db.add(st)
        db.flush()
        ids["users"] += [coach.id, other.id, st.id]
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(tyt)
        db.flush()
        ids["subjects"].append(tyt.id)
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t_foreign = Topic(subject_id=tyt.id, name="Gizli konu", order=2, teacher_id=other.id)
        db.add_all([t1, t_foreign])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        s1 = BookSection(book_id=b.id, label="Köklü Sayılar", test_count=10, order=1)
        db.add(s1)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s1.id, reserved_count=0, completed_count=2))
        pool_mode.open_period(db, student=st, coach=coach, opened_on=today, expected_next_on=today + timedelta(days=7))
        db.commit()
        return {"coach": coach.id, "st": st.id, "tyt": tyt.id, "t1": t1.id, "tf": t_foreign.id,
                "b": b.id, "s1": s1.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def login(uid: int) -> TestClient:
    with SessionLocal() as db:
        email = db.get(User, uid).email
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    try:
        s = login(d["st"])
        r = s.get("/api/v2/student/pool")
        subj = next((x for x in r.json()["subjects"] if x["id"] == d["tyt"]), None)
        check("1 ders listesinde kitap sayısı", subj is not None and subj.get("book_count") == 1, r.text[:300])
        check("1b yanıtta sınıf (konu süzgeci)", r.json().get("grade_level") == 12, r.json().get("grade_level"))

        r = s.get(f"/api/v2/student/pool/topics?subject_id={d['tyt']}")
        names = [t["name"] for t in r.json().get("topics", [])] if r.status_code == 200 else []
        check("2 öğrenci müfredat konularını görür", r.status_code == 200 and "Üslü Sayılar" in names, r.text[:300])
        check("2b başka koçun konusu listede yok", "Gizli konu" not in names, names)

        r = s.get(f"/api/v2/student/pool/books?subject_id={d['tyt']}")
        secs = r.json()["books"][0]["sections"] if r.status_code == 200 and r.json()["books"] else []
        check("3 öğrenci kitabını + bölüm kalanını görür",
              r.status_code == 200 and secs and secs[0]["section_id"] == d["s1"] and secs[0]["remaining"] == 8,
              r.text[:300])

        r = s.post("/api/v2/student/pool/items", json={"subject_id": d["tyt"], "unit": "test", "quantity": 3,
                                                       "label": "kendi testim"})
        check("4 konusuz test kalemi reddedilir (konu/kitap ister)",
              r.status_code == 422 and r.json()["detail"]["code"] == "topic_required", r.text[:200])

        r = s.post("/api/v2/student/pool/items", json={"subject_id": d["tyt"], "unit": "test", "quantity": 3,
                                                       "topic_id": d["tf"]})
        check("5 başka koçun konusu enjekte edilemez (404)", r.status_code == 404, r.text[:200])

        r = s.post("/api/v2/student/pool/items", json={"subject_id": d["tyt"], "unit": "test", "quantity": 3,
                                                       "topic_id": d["t1"], "label": "Palme yaprak"})
        check("6 müfredat konusundan kalem eklenir", r.status_code == 200, r.text[:200])
        r = s.post("/api/v2/student/pool/items", json={"subject_id": d["tyt"], "unit": "test", "quantity": 2,
                                                       "book_id": d["b"], "section_id": d["s1"]})
        check("7 kitabın bölümünden kalem eklenir", r.status_code == 200, r.text[:200])
        r = s.post("/api/v2/student/pool/items", json={"subject_id": d["tyt"], "unit": "sayfa",
                                                       "topic_id": d["t1"], "page_from": 45, "page_to": 50})
        check("8 sayfa aralığı → 6 sayfa", r.status_code == 200, r.text[:200])

        with SessionLocal() as db:
            items = db.query(PoolItem).filter(PoolItem.student_id == d["st"], PoolItem.removed_at.is_(None)).all()
            by = {(it.topic_id, it.book_section_id, it.unit): it for it in items}
            ti = by.get((d["t1"], None, "test"))
            bi = by.get((None, d["s1"], "test")) or next((it for it in items if it.book_section_id == d["s1"]), None)
            pi = next((it for it in items if it.unit == "sayfa"), None)
            check("9 konu kalemi: konuya bağlı + onay bekler + yüzdeye girmez",
                  ti is not None and ti.approval == "bekliyor" and not ti.counts_toward_pool and ti.label == "Palme yaprak",
                  f"{ti and (ti.approval, ti.counts_toward_pool)}")
            check("10 kitap kalemi: kitap + bölüm bağlı", bi is not None and bi.book_id == d["b"], f"{bi}")
            check("11 sayfa kalemi: aralık + adet", pi is not None and pi.page_from == 45 and pi.quantity == 6, f"{pi}")
            sig = pool_mode.topic_pool_signals(db, d["st"])
            check("12 onaydan önce müfredatta 'planlandı' sinyali yok", d["t1"] not in sig.planned, f"{sig.planned}")
            tid = ti.id if ti else 0
            bid = bi.id if bi else 0
            pid = pi.id if pi else 0

        c = login(d["coach"])
        r = c.post(f"/api/v2/teacher/students/{d['st']}/pool/items/{tid}/approve", json={"approved": True})
        check("13 koç onaylar", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            it = db.get(PoolItem, tid)
            sig = pool_mode.topic_pool_signals(db, d["st"])
            check("14 onay sonrası yüzdeye girer + müfredatta planlandı",
                  it.counts_toward_pool and d["t1"] in sig.planned, f"{it.approval} {sig.planned}")

        # --- koç onaydan önce konuyu/kitabı düzeltir (relink)
        base = f"/api/v2/teacher/students/{d['st']}/pool/items"
        r = c.post(f"{base}/{bid}/relink", json={"topic_id": d["t1"]})
        with SessionLocal() as db:
            it = db.get(PoolItem, bid)
            check("15 kitap kalemi konuya taşındı (kitap bağı temizlendi, hâlâ bekliyor)",
                  r.status_code == 200 and it.topic_id == d["t1"] and it.book_id is None
                  and it.book_section_id is None and it.approval == "bekliyor" and it.quantity == 2,
                  r.text[:200])
        r = c.post(f"{base}/{pid}/relink", json={"book_id": d["b"], "section_id": d["s1"], "approve": True})
        with SessionLocal() as db:
            it = db.get(PoolItem, pid)
            check("16 sayfa kalemi kitaba bağlandı + onaylandı (birim test, aralık temiz)",
                  r.status_code == 200 and it.book_section_id == d["s1"] and it.unit == "test"
                  and it.page_from is None and it.approval == "onaylandi", r.text[:200])
        r = c.post(f"{base}/{bid}/relink", json={"topic_id": d["tf"]})
        check("17 başka koçun konusu ile relink 422", r.status_code == 422, r.text[:200])
        r = c.post(f"{base}/{bid}/relink", json={})
        check("18 bağ verilmezse 422 link_required",
              r.status_code == 422 and r.json()["detail"]["code"] == "link_required", r.text[:200])
        with SessionLocal() as db:
            db.get(PoolItem, bid).completed = 1
            db.commit()
        r = c.post(f"{base}/{bid}/relink", json={"book_id": d["b"], "section_id": d["s1"]})
        check("19 ilerlemeli kalem relink edilemez (409)", r.status_code == 409, r.text[:200])
        o = login(ids["users"][1])
        r = o.post(f"/api/v2/teacher/students/{d['st']}/pool/items/{bid}/relink", json={"topic_id": d["t1"]})
        check("20 başka koç 404", r.status_code == 404, r.text[:200])
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
