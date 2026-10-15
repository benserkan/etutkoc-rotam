"""Havuz seans ekranı uçları smoke (Adım 2b, 2026-10-12; K18–K22).

  1. Seans paketi: tek cümle özet · kalem kalem yapıldı (öğrenci kaydı) · kaçınılan (4 gün kap yok)
  2. Deneme şeridi: net + aynı seride fark · yanlış konular · bu dönem çalışılan konuda yanlış
  3. Önceki seans notu + gündem kuyruğu
  4. Seansta işaretle (K18): ayrı sayaç; kitaplı kalemde kitap sayacına izli koç kaydı; aşım 422
  5. Seansı bitir (K22/K32): başarısız devir → hiçbir şey yazılmaz; başarılı → dönem kapandı +
     seans kaydı + yeni dönem + devir kalemleri (miktar yeniden yazıldı, sayaç 1)
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
    Book, BookSection, BookType, ClassGroup, CoachingSession, PoolItem, SectionProgress, StudentBook,
    StudyPeriod, Subject, Task, TaskBookItem, Topic, Track, User, UserRole,
)
from app.models.coaching_session import CoachingSessionStatus  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.exam_progress import SessionAgendaItem  # noqa: E402
from app.models.exam_result import EQ_RESULT_DOGRU, EQ_RESULT_YANLIS, ExamResult, ExamResultQuestion  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import pool_mode, task_service  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"ps_{secrets.token_hex(3)}"
PWD = "Seans!234567xy"
today = date.today()
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": [], "exams": []}


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
                     full_name="Seans Rehber", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD),
                  full_name="Seans Öğrenci", role=UserRole.STUDENT, is_active=True,
                  teacher_id=coach.id, grade_level=12, track=Track.SAYISAL, program_mode="havuz")
        db.add(st)
        db.flush()
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(tyt)
        db.flush()
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t2 = Topic(subject_id=tyt.id, name="Köklü Sayılar", order=2, teacher_id=coach.id)
        t3 = Topic(subject_id=tyt.id, name="Çarpanlara Ayırma", order=3, teacher_id=coach.id)
        db.add_all([t1, t2, t3])
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
        # denemeler: aynı seri (TYT), eski 40 net → yeni 45 net; yeni denemede Üslü'de 2 yanlış, Köklü 1 yanlış
        e_old = ExamResult(student_id=st.id, created_by_id=coach.id, title="TYT Deneme 1",
                           exam_date=today - timedelta(days=20), section=ExamSection.TYT,
                           total_correct=50, total_wrong=10, total_blank=60, net=40.0)
        e_new = ExamResult(student_id=st.id, created_by_id=coach.id, title="TYT Deneme 2",
                           exam_date=today - timedelta(days=2), section=ExamSection.TYT,
                           total_correct=55, total_wrong=10, total_blank=55, net=45.0)
        db.add_all([e_old, e_new])
        db.flush()
        for n, (tid, res) in enumerate([(t1.id, EQ_RESULT_YANLIS), (t1.id, EQ_RESULT_YANLIS),
                                        (t2.id, EQ_RESULT_YANLIS), (t3.id, EQ_RESULT_DOGRU)], start=1):
            db.add(ExamResultQuestion(exam_result_id=e_new.id, question_no=n, subject_id=tyt.id,
                                      topic_id=tid, result=res))
        db.add(CoachingSession(coach_id=coach.id, student_id=st.id, session_date=today - timedelta(days=6),
                               status=CoachingSessionStatus.DONE, agenda="Geçen seans gündemi",
                               coach_note="Motivasyon düşük", next_change="Fizik azalt", mood=3))
        db.add(SessionAgendaItem(student_id=st.id, created_by_id=coach.id, item_key=f"forgot:{t2.id}",
                                 text="Köklü Sayılar unutuluyor", source="exam"))
        db.commit()
        ids["users"] += [coach.id, st.id]
        ids["subjects"].append(tyt.id)
        ids["books"].append(b.id)
        ids["exams"] += [e_old.id, e_new.id]
        return {"coach": coach.id, "st": st.id, "tyt": tyt.id, "t1": t1.id, "t2": t2.id, "t3": t3.id,
                "book": b.id, "s1": s1.id, "sb": sb.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(u)))
        db.execute(sa_delete(SessionAgendaItem).where(SessionAgendaItem.student_id.in_(u)))
        db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id.in_(ids["exams"])))
        db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(ids["exams"])))
        db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
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


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    print(f"\n=== havuz seans ekranı smoke — {PFX} ===\n")
    try:
        # dönem 5 gün önce açıldı; kalemler servisle (kap akışı dahil)
        with SessionLocal() as db:
            st = db.get(User, d["st"]); coach = db.get(User, d["coach"])
            tyt = db.get(Subject, d["tyt"]); book = db.get(Book, d["book"]); sec = db.get(BookSection, d["s1"])
            p = pool_mode.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=5),
                                      expected_next_on=today)
            i1 = pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=4, unit="test", book=book, section=sec)
            i2 = pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=3, unit="test",
                                    topic=db.get(Topic, d["t2"]))
            i3 = pool_mode.add_item(db, period=p, student=st, subject=tyt, quantity=None, unit="etkinlik", label="Video")
            t = pool_mode.put_in_cup(db, item=i1, day=today - timedelta(days=3), count=2)
            task_service.complete_task(db, t)
            pool_mode.sync_item_progress(db, i1)
            db.commit()
            ids.update({"i1": i1.id, "i2": i2.id, "i3": i3.id, "pid": p.id})

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        base = f"/api/v2/teacher/students/{d['st']}"

        # 1
        r = c.get(f"{base}/pool/session")
        check("1a seans paketi 200", r.status_code == 200, r.text[:200])
        j = r.json()
        check("1b tek cümle özet: yüzde 25 (2/8 birim, 0/3 kalem) + kaçınma",
              "25" in j["headline"] and "2/8" in j["headline"] and "kaçınma" in j["headline"], j["headline"])
        by = {i["id"]: i for i in j["items"]}
        check("1c kitaplı kalem: öğrenci kaydı 2, kalan 2, kaçınılan DEĞİL",
              by[ids["i1"]]["completed"] == 2 and by[ids["i1"]]["remaining"] == 2 and not by[ids["i1"]]["avoided"])
        check("1d 4+ gündür kaba alınmayan iki kalem kaçınılan (gerekçeli)",
              by[ids["i2"]]["avoided"] and by[ids["i3"]]["avoided"]
              and "gündür" in (by[ids["i2"]]["avoided_reason"] or ""), str(by[ids["i2"]]))
        check("1e kaçınılan listesi 2", len(j["avoided"]) == 2)

        # 2
        ex = j["exam"]
        check("2a deneme şeridi: son deneme 45 net, aynı seride +5", ex and ex["net"] == 45.0 and ex["delta"] == 5.0
              and ex["prev_title"] == "TYT Deneme 1", str(ex)[:200])
        check("2b yanlış konular Üslü 2 · Köklü 1 (en çoktan)", [w["name"] for w in ex["wrong_topics"]][:2]
              == ["Üslü Sayılar", "Köklü Sayılar"] and ex["wrong_topics"][0]["wrong"] == 2)
        check("2c bu dönem çalışılan konuda yanlış: yalnız Üslü (Köklü'de ilerleme yok)",
              [w["name"] for w in ex["studied_but_wrong"]] == ["Üslü Sayılar"], str(ex["studied_but_wrong"]))

        # 3
        check("3a önceki seans notu", j["previous_session"] and j["previous_session"]["coach_note"] == "Motivasyon düşük"
              and j["previous_session"]["next_change"] == "Fizik azalt")
        check("3b gündem kuyruğu (Seansa ekle) görünür", any("Köklü" in q["text"] for q in j["agenda_queue"]))

        # 4
        r = c.post(f"{base}/pool/items/{ids['i2']}/session-mark", json={"count": 2})
        check("4a konulu kaleme seansta 2 işaretlendi → yapılan 2, kalan 1", r.status_code == 200
              and next(i for i in r.json()["data"]["items"] if i["id"] == ids["i2"])["session_marked"] == 2
              and next(i for i in r.json()["data"]["items"] if i["id"] == ids["i2"])["remaining"] == 1, r.text[:200])
        check("4b işaret öğrenci kaydına KARIŞMAZ (completed 0)",
              next(i for i in r.json()["data"]["items"] if i["id"] == ids["i2"])["completed"] == 0)
        r = c.post(f"{base}/pool/items/{ids['i1']}/session-mark", json={"count": 1})
        check("4c kitaplı kaleme 1 işaret → done 3 (2 öğrenci + 1 rehber)", r.status_code == 200
              and next(i for i in r.json()["data"]["items"] if i["id"] == ids["i1"])["done_units"] == 3)
        with SessionLocal() as db:
            sp = db.query(SectionProgress).filter_by(book_section_id=d["s1"]).one()
            ent = db.query(SelfStudyEntry).filter(SelfStudyEntry.student_id == d["st"]).all()
            check("4d kitap sayacı 3 çözüldü (2 görev + 1 izli koç kaydı), rezerv 0, kayıt notu seans",
                  sp.completed_count == 3 and sp.reserved_count == 0 and len(ent) == 1
                  and "Seansta" in (ent[0].note or ""), f"c={sp.completed_count} ent={len(ent)}")
        r = c.post(f"{base}/pool/items/{ids['i1']}/session-mark", json={"count": 5})
        check("4e aşım 422 bad_count (en fazla kalan+işaret)", r.status_code == 422 and r.json()["detail"]["code"] == "bad_count")
        r = c.get(f"{base}/pool/session")
        check("4f özet yüzde 62 (5/8 birim)", "yüzde 62 (5/8" in r.json()["headline"], r.json()["headline"])

        # 5
        r = c.post(f"{base}/pool/session/finish", json={
            "closed_on": today.isoformat(), "expected_next_on": (today + timedelta(days=7)).isoformat(),
            "carry": [{"item_id": 999999, "quantity": 1}], "agenda": "x"})
        check("5a devir listesinde olmayan kalem → 422, hiçbir şey yazılmadı",
              r.status_code == 422 and r.json()["detail"]["code"] == "carry_not_leftover")
        with SessionLocal() as db:
            check("5b başarısız bitirme sonrası dönem hâlâ açık, seans kaydı yok",
                  db.get(StudyPeriod, ids["pid"]).status == "acik"
                  and db.query(CoachingSession).filter(CoachingSession.student_id == d["st"]).count() == 1)
        r = c.post(f"{base}/pool/session/finish", json={
            "closed_on": today.isoformat(), "expected_next_on": (today + timedelta(days=7)).isoformat(),
            "carry": [{"item_id": ids["i1"], "quantity": None}, {"item_id": ids["i2"], "quantity": 1}],
            "record_session": True, "agenda": "Havuz değerlendirmesi", "coach_note": "iyi", "mood": 4})
        check("5c seans bitti → yeni açık dönem", r.status_code == 200 and r.json()["data"]["period"]
              and r.json()["data"]["period"]["opened_on"] == today.isoformat(), r.text[:300])
        items = r.json()["data"]["period"]["items"]
        check("5d yeni havuz: 2 devir kalemi (kalan 1 + 1), kaynak devir, sayaç 1",
              len(items) == 2 and all(i["source"] == "devir" and i["carry_count"] == 1 and i["quantity"] == 1 for i in items),
              str([(i["source"], i["quantity"], i["carry_count"]) for i in items]))
        with SessionLocal() as db:
            old = db.get(StudyPeriod, ids["pid"])
            ses = (db.query(CoachingSession).filter(CoachingSession.student_id == d["st"])
                   .order_by(CoachingSession.id.desc()).first())
            newp = pool_mode.get_open_period(db, d["st"])
            check("5e eski dönem kapandı + seans kaydı bağlı; yeni dönem seansla açıldı",
                  old.status == "kapandi" and old.closed_session_id == ses.id and ses.agenda == "Havuz değerlendirmesi"
                  and ses.mood == 4 and newp.opened_session_id == ses.id)
        check("5f eski dönem geçmişte yüzde 62", any(p["id"] == ids["pid"] and p["pct"] == 62 for p in r.json()["data"]["periods"]))
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    if failed:
        print("Başarısız:", failed)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
