"""Program modu geçişi smoke — gün gün ↔ haftalık havuz (2026-10-15).

Kapsam: önizleme (yazmaz) · gün gün → havuz: ileri tarihli dokunulmamış görev silinir + rezerv iade,
kısmi görev kalır (kalan rezervi bırakılır), geçmiş ölü rezerv serbest, ilk dönem açılır, kayıt yazılır ·
havuz → gün gün: açık dönemde engel, seansı bitir + geç → dönem kapanır, yeni dönem açılmaz,
dokunulmamış kap görevi silinir · gün güne geçişten sonra "Programı yok" yerine sarı uyarı · HTTP uçları.

Çalıştır: PYTHONPATH=. python scripts/test_program_mode_switch.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

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
    Book, BookSection, BookType, CoachingSession, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, Task, TaskBookItem, TaskStatus, Topic, Track, User, UserRole, WarningState,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.pool import PERIOD_OPEN, ProgramModeChange  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import analytics, pool_mode as pm, program_mode_switch as pms  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.student_flags import evaluate_flags  # noqa: E402

PFX = f"pms_{secrets.token_hex(3)}"
PWD = "Switch!234567xy"
today = date.today()
now = datetime.now(timezone.utc)
analytics._tr_now = lambda: datetime.combine(today, time(12, 0), tzinfo=timezone.utc)
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
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"PMS {tag}",
             role=role, is_active=True, created_at=now - timedelta(days=60), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _task(db, student, day, planned, done=0, sec=None, book=None, draft=False):
    t = Task(student_id=student.id, date=day, title=f"Görev {day}", type="test", is_draft=draft,
             status=(TaskStatus.COMPLETED if done >= planned else TaskStatus.PARTIAL if done else TaskStatus.PENDING))
    db.add(t)
    db.flush()
    db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=sec.id, planned_count=planned,
                        completed_count=done))
    db.flush()
    return t


def _progress(db, sb_id, sec_id):
    return db.query(SectionProgress).filter_by(student_book_id=sb_id, book_section_id=sec_id).one()


def seed() -> dict:
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add(tyt)
        db.flush()
        ids["subjects"].append(tyt.id)
        top = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        db.add(top)
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Kitap", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=100, order=1, topic_id=top.id)
        db.add(sec)
        db.flush()

        # gün gün öğrenci: geçmişte yapılmamış (ölü rezerv 3) + bugün dokunulmamış 4 + yarın kısmi 5/2 + yarın taslak 2
        s = _user(db, "gg", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL)
        sb = StudentBook(student_id=s.id, book_id=b.id)
        db.add(sb)
        db.flush()
        t_past = _task(db, s, today - timedelta(days=3), 3, sec=sec, book=b)
        t_today = _task(db, s, today, 4, sec=sec, book=b)
        t_part = _task(db, s, today + timedelta(days=1), 5, done=2, sec=sec, book=b)
        t_draft = _task(db, s, today + timedelta(days=2), 2, sec=sec, book=b, draft=True)
        t_done = _task(db, s, today - timedelta(days=1), 2, done=2, sec=sec, book=b)
        # rezerv = yapılmamış toplam: 3 + 4 + 3 + 2 = 12, çözülen 2 + 2 = 4
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=12, completed_count=4))

        # havuz öğrencisi: açık dönem + kalem + bugün dokunulmamış kap + dün kısmi kap
        h = _user(db, "hv", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                  program_mode="havuz")
        sbh = StudentBook(student_id=h.id, book_id=b.id)
        db.add(sbh)
        db.flush()
        db.add(SectionProgress(student_book_id=sbh.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        db.flush()
        p = pm.open_period(db, student=h, coach=coach, opened_on=today - timedelta(days=5))
        it = pm.add_item(db, period=p, student=h, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        cup_today = pm.put_in_cup(db, item=it, day=today, count=3)
        db.commit()
        return {"coach": coach.id, "s": s.id, "h": h.id, "sb": sb.id, "sbh": sbh.id, "sec": sec.id,
                "t_past": t_past.id, "t_today": t_today.id, "t_part": t_part.id, "t_draft": t_draft.id,
                "t_done": t_done.id, "p": p.id, "item": it.id, "cup_today": cup_today.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        db.execute(sa_delete(ProgramModeChange).where(ProgramModeChange.student_id.in_(u)))
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(u)))
        db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(u)))
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
    try:
        # ---------------- önizleme (gün gün → havuz)
        with SessionLocal() as db:
            s = db.get(User, d["s"])
            pv = pms.preview(db, s, "havuz", today)
            del_ids = {t.task_id for t in pv.delete_tasks}
            keep_ids = {t.task_id for t in pv.keep_partial}
            check("P1 önizleme: bugün + taslak silinecek, kısmi kalacak, geçmiş/tamam dokunulmaz",
                  del_ids == {d["t_today"], d["t_draft"]} and keep_ids == {d["t_part"]}, f"{del_ids} {keep_ids}")
            check("P2 önizleme: iade 4+3+2=9 test, ölü rezerv 3", pv.release_tests == 9 and pv.dead_reserve_tests == 3,
                  f"{pv.release_tests} {pv.dead_reserve_tests}")
            check("P3 önizleme hiçbir şey yazmaz", db.query(Task).filter(Task.id == d["t_today"]).count() == 1
                  and s.program_mode in (None, "gun_gun"))
            h = db.get(User, d["h"])
            pv2 = pms.preview(db, h, "gun_gun", today)
            check("P4 havuz → gün gün: açık dönem varken engelli (open_period)",
                  not pv2.allowed and pv2.blocker == "open_period", pv2.blocker)

        # ---------------- HTTP
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_coach@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r = c.get(f"/api/v2/teacher/students/{d['s']}/program-mode/preview?to=havuz")
        check("H1 önizleme ucu 200 + 2 silinecek", r.status_code == 200 and len(r.json()["delete_tasks"]) == 2, r.text[:200])
        r = c.post(f"/api/v2/teacher/students/{d['s']}/program-mode/switch",
                   json={"to_mode": "havuz", "effective_on": (today - timedelta(days=1)).isoformat()})
        check("H2 geçmiş geçiş günü 422", r.status_code == 422, str(r.status_code))
        r = c.post(f"/api/v2/teacher/students/{d['s']}/program-mode/switch",
                   json={"to_mode": "havuz", "expected_next_on": (today + timedelta(days=7)).isoformat()})
        j = r.json()["data"] if r.status_code == 200 else {}
        check("H3 havuza geç → 200, mod havuz, ilk dönem açık",
              r.status_code == 200 and j["student"]["program_mode"] == "havuz" and j["period"] is not None, r.text[:300])
        with SessionLocal() as db:
            left = {t.id for t in db.query(Task).filter(Task.student_id == d["s"]).all()}
            check("A1 bugün + taslak silindi; geçmiş, tamamlanmış, kısmi kaldı",
                  left == {d["t_past"], d["t_done"], d["t_part"]}, str(left))
            prog = _progress(db, d["sb"], d["sec"])
            check("A2 rezerv 12 → 0 (iade 9 + ölü 3), çözülen 4 aynen", prog.reserved_count == 0 and prog.completed_count == 4,
                  f"{prog.reserved_count} {prog.completed_count}")
            part = db.get(Task, d["t_part"])
            check("A3 kısmi görev: çözülen 2 duruyor, kalem serbest bırakıldı işaretli",
                  part.book_items[0].completed_count == 2 and part.book_items[0].reservation_released_at is not None)
            ch = db.query(ProgramModeChange).filter_by(student_id=d["s"]).one()
            import json
            summ = json.loads(ch.summary_json)
            check("A4 geçiş kaydı: gun_gun→havuz, elle, dönem bağlı, özet sayıları",
                  ch.from_mode == "gun_gun" and ch.to_mode == "havuz" and ch.trigger == "manual" and ch.period_id
                  and summ["deleted_tasks"] == 2 and summ["kept_partial_tasks"] == 1 and summ["dead_reserve_released"] == 3,
                  str(summ))
        r = c.post(f"/api/v2/teacher/students/{d['s']}/program-mode/switch", json={"to_mode": "havuz"})
        check("H4 aynı moda tekrar geçiş 409 same_mode", r.status_code == 409 and r.json()["detail"]["code"] == "same_mode")

        # ---------------- havuz → gün gün (açık dönemde engel, seansı bitir + geç)
        r = c.post(f"/api/v2/teacher/students/{d['h']}/program-mode/switch", json={"to_mode": "gun_gun"})
        check("H5 açık dönemde gün güne elle geçiş 409 open_period",
              r.status_code == 409 and r.json()["detail"]["code"] == "open_period", r.text[:200])
        r = c.post(f"/api/v2/teacher/students/{d['h']}/pool/session/finish",
                   json={"closed_on": today.isoformat(), "switch_to_gun_gun": True,
                         "carry": [{"item_id": d["item"]}]})
        check("H6 geçerken devir 422 carry_with_switch", r.status_code == 422, str(r.status_code))
        r = c.post(f"/api/v2/teacher/students/{d['h']}/pool/session/finish",
                   json={"closed_on": today.isoformat(), "switch_to_gun_gun": True,
                         "agenda": "Gün güne geçiyoruz", "record_session": True})
        j = r.json()["data"] if r.status_code == 200 else {}
        check("H7 seansı bitir + gün güne geç → 200, mod gun_gun, açık dönem yok",
              r.status_code == 200 and j["student"]["program_mode"] == "gun_gun" and j["period"] is None, r.text[:300])
        with SessionLocal() as db:
            check("B1 yeni dönem açılmadı", db.query(StudyPeriod).filter_by(student_id=d["h"], status=PERIOD_OPEN).count() == 0)
            check("B2 dokunulmamış bugünkü kap görevi silindi", db.get(Task, d["cup_today"]) is None)
            ch = db.query(ProgramModeChange).filter_by(student_id=d["h"]).one()
            check("B3 kayıt: havuz→gun_gun, seansı bitirirken, dönem bağlı",
                  ch.to_mode == "gun_gun" and ch.trigger == "session_finish" and ch.period_id == d["p"])
            check("B4 seans kaydı yazıldı + dönem kapanış seansına bağlı",
                  db.get(StudyPeriod, d["p"]).closed_session_id is not None
                  and db.query(CoachingSession).filter_by(student_id=d["h"]).count() == 1)
            h = db.get(User, d["h"])
            rep = evaluate_flags(db, h, today)
            codes = {w.code for w in rep.primary} | {w.code for w in rep.secondary}
            check("B5 uyarı: 'Programı yok' kırmızı değil, sarı 'ilk programı hazırla'",
                  "program_after_switch" in codes and "program_none" not in codes, str(codes))
        r = c.get(f"/api/v2/teacher/students/{d['h']}/program-mode/history")
        j = r.json()
        check("H8 geçmiş ucu: 1 kayıt, etiketler", r.status_code == 200 and len(j["items"]) == 1
              and j["items"][0]["trigger_label"] == "Seansı bitirirken" and j["current_mode"] == "gun_gun", r.text[:200])
        # 3 gün sonra sarı süre biter
        with SessionLocal() as db:
            check("B6 3 gün sonra geçiş süresi biter", pms.recent_switch_to_gun_gun(db, d["h"], today + timedelta(days=3)) is None
                  and pms.recent_switch_to_gun_gun(db, d["h"], today + timedelta(days=2)) is not None)
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
