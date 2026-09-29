"""'Bugün henüz başlamadı' uyarısı öğrencinin kendi ritmine göre (2026-09-29).

Koç: sabah 08:52'de "bugün hiç tik yapmadı" demek anlamsız, alarm körlüğü yapar.
Prod: tiklerin çoğu 22:00–01:00 arası.

  1. Akşamcı öğrenci (ilk tik ~21:00) → 08:52'de uyarı YOK
  2. ...22:10'da (21:00 + 1 saat geçti) → uyarı VAR, sarı, kanıtta olağan saat
  3. Geçmişi olmayan öğrenci → varsayılan 19:00: 18:30 yok / 19:30 var
  4. Gece yarısından sonra tik atan öğrenci → saat 24+ sayılır, üst sınır 23:00
  5. Tutarlılık = programlı günler; tiksiz bugün ve programsız gün paydada değil
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Task, TaskStatus, TaskType, User, UserRole
from app.services import analytics
from app.services.security import hash_password

PFX = f"tnt_{secrets.token_hex(3)}"
today = date.today()
now = datetime.now(timezone.utc)
uids: list[int] = []
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def mk(tag, coach_id=None):
    with SessionLocal() as db:
        u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password("x"),
                 full_name=f"{PFX} {tag}", role=UserRole.STUDENT if coach_id else UserRole.TEACHER,
                 teacher_id=coach_id, grade_level=12 if coach_id else None, is_active=True,
                 created_at=now - timedelta(days=40))
        db.add(u)
        db.commit()
        uids.append(u.id)
        return u.id


def task(sid, day, done_at_tr: datetime | None):
    """done_at_tr: TR saati (naive) — UTC'ye çevrilip yazılır."""
    with SessionLocal() as db:
        t = Task(student_id=sid, date=day, type=TaskType.OTHER, title="G", is_draft=False,
                 published_at=now,
                 status=TaskStatus.COMPLETED if done_at_tr else TaskStatus.PENDING,
                 completed_at=(done_at_tr - timedelta(hours=3)).replace(tzinfo=timezone.utc) if done_at_tr else None)
        db.add(t)
        db.commit()


def at(hh, mm):
    return lambda: datetime.combine(today, time(hh, mm), tzinfo=timezone.utc)


def warn(sid, clock):
    analytics._tr_now = clock
    with SessionLocal() as db:
        s = db.get(User, sid)
        proj = analytics.compute_projection(db, s, today, window_days=28, buffer_days=5)
        return {w.code: w for w in analytics.generate_warnings(db, s, today, proj)}


def main() -> int:
    coach = mk("coach")
    try:
        # 1-2 akşamcı: son 10 gün ilk tik 21:00
        ev = mk("aksam", coach)
        for k in range(1, 11):
            d = today - timedelta(days=k)
            task(ev, d, datetime.combine(d, time(21, 0)))
        task(ev, today, None)
        w = warn(ev, at(8, 52))
        chk("1 akşamcı öğrenci 08:52 → uyarı yok", "today_no_tick" not in w, str(list(w)))
        w = warn(ev, at(22, 10))
        tw = w.get("today_no_tick")
        chk("2 22:10 → uyarı var (sarı)", tw is not None and tw.level == "amber", str(list(w)))
        chk("2b kanıtta olağan başlama 21:00",
            tw is not None and any(lbl == "Olağan başlama" and v.startswith("21:00") for lbl, v in tw.evidence),
            str(tw.evidence if tw else None))

        # 3 geçmişsiz öğrenci → varsayılan 19:00
        nw = mk("yeni", coach)
        task(nw, today, None)
        chk("3a geçmişsiz 18:30 → yok", "today_no_tick" not in warn(nw, at(18, 30)))
        chk("3b geçmişsiz 19:30 → var", "today_no_tick" in warn(nw, at(19, 30)))

        # 4 gece tikçi: ilk tik ertesi gün 00:30
        gc = mk("gece", coach)
        for k in range(2, 12):
            d = today - timedelta(days=k)
            task(gc, d, datetime.combine(d + timedelta(days=1), time(0, 30)))
        with SessionLocal() as db:
            due, n = analytics.usual_first_tick(db, gc, today)
        chk("4 gece tikçi → üst sınır 23:00", due == 23 * 60 and n == 10, f"due={due} n={n}")

        # 5 tutarlılık: 3 programlı gün tikli, 1 programsız gün, bugün tiksiz
        cs = mk("tutarli", coach)
        for k in (1, 2, 4):
            d = today - timedelta(days=k)
            task(cs, d, datetime.combine(d, time(20, 0)))
        task(cs, today, None)
        with SessionLocal() as db:
            c = analytics.consistency_score(db, cs, today, 7)
        chk("5 tutarlılık programlı günlere göre = %100", abs(c - 1.0) < 1e-9, str(c))
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(Task).where(Task.student_id.in_(uids)))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.commit()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
