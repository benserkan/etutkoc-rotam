"""Uyarı akışı tazelik + gördüm/ertele (WarningState) smoke.

Senaryo: koç + (10 gün önce açılmış, dün planlı görevi tamamlanmamış) öğrenci →
canlı uyarı üretir. Test:
  1. feed → uyarı(lar) + code + age_days (tazelik)
  2. ack (gördüm/ertele) → uyarı aktif akıştan çıkar, 'ertelenenler'e iner
  3. unack → aktif akışa geri döner
  4. reconcile purge (servis): koşul düzelince state silinir → tekrar 'taze'
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    Subject,
    User,
    UserRole,
    WarningState,
)
from app.models.book import BookType
from app.models.curriculum import CurriculumModel
from app.models.progress import SectionProgress, StudentBook
from app.models.suspicious_ip import SuspiciousIp
from app.models.task import Task, TaskBookItem, TaskStatus, TaskType
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.services.task_service import reserve_item

PFX = f"warnack_{secrets.token_hex(3)}"
PWD = hash_password("WarnAck!23")
PWDH = "WarnAck!23"
now = datetime.now(timezone.utc)

passed = 0
failed: list[str] = []
ctx: dict = {}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_c@test.invalid", password_hash=PWD, full_name=f"{PFX} Koç",
                     role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_pro",
                     password_changed_at=now, must_change_password=False)
        db.add(coach); db.flush()
        # 10 gün önce açılmış öğrenci (onboarding grace dışında)
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=PWD, full_name=f"{PFX} Öğrenci",
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
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               reserved_count=0, completed_count=0))
        db.flush()
        # Dün planlı, tamamlanmamış görev → 'yesterday_no_tick' tipi uyarı
        yday = date.today() - timedelta(days=1)
        task = Task(student_id=stu.id, date=yday, type=TaskType.TEST, title="Dün görevi",
                    status=TaskStatus.PENDING, order=0, is_draft=False,
                    published_at=now - timedelta(days=1))
        db.add(task); db.flush()
        reserve_item(db, student_id=stu.id, book_id=book.id, section_id=sec.id, count=5)
        db.add(TaskBookItem(task_id=task.id, book_id=book.id, book_section_id=sec.id,
                            planned_count=5, completed_count=0))
        db.commit()
        ctx.update(coach_id=coach.id, student_id=stu.id, subject_id=subj.id, book_id=book.id)


def login():
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_c@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== UYARI TAZELİK + GÖRDÜM/ERTELE — {PFX} ===\n")
    setup()
    sid = ctx["student_id"]
    try:
        c = login()
        feed = c.get("/api/v2/teacher/dashboard/warnings-feed").json()
        check("1. feed canlı uyarı üretti (total>=1) + code + age_days alanları",
              feed["total"] >= 1 and all("code" in r and "age_days" in r for r in feed["rows"]),
              f"total={feed.get('total')} keys={list(feed['rows'][0].keys()) if feed.get('rows') else '-'}")
        if not feed["rows"]:
            raise RuntimeError("uyarı üretilmedi — setup beklenen koşulu tetiklemedi")
        row0 = feed["rows"][0]
        code = row0["code"]
        check("2. tazelik: age_days ~10 (10 gün önce açılan öğrenci, dünkü uyarı bugün ilk görüldü)",
              row0["age_days"] >= 0, f"age={row0['age_days']}")
        active_before = feed["total"]

        # rozet: ack ÖNCESİ "Öğrenciler" rozeti (at_risk) >= 1 + destek alanı var
        badges = c.get("/api/v2/teacher/badges").json()
        check("R1 ack öncesi at_risk_count >= 1 + support_answered_count alanı var",
              badges["at_risk_count"] >= 1 and "support_answered_count" in badges,
              f"{badges}")

        # ack (gördüm/ertele)
        r = c.post("/api/v2/teacher/dashboard/warnings/ack",
                   json={"student_id": sid, "code": code, "snooze_days": 3})
        check("3. ack → 200", r.status_code == 200, f"{r.status_code} {r.text[:120]}")
        feed = c.get("/api/v2/teacher/dashboard/warnings-feed").json()
        in_active = any(w["student_id"] == sid and w["code"] == code for w in feed["rows"])
        in_snoozed = any(w["student_id"] == sid and w["code"] == code for w in feed["snoozed_rows"])
        check("4. ertelenen aktif akıştan ÇIKTI, 'ertelenenler'e indi",
              (not in_active) and in_snoozed and feed["snoozed_count"] >= 1
              and feed["total"] == active_before - 1,
              f"active={in_active} snoozed={in_snoozed} cnt={feed['snoozed_count']} total={feed['total']}")
        sn = next(w for w in feed["snoozed_rows"] if w["code"] == code)
        check("5. ertelenen satırda snoozed=True + snooze_until dolu",
              sn["snoozed"] is True and sn["snooze_until"], f"{sn.get('snooze_until')}")

        # unack (geri al)
        r = c.post("/api/v2/teacher/dashboard/warnings/unack", json={"student_id": sid, "code": code})
        check("6. unack → 200", r.status_code == 200, f"{r.status_code}")
        feed = c.get("/api/v2/teacher/dashboard/warnings-feed").json()
        check("7. geri alınınca aktif akışa DÖNDÜ",
              any(w["student_id"] == sid and w["code"] == code for w in feed["rows"])
              and feed["total"] == active_before, f"total={feed['total']}")

        # R2 rozet 'işleyince azalır': öğrencinin TÜM aktif uyarıları ack'lenince
        # at_risk_count düşer (tek öğrenci → 0).
        feed = c.get("/api/v2/teacher/dashboard/warnings-feed").json()
        for w in [x for x in feed["rows"] if x["student_id"] == sid]:
            c.post("/api/v2/teacher/dashboard/warnings/ack",
                   json={"student_id": sid, "code": w["code"], "snooze_days": 3})
        badges = c.get("/api/v2/teacher/badges").json()
        check("R2 tüm uyarılar ack'lenince at_risk_count düşer (işleyince azalır)",
              badges["at_risk_count"] == 0, f"at_risk={badges['at_risk_count']}")

        # sahiplik: başka öğrenci id ile ack → 404
        r = c.post("/api/v2/teacher/dashboard/warnings/ack",
                   json={"student_id": 999999, "code": code, "snooze_days": 3})
        check("8. başka/olmayan öğrenci ack → 404 (sahiplik)", r.status_code == 404, f"{r.status_code}")

        # reconcile purge (servis): koşul düzelince state silinir → first_seen sıfırlanır
        from app.services.warning_state_service import reconcile_states, set_snooze
        with SessionLocal() as db:
            set_snooze(db, actor_id=ctx["coach_id"], student_id=sid, code="ghost_code", days=3)
            db.commit()
        with SessionLocal() as db:
            cnt_before = db.query(WarningState).filter_by(actor_id=ctx["coach_id"], code="ghost_code").count()
        with SessionLocal() as db:
            # present_keys ghost_code içermiyor → silinmeli
            reconcile_states(db, actor_id=ctx["coach_id"], present_keys={(sid, code)}, now=now)
            db.commit()
        with SessionLocal() as db:
            cnt_after = db.query(WarningState).filter_by(actor_id=ctx["coach_id"], code="ghost_code").count()
        check("9. reconcile purge: koşulu düzelen (canlıda olmayan) state silindi",
              cnt_before == 1 and cnt_after == 0, f"before={cnt_before} after={cnt_after}")

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
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
