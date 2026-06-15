"""Dönüşüm döngüsü smoke — üye olan oturumun TIKLADIĞI kartlara bandit ödülü.

#1 (dinamik gösterim): bandit anasayfayı "tıklamaya" değil "üyeliğe" göre
öğrensin → record_signup_attribution, oturumun cta_click/demo_click yaptığı
kartlara CONVERSION_REWARD verir.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    AuditLog,
    FeatureBanditState,
    FeatureCardEvent,
    SignupAttribution,
    User,
    UserRole,
)
from app.services import bandit, conversion_service
from app.services.security import hash_password
from app.services.telemetry import SESSION_COOKIE_NAME

PFX = f"convrew_{secrets.token_hex(3)}"
SESSION = f"{PFX}_s1"
SESSION_NOCLICK = f"{PFX}_s2"
CARD_A = 999201
CARD_B = 999202

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


class _FakeReq:
    def __init__(self, cookies):
        self.cookies = cookies


def _ev(session, etype, card):
    return FeatureCardEvent(
        card_id=card, card_slug=f"{PFX}c", event_type=etype,
        session_id=session, created_at=datetime.now(timezone.utc),
    )


def _cleanup(uid=None):
    with SessionLocal() as db:
        db.execute(sa_delete(FeatureBanditState).where(FeatureBanditState.card_id.in_([CARD_A, CARD_B])))
        db.execute(sa_delete(FeatureCardEvent).where(FeatureCardEvent.session_id.in_([SESSION, SESSION_NOCLICK])))
        db.execute(sa_delete(SignupAttribution).where(SignupAttribution.session_id == SESSION))
        if uid:
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id == uid))
            db.execute(sa_delete(SignupAttribution).where(SignupAttribution.user_id == uid))
            db.execute(sa_delete(User).where(User.id == uid))
        db.commit()


def main() -> int:
    print(f"\n=== bandit conversion reward smoke — {PFX} ===\n")
    _cleanup()
    uid = None
    try:
        with SessionLocal() as db:
            # cta_click on A, demo_click on B, view on A (view sayılmaz)
            db.add_all([
                _ev(SESSION, "cta_click", CARD_A),
                _ev(SESSION, "demo_click", CARD_B),
                _ev(SESSION, "view", CARD_A),
            ])
            db.commit()

            n = bandit.reward_conversion_for_session(db, session_id=SESSION)
            check("1. tıklanan 2 kart ödüllendi (cta+demo; view sayılmaz)", n == 2, f"n={n}")

            ra = bandit.ensure_state(db, CARD_A).reward_count
            rb = bandit.ensure_state(db, CARD_B).reward_count
            check("2. CARD_A bandit reward_count >= 1", ra >= 1, f"ra={ra}")
            check("3. CARD_B bandit reward_count >= 1", rb >= 1, f"rb={rb}")

            # tıklamasız oturum → 0
            db.add_all([_ev(SESSION_NOCLICK, "view", CARD_A), _ev(SESSION_NOCLICK, "impression", CARD_A)])
            db.commit()
            n2 = bandit.reward_conversion_for_session(db, session_id=SESSION_NOCLICK)
            check("4. tıklamasız oturum → 0 ödül", n2 == 0, f"n2={n2}")

            # entegrasyon: record_signup_attribution ödül verir
            before = bandit.ensure_state(db, CARD_A).reward_count
            now = datetime.now(timezone.utc)
            user = User(
                email=f"{PFX}@test.invalid", password_hash=hash_password("X!23pass"),
                full_name=f"{PFX} U", role=UserRole.TEACHER, institution_id=None,
                is_active=True, password_changed_at=now, must_change_password=False,
            )
            db.add(user)
            db.commit()
            uid = user.id
            conversion_service.record_signup_attribution(
                db, user=user, request=_FakeReq({SESSION_COOKIE_NAME: SESSION}),
                signup_role="teacher",
            )
            after = bandit.ensure_state(db, CARD_A).reward_count
            check("5. record_signup_attribution → CARD_A ödülü arttı",
                  after > before, f"before={before} after={after}")
    finally:
        _cleanup(uid)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
