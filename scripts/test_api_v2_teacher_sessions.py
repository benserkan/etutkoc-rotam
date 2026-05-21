"""API v2 /teacher koçluk seansları smoke (KS1).

Senaryolar:
   1. Anonim → 401
   2. POST create happy (agenda) → 200 + auto_snapshot dolu + status done
   3. POST agenda boş → 422 agenda_required
   4. POST geçersiz tarih → 422 invalid_date
   5. POST geçersiz mood (6) → 422 invalid_mood
   6. POST başka öğretmenin öğrencisi → 404
   7. GET liste → summary (done sayım) + rows DESC
   8. GET prefill → şekil
   9. GET detay → row
  10. POST update → status ertelendi + agenda değişti
  11. DELETE → 200 + gider
  12. başka öğretmen DELETE → 404
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import CoachingSession, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2tses{secrets.token_hex(3)}"
T_EMAIL = f"{PFX}_t@test.invalid"
T2_EMAIL = f"{PFX}_t2@test.invalid"
PASSWORD = "SesPass1!@xyz"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed():
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        t = User(email=T_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        t2 = User(email=T2_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç2",
                  role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([t, t2]); db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=pwd, full_name="Öğr",
                 role=UserRole.STUDENT, is_active=True, grade_level=8, teacher_id=t.id)
        s2 = User(email=f"{PFX}_s2@test.invalid", password_hash=pwd, full_name="Öğr2",
                  role=UserRole.STUDENT, is_active=True, grade_level=8, teacher_id=t2.id)
        db.add_all([s, s2]); db.flush()
        out = {"t_id": t.id, "t2_id": t2.id, "s_id": s.id, "s2_id": s2.id}
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        db.execute(sa_delete(CoachingSession).where(
            CoachingSession.student_id.in_([seed["s_id"], seed["s2_id"]])))
        db.execute(sa_delete(User).where(User.id.in_(
            [seed["t_id"], seed["t2_id"], seed["s_id"], seed["s2_id"]])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text[:120]}")
    return c


def main():
    print(f"\n=== API v2 /teacher sessions smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
    seed = _seed()
    try:
        tc = _login(T_EMAIL)
        t2c = _login(T2_EMAIL)
        sid = seed["s_id"]

        r = TestClient(app).get(f"/api/v2/teacher/students/{sid}/sessions")
        check("1. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 2. happy
        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": "2026-05-15", "status": "done",
            "agenda": "Sınav kaygısı konuşuldu", "coach_note": "Motivasyon düşük",
            "mood": 3, "tags": ["kaygı", "motivasyon"]})
        j = r.json()
        ok = (r.status_code == 200 and j["data"]["status"] == "done"
              and j["data"]["agenda"] == "Sınav kaygısı konuşuldu"
              and j["data"]["auto_snapshot"] is not None
              and j["data"]["tags"] == ["kaygı", "motivasyon"])
        check("2. POST happy + auto_snapshot + tags", ok, f"status={r.status_code} {r.text[:160]}")
        sess_id = j["data"]["id"] if r.status_code == 200 else None
        check("2b. invalidate sessions key",
              r.status_code == 200 and any("sessions" in k for k in j["invalidate"]), f"{j.get('invalidate')}")

        # 3. agenda boş
        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": "2026-05-15", "agenda": "   "})
        check("3. agenda boş → 422 agenda_required",
              r.status_code == 422 and r.json()["detail"]["code"] == "agenda_required", f"status={r.status_code}")

        # 4. geçersiz tarih
        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": "bozuk", "agenda": "X"})
        check("4. geçersiz tarih → 422 invalid_date",
              r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date", f"status={r.status_code}")

        # 5. geçersiz mood
        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": "2026-05-15", "agenda": "X", "mood": 6})
        check("5. mood 6 → 422 invalid_mood",
              r.status_code == 422 and r.json()["detail"]["code"] == "invalid_mood", f"status={r.status_code}")

        # 6. başka öğretmenin öğrencisi
        r = tc.post(f"/api/v2/teacher/students/{seed['s2_id']}/sessions", json={
            "session_date": "2026-05-15", "agenda": "X"})
        check("6. başka öğr. öğrencisi → 404", r.status_code == 404, f"status={r.status_code}")

        # 7. liste
        r = tc.get(f"/api/v2/teacher/students/{sid}/sessions")
        j = r.json()
        check("7. liste summary done=1",
              r.status_code == 200 and j["summary"]["total"] == 1 and j["summary"]["done_count"] == 1
              and j["summary"]["last_session_date"] == "2026-05-15", f"{j.get('summary')}")

        # 8. prefill
        r = tc.get(f"/api/v2/teacher/students/{sid}/sessions/prefill")
        j = r.json()
        check("8. prefill şekil",
              r.status_code == 200 and "week_planned" in j and "behind_subjects" in j and "exam_count" in j,
              f"status={r.status_code} {r.text[:120]}")

        # 9. detay
        r = tc.get(f"/api/v2/teacher/sessions/{sess_id}")
        check("9. detay row", r.status_code == 200 and r.json()["id"] == sess_id, f"status={r.status_code}")

        # 10. update
        r = tc.post(f"/api/v2/teacher/sessions/{sess_id}", json={
            "session_date": "2026-05-15", "status": "postponed", "agenda": "Ertelendi - yeni gündem"})
        j = r.json()
        check("10. update status+agenda",
              r.status_code == 200 and j["data"]["status"] == "postponed"
              and j["data"]["agenda"] == "Ertelendi - yeni gündem", f"status={r.status_code} {j.get('data',{})}")

        # 11. delete
        r = tc.delete(f"/api/v2/teacher/sessions/{sess_id}")
        check("11. DELETE → 200", r.status_code == 200 and r.json()["data"]["deleted"], f"status={r.status_code}")
        r = tc.get(f"/api/v2/teacher/students/{sid}/sessions")
        check("11b. silindikten sonra total=0", r.json()["summary"]["total"] == 0, f"{r.json()['summary']}")

        # 12. başka öğretmen delete → 404 (yeni kayıt aç)
        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": "2026-05-16", "agenda": "tekrar"})
        new_id = r.json()["data"]["id"]
        r = t2c.delete(f"/api/v2/teacher/sessions/{new_id}")
        check("12. başka öğr. DELETE → 404", r.status_code == 404, f"status={r.status_code}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
