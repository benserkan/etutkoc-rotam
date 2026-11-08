"""Toplu deneme sonucu (2026-11-08).

Öğrenci bir görevdeki birden çok branş denemesinin toplamını tek satıra girerse
(combine_with) sonuç tek kayıt olur ama deneme adedi korunur:
  1. Aynı bölümden 3 deneme → Denemeler kayıtları "· 1. deneme / 2. / 3." diye ayrışır
  2. 1. satır 2 denemenin toplamı (12 soru, 10D 2B) → tek kayıt "· 1.–2. deneme (toplu)",
     2. deneme çözüldü + sonuç beklemez; 3. deneme ayrı (sonuç bekler)
  3. Kitap sayacı: 2 deneme çözüldü sayılır
  4. Analiz: deneme adedi 2, deneme başına ortalama net 5 (10 ÷ 2), ortalama net % deneme ağırlıklı
  5. Başka gün tek deneme → ağırlıklı ortalama (83,3 × 2 + 37,5) ÷ 3
  6. Hatırlatma cron'u toplu sonuca bağlı denemeye bildirim üretmez
  7. Ayrı girişe dönüş: bağ çözülür, soru sayısı deneme başına değere iner
  8. Hatalar: sonuçsuz toplu · kendi kendine bağ · zincir
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

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, ExamResult, SectionProgress, StudentBook, Subject, Task, TaskBookItem, User, UserRole,
)
from app.models.book import BookType  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.services.deneme_service import run_result_reminders  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"dcr_{secrets.token_hex(3)}"
PWD = "Toplu!Deneme2345"
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


def login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def main() -> int:
    ids: dict[str, int] = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                         role=UserRole.TEACHER, is_active=True)
            db.add(coach); db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Öğrenci",
                      role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                      must_change_password=False)
            db.add(st); db.flush()
            bio = Subject(name="TYT Biyoloji", teacher_id=coach.id, order=1, exam_section=ExamSection.TYT)
            db.add(bio); db.flush()
            book = Book(name=f"{PFX} 3D Biyoloji Branş", teacher_id=coach.id, subject_id=bio.id,
                        type=BookType.BRANS_DENEMESI)
            db.add(book); db.flush()
            sec = BookSection(book_id=book.id, label="Deneme", order=1, test_count=10)
            db.add(sec); db.flush()
            db.add(StudentBook(student_id=st.id, book_id=book.id))
            db.commit()
            ids.update(coach=coach.id, st=st.id, bio=bio.id, book=book.id, sec=sec.id)

        c = login(f"{PFX}_t@test.invalid")
        sid = ids["st"]
        d1 = (date.today() - timedelta(days=3)).isoformat()
        d2 = (date.today() - timedelta(days=1)).isoformat()
        t = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": d1, "kind": "brans", "book_id": ids["book"], "count": 3,
                         "question_count": 6}).json()["data"]
        t2 = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                    json={"date": d2, "kind": "brans", "book_id": ids["book"], "count": 1,
                          "question_count": 6}).json()["data"]
        with SessionLocal() as db:
            for x in (t, t2):
                db.get(Task, x["id"]).is_draft = False
            db.commit()
        i1, i2, i3 = [it["id"] for it in t["items"]]
        s = login(f"{PFX}_s@test.invalid")
        url = f"/api/v2/student/tasks/{t['id']}/deneme-results"

        # 1 — ayrı giriş: numaralı başlıklar
        r = s.post(url, json={"rows": [{"item_id": i1, "solved": True, "correct": 5, "wrong": 1},
                                       {"item_id": i2, "solved": True, "correct": 4, "wrong": 2},
                                       {"item_id": i3, "solved": False}]})
        check("1a ayrı giriş 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            titles = sorted(e.title for e in db.query(ExamResult).filter(ExamResult.student_id == sid))
        check("1b aynı bölüm denemeleri numaralı",
              titles == [f"{PFX} 3D Biyoloji Branş — Deneme · 1. deneme",
                         f"{PFX} 3D Biyoloji Branş — Deneme · 2. deneme"], str(titles))

        # 2 — toplu giriş (1+2), 3. sonuçsuz çözüldü
        r = s.post(url, json={"rows": [
            {"item_id": i1, "solved": True, "correct": 10, "wrong": 0, "blank": 2, "question_count": 12,
             "combine_with": [i2]},
            {"item_id": i3, "solved": True}]})
        check("2a toplu giriş 200", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            a, b, cc = db.get(TaskBookItem, i1), db.get(TaskBookItem, i2), db.get(TaskBookItem, i3)
            recs = db.query(ExamResult).filter(ExamResult.student_id == sid).all()
            check("2b tek kayıt + toplu başlık",
                  len(recs) == 1 and recs[0].title.endswith("· 1.–2. deneme (toplu)")
                  and recs[0].total_correct == 10 and recs[0].total_blank == 2, str([x.title for x in recs]))
            check("2c '\"exams\": 2' kayıtta", '"exams": 2' in (recs[0].analysis_meta or ""), recs[0].analysis_meta)
            check("2d 1. satır: 2 deneme, 12 soru", a.combined_count == 2 and a.question_count == 12,
                  f"{a.combined_count} {a.question_count}")
            check("2e 2. deneme bağlı + çözüldü + sonuç yok",
                  b.combined_into_id == a.id and b.completed_count == 1 and b.correct_count is None,
                  f"{b.combined_into_id} {b.completed_count} {b.correct_count}")
            check("2f 3. deneme çözüldü, sonuç bekliyor", cc.completed_count == 1 and cc.correct_count is None)
            sbk = db.query(StudentBook).filter(StudentBook.student_id == sid).first()
            sp = db.query(SectionProgress).filter(SectionProgress.student_book_id == sbk.id).first()
            check("3 kitap sayacı 3 deneme çözüldü (toplu 2 + 1)", sp.completed_count == 3, str(sp.completed_count))
        pend = s.get("/api/v2/student/deneme-pending").json()
        check("2g sonucu eksik listesi yalnız 3. deneme", [x["item_id"] for x in pend["rows"]] == [i3], str(pend))
        task_out = s.get(f"/api/v2/student/day?date={d1}").json()
        it_out = {it["id"]: it for tk in task_out.get("tasks", []) for it in tk["items"]}
        check("2h görev çıktısı bağı taşır",
              it_out.get(i2, {}).get("combined_into_id") == i1 and it_out.get(i2, {}).get("result_pending") is False
              and it_out.get(i1, {}).get("combined_count") == 2, str(it_out.get(i2)))

        # 4 — analiz
        an = c.get(f"/api/v2/teacher/students/{sid}/deneme-analysis").json()
        bs = next(x for x in an["series"] if x["kind"] == "brans")
        check("4a deneme adedi 2, 1 nokta, 1 toplu", bs["count"] == 2 and bs["points_count"] == 1
              and bs["combined_points"] == 1, f"{bs['count']} {bs['points_count']} {bs['combined_points']}")
        check("4b deneme başına ortalama net 5", bs["avg_net"] == 5.0, str(bs["avg_net"]))
        check("4c deneme başına soru 6", bs["avg_questions"] == 6.0, str(bs["avg_questions"]))
        check("4d nokta 2 deneme taşır", bs["points"][0]["exams"] == 2 and bs["points"][0]["questions"] == 12,
              str(bs["points"][0]))
        check("4e bekleyen 1", bs["pending"] == 1, str(bs["pending"]))

        # 5 — başka gün tek deneme → ağırlıklı ortalama
        r = s.post(f"/api/v2/student/tasks/{t2['id']}/deneme-results",
                   json={"rows": [{"item_id": t2["items"][0]["id"], "solved": True, "correct": 3, "wrong": 3}]})
        check("5a tek deneme 200", r.status_code == 200, r.text[:200])
        bs = next(x for x in c.get(f"/api/v2/teacher/students/{sid}/deneme-analysis").json()["series"]
                  if x["kind"] == "brans")
        want = round((83.3 * 2 + 37.5) / 3, 1)
        check("5b ortalama net % deneme ağırlıklı", abs(bs["avg_net_pct"] - want) <= 0.1 and bs["count"] == 3,
              f"{bs['avg_net_pct']} beklenen {want}")
        check("5c deneme başına ortalama net (10 + 2,25) ÷ 3", bs["avg_net"] == round(12.25 / 3, 2), str(bs["avg_net"]))

        # 6 — hatırlatma
        with SessionLocal() as db:
            run_result_reminders(db, now=datetime.now(timezone.utc))
            b = db.get(TaskBookItem, i2); cc = db.get(TaskBookItem, i3)
            check("6 hatırlatma yalnız 3. denemeye", b.result_reminded_at is None and cc.result_reminded_at is not None,
                  f"{b.result_reminded_at} {cc.result_reminded_at}")

        # 8 — hatalar
        r = s.post(url, json={"rows": [{"item_id": i1, "solved": True, "combine_with": [i2]}]})
        check("8a sonuçsuz toplu 422", r.status_code == 422 and "invalid_combine" in r.text, r.text[:200])
        r = s.post(url, json={"rows": [{"item_id": i1, "solved": True, "correct": 5, "wrong": 0,
                                        "combine_with": [i1]}]})
        check("8b kendine bağ reddedilir", r.status_code in (404, 422), r.text[:200])
        r = s.post(url, json={"rows": [
            {"item_id": i1, "solved": True, "correct": 10, "wrong": 0, "combine_with": [i2]},
            {"item_id": i2, "solved": True, "correct": 10, "wrong": 0, "combine_with": [i3]}]})
        check("8c zincir reddedilir", r.status_code == 422, r.text[:200])

        # 7 — ayrı girişe dönüş
        r = s.post(url, json={"rows": [{"item_id": i1, "solved": True, "correct": 5, "wrong": 0, "question_count": 6},
                                       {"item_id": i2, "solved": True, "correct": 6, "wrong": 0},
                                       {"item_id": i3, "solved": True, "correct": 4, "wrong": 1}]})
        check("7a ayrı giriş 200", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            a, b = db.get(TaskBookItem, i1), db.get(TaskBookItem, i2)
            n = db.query(ExamResult).filter(ExamResult.student_id == sid).count()
            check("7b bağ çözüldü, soru 6", a.combined_count is None and b.combined_into_id is None
                  and a.question_count == 6, f"{a.combined_count} {b.combined_into_id} {a.question_count}")
            check("7c 4 ayrı kayıt", n == 4, str(n))
    finally:
        with SessionLocal() as db:
            uids = [v for k, v in ids.items() if k in ("coach", "st")]
            if uids:
                tids = [x.id for x in db.query(Task).filter(Task.student_id.in_(uids)).all()]
                if tids:
                    iids = [x.id for x in db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).all()]
                    if iids:
                        db.query(ExamResult).filter(ExamResult.task_book_item_id.in_(iids)).delete(synchronize_session=False)
                        db.query(TaskBookItem).filter(TaskBookItem.id.in_(iids)).update(
                            {TaskBookItem.combined_into_id: None}, synchronize_session=False)
                    db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
                    db.query(Task).filter(Task.id.in_(tids)).delete(synchronize_session=False)
                db.query(ExamResult).filter(ExamResult.student_id.in_(uids)).delete(synchronize_session=False)
                sbs = [x.id for x in db.query(StudentBook).filter(StudentBook.student_id.in_(uids)).all()]
                if sbs:
                    db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sbs)).delete(synchronize_session=False)
                    db.query(StudentBook).filter(StudentBook.id.in_(sbs)).delete(synchronize_session=False)
                if ids.get("book"):
                    db.query(BookSection).filter(BookSection.book_id == ids["book"]).delete(synchronize_session=False)
                    db.query(Book).filter(Book.id == ids["book"]).delete(synchronize_session=False)
                db.query(Subject).filter(Subject.teacher_id == ids.get("coach")).delete(synchronize_session=False)
                db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
                db.commit()
    print(f"\n{passed} geçti, {len(failed)} kaldı")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
