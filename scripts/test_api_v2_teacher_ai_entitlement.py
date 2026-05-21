"""API v2 — AI ücretli paket kapısı (entitlement) + self-serve yükseltme smoke (Paket C).

Gerçek AI çağrısı YAPILMAZ — parse_session_photo monkeypatch'lenir.

Senaryolar:
   1. free koç GET /plan → ai_premium False + solo_pro option is_upgrade True
   2. free koç ai-consent POST → ai_premium False
   3. free koç parse-photo → 403 plan_upgrade_required
   4. free koç parse-voice → 403 plan_upgrade_required
   5. free koç coaching-insight POST → 403 plan_upgrade_required
   6. trial koç parse-photo → 403 (trial de kapalı)
   7. paid koç (solo_pro) GET /plan → ai_premium True
   8. paid koç ai-consent + parse-photo (monkeypatch) → 200 (kapı geçilir)
   9. free koç POST /plan/upgrade solo_pro → ai_premium True olur, parse-photo 200
  10. kurumlu öğretmen /plan/upgrade → 403 managed_by_institution
  11. geçersiz plan → 400 invalid_plan
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
from app.models import CoachingSession, Institution, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.models.usage import UsageEvent
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
import app.services.ai_session_capture as ai_capture

PFX = f"v2ent{secrets.token_hex(3)}"
PASSWORD = "EntPass1!@xyz"
IMG = {"image_base64": "Zm9vYmFy", "media_type": "image/jpeg"}

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


def _mk_teacher(db, key, plan, institution_id=None):
    t = User(email=f"{PFX}_{key}@test.invalid", password_hash=hash_password(PASSWORD),
             full_name=f"{PFX} {key}", role=UserRole.TEACHER, is_active=True,
             plan=plan, institution_id=institution_id)
    db.add(t); db.flush()
    s = User(email=f"{PFX}_{key}_s@test.invalid", password_hash=hash_password(PASSWORD),
             full_name=f"{PFX} {key} Öğr", role=UserRole.STUDENT, is_active=True,
             grade_level=8, teacher_id=t.id, institution_id=institution_id)
    db.add(s); db.flush()
    return t, s


def _seed():
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Inst", slug=f"{PFX}-inst",
                           contact_email=f"{PFX}@test.invalid", plan="institution_free", is_active=True)
        db.add(inst); db.flush()
        free_t, free_s = _mk_teacher(db, "free", "solo_free")
        paid_t, paid_s = _mk_teacher(db, "paid", "solo_pro")
        trial_t, trial_s = _mk_teacher(db, "trial", "solo_trial")
        inst_t, inst_s = _mk_teacher(db, "inst", "institution_free", institution_id=inst.id)
        from app.services.credits import CreditOwner, get_or_create_account
        get_or_create_account(db, owner=CreditOwner.for_user(paid_t))
        get_or_create_account(db, owner=CreditOwner.for_user(free_t))  # yükseltme sonrası
        out = {
            "inst_id": inst.id,
            "free_t": free_t.id, "free_s": free_s.id,
            "paid_t": paid_t.id, "paid_s": paid_s.id,
            "trial_t": trial_t.id, "trial_s": trial_s.id,
            "inst_t": inst_t.id, "inst_s": inst_s.id,
        }
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        sids = [seed["free_s"], seed["paid_s"], seed["trial_s"], seed["inst_s"]]
        uids = [seed["free_t"], seed["paid_t"], seed["trial_t"], seed["inst_t"], *sids]
        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id.in_(sids)))
        db.execute(sa_delete(UsageEvent).where(UsageEvent.owner_id.in_(uids)))
        try:
            from app.models import CreditAccount, PlanChangeHistory, PlanOwnerType
            db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id.in_(uids)))
            db.execute(sa_delete(PlanChangeHistory).where(
                PlanChangeHistory.owner_type == PlanOwnerType.USER,
                PlanChangeHistory.owner_id.in_(uids)))
        except Exception:
            pass
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(uid_email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": uid_email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code} {r.text[:120]}")
    return c


def email(key):
    return f"{PFX}_{key}@test.invalid"


def main():
    print(f"\n=== API v2 AI entitlement smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
    seed = _seed()

    orig = ai_capture.parse_session_photo
    ai_capture.parse_session_photo = lambda img, mt, **kw: {
        "agenda": "x", "coach_note": "y", "next_change": "", "mood": 3, "tags": ["a"]}
    try:
        free = _login(email("free"))
        free_s = seed["free_s"]

        r = free.get("/api/v2/teacher/plan")
        j = r.json()
        pro = next((o for o in j.get("options", []) if o["code"] == "solo_pro"), {})
        check("1. free GET /plan → ai_premium False + pro is_upgrade",
              r.status_code == 200 and j.get("ai_premium") is False and pro.get("is_upgrade") is True,
              f"status={r.status_code} {j}")

        r = free.post("/api/v2/teacher/ai-consent")
        check("2. free ai-consent → ai_premium False",
              r.status_code == 200 and r.json()["data"]["ai_premium"] is False, f"{r.text[:120]}")

        r = free.post(f"/api/v2/teacher/students/{free_s}/sessions/parse-photo", json=IMG)
        check("3. free parse-photo → 403 plan_upgrade_required",
              r.status_code == 403 and r.json()["detail"]["code"] == "plan_upgrade_required", f"status={r.status_code}")

        r = free.post(f"/api/v2/teacher/students/{free_s}/sessions/parse-voice",
                      json={"audio_base64": "Zm9v", "media_type": "audio/webm"})
        check("4. free parse-voice → 403", r.status_code == 403 and r.json()["detail"]["code"] == "plan_upgrade_required", f"status={r.status_code}")

        r = free.post(f"/api/v2/teacher/students/{free_s}/coaching-insight")
        check("5. free coaching-insight → 403", r.status_code == 403 and r.json()["detail"]["code"] == "plan_upgrade_required", f"status={r.status_code}")

        trial = _login(email("trial"))
        r = trial.post(f"/api/v2/teacher/students/{seed['trial_s']}/sessions/parse-photo", json=IMG)
        check("6. trial parse-photo → 403", r.status_code == 403 and r.json()["detail"]["code"] == "plan_upgrade_required", f"status={r.status_code}")

        paid = _login(email("paid"))
        r = paid.get("/api/v2/teacher/plan")
        check("7. paid GET /plan → ai_premium True", r.status_code == 200 and r.json().get("ai_premium") is True, f"{r.text[:120]}")

        paid.post("/api/v2/teacher/ai-consent")
        r = paid.post(f"/api/v2/teacher/students/{seed['paid_s']}/sessions/parse-photo", json=IMG)
        check("8. paid parse-photo → 200 (kapı geçildi)", r.status_code == 200 and r.json().get("agenda") == "x", f"status={r.status_code} {r.text[:120]}")

        # 9. free yükselt → açılır
        r = free.post("/api/v2/teacher/plan/upgrade", json={"plan": "solo_pro"})
        check("9a. free upgrade solo_pro → ai_premium True",
              r.status_code == 200 and r.json()["data"]["ai_premium"] is True, f"status={r.status_code} {r.text[:140]}")
        r = free.post(f"/api/v2/teacher/students/{free_s}/sessions/parse-photo", json=IMG)
        check("9b. yükseltme sonrası parse-photo → 200", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")

        inst = _login(email("inst"))
        r = inst.post("/api/v2/teacher/plan/upgrade", json={"plan": "solo_pro"})
        check("10. kurumlu öğretmen upgrade → 403 managed_by_institution",
              r.status_code == 403 and r.json()["detail"]["code"] == "managed_by_institution", f"status={r.status_code}")

        r = paid.post("/api/v2/teacher/plan/upgrade", json={"plan": "solo_free"})
        check("11. geçersiz hedef → 400 invalid_plan",
              r.status_code == 400 and r.json()["detail"]["code"] == "invalid_plan", f"status={r.status_code}")

    finally:
        ai_capture.parse_session_photo = orig
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
