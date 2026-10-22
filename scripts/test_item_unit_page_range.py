"""Smoke — kaynaksız konulu görevde birim (test/soru/sayfa) + sayfa aralığı (2026-10-22).

Koç kayıtlı kitabı sayfa aralığıyla böler ("Basınç (Hız Fen): s. 45–50"). Sayfa/soru
kalemi müfredat konusuna bağlı kalır ama TEST hacmine girmez; soru kaleminde D/Y/B konu
performansına girer; devam sayfası önerilir; havuzda sayfa/soru kalemi güne alınınca
konusunu kaybetmez.

  python scripts/test_item_unit_page_range.py
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
from sqlalchemy.orm import joinedload  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    PoolItem, StudyPeriod, Subject, Task, TaskBookItem, Track, User, UserRole,
)
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import completion, curriculum_progress as cp, gorev_stats, pool_mode as pm  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.topic_performance import compute_topic_performance  # noqa: E402

PFX = f"unitpg_{secrets.token_hex(3)}"
PWD = "Ogrenci!234567xy"
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
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Birim Koç",
                     role=UserRole.TEACHER, is_active=True, must_change_password=False)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Birim Öğrenci",
                  role=UserRole.STUDENT, is_active=True, must_change_password=False, teacher_id=coach.id,
                  grade_level=12, track=Track.SAYISAL, entry_year_grade9=2023)
        db.add(st)
        db.flush()
        kim = db.query(Subject).filter(Subject.name == "TYT Kimya", Subject.is_builtin.is_(True)).first()
        topics = cp.leaf_topics_for_student(db, st, coach.id, [kim.id]).by_subject[kim.id]
        db.commit()
        return {"coach": coach.id, "st": st.id, "subject": kim.id, "t1": topics[0].id, "t2": topics[1].id,
                "t1name": topics[0].name}


def cleanup(d):
    with SessionLocal() as db:
        u = [d["st"], d["coach"]]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _task(db, tid):
    return (db.query(Task).options(joinedload(Task.book_items)).filter(Task.id == tid).one())


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    today = date.today()
    print(f"\n=== birim + sayfa aralığı — {PFX} ===\n")
    try:
        c = TestClient(app)
        assert c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD}).status_code == 200
        base = f"/api/v2/teacher/students/{d['st']}"

        def create(item, title="Görev", day=today):
            return c.post(f"{base}/tasks", json={"date": day.isoformat(), "type": "test", "title": title,
                                                 "is_draft": False, "items": [item]})

        # 1 sayfa aralığı → adet aralıktan, başlık + birim
        r = create({"book_id": None, "section_id": None, "topic_id": d["t1"], "label": "Hız Fen",
                    "planned_count": 1, "unit": "sayfa", "page_from": 45, "page_to": 50})
        check("1 sayfa görevi oluştu", r.status_code == 200, r.text[:300])
        with SessionLocal() as db:
            t = db.query(Task).filter(Task.student_id == d["st"]).order_by(Task.id.desc()).first()
            sayfa_tid = t.id
            it = t.book_items[0]
            check("2 kalem: unit=sayfa · s.45–50 · adet 6 · konu bağlı",
                  it.unit == "sayfa" and it.page_from == 45 and it.page_to == 50
                  and it.planned_count == 6 and it.topic_id == d["t1"], f"{it.unit} {it.page_from} {it.planned_count}")
            check("3 başlık 'Konu (Hız Fen): s. 45–50'",
                  t.title == f"{d['t1name']} (Hız Fen): s. 45–50", t.title)

        # 4 ters aralık 422
        r = create({"book_id": None, "section_id": None, "topic_id": d["t1"], "planned_count": 1,
                    "unit": "sayfa", "page_from": 50, "page_to": 45})
        check("4 ters aralık → 422 invalid_page_range",
              r.status_code == 422 and "invalid_page_range" in r.text, r.text[:200])

        # 5 soru görevi
        r = create({"book_id": None, "section_id": None, "topic_id": d["t2"], "planned_count": 20, "unit": "soru"})
        check("5 soru görevi oluştu", r.status_code == 200, r.text[:300])
        # 6 test görevi (eski davranış)
        r = create({"book_id": None, "section_id": None, "topic_id": d["t2"], "planned_count": 3})
        check("6 test görevi (birimsiz) oluştu", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            tasks = (db.query(Task).options(joinedload(Task.book_items))
                     .filter(Task.student_id == d["st"]).order_by(Task.id).all())
            soru_t = next(t for t in tasks if t.book_items[0].unit == "soru")
            test_t = next(t for t in tasks if t.book_items[0].unit is None)
            sayfa_t = next(t for t in tasks if t.id == sayfa_tid)
            check("7 sınıflama: sayfa/soru=etkinlik · test=test",
                  gorev_stats.classify_gorev(sayfa_t) == "etkinlik"
                  and gorev_stats.classify_gorev(soru_t) == "etkinlik"
                  and gorev_stats.classify_gorev(test_t) == "test")
            s = gorev_stats.summarize(tasks)
            check("8 özet: 3 görev · test hacmi yalnız 3", s.gorev_total == 3 and s.test_planned == 3,
                  f"{s.gorev_total} {s.test_planned}")
            check("9 tamamlama hesabı: sayfa/soru girmez",
                  not completion.item_counts(sayfa_t.book_items[0])
                  and not completion.item_counts(soru_t.book_items[0])
                  and completion.item_counts(test_t.book_items[0]))
            check("10 analitik test kalemi: sayfa/soru değil",
                  not gorev_stats.item_is_test(soru_t.book_items[0]) and gorev_stats.item_is_test(test_t.book_items[0]))
            ids = {"sayfa": (sayfa_t.id, sayfa_t.book_items[0].id), "soru": (soru_t.id, soru_t.book_items[0].id)}

        # 11 koç görev yanıtı birim taşır
        wk = c.get(f"{base}/day", params={"date": today.isoformat()}).json()
        unit_map = {i["id"]: (i.get("unit"), i.get("page_from")) for t in wk["tasks"] for i in t["items"]}
        check("11 koç yanıtı: unit + page_from", unit_map.get(ids["sayfa"][1]) == ("sayfa", 45)
              and unit_map.get(ids["soru"][1])[0] == "soru", str(unit_map))

        # 12 devam önerisi — nota göre
        r = c.get(f"{base}/page-suggestion", params={"note": "hız fen"}).json()
        check("12 öneri: son s.45–50 → devam 51 + not listesinde 'Hız Fen'",
              r.get("next_from") == 51 and r["last"]["page_to"] == 50 and "Hız Fen" in r.get("notes", []), str(r))
        r = c.get(f"{base}/page-suggestion", params={"topic_id": d["t1"]}).json()
        check("13 öneri konuya göre de bulur", r.get("next_from") == 51, str(r))

        # 14-16 öğrenci tarafı
        sc = TestClient(app)
        get_login_limiter().reset()
        assert sc.post("/api/v2/auth/login", json={"email": f"{PFX}_s@test.invalid", "password": PWD}).status_code == 200
        day = sc.get("/api/v2/student/day").json()
        items = {i["id"]: i for t in day["tasks"] for i in t["items"]}
        si = items[ids["sayfa"][1]]
        check("14 öğrenci: sayfa kalemi is_test_unit=False + aralık",
              si["is_test_unit"] is False and si["unit"] == "sayfa" and si["page_to"] == 50, str(si))
        r = sc.post(f"/api/v2/student/tasks/{ids['soru'][0]}/items/{ids['soru'][1]}/set-completed",
                    json={"completed": 20, "correct": 14, "wrong": 4, "blank": 2})
        check("15 soru: 20 çözüldü 14D 4Y 2B kabul", r.status_code == 200, r.text[:200])
        r = sc.post(f"/api/v2/student/tasks/{ids['soru'][0]}/items/{ids['soru'][1]}/set-completed",
                    json={"completed": 20, "correct": 18, "wrong": 4, "blank": 0})
        check("16 soru: D+Y > çözülen → 422", r.status_code == 422, r.text[:200])
        r = sc.post(f"/api/v2/student/tasks/{ids['sayfa'][0]}/items/{ids['sayfa'][1]}/set-completed",
                    json={"completed": 6})
        check("17 sayfa: 6 sayfa yaptım", r.status_code == 200, r.text[:200])

        with SessionLocal() as db:
            perf = compute_topic_performance(db, d["st"])
            sp = next((s for s in perf if s.subject_id == d["subject"]), None)
            t2 = next((t for t in sp.topics if t.topic_id == d["t2"]), None) if sp else None
            t1 = next((t for t in sp.topics if t.topic_id == d["t1"]), None) if sp else None
            check("18 konu performansı: soru D/Y girer, test sayılmaz",
                  t2 is not None and t2.correct == 14 and t2.wrong == 4 and t2.tests_solved == 0, str(t2))
            check("19 sayfa konu performansına girmez", t1 is None or t1.tests_solved == 0, str(t1))
            st = db.get(User, d["st"])
            prog = cp.compute_curriculum_progress(db, st, d["coach"])
            tp = next((t for s in prog.subjects for t in s.topics if t.topic_id == d["t1"]), None)
            check("20 müfredat: sayfa çalışılan konu 'devam' · kaynaksız test 0",
                  tp is not None and tp.status == "devam" and tp.sourceless_completed == 0,
                  f"{tp.status if tp else None} {tp.sourceless_completed if tp else None}")

        # 21 haftaya yay: konu + birim korunur, aralık taşınmaz
        tom = today + timedelta(days=1)
        r = c.post(f"/api/v2/teacher/tasks/{ids['sayfa'][0]}/spread", json={"dates": [tom.isoformat()]})
        check("21 yay ucu 200", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            cp_t = (db.query(Task).options(joinedload(Task.book_items))
                    .filter(Task.student_id == d["st"], Task.date == tom).first())
            bi = cp_t.book_items[0] if cp_t else None
            check("22 kopya: konu + unit=sayfa korunur, aralık yok",
                  bi is not None and bi.topic_id == d["t1"] and bi.unit == "sayfa" and bi.page_from is None,
                  f"{bi.topic_id if bi else None} {bi.unit if bi else None}")

        # 23-24 havuz: sayfa kalemi güne alınınca konusunu korur
        with SessionLocal() as db:
            st = db.get(User, d["st"])
            st.program_mode = "havuz"
            coach = db.get(User, d["coach"])
            kim = db.get(Subject, d["subject"])
            from app.models import Topic
            topic = db.get(Topic, d["t1"])
            p = pm.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=1),
                               expected_next_on=today + timedelta(days=5))
            pit = pm.add_item(db, period=p, student=st, subject=kim, quantity=None, unit="sayfa",
                              topic=topic, label="Hız Fen", page_from=51, page_to=55)
            check("23 havuz kalemi: s.51–55 → miktar 5", pit.quantity == 5 and pit.page_to == 55)
            task = pm.put_in_cup(db, item=pit, day=today + timedelta(days=2))
            bi = task.book_items[0]
            check("24 kaba alınca: konulu birimli kalem (Diğer değil) + aralık",
                  bi.topic_id == d["t1"] and bi.unit == "sayfa" and bi.page_from == 51
                  and "s. 51–55" in task.title, f"{task.title} {bi.unit}")
            db.commit()
        r = c.get(f"{base}/page-suggestion", params={"note": "Hız Fen"}).json()
        check("25 öneri havuzu da görür → devam 56", r.get("next_from") == 56, str(r))

        # 26-31 konuya bağlı ETKİNLİK görevi (özet) — müfredat sinyali, test sayılmaz
        with SessionLocal() as db:
            st = db.get(User, d["st"])
            st.program_mode = "gun_gun"
            from app.models import Topic
            t3 = cp.leaf_topics_for_student(db, st, d["coach"], [d["subject"]]).by_subject[d["subject"]][2]
            t3id = t3.id
            db.commit()
        r = c.post(f"{base}/tasks", json={"date": today.isoformat(), "type": "ozet", "title": "TYT Kimya · özet",
                                          "is_draft": False, "items": [], "topic_id": t3id})
        check("26 konuya bağlı özet görevi oluştu", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            ot = db.query(Task).filter(Task.student_id == d["st"], Task.topic_id == t3id).first()
            oz_id = ot.id if ot else None
            check("27 tasks.topic_id yazıldı + etkinlik sınıfı",
                  ot is not None and gorev_stats.classify_gorev(ot) == "etkinlik")
            st = db.get(User, d["st"])
            prog = cp.compute_curriculum_progress(db, st, d["coach"])
            tp = next((t for s_ in prog.subjects for t in s_.topics if t.topic_id == t3id), None)
            check("28 tamamlanmadan: müfredatta 'planlandi'", tp is not None and tp.status == "planlandi",
                  tp.status if tp else None)
        wk = c.get(f"{base}/day", params={"date": today.isoformat()}).json()
        tt = next((t for t in wk["tasks"] if t["id"] == oz_id), {})
        check("29 koç yanıtı: activity_topic_name", tt.get("activity_topic_id") == t3id
              and tt.get("activity_topic_name"), str(tt.get("activity_topic_name")))
        r = sc.post(f"/api/v2/student/tasks/{oz_id}/complete", json={})
        check("30 öğrenci özeti tamamladı", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            st = db.get(User, d["st"])
            prog = cp.compute_curriculum_progress(db, st, d["coach"])
            tp = next((t for s_ in prog.subjects for t in s_.topics if t.topic_id == t3id), None)
            check("31 tamamlanınca: 'devam' · kaynaksız test 0",
                  tp is not None and tp.status == "devam" and tp.sourceless_completed == 0,
                  f"{tp.status if tp else None}")
        r = c.post(f"/api/v2/teacher/tasks/{oz_id}/spread", json={"dates": [(today + timedelta(days=3)).isoformat()]})
        with SessionLocal() as db:
            cpy = db.query(Task).filter(Task.student_id == d["st"], Task.date == today + timedelta(days=3)).first()
            check("32 yay: etkinlik kopyası konuyu taşır", cpy is not None and cpy.topic_id == t3id, r.text[:150])
        r = c.post(f"{base}/tasks", json={"date": today.isoformat(), "type": "ozet", "title": "x · y",
                                          "is_draft": False, "items": [], "topic_id": 99999999})
        check("33 olmayan konu reddedilir", r.status_code in (404, 422), str(r.status_code))
    finally:
        cleanup(d)
    print(f"\n=== {passed} passed · {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
