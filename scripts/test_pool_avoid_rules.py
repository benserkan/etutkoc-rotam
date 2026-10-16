"""Havuz kaçınma kuralı (K44) — "hiç kaba alınmadı" sayımı (2026-10-16 düzeltmesi).

  1 dönem açılışında eklenen, 4 gündür kaba alınmayan kalem → kaçınılan
  2 dün eklenen kalem → kaçınılan DEĞİL (süre kalemin eklendiği günden)
  3 onay bekleyen öğrenci kalemi → kaçınılan DEĞİL
  4 3 kez kaba girip dönen kalem → kaçınılan (dönüş gerekçesiyle)
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

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Subject, Task, Topic, User, UserRole  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.pool import PoolItem, StudyPeriod  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"tpar_{secrets.token_hex(3)}"
today = date.today()
passed, failed = 0, []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def at(day: date) -> datetime:
    return datetime.combine(day, time(12), tzinfo=timezone.utc)


def main() -> int:
    ids: dict = {}
    with SessionLocal() as db:
        try:
            coach = User(email=f"{PFX}_c@test.invalid", password_hash=hash_password("x"), full_name="K",
                         role=UserRole.TEACHER, is_active=True)
            db.add(coach)
            db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password("x"), full_name="S",
                      role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                      program_mode="havuz")
            db.add(st)
            sub = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
            db.add(sub)
            db.flush()
            top = Topic(subject_id=sub.id, name="Üslü", order=1, teacher_id=coach.id)
            db.add(top)
            db.flush()
            ids.update(coach=coach.id, st=st.id, sub=sub.id)
            opened = today - timedelta(days=5)
            p = pm.open_period(db, student=st, coach=coach, opened_on=opened)
            a = pm.add_item(db, period=p, student=st, subject=sub, quantity=4, unit="test", topic=top)
            b = pm.add_item(db, period=p, student=st, subject=sub, quantity=4, unit="test", topic=top)
            c = pm.add_item(db, period=p, student=st, subject=sub, quantity=3, unit="test", label="kendi",
                            source="ogrenci", created_by=st)
            e = pm.add_item(db, period=p, student=st, subject=sub, quantity=4, unit="test", topic=top)
            a.created_at = at(opened)
            b.created_at = at(today - timedelta(days=1))
            c.created_at = at(opened)
            e.created_at = at(opened)
            for off in (3, 2, 1):
                pm.put_in_cup(db, item=e, day=today - timedelta(days=off), count=2)
                pm.close_day(db, student=st, day=today - timedelta(days=off))
            db.flush()
            r = pm.avoid_reasons(p, today, db)
            check("1 açılışta eklenen, 5 gündür alınmayan kalem kaçınılan", a in r, str(r.get(a)))
            check("2 dün eklenen kalem kaçınılan değil", b not in r, str(r.get(b)))
            check("3 onay bekleyen öğrenci kalemi kaçınılan değil", c not in r, str(r.get(c)))
            check("4 3 kez kaba girip dönen kalem kaçınılan", "geri döndü" in (r.get(e) or ""), str(r.get(e)))
        finally:
            db.rollback()
            db.execute(sa_delete(Task).where(Task.student_id == ids.get("st", 0)))
            db.execute(sa_delete(PoolItem).where(PoolItem.student_id == ids.get("st", 0)))
            db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id == ids.get("st", 0)))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids.get("sub", 0)))
            db.execute(sa_delete(Subject).where(Subject.id == ids.get("sub", 0)))
            db.execute(sa_delete(User).where(User.email.like(f"{PFX}_%")))
            db.commit()
    print(f"\n{passed} passed · {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
