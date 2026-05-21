"""API v2 /teacher AI koçluk içgörüsü smoke (KS4 — cache'li).

Gerçek Claude çağrısı YAPILMAZ — generate_coaching_insight monkeypatch'lenir.

KREDİ GÜVENLİĞİ vurgusu: POST üretir + DB'ye cache'ler + kredi düşer; GET cache'den
okur + KREDİ DÜŞMEZ; yeni seans → is_stale True; POST yenile → kredi tekrar düşer.

Senaryolar:
   1. Anonim POST → 401
   2. GET üretilmemiş → insight null (kredi yok)
   3. POST rıza yok → 403 consent_required
   4. consent ver → true
   5. POST seans yok → 422 not_enough_data
   6. seans ekle + POST üret → insight + based_on=1 + is_stale False; kredi=1
   7. GET → cache döner, KREDİ DÜŞMEZ (hâlâ 1)
   8. yeni seans ekle → GET is_stale True
   9. POST yenile → kredi=2 + is_stale False
  10. başka öğretmenin öğrencisi → 404 (GET + POST)
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
from app.models import CoachingInsight, CoachingSession, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.models.usage import UsageEvent
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
import app.services.ai_coaching_insight as ai_insight

PFX = f"v2tcin{secrets.token_hex(3)}"
T_EMAIL = f"{PFX}_t@test.invalid"
T2_EMAIL = f"{PFX}_t2@test.invalid"
PASSWORD = "InsPass1!@xyz"

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
        from app.services.credits import CreditOwner, get_or_create_account
        get_or_create_account(db, owner=CreditOwner.for_user(t))
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        sids = [seed["s_id"], seed["s2_id"]]
        uids = [seed["t_id"], seed["t2_id"], *sids]
        db.execute(sa_delete(CoachingInsight).where(CoachingInsight.student_id.in_(sids)))
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
    print(f"\n=== API v2 /teacher coaching-insight smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
    seed = _seed()
    sid = seed["s_id"]

    orig = ai_insight.generate_coaching_insight
    ai_insight.generate_coaching_insight = lambda name, sessions, academic, **kw: {
        "summary": "Öğrenci son seanslarda istikrar kazandı ama matematik kaygısı sürüyor.",
        "agenda_suggestions": ["Matematik kaygısını konuş", "Hafta sonu planını gözden geçir"],
        "psychological_tips": ["Küçük başarıları kutla", "Baskı yerine merak dilini kullan"],
        "watch_outs": ["Uyku düzensizliği işaretleri"],
    }
    def credit_count():
        with SessionLocal() as db:
            from app.models.usage import UsageKind
            return db.query(UsageEvent).filter(
                UsageEvent.owner_id == seed["t_id"],
                UsageEvent.kind == UsageKind.AI_COACHING_INSIGHT).count()

    try:
        tc = _login(T_EMAIL)
        url = f"/api/v2/teacher/students/{sid}/coaching-insight"

        r = TestClient(app).post(url)
        check("1. Anonim POST → 401", r.status_code == 401, f"status={r.status_code}")

        r = tc.get(url)
        check("2. GET üretilmemiş → insight null (kredi yok)",
              r.status_code == 200 and r.json()["insight"] is None and credit_count() == 0,
              f"status={r.status_code} {r.text[:120]}")

        r = tc.post(url)
        check("3. rıza yok → 403 consent_required",
              r.status_code == 403 and r.json()["detail"]["code"] == "consent_required", f"status={r.status_code}")

        r = tc.post("/api/v2/teacher/ai-consent")
        check("4. consent ver → true", r.status_code == 200 and r.json()["data"]["consented"] is True, f"status={r.status_code}")

        r = tc.post(url)
        check("5. seans yok → 422 not_enough_data",
              r.status_code == 422 and r.json()["detail"]["code"] == "not_enough_data", f"status={r.status_code}")

        # Seans ekle
        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": "2026-05-20", "status": "done",
            "agenda": "Genel değerlendirme", "coach_note": "İyi gidiyor", "mood": 3, "tags": ["motivasyon"]})
        if r.status_code != 200:
            raise RuntimeError(f"seans create fail {r.status_code} {r.text[:120]}")

        r = tc.post(url)
        j = r.json()
        ins = j.get("insight") or {}
        check("6. POST üret → içgörü + based_on=1 + is_stale False",
              r.status_code == 200 and ins.get("summary", "").startswith("Öğrenci")
              and len(ins.get("agenda_suggestions", [])) == 2
              and ins.get("based_on_sessions") == 1 and j.get("is_stale") is False
              and credit_count() == 1, f"status={r.status_code} count={credit_count()} {r.text[:160]}")

        r = tc.get(url)
        j = r.json()
        check("7. GET → cache döner, KREDİ DÜŞMEZ (hâlâ 1)",
              r.status_code == 200 and (j.get("insight") or {}).get("summary", "").startswith("Öğrenci")
              and credit_count() == 1, f"status={r.status_code} count={credit_count()}")

        # Yeni seans ekle → cache bayatlar
        r = tc.post(f"/api/v2/teacher/students/{sid}/sessions", json={
            "session_date": "2026-05-21", "status": "done", "agenda": "Takip"})
        if r.status_code != 200:
            raise RuntimeError(f"seans2 create fail {r.status_code} {r.text[:120]}")
        r = tc.get(url)
        check("8. yeni seans → GET is_stale True (kredi hâlâ 1)",
              r.status_code == 200 and r.json().get("is_stale") is True and credit_count() == 1,
              f"status={r.status_code} stale={r.json().get('is_stale')} count={credit_count()}")

        r = tc.post(url)
        j = r.json()
        check("9. POST yenile → kredi=2 + is_stale False + based_on=2",
              r.status_code == 200 and j.get("is_stale") is False
              and (j.get("insight") or {}).get("based_on_sessions") == 2
              and credit_count() == 2, f"status={r.status_code} count={credit_count()}")

        r = tc.post(f"/api/v2/teacher/students/{seed['s2_id']}/coaching-insight")
        check("10a. başka öğr. POST → 404", r.status_code == 404, f"status={r.status_code}")
        r = tc.get(f"/api/v2/teacher/students/{seed['s2_id']}/coaching-insight")
        check("10b. başka öğr. GET → 404", r.status_code == 404, f"status={r.status_code}")

    finally:
        ai_insight.generate_coaching_insight = orig
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
