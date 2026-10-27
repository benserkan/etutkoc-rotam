"""Program yarıda kesilip yeni program başlatılınca (Beril vakası, 2026-10-27).

Eski program 21→27, yeni program 27'de başlıyor:
  1. trim_previous olmadan → 409 overlap + trimmable=True, trim_to=26
  2. trim_previous=True → 200, eski program 26'da biter, görevler yerinde kalır
  3. Liste: yalnız YENİ program "bu hafta"; 27'deki görev yalnız yeni programa sayılır
  4. allow_overlap ile eski davranış (iki program) → yine tek "bu hafta" (en geç başlayan)
  5. Yeni program eskiyle AYNI gün başlıyorsa kırpılamaz → trimmable=False
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Task, TaskBookItem, TaskStatus, TaskType, User, UserRole, WeeklyProgram  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"wpt_{secrets.token_hex(3)}"
PWD = "Kirp!Program2345"
today = date.today()
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


def main() -> int:
    uids: list[int] = []
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD), full_name="Koç",
                         role=UserRole.TEACHER, is_active=True, plan="solo_pro")
            db.add(coach); db.flush()
            st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PWD), full_name="Beril",
                      role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=8)
            db.add(st); db.flush()
            old = WeeklyProgram(student_id=st.id, coach_id=coach.id,
                                start_date=today - timedelta(days=6), end_date=today)
            db.add(old)
            for d in range(7):
                db.add(Task(student_id=st.id, date=today - timedelta(days=6 - d), title=f"G{d}",
                            type=TaskType.OTHER, status=TaskStatus.PENDING, is_draft=False, order=0))
            db.commit()
            uids += [coach.id, st.id]
            sid, old_id = st.id, old.id
        get_login_limiter().reset()
        c = TestClient(app)
        assert c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD}).status_code == 200
        body = {"start_date": today.isoformat(), "end_date": (today + timedelta(days=6)).isoformat()}
        url = f"/api/v2/teacher/students/{sid}/programs"

        r = c.post(url, json=body)
        ov = (r.json().get("detail") or {}).get("overlaps") or []
        check("1a çakışma 409", r.status_code == 409, r.text[:200])
        check("1b kırpılabilir + trim_to dün",
              ov and ov[0]["trimmable"] and ov[0]["trim_to"] == (today - timedelta(days=1)).isoformat(), str(ov))

        r = c.post(url, json={**body, "trim_previous": True})
        check("2a trim ile 200", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            o = db.get(WeeklyProgram, old_id)
            check("2b eski program dün biter", o.end_date == today - timedelta(days=1), str(o.end_date))
            check("2c görevler yerinde", db.query(Task).filter(Task.student_id == sid).count() == 7)

        lst = c.get(url).json()["items"]
        act = [p for p in lst if p["is_active"]]
        check("3a tek 'bu hafta'", len(act) == 1 and act[0]["start_date"] == today.isoformat(), str(act))
        cnt = {p["start_date"]: p["task_count"] for p in lst}
        check("3b sayım: eski 6, yeni 1", cnt.get((today - timedelta(days=6)).isoformat()) == 6
              and cnt.get(today.isoformat()) == 1, str(cnt))

        # 4 — eski davranış: iki program çakışık kalsa da tek "bu hafta"
        with SessionLocal() as db:
            o = db.get(WeeklyProgram, old_id); o.end_date = today; db.commit()
        lst = c.get(url).json()["items"]
        act = [p for p in lst if p["is_active"]]
        check("4 çakışık iki programda tek 'bu hafta' (en geç başlayan)",
              len(act) == 1 and act[0]["start_date"] == today.isoformat(), str(act))
        wk = c.get(f"/api/v2/teacher/students/{sid}/week").json()
        wact = [p for p in wk.get("programs", []) if p["is_active"]]
        check("4b hafta yanıtında da tek 'bu hafta'", len(wact) == 1, str(wact))

        # 5 — aynı gün başlayan program kırpılamaz
        r = c.post(url, json={"start_date": today.isoformat(), "end_date": (today + timedelta(days=3)).isoformat()})
        ov = (r.json().get("detail") or {}).get("overlaps") or []
        same = [o for o in ov if o["start_date"] == today.isoformat()]
        check("5 aynı gün başlayan kırpılamaz", r.status_code == 409 and same and not same[0]["trimmable"], str(ov))
    finally:
        with SessionLocal() as db:
            tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(uids)).all()]
            if tids:
                db.query(TaskBookItem).filter(TaskBookItem.task_id.in_(tids)).delete(synchronize_session=False)
                db.query(Task).filter(Task.id.in_(tids)).delete(synchronize_session=False)
            db.query(WeeklyProgram).filter(WeeklyProgram.student_id.in_(uids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
            db.commit()
    print(f"\n{passed} geçti, {len(failed)} kaldı")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
