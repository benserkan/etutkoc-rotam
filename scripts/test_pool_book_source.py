"""Havuz "Nereden? → Öğrencinin kitapları" + kitaptan ilerleme takibi (2026-10-13).

Kural: rehber kitabın KENDİ bölümünü seçer (konu eşleştirmesine bakılmaz). Kitaptan verilen kalem öğrencinin kap
kaydı ve rehberin seans işaretiyle KİTAP SAYACINI ilerletir; deneme kitabı da aynı. Kitap listesi her bölümde
kalan · havuzda bekleyen · verilebilir · SON gösterir (havuz rezerv tutmadığından iki kez vermeyi önler).

Çalıştır: PYTHONPATH=. python scripts/test_pool_book_source.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

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
    Book, BookSection, BookType, PoolItem, SectionProgress, StudentBook, StudyPeriod, Subject, Task,
    TaskBookItem, Topic, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"pbs_{secrets.token_hex(3)}"
PWD = "BookSrc!234567xy"
today = date.today()
now = datetime.now(timezone.utc)
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


def _user(db, tag, role, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"PBS {tag}",
             role=role, is_active=True, created_at=now - timedelta(days=40), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _complete(db, task, n):
    """GERÇEK tamamlama servisi (öğrencinin işaretleme ucunun kullandığı) — kitap sayacını o günceller."""
    from app.services import task_service
    for bi in task.book_items:
        task_service.set_item_completion(db, bi, n)
    db.flush()


def seed() -> dict:
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        subj = Subject(name=f"TYT {PFX} Fizik", teacher_id=coach.id, curriculum_model=None,
                       exam_section=ExamSection.TYT, min_grade_level=9, max_grade_level=12,
                       available_for_graduate=True, order=1)
        other = Subject(name=f"TYT {PFX} Kimya", teacher_id=coach.id, curriculum_model=None,
                        exam_section=ExamSection.TYT, min_grade_level=9, max_grade_level=12,
                        available_for_graduate=True, order=2)
        db.add_all([subj, other])
        db.flush()
        ids["subjects"] += [subj.id, other.id]
        t1 = Topic(subject_id=subj.id, name="Hareket", order=1, teacher_id=coach.id)
        db.add(t1)
        db.flush()
        sb_book = Book(teacher_id=coach.id, subject_id=subj.id, name=f"{PFX} 345 Fizik", type=BookType.SORU_BANKASI)
        dn_book = Book(teacher_id=coach.id, subject_id=subj.id, name=f"{PFX} Fizik Branş Deneme", type=BookType.BRANS_DENEMESI)
        db.add_all([sb_book, dn_book])
        db.flush()
        ids["books"] += [sb_book.id, dn_book.id]
        s1 = BookSection(book_id=sb_book.id, label="Hareket (kitap bölümü)", test_count=10, order=1, topic_id=t1.id)
        s2 = BookSection(book_id=sb_book.id, label="Madde ve Özellikleri", test_count=11, order=2, topic_id=None)
        d1 = BookSection(book_id=dn_book.id, label="Deneme 1 (40 soru)", test_count=1, order=1)
        d2 = BookSection(book_id=dn_book.id, label="Deneme 2 (40 soru)", test_count=1, order=2)
        db.add_all([s1, s2, d1, d2])
        db.flush()
        st = _user(db, "ogr", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                   program_mode="havuz")
        for bk, secs in ((sb_book, (s1, s2)), (dn_book, (d1, d2))):
            sb = StudentBook(student_id=st.id, book_id=bk.id)
            db.add(sb)
            db.flush()
            for sec in secs:
                db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        pm.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=2))
        db.commit()
        return {"coach": coach.id, "st": st.id, "subj": subj.id, "other": other.id, "t1": t1.id,
                "sb": sb_book.id, "dn": dn_book.id, "s1": s1.id, "s2": s2.id, "d1": d1.id, "d2": d2.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
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


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    base = f"/api/v2/teacher/students/{d['st']}"

    def books():
        r = c.get(f"{base}/pool/books?subject_id={d['subj']}")
        assert r.status_code == 200, r.text
        return {b["book_id"]: b for b in r.json()["books"]}

    def sec(bs, book_id, section_id):
        return next(x for x in bs[book_id]["sections"] if x["section_id"] == section_id)

    try:
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_coach@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text

        j = c.get(f"{base}/pool").json()
        sj = next(s for s in j["subjects"] if s["id"] == d["subj"])
        check("B1 ders çipinde kaynak sayısı: 1 kitap + 1 deneme", sj["book_count"] == 1 and sj["deneme_count"] == 1, str(sj))
        bs = books()
        check("B2 kitap listesi: soru bankası + deneme kitabı (deneme işaretli), kitabın KENDİ bölüm adları",
              set(bs) == {d["sb"], d["dn"]} and bs[d["dn"]]["is_deneme"] and not bs[d["sb"]]["is_deneme"]
              and [x["label"] for x in bs[d["sb"]]["sections"]] == ["Hareket (kitap bölümü)", "Madde ve Özellikleri"],
              str(bs.keys()))
        s2 = sec(bs, d["sb"], d["s2"])
        check("B3 eşleşmesiz bölüm de listede: kalan 11 · havuzda 0 · verilebilir 11 · konu yok",
              s2["remaining"] == 11 and s2["in_pool"] == 0 and s2["available"] == 11 and s2["topic_name"] is None, str(s2))
        r = c.get(f"{base}/pool/books?subject_id=999999")
        check("B4 bilinmeyen ders 404", r.status_code == 404, str(r.status_code))

        # eşleşmesiz bölümden 4 test
        r = c.post(f"{base}/pool/items", json={"subject_id": d["subj"], "book_id": d["sb"], "section_id": d["s2"],
                                               "quantity": 4, "unit": "test"})
        check("K1 eşleşmesiz kitap bölümünden kalem eklendi (konu gerekmedi)", r.status_code == 200, r.text[:200])
        items = r.json()["data"]["period"]["items"]
        it2 = next(i for i in items if i["section_id"] == d["s2"])
        check("K2 havuz listesinde kitap ilerlemesi: kitapta 0/11", it2["book_completed"] == 0 and it2["book_total"] == 11, str(it2))
        s2 = sec(books(), d["sb"], d["s2"])
        check("K3 kitap listesinde 'havuzda 4' · verilebilir 7 · SON", s2["in_pool"] == 4 and s2["available"] == 7 and s2["is_last"],
              str(s2))
        # eşli bölüm → konu türetilir (müfredat ilerlemesi işler)
        r = c.post(f"{base}/pool/items", json={"subject_id": d["subj"], "book_id": d["sb"], "section_id": d["s1"],
                                               "quantity": 2, "unit": "test"})
        it1 = next(i for i in r.json()["data"]["period"]["items"] if i["section_id"] == d["s1"])
        check("K4 eşli bölümden kalem konu bağını kitaptan alır (müfredata yansır)", it1["topic_id"] == d["t1"], str(it1))

        # öğrenci kaba alır + işaretler → kitap sayacı
        with SessionLocal() as db:
            item = db.query(PoolItem).filter(PoolItem.book_section_id == d["s2"]).first()
            t = pm.put_in_cup(db, item=item, day=today - timedelta(days=1), count=3)
            _complete(db, t, 3)
            pm.sync_item_progress(db, item)
            db.commit()
        s2 = sec(books(), d["sb"], d["s2"])
        check("T1 öğrenci 3 test işaretledi → kitap sayacı 3 · havuzda 1 · verilebilir 7",
              s2["completed"] == 3 and s2["in_pool"] == 1 and s2["available"] == 7, str(s2))
        it2 = next(i for i in c.get(f"{base}/pool").json()["period"]["items"] if i["section_id"] == d["s2"])
        check("T2 havuz listesi: kitapta 3/11", it2["book_completed"] == 3, str(it2))
        # rehber seansta kalan 1'i işaretler → kitap sayacına izli koç kaydı
        r = c.post(f"{base}/pool/items/{it2['id']}/session-mark", json={"count": 1})
        s2 = sec(books(), d["sb"], d["s2"])
        check("T3 seans işareti kitap sayacına yazıldı (4) · havuzda 0", r.status_code == 200 and s2["completed"] == 4
              and s2["in_pool"] == 0, f"{r.status_code} {s2}")

        # deneme kitabı
        r = c.post(f"{base}/pool/items", json={"subject_id": d["subj"], "book_id": d["dn"], "section_id": d["d1"],
                                               "quantity": 1, "unit": "deneme"})
        check("D1 deneme kitabından 'Deneme 1' kalemi eklendi", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            item = db.query(PoolItem).filter(PoolItem.book_section_id == d["d1"]).first()
            t = pm.put_in_cup(db, item=item, day=today - timedelta(days=1), count=1)
            check("D2 deneme kap görevi kitap bölümüne bağlı", any(bi.book_section_id == d["d1"] for bi in t.book_items))
            _complete(db, t, 1)
            pm.sync_item_progress(db, item)
            db.commit()
        dn = books()[d["dn"]]
        check("D3 öğrenci denemeyi çözdü → deneme kitabı 1/2", dn["completed"] == 1 and sec({d["dn"]: dn}, d["dn"], d["d1"])["completed"] == 1,
              str(dn))
        r = c.post(f"{base}/pool/items", json={"subject_id": d["subj"], "book_id": d["dn"], "section_id": d["d2"],
                                               "quantity": 1, "unit": "deneme"})
        i2 = next(i for i in r.json()["data"]["period"]["items"] if i["section_id"] == d["d2"])
        r = c.post(f"{base}/pool/items/{i2['id']}/session-mark", json={"count": 1})
        dn = books()[d["dn"]]
        check("D4 deneme seans işareti de kitap sayacına yazıldı (2/2)", r.status_code == 200 and dn["completed"] == 2, str(dn))

        # kitap yanlış derse
        r = c.post(f"{base}/pool/items", json={"subject_id": d["other"], "book_id": d["sb"], "section_id": d["s2"],
                                               "quantity": 1, "unit": "test"})
        check("V1 kitap başka ders adına eklenemez (book_subject_mismatch)", r.status_code == 422
              and r.json()["detail"]["code"] == "book_subject_mismatch", r.text[:160])
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
