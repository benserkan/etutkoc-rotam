"""Öğrenci detayı — haftalık ilerleme smoke (2026-10-20).

Kurgu: bugün programın 3. günü (2 gün geçti). Öncesinde 6 program haftası (ilk 2'si alışma
haftası → tabana girmez, taban 4 hafta). Her gün 4 görev.
  1. Hafta + aynı nokta: compare_days 2, day_index 3
  2. Görev uyumu: taban (ilk 2 gün) %100/%87.5/%100/%87.5 → genelde %87.5–100; bu hafta 4/8 = %50
     → "critical" (geçmişin en kötüsünden de kötü) · geçen hafta aynı noktada değeri
  3. Gün gün: dün kaçırıldı (missed + 4 yapılmayan) · bugün "today" · sonrası "future"
  4. Önlem: "Kalan 4 görevi hafta içine dağıt" + gündem metni
  5. Grafik: son nokta bu hafta · dönem özeti 4 hafta
  6. Gününde tamamlama eğilimi: son 3 tam haftada her hafta düşüş → trend
  7. Taban az (yeni öğrenci): durum "insufficient"
  8. Başka koç 404 · öğrenci 403
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
from app.models import Task, TaskBookItem, User, UserRole, WeeklyProgram  # noqa: E402
from app.models.pool import StudyPeriod  # noqa: E402
from app.models.student_period import StudentGradePeriod  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.models.task import TaskStatus, TaskType  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"wpg_{secrets.token_hex(3)}"
PWD = "Haftalik!2345x"
today = date.today()
cur_start = today - timedelta(days=2)
passed = 0
failed: list[str] = []
ids: dict = {"users": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    assert r.status_code == 200, r.text
    return c


def utc(d: date, hour: int) -> datetime:
    """TR saatini UTC'ye çevir (TR = UTC+3)."""
    return datetime.combine(d, time(hour)) - timedelta(hours=3)


def seed() -> dict:
    with SessionLocal() as db:
        # Önceki yarım koşulardan kalan sahipsiz dönem kayıtları (id yeniden kullanımı) temizlenir.
        db.execute(sa_delete(StudentGradePeriod).where(~StudentGradePeriod.student_id.in_(db.query(User.id))))
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                     role=UserRole.TEACHER, is_active=True)
        other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD), full_name="Öbür",
                     role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other]); db.flush()
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Öğrenci",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                  must_change_password=False)
        new = User(email=f"{PFX}_n@test.invalid", password_hash=hash_password(PWD), full_name="Yeni",
                   role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                   must_change_password=False)
        db.add_all([st, new]); db.flush()
        ids["users"] += [coach.id, other.id, st.id, new.id]

        def add_week(sid: int, start: date, done_first2: int, ontime_late: int = 0, cur: bool = False):
            db.add(WeeklyProgram(student_id=sid, coach_id=coach.id, start_date=start,
                                 end_date=start + timedelta(days=6)))
            n_first2 = 0
            late = 0
            for day in range(7):
                d = start + timedelta(days=day)
                for j in range(4):
                    if cur and d >= today:
                        done = False
                    elif day < 2:
                        done = n_first2 < done_first2
                        n_first2 += 1
                    else:
                        done = True
                    is_late = done and late < ontime_late
                    if is_late:
                        late += 1
                    db.add(Task(student_id=sid, date=d, title=f"Görev {day}-{j}", type=TaskType.OTHER,
                                status=TaskStatus.COMPLETED if done else TaskStatus.PENDING, is_draft=False,
                                order=j, completed_at=(utc(d + timedelta(days=2), 20) if is_late
                                                       else utc(d, 20)) if done else None))

        # 6 geçmiş hafta (eskiden yeniye): ilk 2'si alışma; taban: 8,7,8,7 / 8 ilk iki günde
        firsts = [8, 8, 8, 7, 8, 7]
        lates = [0, 0, 2, 4, 6, 8]       # son 3 tam haftada gününde tamamlama düşüyor
        for i, (f, lt) in enumerate(zip(firsts, lates)):
            add_week(st.id, cur_start - timedelta(days=7 * (6 - i)), f, lt)
        # bu hafta: 1. gün 4/4, 2. gün 0/4
        add_week(st.id, cur_start, 4, cur=True)
        # yeni öğrenci: yalnız bu hafta
        add_week(new.id, cur_start, 6, cur=True)

        # programsız gün-gün öğrencisi: görevler var ama WeeklyProgram kaydı yok
        noprog = User(email=f"{PFX}_np@test.invalid", password_hash=hash_password(PWD), full_name="Programsız",
                      role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                      must_change_password=False)
        # havuz öğrencisi: dönemler hafta yerine geçer
        pool = User(email=f"{PFX}_pl@test.invalid", password_hash=hash_password(PWD), full_name="Havuz",
                    role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                    must_change_password=False, program_mode="havuz")
        db.add_all([noprog, pool]); db.flush()
        ids["users"] += [noprog.id, pool.id]
        for back in (9, 1):
            db.add(Task(student_id=noprog.id, date=today - timedelta(days=back), title="Etkinlik",
                        type=TaskType.OTHER, status=TaskStatus.COMPLETED, is_draft=False, order=0,
                        completed_at=utc(today - timedelta(days=back), 20)))
        db.add(StudyPeriod(student_id=pool.id, coach_id=coach.id, opened_on=today - timedelta(days=10),
                           closed_on=today - timedelta(days=3), status="kapandi"))
        db.add(StudyPeriod(student_id=pool.id, coach_id=coach.id, opened_on=today - timedelta(days=3),
                           expected_next_on=today + timedelta(days=4), status="acik"))
        db.add(Task(student_id=pool.id, date=today - timedelta(days=1), title="Kap", type=TaskType.OTHER,
                    status=TaskStatus.COMPLETED, is_draft=False, order=0,
                    completed_at=utc(today - timedelta(days=1), 20)))
        # havuzdan gün güne geçmiş öğrenci: kapanış günü (yeni dönem açılmadı) o dönemde kalır
        sw = User(email=f"{PFX}_sw@test.invalid", password_hash=hash_password(PWD), full_name="Geçişli",
                  role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                  must_change_password=False, program_mode="havuz")
        db.add(sw); db.flush()
        ids["users"].append(sw.id)
        db.add(StudyPeriod(student_id=sw.id, coach_id=coach.id, opened_on=today - timedelta(days=4),
                           closed_on=today - timedelta(days=2), status="kapandi"))
        db.add(Task(student_id=sw.id, date=today - timedelta(days=2), title="Kap", type=TaskType.OTHER,
                    status=TaskStatus.COMPLETED, is_draft=False, order=0,
                    completed_at=utc(today - timedelta(days=2), 20)))
        db.commit()
        return {"st": st.id, "new": new.id, "np": noprog.id, "pl": pool.id, "sw": sw.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        # Sayfa açılışı sınıf dönemi kaydı açar; silinmezse id yeniden kullanımında sonraki koşuya sızar.
        db.execute(sa_delete(StudentGradePeriod).where(StudentGradePeriod.student_id.in_(u)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    d = seed()
    print(f"\n=== haftalık ilerleme — {PFX} ===\n")
    try:
        c = login(f"{PFX}_t@test.invalid")
        r = c.get(f"/api/v2/teacher/students/{d['st']}/weekly-progress")
        check("0 200", r.status_code == 200, r.text[:300])
        a = r.json()
        w = a.get("week") or {}
        check("1 aynı nokta: 2 gün, 3. gün", w.get("compare_days") == 2 and w.get("day_index") == 3, str(w))
        g = a["headline"].get("gorev_pct", {})
        check("2a bu hafta %50", g.get("value") == 50.0, str(g.get("value")))
        check("2b genelde %87.5–100", g.get("low") == 87.5 and g.get("high") == 100.0, f"{g.get('low')} {g.get('high')}")
        check("2c geçmişin en kötüsünden de kötü → critical", g.get("status") == "critical", g.get("status"))
        check("2d taban 4 hafta (alışma haftaları hariç)", len(g.get("baseline", [])) == 4, str(g.get("baseline")))
        check("2e geçen hafta aynı noktada %88", g.get("prev_label") == "%88", g.get("prev_label"))
        check("2f düz yorum cümlesi", "en kötüsünden" in g.get("verdict", ""), g.get("verdict"))
        days = a["days"]
        check("3a 7 gün", len(days) == 7)
        check("3b 1. gün tamam", days[0]["state"] == "done" and days[0]["done"] == 4, str(days[0]))
        check("3c dün kaçırıldı, 4 yapılmayan", days[1]["state"] == "missed" and len(days[1]["missing"]) == 4,
              str(days[1]))
        check("3d bugün 'today', sonrası 'future'", days[2]["state"] == "today"
              and all(x["state"] == "future" for x in days[3:]), str([x["state"] for x in days]))
        acts = {x["key"]: x for x in a["actions"]}
        check("4 önlem: kalan 4 görev", "carry" in acts and "4 görev" in acts["carry"]["title"]
              and acts["carry"]["agenda"], str(list(acts)))
        ch = a["chart"]
        check("5a grafik ≤8, son nokta bu hafta", 0 < len(ch) <= 8 and ch[-1]["current"], str(ch[-1:]))
        check("5b dönem özeti 4 hafta", a["period_summary"]["weeks"] == 4, str(a["period_summary"]))
        cards = {x["key"]: x for x in a["cards"]}
        ot = cards.get("ontime_pct", {})
        check("6 gününde tamamlama: 3 hafta üst üste düşüş", ot.get("trend") is True and ot.get("trend_run", 0) >= 3,
              f"{ot.get('trend_run')} {ot.get('verdict')}")
        check("6b kart grupları", {x["group"] for x in a["cards"]} == {"gelisim", "ilerleme", "risk"})

        r = c.get(f"/api/v2/teacher/students/{d['new']}/weekly-progress")
        g2 = r.json()["headline"].get("gorev_pct", {})
        check("7 yeni öğrenci: veri az", g2.get("status") == "insufficient", g2.get("status"))

        r = c.get(f"/api/v2/teacher/students/{d['np']}/weekly-progress")
        a3 = r.json()
        w3 = a3.get("week") or {}
        mon = today - timedelta(days=today.weekday())
        check("9a programsız görevler → takvim haftası", a3.get("has_program") is True and w3.get("kind") == "takvim"
              and w3.get("start") <= (today - timedelta(days=1)).isoformat(), str(w3))
        check("9b takvim haftası Pazartesi'den başlar", w3.get("start") == mon.isoformat()
              or w3.get("start") > mon.isoformat(), str(w3))

        r = c.get(f"/api/v2/teacher/students/{d['pl']}/weekly-progress")
        a4 = r.json()
        w4 = a4.get("week") or {}
        check("10a havuz öğrencisi → açık dönem", a4.get("has_program") is True and w4.get("kind") == "donem"
              and w4.get("start") == (today - timedelta(days=3)).isoformat(), str(w4))
        check("10b açık dönem beklenen seansın bir gün öncesine kadar",
              w4.get("end") == (today + timedelta(days=3)).isoformat(), str(w4))
        check("10c grafikte önceki dönem de var", len(a4.get("chart", [])) == 2, str(a4.get("chart")))

        r = c.get(f"/api/v2/teacher/students/{d['sw']}/weekly-progress")
        w5 = r.json().get("week") or {}
        check("11 yeni dönem açılmadıysa kapanış günü dönemde kalır",
              w5.get("kind") == "donem" and w5.get("end") == (today - timedelta(days=2)).isoformat()
              and r.json()["days"][-1]["done"] == 1, str(w5))

        o = login(f"{PFX}_o@test.invalid")
        check("8a başka koç 404", o.get(f"/api/v2/teacher/students/{d['st']}/weekly-progress").status_code == 404)
        s = login(f"{PFX}_s@test.invalid")
        check("8b öğrenci 403", s.get(f"/api/v2/teacher/students/{d['st']}/weekly-progress").status_code == 403)
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
