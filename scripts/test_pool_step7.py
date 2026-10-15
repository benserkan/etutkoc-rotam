"""Havuz modu Adım 7 smoke — geçmiş dönem penceresi (kalem kalem + gün gün), 2026-10-13.

Rehber / öğrenci / veli üç uç aynı üreticiyi kullanır; yüzey farkı (kaldırılan iz, kaçınma
sayaçları, onay bekleyen kalem) burada kilitlenir. Gün gün görünümde gün sonu kapanışının
ilerlemesiz kap görevini SİLMESİ (K34) ve kısmi görevi küçültmesi de doğrulanır.

Çalıştır: PYTHONPATH=. python scripts/test_pool_step7.py
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
    StudyPeriod, Subject, Task, TaskBookItem, TaskStatus, TaskType, Topic, Track, User, UserRole, WarningState,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.parent import ParentRelation  # noqa: E402
from app.models.pool import PERIOD_CLOSED, SOURCE_STUDENT  # noqa: E402
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import analytics, pool_mode as pm  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"p7_{secrets.token_hex(3)}"
PWD = "Step7!234567xy"
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
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"P7 {tag}",
             role=role, is_active=True, created_at=now - timedelta(days=60), **kw)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _cup(db, item, day, count, done=None, dyb=None):
    t = pm.put_in_cup(db, item=item, day=day, count=count)
    if done:
        for bi in t.book_items:
            bi.completed_count = done
            if dyb:
                bi.correct_count, bi.wrong_count, bi.blank_count = dyb
        t.status = TaskStatus.COMPLETED if done >= count else TaskStatus.PARTIAL
        t.completed_at = datetime.combine(day, time(20, 0), tzinfo=timezone.utc)
        db.flush()
        pm.sync_item_progress(db, item)
    return t


def seed() -> dict:
    with SessionLocal() as db:
        coach = _user(db, "coach", UserRole.TEACHER)
        other = _user(db, "other", UserRole.TEACHER)
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
        s = _user(db, "ogr", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL,
                  program_mode="havuz", class_group="12-A", last_seen_at=now - timedelta(hours=20))
        s2 = _user(db, "ogr2", UserRole.STUDENT, teacher_id=other.id, grade_level=12, track=Track.SAYISAL,
                   program_mode="havuz")
        sb = StudentBook(student_id=s.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        parent = _user(db, "veli", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=parent.id, student_id=s.id, relation=ParentRelation.ANNE, is_primary=True))
        parent2 = _user(db, "veli2", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=parent2.id, student_id=s2.id, relation=ParentRelation.ANNE, is_primary=True))

        # ---- P1: 8 gün önce açıldı, dün kapandı
        p1 = pm.open_period(db, student=s, coach=coach, opened_on=today - timedelta(days=8))
        i_a = pm.add_item(db, period=p1, student=s, subject=tyt, quantity=10, unit="test", book=b, section=sec)
        i_b = pm.add_item(db, period=p1, student=s, subject=fiz, quantity=6, unit="test", topic=t3)
        i_c = pm.add_item(db, period=p1, student=s, subject=fiz, quantity=None, unit="etkinlik", label="Optik videosu")
        i_stu = pm.add_item(db, period=p1, student=s, subject=tyt, quantity=3, unit="test", label="Kendi paragrafım",
                            source=SOURCE_STUDENT, created_by=s)
        i_rm = pm.add_item(db, period=p1, student=s, subject=tyt, quantity=5, unit="sayfa", label="Yanlışlıkla")
        pm.remove_item(db, i_rm, coach)
        # gün-7: 4 test, 3D 1Y 0B · gün-6: 3 aldı 2 çözdü (gün sonu küçülür) · gün-5: 2 aldı hiç dokunmadı (silinir)
        _cup(db, i_a, today - timedelta(days=7), 4, done=4, dyb=(3, 1, 0))
        t_partial = _cup(db, i_a, today - timedelta(days=6), 3, done=2)
        t_partial.status = TaskStatus.PARTIAL
        db.flush()
        pm.close_day(db, student=s, day=today - timedelta(days=6))
        _cup(db, i_a, today - timedelta(days=5), 2)
        pm.close_day(db, student=s, day=today - timedelta(days=5))
        # gün-4: etkinlik yapıldı
        _cup(db, i_c, today - timedelta(days=4), 1, done=1)
        # rehber seansta i_b'den 2 birim işaretledi
        pm.session_mark(db, item=i_b, actor=coach, count=2)
        pm.close_period(db, p1, closed_on=today - timedelta(days=1), status=PERIOD_CLOSED)
        # ---- P2: dün açıldı, i_a devredildi
        p2 = pm.open_period(db, student=s, coach=coach, opened_on=today - timedelta(days=1), carry=[(i_a.id, None)])
        db.execute(sa_delete(NotificationLog).where(NotificationLog.student_id.in_([s.id, s2.id])))
        db.commit()
        return {"coach": coach.id, "other": other.id, "s": s.id, "s2": s2.id, "parent": parent.id,
                "parent2": parent2.id, "p1": p1.id, "p2": p2.id, "i_a": i_a.id, "i_b": i_b.id, "i_c": i_c.id,
                "i_stu": i_stu.id, "i_rm": i_rm.id}


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
        from app.models.audit_log import AuditLog
        db.execute(sa_delete(AuditLog).where(AuditLog.target_id.in_(u), AuditLog.details_json.like("%pool_period_delete%")))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def main() -> int:
    get_login_limiter().reset()
    d = seed()
    try:
        d7, d6, d5, d4 = [(today - timedelta(days=k)).isoformat() for k in (7, 6, 5, 4)]

        # ---------------- rehber
        c = _login(f"{PFX}_coach@test.invalid")
        r = c.get(f"/api/v2/teacher/students/{d['s']}/pool/periods/{d['p1']}")
        j = r.json()
        check("T1 rehber dönem penceresi 200 · audience teacher · dönem kapandı",
              r.status_code == 200 and j["audience"] == "teacher" and j["period"]["id"] == d["p1"]
              and j["period"]["status"] == "kapandi", r.text[:200])
        items = {it["id"]: it for it in j["items"]}
        check("T2 canlı kalemler 4 (a,b,c,öğrenci) · kaldırılan 1 ayrı listede (iz)",
              set(items) == {d["i_a"], d["i_b"], d["i_c"], d["i_stu"]} and [x["id"] for x in j["removed_items"]] == [d["i_rm"]]
              and j["removed_items"][0]["removed"] and j["removed_items"][0]["removed_at"],
              f"{sorted(items)} rm={j['removed_items']}")
        a = items[d["i_a"]]
        check("T3 i_a: öğrenci 6 çözdü (4+2) · kaba 3 kez girdi · 1 kez geri döndü · devredildi",
              a["completed"] == 6 and a["cup_attempts"] == 3 and a["cup_returns"] == 1 and a["carried_out"] is True
              and a["remaining"] == 4, str(a))
        bb = items[d["i_b"]]
        check("T4 i_b: hiç kaba alınmadı · rehber seansta 2 işaretledi · done 2 · devredilmedi",
              bb["cup_attempts"] == 0 and bb["session_marked"] == 2 and bb["done"] == 2 and bb["completed"] == 0
              and bb["carried_out"] is False, str(bb))
        st = items[d["i_stu"]]
        check("T5 öğrenci kalemi: onay bekliyor · yüzdeye girmez · kaynak ogrenci",
              st["approval"] == "bekliyor" and st["counts"] is False and st["source"] == "ogrenci", str(st))
        days = {x["date"]: x for x in j["days"]}
        p = j["period"]
        check("T6 gün listesi açılış→kapanış kesintisiz (8 gün)",
              len(j["days"]) == 8 and j["days"][0]["date"] == p["opened_on"] and j["days"][-1]["date"] == p["closed_on"],
              f"{len(j['days'])} {j['days'][0]['date']}..{j['days'][-1]['date']}")
        g7 = days[d7]["tasks"]
        check("T7 gün-7: 4/4 test · 3D 1Y 0B · tamamlandı · günün birimi 4",
              len(g7) == 1 and g7[0]["planned"] == 4 and g7[0]["done"] == 4 and g7[0]["correct"] == 3
              and g7[0]["wrong"] == 1 and g7[0]["blank"] == 0 and g7[0]["status"] == "completed"
              and days[d7]["done_units"] == 4, str(g7))
        g6 = days[d6]["tasks"]
        check("T8 gün-6: kısmi görev gün sonunda 2/2'ye küçüldü (K34)",
              len(g6) == 1 and g6[0]["planned"] == 2 and g6[0]["done"] == 2 and g6[0]["status"] == "completed", str(g6))
        check("T9 gün-5: ilerlemesiz kap görevi silindi → gün boş (yalnız geri-döndü sayacında iz)",
              days[d5]["tasks"] == [] and days[d5]["done_units"] == 0, str(days[d5]))
        g4 = days[d4]["tasks"]
        check("T10 gün-4: etkinlik görevi kalemsiz · yapıldı · günün birimi 1",
              len(g4) == 1 and g4[0]["itemless"] is True and g4[0]["planned"] is None and g4[0]["done"] == 1
              and days[d4]["done_units"] == 1, str(g4))
        check("T11 weekday 0-6 ve ders kırılımı başlıkta (period.subjects)",
              all(0 <= x["weekday"] <= 6 for x in j["days"]) and len(p["subjects"]) >= 2, str(p["subjects"]))
        r2 = c.get(f"/api/v2/teacher/students/{d['s']}/pool/periods/{d['p2']}")
        j2 = r2.json()
        check("T12 açık dönem de açılır: devirle gelen kalem · günler bugüne kadar",
              r2.status_code == 200 and j2["period"]["status"] == "acik" and len(j2["items"]) == 1
              and j2["items"][0]["source"] == "devir" and j2["days"][-1]["date"] == today.isoformat(), r2.text[:200])
        r3 = c.get(f"/api/v2/teacher/students/{d['s2']}/pool/periods/{d['p1']}")
        r4 = c.get(f"/api/v2/teacher/students/{d['s']}/pool/periods/999999")
        check("T13 yabancı öğrenci 404 · olmayan dönem 404", r3.status_code == 404 and r4.status_code == 404,
              f"{r3.status_code} {r4.status_code}")
        rh = c.get(f"/api/v2/teacher/students/{d['s']}/pool/periods?offset=0&limit=10")
        check("T14 geçmiş listesi (K60) regresyon: 2 satır, ilk açık", rh.status_code == 200 and rh.json()["total"] == 2
              and rh.json()["rows"][0]["status"] == "acik", rh.text[:200])

        # ---------------- öğrenci
        cs = _login(f"{PFX}_ogr@test.invalid")
        r = cs.get(f"/api/v2/student/pool/periods/{d['p1']}")
        j = r.json()
        sitems = {it["id"]: it for it in j["items"]}
        check("S1 öğrenci penceresi 200 · kaldırılan yok · kendi bekleyen kalemi görünür",
              r.status_code == 200 and j["audience"] == "student" and j["removed_items"] == []
              and set(sitems) == {d["i_a"], d["i_b"], d["i_c"], d["i_stu"]}, r.text[:200])
        check("S2 öğrenciye kaçınma sayaçları gösterilmez (K41)",
              all(it["cup_attempts"] == 0 and it["cup_returns"] == 0 for it in j["items"]), str(sitems[d["i_a"]]))
        check("S3 öğrenci gün gün: gün-7 D/Y/B dolu", any(t["correct"] == 3 for x in j["days"] for t in x["tasks"]))
        r = cs.get(f"/api/v2/student/pool/periods/{d['p2']}")
        check("S4 öğrenci açık dönemini de görür", r.status_code == 200 and r.json()["period"]["status"] == "acik")
        cs2 = _login(f"{PFX}_ogr2@test.invalid")
        r = cs2.get(f"/api/v2/student/pool/periods/{d['p1']}")
        check("S5 başka öğrencinin dönemi 404", r.status_code == 404, str(r.status_code))

        # ---------------- veli
        cp = _login(f"{PFX}_veli@test.invalid")
        r = cp.get(f"/api/v2/parent/students/{d['s']}/pool/periods/{d['p1']}")
        j = r.json()
        pitems = {it["id"] for it in j["items"]}
        check("V1 veli penceresi 200 · onay bekleyen kalem YOK · kaldırılan YOK · sayaç YOK (K52)",
              r.status_code == 200 and j["audience"] == "parent" and pitems == {d["i_a"], d["i_b"], d["i_c"]}
              and j["removed_items"] == [] and all(it["cup_returns"] == 0 for it in j["items"]), r.text[:200])
        check("V2 veli gün gün: 8 gün · gün-7 görevi görünür", len(j["days"]) == 8
              and any(t["done"] == 4 for x in j["days"] for t in x["tasks"]))
        cp2 = _login(f"{PFX}_veli2@test.invalid")
        r = cp2.get(f"/api/v2/parent/students/{d['s']}/pool/periods/{d['p1']}")
        check("V3 bağsız veli 404 (sızıntı yok)", r.status_code == 404, str(r.status_code))

        # ---------------- dönem silme
        with SessionLocal() as db:   # kapanmış dönemde hiç dokunulmamış kap görevi (silinmeli)
            t = Task(student_id=d["s"], date=today - timedelta(days=3), type=TaskType.OTHER, title="dokunulmamış kap",
                     status=TaskStatus.PENDING, order=9, is_draft=False, pool_item_id=d["i_b"])
            db.add(t)
            db.commit()
            untouched_id = t.id
        r = c.get(f"/api/v2/teacher/students/{d['s']}/pool/periods/{d['p1']}/delete-impact")
        im = r.json()
        check("D1 etki: 4 kalem · 1 kaldırılan · 3 görev korunur · 1 görev silinir · devredilen 1 · silinebilir",
              r.status_code == 200 and im["deletable"] and im["items"] == 4 and im["removed_items"] == 1
              and im["tasks_kept"] == 3 and im["tasks_deleted"] == 1 and im["carried_out"] == 1, str(im))
        r = c.get(f"/api/v2/teacher/students/{d['s']}/pool/periods/{d['p2']}/delete-impact")
        r2 = c.post(f"/api/v2/teacher/students/{d['s']}/pool/periods/{d['p2']}/delete")
        check("D2 açık dönem: deletable false + silme 409 period_open",
              r.json()["deletable"] is False and r2.status_code == 409 and r2.json()["detail"]["code"] == "period_open",
              f"{r.json()} {r2.status_code}")
        co = _login(f"{PFX}_other@test.invalid")
        r = co.post(f"/api/v2/teacher/students/{d['s']}/pool/periods/{d['p1']}/delete")
        check("D3 başka rehber silemez (404)", r.status_code == 404, str(r.status_code))
        r = c.post(f"/api/v2/teacher/students/{d['s']}/pool/periods/{d['p1']}/delete")
        j = r.json()
        check("D4 silme 200 · paket döner · geçmiş artık 1 dönem", r.status_code == 200
              and j["data"]["periods_total"] == 1, r.text[:200])
        with SessionLocal() as db:
            gone = db.get(StudyPeriod, d["p1"]) is None
            items_left = db.query(PoolItem).filter(PoolItem.period_id == d["p1"]).count()
            kept = db.query(Task).filter(Task.student_id == d["s"], Task.date < today - timedelta(days=1)).all()
            child = db.query(PoolItem).filter(PoolItem.period_id == d["p2"]).first()
            from app.models.audit_log import AuditLog
            aud = (db.query(AuditLog).filter(AuditLog.target_id == d["s"], AuditLog.details_json.like("%pool_period_delete%"),
                           AuditLog.details_json.like(f'%"period_id": {d["p1"]},%'))
                   .count())
            check("D5 dönem + kalemleri silindi", gone and items_left == 0, f"{gone} {items_left}")
            check("D6 çalışılmış 3 kap görevi KORUNDU (havuz bağı koptu) · dokunulmamış görev silindi",
                  len(kept) == 3 and all(t.pool_item_id is None for t in kept) and db.get(Task, untouched_id) is None,
                  f"{[(t.title, t.pool_item_id) for t in kept]}")
            check("D7 sonraki dönemdeki devir kalemi yerinde, köken bağı koptu",
                  child is not None and child.parent_item_id is None, str(child.parent_item_id if child else None))
            check("D8 audit izi (op pool_period_delete)", aud == 1, str(aud))
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
