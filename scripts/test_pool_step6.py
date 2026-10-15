"""Havuz modu Adım 6 smoke — devir ekranı (K22/K58) · ara/tatil (K61) · geç kayıt kilidi (K59/K15) ·
dönem geçmişi (K60), 2026-10-13.

Çalıştır: PYTHONPATH=. python scripts/test_pool_step6.py
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
    Book, BookSection, BookType, NotificationLog, ParentStudentLink, PoolItem, SectionProgress, StudentBook,
    StudyPeriod, Subject, Task, TaskBookItem, TaskStatus, Topic, Track, User, UserRole, WarningState,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.parent import ParentRelation  # noqa: E402
from app.models.pool import PERIOD_BREAK, PERIOD_CLOSED, SOURCE_CARRY  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import analytics, pool_mode as pm  # noqa: E402
from app.services.pool_mode import PoolError  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.student_flags import evaluate_flags  # noqa: E402

PFX = f"p6_{secrets.token_hex(3)}"
PWD = "Step6!234567xy"
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
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"P6 {tag}",
             role=role, is_active=True, created_at=now - timedelta(days=60), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _cup(db, item, day, count, done=None):
    t = pm.put_in_cup(db, item=item, day=day, count=count)
    if done:
        for bi in t.book_items:
            bi.completed_count = done
        t.status = TaskStatus.COMPLETED if done >= count else TaskStatus.PARTIAL
        t.completed_at = datetime.combine(day, time(20, 0), tzinfo=timezone.utc)
        db.flush()
        pm.sync_item_progress(db, item)
    return t


def seed() -> dict:
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        fiz = Subject(name=f"{PFX} TYT Fizik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add_all([tyt, fiz])
        db.flush()
        ids["subjects"] += [tyt.id, fiz.id]
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t3 = Topic(subject_id=fiz.id, name="Optik", order=1, teacher_id=coach.id)
        db.add_all([t1, t3])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=100, order=1, topic_id=t1.id)
        db.add(sec)
        db.flush()

        def mk(tag):
            s = _user(db, tag, UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                      program_mode="havuz", class_group="12-A", last_seen_at=now - timedelta(hours=20))
            sb = StudentBook(student_id=s.id, book_id=b.id)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
            return s

        # s_carry: 3 kapanmış dönem (geçmiş) + son dönem kalanlı, kapalı (devir adayı)
        s_carry = mk("carry")
        for k in (3, 2):
            p = pm.open_period(db, student=s_carry, coach=coach, opened_on=today - timedelta(days=7 * k + 3))
            it = pm.add_item(db, period=p, student=s_carry, subject=tyt, quantity=4, unit="test", book=b, section=sec)
            _cup(db, it, p.opened_on + timedelta(days=2), 4, done=4)
            pm.close_period(db, p, closed_on=p.opened_on + timedelta(days=7), status=PERIOD_CLOSED)
        p_last = pm.open_period(db, student=s_carry, coach=coach, opened_on=today - timedelta(days=8),
                                expected_next_on=today - timedelta(days=1))
        i_a = pm.add_item(db, period=p_last, student=s_carry, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        i_b = pm.add_item(db, period=p_last, student=s_carry, subject=fiz, quantity=6, unit="test", topic=t3)
        i_c = pm.add_item(db, period=p_last, student=s_carry, subject=fiz, quantity=None, unit="etkinlik", label="Optik videosu")
        i_a.carry_count = 2  # K58: bu devirle 3. olacak
        _cup(db, i_a, today - timedelta(days=5), 4, done=4)
        _cup(db, i_c, today - timedelta(days=4), 1, done=1)
        pm.close_period(db, p_last, closed_on=today - timedelta(days=1), status=PERIOD_CLOSED)
        # s_break: ara ile kapanmış
        s_break = mk("break")
        p_b = pm.open_period(db, student=s_break, coach=coach, opened_on=today - timedelta(days=9))
        i_bk = pm.add_item(db, period=p_b, student=s_break, subject=tyt, quantity=8, unit="test", book=b, section=sec)
        pm.close_period(db, p_b, closed_on=today - timedelta(days=2), status=PERIOD_BREAK)
        parent = _user(db, "veli", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=parent.id, student_id=s_break.id, relation=ParentRelation.ANNE, is_primary=True))
        # s_late: geç kayıt kilidi — 1 gün önce kapanmış (serbest) ve 3 gün önce kapanmış (kilitli) kap görevleri
        s_late = mk("late")
        p_old = pm.open_period(db, student=s_late, coach=coach, opened_on=today - timedelta(days=12))
        i_o = pm.add_item(db, period=p_old, student=s_late, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        t_locked_done = _cup(db, i_o, today - timedelta(days=7), 2, done=2)
        t_locked = _cup(db, i_o, today - timedelta(days=6), 3)           # ilerlemesiz, kapalı dönem 3 gün önce
        pm.close_period(db, p_old, closed_on=today - timedelta(days=3), status=PERIOD_CLOSED)
        p_rec = pm.open_period(db, student=s_late, coach=coach, opened_on=today - timedelta(days=3))
        i_r = pm.add_item(db, period=p_rec, student=s_late, subject=fiz, quantity=6, unit="test", topic=t3)
        t_free = _cup(db, i_r, today - timedelta(days=2), 2)
        pm.close_period(db, p_rec, closed_on=today - timedelta(days=1), status=PERIOD_CLOSED)
        db.execute(sa_delete(NotificationLog).where(NotificationLog.student_id.in_([s_carry.id, s_break.id, s_late.id])))
        db.commit()
        return {"coach": coach.id, "carry": s_carry.id, "break": s_break.id, "late": s_late.id, "parent": parent.id,
                "p_last": p_last.id, "i_a": i_a.id, "i_b": i_b.id, "i_c": i_c.id, "p_b": p_b.id, "i_bk": i_bk.id,
                "t_locked": t_locked.id, "t_locked_done": t_locked_done.id, "t_free": t_free.id, "i_o": i_o.id,
                "tyt": tyt.id, "fiz": fiz.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(u)))
        db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(u)))
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
    try:
        with SessionLocal() as db:
            coach = db.get(User, d["coach"])
            s_carry = db.get(User, d["carry"])
            s_break = db.get(User, d["break"])
            s_late = db.get(User, d["late"])

            # ---- devir (K22/K58)
            src, cands = pm.carry_candidates(db, s_carry.id)
            cid = {c.id for c in cands}
            check("A1 devir adayları: son kapanmış dönemin kalanlı 2 kalemi (bitmiş etkinlik hariç)",
                  src is not None and src.id == d["p_last"] and cid == {d["i_a"], d["i_b"]}, str(cid))
            try:
                pm.open_period(db, student=s_carry, coach=coach, opened_on=today, carry=[(d["i_c"], None)])
                check("A2 kalanı olmayan kalem devredilemez (carry_not_leftover)", False)
            except PoolError as e:
                check("A2 kalanı olmayan kalem devredilemez (carry_not_leftover), dönem AÇILMAZ",
                      e.code == "carry_not_leftover" and pm.get_open_period(db, s_carry.id) is None, e.code)
            db.rollback()
            s_carry = db.get(User, d["carry"]); coach = db.get(User, d["coach"])
            newp = pm.open_period(db, student=s_carry, coach=coach, opened_on=today, expected_next_on=today + timedelta(days=7),
                                  carry=[(d["i_a"], 3), (d["i_b"], None)])
            db.commit()
            items = {it.parent_item_id: it for it in newp.items}
            check("A3 devir: 2 kalem yeni dönemde, kaynak devir, miktar (3 / kalan 6), sayaç +1 (3 / 1)",
                  len(items) == 2 and items[d["i_a"]].quantity == 3 and items[d["i_b"]].quantity == 6
                  and items[d["i_a"]].source == SOURCE_CARRY and items[d["i_a"]].carry_count == 3 and items[d["i_b"]].carry_count == 1,
                  str([(it.quantity, it.source, it.carry_count) for it in newp.items]))
            rep = evaluate_flags(db, s_carry, today)
            check("A4 K58: 3. devir → kaçınılan sinyali (pool_avoided, gerekçe '3. kez devrediliyor')",
                  any(w.code == "pool_avoided" and "3. kez" in " ".join(v for _, v in w.evidence) for w in rep.primary + rep.secondary),
                  str([w.code for w in rep.primary + rep.secondary]))

            # ---- ara (K61)
            br = pm.break_state(db, s_break.id)
            check("B1 ara ile kapanan öğrenci: break_state dolu", br is not None and br.id == d["p_b"])
            rep = evaluate_flags(db, s_break, today)
            check("B2 arada bayrak yok, başlık 'Ara'", not rep.primary and rep.headline.startswith("Ara"), rep.headline)
            src, cands = pm.carry_candidates(db, s_break.id)
            check("B3 aradan dönüşte devir adayı ara döneminin kalemi", {c.id for c in cands} == {d["i_bk"]})

            # ---- geç kayıt kilidi (K59)
            t_locked = db.get(Task, d["t_locked"])
            t_free = db.get(Task, d["t_free"])
            check("C1 kapanıştan 3 gün sonra kilitli (kilit tarihi kapanış+3), 1 gün sonra serbest",
                  pm.late_entry_lock(db, t_locked, today) == today - timedelta(days=3) + timedelta(days=3)
                  and pm.late_entry_lock(db, t_free, today) is None)
            check("C2 kilit tam 2 gün sonra: kapanış+2 serbest, kapanış+3 kilitli",
                  pm.late_entry_lock(db, t_locked, today - timedelta(days=1)) is None
                  and pm.late_entry_lock(db, t_locked, today) is not None)
            i_o = db.get(PoolItem, d["i_o"])
            pm.session_mark(db, item=i_o, actor=coach, count=3)
            db.commit()
            check("C3 rehber izli düzeltme kapalı dönemde çalışır (session_mark 3)", db.get(PoolItem, d["i_o"]).session_marked == 3)

            # ---- geçmiş (K60)
            total, rows = pm.period_history(db, s_carry.id, offset=0, limit=2)
            check("D1 geçmiş sayfalı: toplam 4 dönem, ilk sayfa 2 (yeni önce)", total == 4 and len(rows) == 2 and rows[0]["id"] == newp.id, f"{total} {len(rows)}")
            last = rows[1]
            check("D2 son kapanmış dönem satırı: devir çıkışı 2, ders kırılımı 2 ders, yüzde 29 (5/17)",
                  last["carried_out"] == 2 and len(last["subjects"]) == 2 and last["pct"] == 29, str({k: last[k] for k in ("carried_out", "pct", "total_units", "done_units")}))
            check("D3 yeni dönem satırı: devir girişi 2", rows[0]["carried_in"] == 2, str(rows[0]["carried_in"]))
            total2, rows2 = pm.period_history(db, s_carry.id, offset=2, limit=10)
            check("D4 ikinci sayfa 2 satır", total2 == 4 and len(rows2) == 2)
            db.rollback()

        # ---- HTTP
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_coach@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r = c.get(f"/api/v2/teacher/students/{d['break']}/pool")
        j = r.json()
        check("H1 editör paketi (ara): on_break dolu + devir adayı 1 + periods_total 1",
              r.status_code == 200 and j["on_break"] and j["on_break"]["period_id"] == d["p_b"]
              and len(j["carry_candidates"]) == 1 and j["periods_total"] == 1, r.text[:200])
        cand = j["carry_candidates"][0]
        check("H2 aday satırı: başlık + kalan 8 + third_carry False", cand["remaining"] == 8 and cand["third_carry"] is False and "Üslü" in cand["title"], str(cand))
        r = c.post(f"/api/v2/teacher/students/{d['break']}/pool/periods",
                   json={"opened_on": today.isoformat(), "expected_next_on": (today + timedelta(days=7)).isoformat(),
                         "carry": [{"item_id": cand["item_id"], "quantity": 5}]})
        j = r.json()["data"] if r.status_code == 200 else {}
        check("H3 aradan dön: dönem aç + devir 5 test → on_break temiz, havuzda 1 devir kalemi",
              r.status_code == 200 and j.get("on_break") is None and j["period"] and len(j["period"]["items"]) == 1
              and j["period"]["items"][0]["quantity"] == 5 and j["period"]["items"][0]["source"] == "devir", r.text[:200])
        r = c.post(f"/api/v2/teacher/students/{d['break']}/pool/periods",
                   json={"opened_on": today.isoformat(), "carry": [{"item_id": 999999}]})
        check("H4 açık dönem varken tekrar açma 409", r.status_code == 409)
        r = c.get(f"/api/v2/teacher/students/{d['carry']}/pool/periods?limit=2")
        j = r.json()
        check("H5 geçmiş ucu: total 4, 2 satır, alanlar (subjects/carried/status_label)",
              r.status_code == 200 and j["total"] == 4 and len(j["rows"]) == 2 and j["rows"][1]["status_label"] == "Kapandı"
              and j["rows"][1]["carried_out"] == 2, r.text[:200])
        r = c.get(f"/api/v2/teacher/students/{d['carry']}/pool/periods?offset=2&limit=2")
        check("H6 geçmiş 2. sayfa", r.status_code == 200 and len(r.json()["rows"]) == 2)
        c.cookies.clear()
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_late@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r = c.post(f"/api/v2/student/tasks/{d['t_locked']}/complete", json={})
        check("H7 K59: kapanıştan 3 gün sonra öğrenci tamamlama 403 late_entry_locked",
              r.status_code == 403 and r.json()["detail"]["code"] == "late_entry_locked", r.text[:150])
        item_id = None
        with SessionLocal() as db:
            t = db.get(Task, d["t_locked"])
            item_id = t.book_items[0].id
        r = c.post(f"/api/v2/student/tasks/{d['t_locked']}/items/{item_id}/set-completed", json={"completed": 1})
        check("H8 kısmi kayıt da kilitli", r.status_code == 403)
        r = c.post(f"/api/v2/student/tasks/{d['t_locked_done']}/uncomplete")
        check("H9 geri alma da kilitli", r.status_code == 403)
        r = c.post(f"/api/v2/student/tasks/{d['t_free']}/complete", json={})
        check("H10 kapanıştan 1 gün sonra geç kayıt SERBEST (200, görev tamamlandı)",
              r.status_code == 200 and r.json()["data"]["status"] == "completed", r.text[:150])
        r = c.get("/api/v2/student/pool")
        j = r.json()
        check("H11 öğrenci paketi: previous (2 kapanmış dönem), on_break yok", r.status_code == 200 and len(j["previous"]) == 2 and j["on_break"] is None, r.text[:200])
        c.cookies.clear()
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_veli@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r = c.get(f"/api/v2/parent/students/{d['break']}/pool")
        check("H12 veli paketi: aradan dönüldü → on_break yok, dönem var", r.status_code == 200 and r.json()["on_break"] is None and r.json()["period_id"])
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    if failed:
        print("Başarısız:", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
