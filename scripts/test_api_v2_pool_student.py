"""Havuz öğrenci uçları + cron smoke (Adım 3, 2026-10-12; K34–K41, K37).

  1. Gün-gün öğrencide /student/pool → mode gun_gun, havuz boş; kap 404 not_havuz
  2. Havuz öğrencisi: paket (özet/tempo cümlesi · kalemler · öneri · bugünkü ders · projeksiyon · dersler)
  3. Kaba al → Bugün ekranında görev (rezerv yok) · aynı kalem ikinci kez 409 · kalandan fazla 422
  4. Mevcut işaretleme ucu ile tamamla → kalem done · kitap sayacı · kaptan geri alma 409 (ilerleme var)
  5. İlerlemesiz kap görevi geri alınır (silinir) · öğrenci kalemi ekler → onay bekliyor, yüzdeye girmez
  6. Günü kapat: kısmi görev küçülür, ilerlemesiz silinir
  7. Cron daily_close dünü kapatır (yalnız havuz öğrencisi) · reminders sabah/akşam + günde bir kez
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
    Book, BookSection, BookType, ClassGroup, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, Task, TaskBookItem, Topic, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.moment_event import MomentEvent  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_cron, pool_mode  # noqa: E402
from app.services import push_notifications  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"pst_{secrets.token_hex(3)}"
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
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Havuz Öğrenci", role=UserRole.STUDENT, is_active=True, teacher_id=coach.id,
                  grade_level=12, track=Track.SAYISAL, program_mode="havuz", class_group="12-C")
        gg = User(email=f"{PFX}_g@test.invalid", password_hash=hash_password(PWD),
                  full_name="Gün Gün", role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12)
        db.add_all([st, gg])
        db.flush()
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        bio = Subject(name=f"{PFX} TYT Biyoloji", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add_all([tyt, bio])
        db.flush()
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t2 = Topic(subject_id=bio.id, name="Hücre", order=1, teacher_id=coach.id)
        db.add_all([t1, t2])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        s1 = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=10, order=1, topic_id=t1.id)
        db.add(s1)
        db.flush()
        sb = StudentBook(student_id=st.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=s1.id, reserved_count=0, completed_count=0))
        db.flush()
        p = pool_mode.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=1),
                                  expected_next_on=today + timedelta(days=6))
        i1 = pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=4, unit="test", book=b, section=s1)
        i2 = pool_mode.add_item(db, period=p, student=st, subject=bio, quantity=3, unit="test", topic=t2)
        i3 = pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=None, unit="etkinlik", label="Video")
        cg = pool_mode.get_or_create_class_group(db, coach=coach, name="12-C")
        pool_mode.set_lesson_days(db, cg, {today.weekday(): [bio.id]})
        db.commit()
        ids["users"] += [coach.id, st.id, gg.id]
        ids["subjects"] += [tyt.id, bio.id]
        ids["books"].append(b.id)
        return {"coach": coach.id, "st": st.id, "gg": gg.id, "tyt": tyt.id, "bio": bio.id, "t2": t2.id,
                "s1": s1.id, "i1": i1.id, "i2": i2.id, "i3": i3.id, "pid": p.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(MomentEvent).where(MomentEvent.user_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(ClassGroup).where(ClassGroup.scope_key == f"coach:{ids['users'][0]}"))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    print(f"\n=== havuz öğrenci uçları + cron smoke — {PFX} ===\n")
    pushes: list[dict] = []
    orig_push = push_notifications.safe_push
    push_notifications.safe_push = lambda db, **kw: pushes.append(kw)  # type: ignore[assignment]
    try:
        # 1
        g = login(f"{PFX}_g@test.invalid")
        r = g.get("/api/v2/student/pool")
        check("1a gün-gün öğrenci: mode gun_gun, havuz yok", r.status_code == 200 and r.json()["mode"] == "gun_gun"
              and r.json()["items"] == [], r.text[:150])
        r = g.post("/api/v2/student/pool/cup", json={"item_id": d["i1"]})
        check("1b gün-gün öğrenci kap kuramaz 404 not_havuz", r.status_code == 404 and r.json()["detail"]["code"] == "not_havuz")

        # 2
        s = login(f"{PFX}_s@test.invalid")
        r = s.get("/api/v2/student/pool")
        j = r.json()
        check("2a havuz paketi: 3 kalem, 8 birim, 6 gün, tempo cümlesi",
              r.status_code == 200 and len(j["items"]) == 3 and j["summary"]["total_units"] == 8
              and j["summary"]["days_left"] == 6 and j["summary"]["pace"] == "yolunda", str(j["summary"]))
        by = {i["id"]: i for i in j["items"]}
        check("2b bugün dershanede Biyoloji → öneri: biyoloji kalemi önerilen", j["lesson_today"] and by[d["i2"]]["suggested"],
              str(j["lesson_today"]))
        check("2c projeksiyon 6 gün, toplam 8", len(j["projection"]) == 6 and sum(x["units"] for x in j["projection"]) == 8)
        check("2d kendi kalemi için ders listesi (alan dolu → AYT dahil olabilir)", any(x["id"] == d["tyt"] for x in j["subjects"]))

        # 3
        r = s.post("/api/v2/student/pool/cup", json={"item_id": d["i1"], "count": 2})
        check("3a kaba al 2 test → bugünün kabında", r.status_code == 200
              and any(c["item_id"] == d["i1"] and c["planned"] == 2 for c in r.json()["data"]["cup"]), r.text[:200])
        check("3b bayatlatma: pool + bugünün günü", f"student:{d['st']}:day:{today.isoformat()}" in r.json()["invalidate"])
        task_id = next(c["task_id"] for c in r.json()["data"]["cup"] if c["item_id"] == d["i1"])
        r = s.get(f"/api/v2/student/day?date={today.isoformat()}")
        check("3c Bugün ekranında kap görevi (mevcut uç)", any(t["id"] == task_id for t in r.json()["tasks"]), r.text[:200])
        with SessionLocal() as db:
            sp = db.query(SectionProgress).filter_by(book_section_id=d["s1"]).one()
            check("3d rezerv 0", sp.reserved_count == 0)
        r = s.post("/api/v2/student/pool/cup", json={"item_id": d["i1"], "count": 1})
        check("3e aynı kalem açık kap görevi varken 409", r.status_code == 409)
        r = s.post("/api/v2/student/pool/cup", json={"item_id": d["i2"], "count": 9})
        check("3f kalandan fazla 422", r.status_code == 422)

        # 4
        r = s.post(f"/api/v2/student/tasks/{task_id}/complete", json={"correct": 20, "wrong": 4, "blank": 0})
        check("4a mevcut tamamlama ucu kap görevini tamamlar", r.status_code == 200, r.text[:150])
        r = s.get("/api/v2/student/pool")
        by = {i["id"]: i for i in r.json()["items"]}
        check("4b kalem done 2 · kalan 2 · özet 2/8", by[d["i1"]]["done"] == 2 and by[d["i1"]]["remaining"] == 2
              and r.json()["summary"]["done_units"] == 2, str(by[d["i1"]]))
        with SessionLocal() as db:
            sp = db.query(SectionProgress).filter_by(book_section_id=d["s1"]).one()
            check("4c kitap sayacı 2 çözüldü, rezerv 0", sp.completed_count == 2 and sp.reserved_count == 0)
        r = s.post(f"/api/v2/student/pool/cup/{task_id}/return")
        check("4d tamamlanmış kap görevi geri alınamaz 409", r.status_code == 409)

        # 5
        r = s.post("/api/v2/student/pool/cup", json={"item_id": d["i2"], "count": 3})
        t2id = next(c["task_id"] for c in r.json()["data"]["cup"] if c["item_id"] == d["i2"])
        r = s.post(f"/api/v2/student/pool/cup/{t2id}/return")
        check("5a ilerlemesiz kap görevi havuza döner (silinir)", r.status_code == 200
              and not any(c["item_id"] == d["i2"] for c in r.json()["data"]["cup"]))
        with SessionLocal() as db:
            check("5b görev gerçekten silindi, kalem kalan 3, kap denemesi 1",
                  db.get(Task, t2id) is None and db.get(PoolItem, d["i2"]).remaining == 3
                  and db.get(PoolItem, d["i2"]).cup_attempts == 1)
        r = s.post("/api/v2/student/pool/items", json={"subject_id": d["bio"], "topic_id": d["t2"], "quantity": 2, "unit": "test"})
        check("5c öğrenci kalem ekledi → onay bekliyor, yüzdeye girmez (toplam hâlâ 8)",
              r.status_code == 200 and any(i["source"] == "ogrenci" and i["approval"] == "bekliyor" and not i["counts"]
                                           for i in r.json()["data"]["items"])
              and r.json()["data"]["summary"]["total_units"] == 8, r.text[:250])
        r = s.post("/api/v2/student/pool/items", json={"subject_id": d["bio"], "unit": "test"})
        check("5d miktarsız 422", r.status_code == 422)

        # 6
        r = s.post("/api/v2/student/pool/cup", json={"item_id": d["i1"], "count": 2})
        t3id = next(c["task_id"] for c in r.json()["data"]["cup"] if c["item_id"] == d["i1"] and c["status"] != "completed")
        r = s.post("/api/v2/student/pool/cup", json={"item_id": d["i3"]})
        with SessionLocal() as db:
            t3 = db.get(Task, t3id)
            bi = t3.book_items[0]
        r = s.post(f"/api/v2/student/tasks/{t3id}/items/{bi.id}/set-completed", json={"completed": 1})
        check("6a kısmi işaretleme (1/2) mevcut uçla", r.status_code == 200, r.text[:150])
        r = s.post("/api/v2/student/pool/close-day", json={})
        j = r.json()["data"]
        by = {i["id"]: i for i in j["items"]}
        check("6b günü kapat: kısmi kalem done 3 kalan 1; etkinlik kabı silindi (kalan 1)",
              r.status_code == 200 and by[d["i1"]]["done"] == 3 and by[d["i1"]]["remaining"] == 1
              and by[d["i3"]]["remaining"] == 1 and not by[d["i3"]]["in_cup_today"], str(by[d["i1"]]))

        # 7 — cron: dün için kap kur (servisle), ilerlemesiz → daily_close siler; gün-gün öğrenci etkilenmez
        yesterday = today - timedelta(days=1)
        with SessionLocal() as db:
            st = db.get(User, d["st"]); it3 = db.get(PoolItem, d["i3"])
            ty = pool_mode.put_in_cup(db, item=it3, day=yesterday)
            gg = db.get(User, d["gg"])
            tg = Task(student_id=gg.id, date=yesterday, type="other", title="Gün-gün görevi", status="pending", is_draft=False)
            db.add(tg)
            db.commit()
            ty_id, tg_id = ty.id, tg.id
        res = pool_cron.daily_close(db=SessionLocal(), now=datetime.now(timezone.utc))
        with SessionLocal() as db:
            check("7a daily_close dünün ilerlemesiz kap görevini sildi, gün-gün görevi durdu",
                  db.get(Task, ty_id) is None and db.get(Task, tg_id) is not None and res["removed"] >= 1, str(res))
        # hatırlatma: bugünkü kapı temizle (kap boş olsun)
        with SessionLocal() as db:
            for t in db.query(Task).filter(Task.student_id == d["st"], Task.date == today).all():
                for bi in t.book_items:
                    db.delete(bi)
                db.delete(t)
            db.commit()
        noon = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=10)   # 13:00 TR
        evening_due = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=17)  # 20:00 TR
        pushes.clear()
        pool_cron.reminders(db=SessionLocal(), now=noon)
        check("7b 13:00 TR — olağan başlama saati (19:00 varsayılan) gelmedi → sabah push yok",
              not [p for p in pushes if p["user_id"] == d["st"]], str(len(pushes)))
        pool_cron.reminders(db=SessionLocal(), now=evening_due)
        mine = [p for p in pushes if p["user_id"] == d["st"]]
        check("7c 20:00 TR — kap boş → sabah hatırlatması, dershane dersi (Biyoloji) cümlesiyle",
              len(mine) == 1 and "Biyoloji" in mine[0]["body"] and mine[0]["data"]["screen"] == "pool", str(mine))
        pool_cron.reminders(db=SessionLocal(), now=evening_due + timedelta(minutes=30))
        check("7d günde bir kez (dedup)", len([p for p in pushes if p["user_id"] == d["st"]]) == 1)
        # akşam: kapta işaretlenmemiş kalem
        with SessionLocal() as db:
            st = db.get(User, d["st"]); it2 = db.get(PoolItem, d["i2"])
            pool_mode.put_in_cup(db, item=it2, day=today, count=1)
            db.commit()
        night = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=18, minutes=30)  # 21:30 TR
        pool_cron.reminders(db=SessionLocal(), now=night)
        ev = [p for p in pushes if p["user_id"] == d["st"] and "işaretle" in p["title"]]
        check("7e 21:30 TR — kapta işaretlenmemiş kalem → akşam hatırlatması", len(ev) == 1, str([p["title"] for p in pushes]))
        pool_cron.reminders(db=SessionLocal(), now=night + timedelta(minutes=30))
        check("7f akşam da günde bir kez", len([p for p in pushes if p["user_id"] == d["st"] and "işaretle" in p["title"]]) == 1)
        check("7g gün-gün öğrenciye hiç push yok", not [p for p in pushes if p["user_id"] == d["gg"]])
    finally:
        push_notifications.safe_push = orig_push  # type: ignore[assignment]
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    if failed:
        print("Başarısız:", failed)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
