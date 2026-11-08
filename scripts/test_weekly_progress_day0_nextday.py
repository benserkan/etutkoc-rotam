"""Emir (#113) canlı denetiminde bulunan 4 hata — regresyon testi (2026-11-08).

  1. Haftanın ilk günü (k=0): kartlar tam haftalarla kıyaslanıp sahte "geçmişin en kötüsü"
     (critical) veriyordu → "insufficient" + boş cetvel; Gelişim Raporu'nda da öncelikli risk yok.
     Verilen yük (load) kıyası sürer (yük haftanın başında bellidir).
  2. development_report._num: 100 → "1", 120 → "12" (sıfırlar silinmiyordu ondalık yokken).
  3. Sonuç girme riski "testin" yerine "test görevinin" der (sayı kalem sayısıdır).
  4. Ertesi gün işaretleyen öğrenci: next_day_marking tanır; gece "bugün başlamadı" çıkmaz.
     Aynı gün işaretleyen öğrencide uyarı sürer (kontrol).
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, time, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Task, TaskBookItem, Topic, User, UserRole, WeeklyProgram  # noqa: E402
from app.models.student_period import StudentGradePeriod  # noqa: E402
from app.models.task import TaskStatus, TaskType  # noqa: E402
from app.services import analytics, development_report  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.weekly_progress import build_weekly_progress  # noqa: E402

PFX = f"wpd0_{secrets.token_hex(3)}"
today = date.today()
passed = 0
failed: list[str] = []
uids: list[int] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def utc(d: date, hour: int) -> datetime:
    return datetime.combine(d, time(hour)) - timedelta(hours=3)


def seed(db, topic_id: int):
    coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password("x"), full_name="Koç",
                 role=UserRole.TEACHER, is_active=True)
    db.add(coach); db.flush()

    def student(tag: str) -> User:
        s = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password("x"), full_name=tag,
                 role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                 must_change_password=False, created_at=utc(today - timedelta(days=120), 10))
        db.add(s); db.flush()
        return s

    late = student("geç")     # ertesi sabah 09:00 işaretler
    same = student("aynı")    # aynı gün 20:00 işaretler
    uids.extend([coach.id, late.id, same.id])

    def week(st: User, start: date, cur: bool, next_day: bool):
        db.add(WeeklyProgram(student_id=st.id, coach_id=coach.id, start_date=start,
                             end_date=start + timedelta(days=6)))
        for day in range(7):
            d = start + timedelta(days=day)
            for j in range(3):
                done = not (cur and d >= today)
                t = Task(student_id=st.id, date=d, title=f"Konu testi {day}-{j}", type=TaskType.TEST,
                         status=TaskStatus.COMPLETED if done else TaskStatus.PENDING, is_draft=False,
                         order=j,
                         completed_at=(utc(d + timedelta(days=1), 9) if next_day else utc(d, 20)) if done else None)
                t.book_items = [TaskBookItem(topic_id=topic_id, planned_count=5,
                                             completed_count=5 if done else 0)]
                db.add(t)

    for st, nd in ((late, True), (same, False)):
        for i in range(7, 0, -1):                 # 7 geçmiş program haftası
            week(st, today - timedelta(days=7 * i), False, nd)
        week(st, today, True, nd)                 # bu hafta bugün başlıyor → k=0
    db.commit()
    return late, same


def cleanup():
    with SessionLocal() as db:
        if not uids:
            return
        tids = [t for (t,) in db.query(Task.id).filter(Task.student_id.in_(uids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
        db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id.in_(uids)))
        db.execute(sa_delete(StudentGradePeriod).where(StudentGradePeriod.student_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def main():
    print("— 2. _num biçimi")
    n = development_report._num
    for v, d, exp in ((100, 0, "100"), (120, 0, "120"), (99.67, 0, "100"), (1.5, 2, "1,5"),
                      (90.17, 2, "90,17"), (0, 0, "0"), (4.0, 2, "4"), (1004, 0, "1004")):
        check(f"_num({v}, {d}) = {exp}", n(v, d) == exp, n(v, d))

    with SessionLocal() as db:
        topic = db.query(Topic).filter(Topic.is_builtin.is_(True)).first()
        late, same = seed(db, topic.id)

        print("— 1. Haftanın ilk günü (k=0)")
        wp = build_weekly_progress(db, late, today=today)
        check("compare_days 0", wp["week"]["compare_days"] == 0, wp["week"])
        cards = {c["key"]: c for c in wp["cards"]}
        td = cards["test_done"]
        check("çözülen test: kritik değil → insufficient", td["status"] == "insufficient", td["status"])
        check("çözülen test: cetvel boş", td["baseline"] == [], td["baseline"])
        check("çözülen test: açıklama 'henüz geçen gün yok'", "henüz geçen gün yok" in td["verdict"], td["verdict"])
        check("yeni konu: insufficient", cards["new_topics"]["status"] == "insufficient",
              cards["new_topics"]["status"])
        check("hiçbir kartta 'geçmişin en kötüsü' yok",
              not any(c["status"] == "critical" for c in wp["cards"]),
              [c["key"] for c in wp["cards"] if c["status"] == "critical"])
        check("verilen yük kıyası sürer", cards["load"]["status"] != "insufficient" and cards["load"]["value"] == 21,
              (cards["load"]["status"], cards["load"]["value"]))

        rep = development_report.build_development_report(db, late, today=today)
        txt = str(rep)
        check("rapor: 'Çözülen test geçmişin en kötüsü' riski yok", "Çözülen test geçmişin en kötüsü" not in txt)
        check("rapor: 'Haftalık test: N → 1' biçim hatası yok", "→ 1." not in txt)

        print("— 1b. Kontrol: 2. gün (k=1) kıyas normal çalışır")
        wp2 = build_weekly_progress(db, late, today=today + timedelta(days=1))
        td2 = {c["key"]: c for c in wp2["cards"]}["test_done"]
        check("k=1: cetvel dolu (geçmiş haftaların 1. günü)", len(td2["baseline"]) >= 4, td2["baseline"])

        print("— 4. Ertesi gün işaretleme")
        nd, due, ns = analytics.next_day_marking(db, late.id, today)
        check("geç işaretleyen tanınır", nd and ns >= 5, (nd, due, ns))
        check("olağan işaretleme ~10:00", due == 10 * 60, due)
        nd2, _, _ = analytics.next_day_marking(db, same.id, today)
        check("aynı gün işaretleyen tanınmaz", not nd2)
        wpl = build_weekly_progress(db, late, today=today)
        check("haftalık ilerleme marks_next_day", wpl["week"].get("marks_next_day") is True
              and wpl["week"].get("next_day_mark_time") == "10:00", wpl["week"])

        orig = analytics._tr_now
        analytics._tr_now = lambda: datetime.combine(today, time(23, 30))
        try:
            codes_late = [w.code for w in analytics.legacy_warnings(db, late, today, None)]
            codes_same = [w.code for w in analytics.legacy_warnings(db, same, today, None)]
        finally:
            analytics._tr_now = orig
        check("geç işaretleyende gece 'bugün başlamadı' YOK", "today_no_tick" not in codes_late, codes_late)
        check("aynı gün işaretleyende gece uyarı VAR (kontrol)", "today_no_tick" in codes_same, codes_same)

    print("— 3. Sonuç girme cümlesi")
    src = open(development_report.__file__, encoding="utf-8").read()
    check("'testin yalnız' ifadesi kalmadı", "testin yalnız" not in src)


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    if failed:
        sys.exit(1)
