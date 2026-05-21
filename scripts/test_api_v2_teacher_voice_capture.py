"""API v2 /teacher AI yakalama (ses→metin) smoke (KS3b).

Gerçek Whisper/Claude çağrısı YAPILMAZ — parse_session_voice monkeypatch'lenir.

Senaryolar:
   1. Anonim → 401
   2. GET ai-consent → consented false
   3. parse-voice rıza yok → 403 consent_required
   4. POST ai-consent → consented true
   5. parse-voice boş ses → 422 audio_required
   6. parse-voice geçersiz media_type → 422 invalid_media_type
   7. parse-voice happy (monkeypatch) → draft + kredi tüketildi (UsageEvent VOICE)
   8. parse-voice başka öğretmenin öğrencisi → 404
   9. drafttan seans kaydet (capture_source=voice) → kalıcı
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
from app.models.usage import UsageEvent
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
import app.services.ai_session_capture as ai_capture

PFX = f"v2tvoc{secrets.token_hex(3)}"
T_EMAIL = f"{PFX}_t@test.invalid"
T2_EMAIL = f"{PFX}_t2@test.invalid"
PASSWORD = "VocPass1!@xyz"

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
                 role=UserRole.TEACHER, is_active=True, plan="solo_pro")  # bağımsız (institution_id NULL)
        t2 = User(email=T2_EMAIL, password_hash=pwd, full_name=f"{PFX} Koç2",
                  role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([t, t2]); db.flush()
        s = User(email=f"{PFX}_s@test.invalid", password_hash=pwd, full_name="Öğr",
                 role=UserRole.STUDENT, is_active=True, grade_level=8, teacher_id=t.id)
        s2 = User(email=f"{PFX}_s2@test.invalid", password_hash=pwd, full_name="Öğr2",
                  role=UserRole.STUDENT, is_active=True, grade_level=8, teacher_id=t2.id)
        db.add_all([s, s2]); db.flush()
        out = {"t_id": t.id, "t2_id": t2.id, "s_id": s.id, "s2_id": s2.id}
        from app.services.credits import CreditOwner, get_or_create_account
        get_or_create_account(db, owner=CreditOwner.for_user(t))
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        sids = [seed["s_id"], seed["s2_id"]]
        uids = [seed["t_id"], seed["t2_id"], *sids]
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(sids)))
        db.execute(sa_delete(UsageEvent).where(UsageEvent.owner_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        try:
            from app.models import CreditAccount
            db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id.in_(uids)))
        except Exception:
            pass
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text[:120]}")
    return c


def main():
    print(f"\n=== API v2 /teacher voice-capture smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
    seed = _seed()
    sid = seed["s_id"]

    orig = ai_capture.parse_session_voice
    ai_capture.parse_session_voice = lambda audio, mt, **kw: {
        "agenda": "Motivasyon düşüklüğü + deneme analizi",
        "coach_note": "Öğrenci son denemede matematikte zorlanmış, moral bozuk.",
        "next_change": "Günlük 20 soru matematik rutini",
        "mood": 3,
        "tags": ["motivasyon", "matematik"],
    }
    try:
        tc = _login(T_EMAIL)
        AUD = {"audio_base64": "Zm9vYmFy", "media_type": "audio/webm"}

        r = TestClient(app).post(f"/api/v2/teacher/students/{sid}/sessions/parse-voice", json=AUD)
        check("1. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        r = tc.get("/api/v2/teacher/ai-consent")
        check("2. consent GET false", r.status_code == 200 and r.json()["consented"] is False, f"{r.text[:100]}")

        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions/parse-voice", json=AUD)
        check("3. rıza yok → 403 consent_required",
              r.status_code == 403 and r.json()["detail"]["code"] == "consent_required", f"status={r.status_code}")

        r = tc.post("/api/v2/teacher/ai-consent")
        check("4. consent ver → true", r.status_code == 200 and r.json()["data"]["consented"] is True, f"status={r.status_code}")

        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions/parse-voice",
                    json={"audio_base64": "", "media_type": "audio/webm"})
        check("5. boş ses → 422 audio_required",
              r.status_code == 422 and r.json()["detail"]["code"] == "audio_required", f"status={r.status_code}")

        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions/parse-voice",
                    json={"audio_base64": "Zm9v", "media_type": "video/mp4"})
        check("6. geçersiz media_type → 422",
              r.status_code == 422 and r.json()["detail"]["code"] == "invalid_media_type", f"status={r.status_code}")

        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions/parse-voice", json=AUD)
        j = r.json()
        check("7. happy → draft (agenda+mood+tags)",
              r.status_code == 200 and j.get("agenda", "").startswith("Motivasyon")
              and j.get("mood") == 3 and "matematik" in j.get("tags", []), f"status={r.status_code} {r.text[:160]}")
        with SessionLocal() as db:
            from app.models.usage import UsageKind
            cnt = db.query(UsageEvent).filter(
                UsageEvent.owner_id == seed["t_id"], UsageEvent.kind == UsageKind.AI_SESSION_VOICE).count()
        check("7b. kredi tüketildi (UsageEvent VOICE)", cnt >= 1, f"count={cnt}")

        r = tc.post(f"/api/v2/teacher/students/{seed['s2_id']}/sessions/parse-voice", json=AUD)
        check("8. başka öğr. öğrencisi → 404", r.status_code == 404, f"status={r.status_code}")

        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": "2026-05-21", "status": "done", "agenda": j["agenda"],
            "coach_note": j["coach_note"], "mood": j["mood"], "tags": j["tags"],
            "capture_source": "voice"})
        check("9. drafttan kaydet capture_source=voice",
              r.status_code == 200 and r.json()["data"]["capture_source"] == "voice",
              f"status={r.status_code} {r.json().get('data',{}).get('capture_source')}")

    finally:
        ai_capture.parse_session_voice = orig
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
