"""Deneme sonuç girişi D2 smoke (2026-10-20).

   1. Öğrenci 2 denemenin sonucunu tek seferde girer: 1. D/Y (boş otomatik), 2. "sonra gireceğim"
   2. Net (YKS 4 yanlış 1 doğru) + sonuç bekliyor işareti + süre
   3. Soru sayısı ESNEK: koç 6 dedi, öğrenci 7 yazar → kabul, kayda geçer
   4. D+Y+B soru sayısını aşarsa 422 (soru sayısını düzelt mesajı)
   5. "Çözmedim" → tamamlanan 0, görev kısmi, kitap sayacı geri
   6. Kaynaksız branş (20 soru) — eski "D+Y ≤ tamamlanan" kuralına takılmaz
   7. Koç aynı uçla düzeltir · başka koç 404
   8. Hatırlatma cron'u: 2+ gün sonucu girilmemiş → öğrenciye 1 push, ikinci koşu yok
   9. Havuz kap görevi aynı uçla → havuz kalemi ilerler
  10. Gelecek tarihli görev 422 · geçersiz süre 422
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
    TaskBookItem, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import deneme_service, pool_mode, push_notifications  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"dres_{secrets.token_hex(3)}"
PWD = "DenemeRes!2345x"
today = date.today()
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "books": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                     role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD), full_name="Diğer Koç",
                     role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other]); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Öğrenci",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                  track=Track.SAYISAL, must_change_password=False)
        hv = User(email=f"{PFX}_h@test.invalid", password_hash=hash_password(PWD), full_name="Havuz",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                  track=Track.SAYISAL, program_mode="havuz", must_change_password=False)
        db.add_all([st, hv]); db.flush()
        bio = Subject(name="TYT Biyoloji", teacher_id=coach.id, exam_section=ExamSection.TYT)
        mat = Subject(name="TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add_all([bio, mat]); db.flush()
        b = Book(teacher_id=coach.id, subject_id=bio.id, name=f"{PFX} Bio Branş", type=BookType.BRANS_DENEMESI)
        db.add(b); db.flush()
        secs = [BookSection(book_id=b.id, label=f"DENEME {i}", test_count=1, order=i) for i in range(1, 6)]
        db.add_all(secs)
        db.add_all([StudentBook(student_id=st.id, book_id=b.id), StudentBook(student_id=hv.id, book_id=b.id)])
        pool_mode.open_period(db, student=hv, coach=coach, opened_on=today - timedelta(days=1),
                              expected_next_on=today + timedelta(days=6))
        db.commit()
        ids["users"] += [coach.id, other.id, st.id, hv.id]
        ids["books"].append(b.id)
        return {"coach": coach.id, "st": st.id, "hv": hv.id, "bio": bio.id, "mat": mat.id, "book": b.id,
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
        db.execute(sa_delete(Subject).where(Subject.teacher_id.in_(u)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def task_items(tid):
    with SessionLocal() as db:
        t = db.get(Task, tid)
        items = sorted(t.book_items, key=lambda x: x.id)
        db.expunge_all()
        return t, items


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    print(f"\n=== deneme sonuç girişi D2 — {PFX} ===\n")
    pushes: list[tuple] = []
    orig_push = push_notifications.safe_push
    push_notifications.safe_push = lambda db, **kw: pushes.append((kw.get("user_id"), kw.get("title")))
    try:
        c = login(f"{PFX}_t@test.invalid")
        s = login(f"{PFX}_s@test.invalid")
        sid = d["st"]
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": today.isoformat(), "kind": "brans", "book_id": d["book"], "count": 2,
                         "is_draft": False})
        assert r.status_code == 200, r.text
        tid = r.json()["data"]["id"]
        _, its = task_items(tid)
        i1, i2 = its[0].id, its[1].id

        # 1-2
        r = s.post(f"/api/v2/student/tasks/{tid}/deneme-results", json={"rows": [
            {"item_id": i1, "correct": 4, "wrong": 1, "duration_minutes": 15},
            {"item_id": i2},
        ]})
        check("1a sonuçlar 200", r.status_code == 200, r.text[:300])
        data = r.json()["data"]
        rows = {x["id"]: x for x in data["items"]}
        check("1b görev tamamlandı (2/2 deneme çözüldü)", data["status"] == "completed", data["status"])
        check("1c boş otomatik (6−4−1=1)", rows[i1]["blank"] == 1, rows[i1])
        check("2a net 4 − 1/4 = 3.75", rows[i1]["net"] == 3.75, rows[i1]["net"])
        check("2b süre 15", rows[i1]["duration_minutes"] == 15)
        check("2c 2. deneme 'sonuç bekliyor'", rows[i2]["result_pending"] is True and rows[i1]["result_pending"] is False)

        # 3
        r = s.post(f"/api/v2/student/tasks/{tid}/deneme-results", json={"rows": [
            {"item_id": i1, "correct": 6, "wrong": 1, "question_count": 7}]})
        check("3a soru 7 + 6D 1Y kabul", r.status_code == 200, r.text[:300])
        _, its = task_items(tid)
        check("3b soru sayısı 7 kaydedildi, boş 0", its[0].question_count == 7 and its[0].blank_count == 0,
              (its[0].question_count, its[0].blank_count))

        # 4
        r = s.post(f"/api/v2/student/tasks/{tid}/deneme-results", json={"rows": [
            {"item_id": i2, "correct": 6, "wrong": 2, "question_count": 6}]})
        check("4 D+Y soru sayısını aşınca 422", r.status_code == 422
              and r.json()["detail"]["code"] == "result_exceeds_questions", r.text[:200])

        # 5
        r = s.post(f"/api/v2/student/tasks/{tid}/deneme-results", json={"rows": [{"item_id": i2, "solved": False}]})
        check("5a çözmedim 200", r.status_code == 200, r.text[:200])
        t, its = task_items(tid)
        check("5b tamamlanan 0, görev kısmi", its[1].completed_count == 0 and t.status.value == "partial",
              (its[1].completed_count, t.status))
        with SessionLocal() as db:
            sp = db.query(SectionProgress).join(StudentBook).filter(
                StudentBook.student_id == sid, SectionProgress.book_section_id == d["secs"][1]).first()
            check("5c kitap sayacı geri (çözülen 0, rezerv 1)", sp and sp.completed_count == 0 and sp.reserved_count == 1,
                  sp and (sp.completed_count, sp.reserved_count))

        # 6
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": today.isoformat(), "kind": "brans", "subject_id": d["mat"], "count": 2,
                         "question_count": 20, "is_draft": False})
        tid6 = r.json()["data"]["id"]
        _, its6 = task_items(tid6)
        r = s.post(f"/api/v2/student/tasks/{tid6}/deneme-results", json={"rows": [
            {"item_id": its6[0].id, "correct": 15, "wrong": 3}]})
        check("6 kaynaksız branş 15D 3Y kabul (eski kurala takılmaz)", r.status_code == 200, r.text[:200])

        # 7
        r = c.post(f"/api/v2/teacher/tasks/{tid}/deneme-results", json={"rows": [
            {"item_id": i2, "correct": 3, "wrong": 2}]})
        check("7a koç düzeltir 200", r.status_code == 200, r.text[:200])
        rows = {x["id"]: x for x in r.json()["data"]["items"]}
        check("7b koç yanıtı net + bekliyor değil", rows[i2]["net"] == 2.5 and rows[i2]["result_pending"] is False,
              rows[i2])
        o = login(f"{PFX}_o@test.invalid")
        r = o.post(f"/api/v2/teacher/tasks/{tid}/deneme-results", json={"rows": [{"item_id": i2, "solved": False}]})
        check("7c başka koç 404", r.status_code == 404, r.status_code)

        # 8 hatırlatma
        with SessionLocal() as db:
            t6 = db.get(Task, tid6)
            t6.date = today - timedelta(days=3)
            db.commit()
        r = s.post(f"/api/v2/student/tasks/{tid6}/deneme-results", json={"rows": [{"item_id": its6[1].id}]})
        with SessionLocal() as db:
            res = deneme_service.run_result_reminders(db, now=datetime.now(timezone.utc))
        mine = [p for p in pushes if p[0] == sid and p[1] == "Deneme sonucun bekliyor"]
        check("8a öğrenciye 1 hatırlatma", len(mine) == 1, str(pushes))
        with SessionLocal() as db:
            res2 = deneme_service.run_result_reminders(db, now=datetime.now(timezone.utc))
        mine = [p for p in pushes if p[0] == sid and p[1] == "Deneme sonucun bekliyor"]
        check("8b ikinci koşuda tekrar yok", len(mine) == 1 and res2["items"] == 0, str(res2))

        # 9 havuz
        h = login(f"{PFX}_h@test.invalid")
        r = c.post(f"/api/v2/teacher/students/{d['hv']}/pool/deneme-items",
                   json={"kind": "brans", "book_id": d["book"], "count": 2})
        with SessionLocal() as db:
            pid = db.query(PoolItem).filter(PoolItem.student_id == d["hv"]).first().id
        h.post("/api/v2/student/pool/cup", json={"item_id": pid, "count": 2})
        with SessionLocal() as db:
            ct = db.query(Task).filter(Task.pool_item_id == pid).first()
            ctid = ct.id
            cits = sorted(x.id for x in ct.book_items)
        r = h.post(f"/api/v2/student/tasks/{ctid}/deneme-results", json={"rows": [
            {"item_id": cits[0], "correct": 5, "wrong": 1}, {"item_id": cits[1], "correct": 4, "wrong": 0}]})
        check("9a havuz kap görevi sonuç 200", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            pi = db.get(PoolItem, pid)
            check("9b havuz kalemi 2/2", pi.completed == 2, pi.completed)

        # 10
        r = c.post(f"/api/v2/teacher/students/{sid}/deneme-tasks",
                   json={"date": (today + timedelta(days=2)).isoformat(), "kind": "brans",
                         "subject_id": d["mat"], "count": 1, "question_count": 20, "is_draft": False})
        ft = r.json()["data"]
        r = s.post(f"/api/v2/student/tasks/{ft['id']}/deneme-results", json={"rows": [
            {"item_id": ft["items"][0]["id"], "correct": 1, "wrong": 0}]})
        check("10a gelecek tarihli görev reddedilir (future_task_blocked)", r.status_code in (400, 422) and r.json()["detail"]["code"] == "future_task_blocked", r.text[:200])
        r = s.post(f"/api/v2/student/tasks/{tid}/deneme-results", json={"rows": [
            {"item_id": i1, "duration_minutes": 0}]})
        check("10b geçersiz süre 422", r.status_code == 422 and r.json()["detail"]["code"] == "invalid_duration")
    finally:
        push_notifications.safe_push = orig_push
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
