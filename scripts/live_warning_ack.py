"""CANLI uyarı tazelik + gördüm/ertele testi — çalışan :3000 → :8081'e HTTP.

Kullanım: python scripts/live_warning_ack.py [BASE_URL]  (vars. http://127.0.0.1:3000)

Geçici koç + (10 gün önce açılmış, dün planlı görevi tamamlanmamış) öğrenci ile
GERÇEK uyarı üretir; tarayıcı yolundan feed→ack→ertelenenler→unack→aktif + pano
render doğrular. Sonunda temizler.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Book, BookSection, Subject, User, UserRole, WarningState
from app.models.book import BookType
from app.models.curriculum import CurriculumModel
from app.models.progress import SectionProgress, StudentBook
from app.models.suspicious_ip import SuspiciousIp
from app.models.task import Task, TaskBookItem, TaskStatus, TaskType
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.services.task_service import reserve_item

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
PFX = f"lwarn_{secrets.token_hex(3)}"
PWD = hash_password("LiveWarn!23")
PWDH = "LiveWarn!23"
now = datetime.now(timezone.utc)
ctx: dict = {}
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


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_c@test.invalid", password_hash=PWD, full_name=f"{PFX} Koç",
                     role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_pro",
                     password_changed_at=now, must_change_password=False)
        db.add(coach); db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=PWD, full_name=f"{PFX} Ogrenci",
                   role=UserRole.STUDENT, teacher_id=coach.id, institution_id=None, grade_level=8,
                   is_active=True, created_at=now - timedelta(days=10),
                   password_changed_at=now, must_change_password=False)
        db.add(stu); db.flush()
        subj = Subject(name=f"{PFX} Mat", order=0, is_builtin=False, teacher_id=coach.id,
                       available_for_graduate=False, curriculum_model=CurriculumModel.LGS)
        db.add(subj); db.flush()
        book = Book(teacher_id=coach.id, subject_id=subj.id, name=f"{PFX} SB", publisher="T",
                    type=BookType.SORU_BANKASI, target_graduate=False)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Ünite 1", test_count=100, order=0)
        db.add(sec); db.flush()
        sb = StudentBook(student_id=stu.id, book_id=book.id)
        db.add(sb); db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
        db.flush()
        task = Task(student_id=stu.id, date=date.today() - timedelta(days=1), type=TaskType.TEST,
                    title="Dün görevi", status=TaskStatus.PENDING, order=0, is_draft=False,
                    published_at=now - timedelta(days=1))
        db.add(task); db.flush()
        reserve_item(db, student_id=stu.id, book_id=book.id, section_id=sec.id, count=5)
        db.add(TaskBookItem(task_id=task.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=5, completed_count=0))
        db.commit()
        ctx.update(coach_id=coach.id, student_id=stu.id, subject_id=subj.id)


def login() -> httpx.Client:
    get_login_limiter().reset()
    c = httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=False)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_c@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login @ {BASE}: {r.status_code} {r.text[:200]}")
    return c


def main() -> int:
    print(f"\n=== CANLI UYARI TAZELİK + GÖRDÜM/ERTELE — BASE={BASE} — {PFX} ===\n")
    setup()
    sid = ctx["student_id"]
    try:
        c = login()
        feed = c.get("/api/v2/teacher/dashboard/warnings-feed").json()
        check("1. canlı uyarı üretti + code + age_days (tazelik)",
              feed["total"] >= 1 and "code" in feed["rows"][0] and "age_days" in feed["rows"][0],
              f"total={feed.get('total')}")
        if not feed["rows"]:
            raise RuntimeError("uyarı yok")
        code = feed["rows"][0]["code"]
        before = feed["total"]
        print(f"     ↪ uyarı: '{feed['rows'][0]['title']}' · {feed['rows'][0]['age_days']} gündür")

        r = c.post("/api/v2/teacher/dashboard/warnings/ack",
                   json={"student_id": sid, "code": code, "snooze_days": 3})
        check("2. 'Gördüm' (ack) → 200", r.status_code == 200, f"{r.status_code}")
        feed = c.get("/api/v2/teacher/dashboard/warnings-feed").json()
        check("3. işlenen uyarı aktif akıştan ÇIKTI + 'ertelenenler'e indi",
              not any(w["code"] == code and w["student_id"] == sid for w in feed["rows"])
              and any(w["code"] == code for w in feed["snoozed_rows"])
              and feed["total"] == before - 1, f"total={feed['total']} snoozed={feed['snoozed_count']}")
        print("     ↪ uyarı akıştan çıktı (alarm körlüğü önlendi) ✓")

        r = c.post("/api/v2/teacher/dashboard/warnings/unack", json={"student_id": sid, "code": code})
        check("4. 'Geri al' (unack) → 200", r.status_code == 200, f"{r.status_code}")
        feed = c.get("/api/v2/teacher/dashboard/warnings-feed").json()
        check("5. geri alınınca aktif akışa DÖNDÜ",
              any(w["code"] == code and w["student_id"] == sid for w in feed["rows"])
              and feed["total"] == before, f"total={feed['total']}")

        if BASE.endswith(":3000"):
            rr = c.get("/teacher/dashboard", follow_redirects=True)
            check("6. /teacher/dashboard render → 200", rr.status_code == 200, f"{rr.status_code}")
        c.close()
    finally:
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                db.execute(sa_delete(WarningState).where(WarningState.actor_id.in_(ids)))
                db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(ids)))
                tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(ids)).all()]
                if tids:
                    db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
                    db.execute(sa_delete(Task).where(Task.id.in_(tids)))
                sbids = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(ids)).all()]
                if sbids:
                    db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbids)))
                    db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(ids)))
            bids = [r[0] for r in db.query(Book.id).filter(Book.teacher_id == ctx.get("coach_id")).all()]
            if bids:
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids)))
                db.execute(sa_delete(Book).where(Book.id.in_(bids)))
            if ctx.get("subject_id"):
                db.execute(sa_delete(Subject).where(Subject.id == ctx["subject_id"]))
            if ids:
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
            db.commit()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
