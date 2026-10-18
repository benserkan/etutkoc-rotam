"""/teacher/students/{id}/topic-insights — hafta ızgarası konu özeti smoke (2026-10-18).

Kurulum: TYT Matematik'te iki konu.
  A (kitaplı): iki kitap — K1 bölüm 10 test (6 çözüldü), K2 bölüm 5 test (0) ;
    görev kalemi D 20 / Y 5 / B 3.
  B (kaynaksız): konuya bağlı kitapsız görev, 4/4 çözüldü, D 30 / Y 6 / B 4.
Kontroller: görev kaleminde curriculum_topic_id (kitaplı + kaynaksız) · yüzde ve
kaynaklar Müfredat ucuyla birebir · kaynak çözülen/toplam · kaynaksız çözülen ·
D/Y/B + doğruluk · başka koçun öğrencisi 404 · geçersiz id 422 · invalidate listesi.
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.main import app
from app.models import Book, BookSection, StudentBook, Subject, Topic, Track, User, UserRole
from app.models.book import BookType
from app.models.progress import SectionProgress
from app.models.suspicious_ip import SuspiciousIp
from app.models.task import Task, TaskBookItem, TaskStatus, TaskType
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"tin{secrets.token_hex(3)}"
PWD = "TopicInsight!2345"
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({str(detail)[:300]})")


def mk(db, tag, role, **kw):
    u = User(email=f"{PFX}-{tag}@test.invalid", password_hash=hash_password(PWD), full_name=f"{PFX} {tag}",
             role=role, is_active=True, must_change_password=False, created_at=now - timedelta(days=30), **kw)
    db.add(u)
    db.flush()
    return u


def main() -> int:
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        subj = db.scalar(select(Subject).where(Subject.name == "TYT Matematik", Subject.curriculum_model.is_(None)))
        topics = db.scalars(select(Topic).where(Topic.subject_id == subj.id).order_by(Topic.order).limit(2)).all()
        ta, tb = topics
        coach = mk(db, "koc", UserRole.TEACHER, plan="solo_pro", subscription_status="active")
        other = mk(db, "diger", UserRole.TEACHER)
        stu = mk(db, "ogr", UserRole.STUDENT, teacher_id=coach.id, grade_level=12, track=Track.SAYISAL)
        k1 = Book(teacher_id=coach.id, name=f"{PFX} Kitap1", subject_id=subj.id, type=BookType.SORU_BANKASI)
        k2 = Book(teacher_id=coach.id, name=f"{PFX} Kitap2", subject_id=subj.id, type=BookType.SORU_BANKASI)
        db.add_all([k1, k2]); db.flush()
        s1 = BookSection(book_id=k1.id, label=ta.name, test_count=10, order=0, topic_id=ta.id)
        s2 = BookSection(book_id=k2.id, label=ta.name, test_count=5, order=0, topic_id=ta.id)
        db.add_all([s1, s2]); db.flush()
        sb1 = StudentBook(student_id=stu.id, book_id=k1.id)
        sb2 = StudentBook(student_id=stu.id, book_id=k2.id)
        db.add_all([sb1, sb2]); db.flush()
        db.add_all([SectionProgress(student_book_id=sb1.id, book_section_id=s1.id, completed_count=6, reserved_count=2),
                    SectionProgress(student_book_id=sb2.id, book_section_id=s2.id, completed_count=0, reserved_count=0)])
        t1 = Task(student_id=stu.id, date=date.today(), type=TaskType.TEST, title="A", status=TaskStatus.COMPLETED,
                  is_draft=False, published_at=now)
        t1.book_items = [TaskBookItem(book_id=k1.id, book_section_id=s1.id, planned_count=2, completed_count=2,
                                      correct_count=20, wrong_count=5, blank_count=3)]
        t2 = Task(student_id=stu.id, date=date.today(), type=TaskType.TEST, title="B", status=TaskStatus.COMPLETED,
                  is_draft=False, published_at=now)
        t2.book_items = [TaskBookItem(topic_id=tb.id, label="B", planned_count=4, completed_count=4,
                                      correct_count=30, wrong_count=6, blank_count=4)]
        db.add_all([t1, t2]); db.commit()
        ids = dict(coach=coach.id, other=other.id, stu=stu.id, k1=k1.id, k2=k2.id, ta=ta.id, tb=tb.id)

    try:
        c = TestClient(app)
        assert c.post("/api/v2/auth/login", json={"email": f"{PFX}-koc@test.invalid", "password": PWD}).status_code == 200
        wk = c.get(f"/api/v2/teacher/students/{ids['stu']}/week?start={date.today().isoformat()}").json()
        items = [it for d in wk["days"] for t in d["tasks"] for it in t["items"]]
        cti = {it["curriculum_topic_id"] for it in items}
        chk("görev kaleminde curriculum_topic_id (kitaplı + kaynaksız)", {ids["ta"], ids["tb"]} <= cti, cti)

        r = c.get(f"/api/v2/teacher/students/{ids['stu']}/topic-insights?topic_ids={ids['ta']},{ids['tb']}")
        chk("200", r.status_code == 200, r.text[:200])
        by = {i["topic_id"]: i for i in r.json()["items"]}
        a, b = by.get(ids["ta"]), by.get(ids["tb"])
        cur = c.get(f"/api/v2/teacher/students/{ids['stu']}/curriculum").json()
        ct = {t["topic_id"]: t for s in cur["subjects"] for t in s["topics"]}
        chk("A yüzde ve durum Müfredat ucuyla birebir",
            a and a["pct"] == ct[ids["ta"]]["pct"] and a["status"] == ct[ids["ta"]]["status"], (a, ct.get(ids["ta"])))
        srcs = {s["book"]: (s["solved"], s["total"]) for s in (a or {}).get("sources", [])}
        chk("A kaynakları: Kitap1 6/10 · Kitap2 0/5",
            srcs.get(f"{PFX} Kitap1") == (6, 10) and srcs.get(f"{PFX} Kitap2") == (0, 5), srcs)
        chk("A konu toplamı 6/15", a and (a["completed"], a["test_total"]) == (6, 15), a)
        chk("A D/Y/B 20/5/3 + %80 doğru",
            a and a["perf"] and (a["perf"]["correct"], a["perf"]["wrong"], a["perf"]["blank"]) == (20, 5, 3)
            and a["perf"]["accuracy_pct"] == 80, a and a["perf"])
        chk("B kaynaksız: 4 test çözüldü, kitap kaynağı yok",
            b and b["sourceless_completed"] == 4 and b["sources"] == [], b)
        chk("B D/Y/B 30/6/4", b and b["perf"] and (b["perf"]["correct"], b["perf"]["wrong"], b["perf"]["blank"]) == (30, 6, 4),
            b and b["perf"])
        chk("geçersiz id 422", c.get(f"/api/v2/teacher/students/{ids['stu']}/topic-insights?topic_ids=x").status_code == 422)
        co = TestClient(app)
        co.post("/api/v2/auth/login", json={"email": f"{PFX}-diger@test.invalid", "password": PWD})
        chk("başka koçun öğrencisi 404",
            co.get(f"/api/v2/teacher/students/{ids['stu']}/topic-insights?topic_ids={ids['ta']}").status_code == 404)
        from app.routes.api_v2.teacher import _capacity_invalidate
        chk("görev değişince konu özeti bayatlar (invalidate)",
            any(k.endswith(":topic-insights") for k in _capacity_invalidate(ids["coach"], ids["stu"])))
    finally:
        with SessionLocal() as db:
            for t in db.query(Task).filter(Task.student_id == ids["stu"]).all():
                db.delete(t)
            db.flush()
            sbs = [x.id for x in db.query(StudentBook).filter(StudentBook.student_id == ids["stu"]).all()]
            db.execute(delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
            db.execute(delete(StudentBook).where(StudentBook.id.in_(sbs)))
            db.execute(delete(BookSection).where(BookSection.book_id.in_([ids["k1"], ids["k2"]])))
            db.execute(delete(Book).where(Book.id.in_([ids["k1"], ids["k2"]])))
            db.execute(delete(User).where(User.id.in_([ids["stu"], ids["coach"], ids["other"]])))
            db.commit()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
