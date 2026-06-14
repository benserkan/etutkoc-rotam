"""API v2 dönüşüm (conversion) hunisi smoke.

Dev DB paylaşımlı (gerçek landing telemetri verisi olabilir) → mutlak sayım
yerine BASELINE + DELTA ölçülür; varyant slug'ları PFX ile BENZERSİZ (izolasyon).

Senaryolar:
   1. attribution servisi: cookie varsa → source=landing + session_id + variant
   2. attribution idempotent: ikinci çağrı yeni satır YARATMAZ
   3. attribution cookie yoksa → source=direct, session_id None
   4. super admin GET /admin/conversion → 200 + funnel
   5. funnel delta: visitors +5 / engaged +3 / demo +2
   6. funnel delta: signups_landing +2 / direct +1 / paid_landing +1
   7. oran self-consistency (rate_visitor_signup = signups_landing/visitors)
   8. varyant kırılımı (benzersiz slug): ctrl 2/1/1 · test 2/1/0
   9. teacher GET → 403
  10. anonim GET → 401
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete
from sqlalchemy import or_

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    FeatureCardEvent,
    SignupAttribution,
    User,
    UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.services import conversion_service
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.services.telemetry import SESSION_COOKIE_NAME

PFX = f"v2conv_{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassConv!23"

S_CTRL1 = f"{PFX}_sctrl1"
S_CTRL2 = f"{PFX}_sctrl2"
S_TEST1 = f"{PFX}_stest1"
S_TEST2 = f"{PFX}_stest2"
S_NONE = f"{PFX}_snone"
ALL_SESSIONS = [S_CTRL1, S_CTRL2, S_TEST1, S_TEST2, S_NONE]

# Benzersiz varyant slug'ları (gerçek A/B verisiyle çakışmasın)
V_CTRL = f"{PFX}c"
V_TEST = f"{PFX}t"

passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


class _FakeReq:
    def __init__(self, cookies: dict[str, str]):
        self.cookies = cookies


def _ev(session_id: str, event_type: str, variant: str | None) -> FeatureCardEvent:
    return FeatureCardEvent(
        card_id=999000,  # SQLite FK kapalı (dev) — sahte kart id
        card_slug=f"{PFX}_card",
        event_type=event_type,
        session_id=session_id,
        variant_slug=variant,
        created_at=datetime.now(timezone.utc),
    )


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        rows = {
            "super": User(email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
                          role=UserRole.SUPER_ADMIN, is_active=True,
                          password_changed_at=now, must_change_password=False),
            "teacher": User(email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
                            role=UserRole.TEACHER, institution_id=None, is_active=True,
                            password_changed_at=now, must_change_password=False),
            "conv1": User(email=f"{PFX}_conv1@test.invalid", password_hash=pwd, full_name=f"{PFX} Conv1",
                          role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_pro",
                          password_changed_at=now, must_change_password=False),
            "conv2": User(email=f"{PFX}_conv2@test.invalid", password_hash=pwd, full_name=f"{PFX} Conv2",
                          role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_free",
                          password_changed_at=now, must_change_password=False),
            "conv3": User(email=f"{PFX}_conv3@test.invalid", password_hash=pwd, full_name=f"{PFX} Conv3",
                          role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_free",
                          password_changed_at=now, must_change_password=False),
            "attr": User(email=f"{PFX}_attr@test.invalid", password_hash=pwd, full_name=f"{PFX} Attr",
                         role=UserRole.TEACHER, institution_id=None, is_active=True,
                         password_changed_at=now, must_change_password=False),
            "attr2": User(email=f"{PFX}_attr2@test.invalid", password_hash=pwd, full_name=f"{PFX} Attr2",
                          role=UserRole.TEACHER, institution_id=None, is_active=True,
                          password_changed_at=now, must_change_password=False),
        }
        db.add_all(list(rows.values()))
        db.commit()
        return {k: u.id for k, u in rows.items()}


def _insert_funnel_data(seed: dict) -> None:
    """5 session event + conv1-3 attribution (baseline'dan SONRA çağrılır)."""
    with SessionLocal() as db:
        db.add_all([
            _ev(S_CTRL1, "impression", V_CTRL),
            _ev(S_CTRL1, "view", V_CTRL),
            _ev(S_CTRL1, "demo_click", V_CTRL),
            _ev(S_CTRL2, "impression", V_CTRL),
            _ev(S_CTRL2, "cta_click", V_CTRL),  # karta tıkladı → signup
            _ev(S_TEST1, "impression", V_TEST),
            _ev(S_TEST1, "view", V_TEST),
            _ev(S_TEST2, "impression", V_TEST),
            _ev(S_TEST2, "demo_click", V_TEST),
            _ev(S_NONE, "impression", None),
        ])
        db.add_all([
            SignupAttribution(user_id=seed["conv1"], session_id=S_CTRL1, variant_slug=V_CTRL,
                              signup_role="teacher", source="landing"),
            SignupAttribution(user_id=seed["conv2"], session_id=S_TEST1, variant_slug=V_TEST,
                              signup_role="teacher", source="landing"),
            SignupAttribution(user_id=seed["conv3"], session_id=None, variant_slug=None,
                              signup_role="teacher", source="direct"),
        ])
        db.commit()


def _cleanup(seed: dict) -> None:
    ids = list(seed.values())
    with SessionLocal() as db:
        db.execute(sa_delete(SignupAttribution).where(SignupAttribution.user_id.in_(ids)))
        db.execute(sa_delete(FeatureCardEvent).where(
            or_(FeatureCardEvent.session_id.in_(ALL_SESSIONS),
                FeatureCardEvent.card_slug == f"{PFX}_card")
        ))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def _funnel(client: TestClient) -> dict:
    r = client.get("/api/v2/admin/conversion", params={"days": 30})
    return r.json().get("funnel", {}) if r.status_code == 200 else {}


def main() -> int:
    print(f"\n=== API v2 conversion smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        # 1-3. attribution servisi (doğrudan) — attr(landing) + attr2(direct)
        with SessionLocal() as db:
            attr_user = db.query(User).filter(User.id == seed["attr"]).first()
            row = conversion_service.record_signup_attribution(
                db, user=attr_user, request=_FakeReq({SESSION_COOKIE_NAME: S_CTRL2}),
                signup_role="teacher")
            check("1. cookie varsa → source=landing + session + variant",
                  row is not None and row.source == "landing" and row.session_id == S_CTRL2, f"row={row}")
            row2 = conversion_service.record_signup_attribution(
                db, user=attr_user, request=_FakeReq({SESSION_COOKIE_NAME: "BASKA"}),
                signup_role="teacher")
            n = db.query(SignupAttribution).filter(SignupAttribution.user_id == seed["attr"]).count()
            check("2. idempotent — ikinci çağrı yeni satır yaratmaz",
                  row2 is not None and row2.session_id == S_CTRL2 and n == 1, f"n={n}")
            attr2_user = db.query(User).filter(User.id == seed["attr2"]).first()
            row3 = conversion_service.record_signup_attribution(
                db, user=attr2_user, request=_FakeReq({}), signup_role="teacher")
            check("3. cookie yoksa → source=direct, session None",
                  row3 is not None and row3.source == "direct" and row3.session_id is None, f"row={row3}")

        super_client = _login(SUPER_EMAIL)
        teacher_client = _login(TEACHER_EMAIL)

        # 4. super admin GET (baseline)
        r = super_client.get("/api/v2/admin/conversion", params={"days": 30})
        check("4. super GET /admin/conversion → 200 + funnel",
              r.status_code == 200 and isinstance(r.json().get("funnel"), dict),
              f"status={r.status_code}")
        base = _funnel(super_client)

        # huni verisini ekle (baseline'dan sonra) → delta ölç
        _insert_funnel_data(seed)
        after = _funnel(super_client)

        def d(k: str) -> int:
            return int(after.get(k, 0)) - int(base.get(k, 0))

        # 5. visitors/engaged/clicked/demo delta
        #    engaged (view/demo_click/cta_click): S_CTRL1,S_CTRL2,S_TEST1,S_TEST2 = 4
        #    clicked (cta_click/demo_click): S_CTRL1,S_CTRL2,S_TEST2 = 3
        #    demo (demo_click): S_CTRL1,S_TEST2 = 2
        check("5. delta visitors=5 engaged=4 clicked=3 demo=2",
              d("visitors") == 5 and d("engaged") == 4 and d("clicked") == 3 and d("demo") == 2,
              f"v={d('visitors')} e={d('engaged')} c={d('clicked')} demo={d('demo')}")

        # 6. signups + paid delta
        check("6. delta signups_landing=2 direct=1 paid_landing=1",
              d("signups_landing") == 2 and d("signups_direct") == 1 and d("paid_landing") == 1,
              f"dL={d('signups_landing')} dD={d('signups_direct')} dPaid={d('paid_landing')}")

        # 7. oran self-consistency
        sl = int(after.get("signups_landing", 0))
        vis = int(after.get("visitors", 0))
        exp_rate = round(sl / vis * 100, 1) if vis else 0.0
        check("7. rate_visitor_signup self-consistency",
              abs(after.get("rate_visitor_signup", -1) - exp_rate) < 0.05,
              f"got={after.get('rate_visitor_signup')} exp={exp_rate}")

        # 8. varyant kırılımı (benzersiz slug → izole)
        rj = super_client.get("/api/v2/admin/conversion", params={"days": 30}).json()
        variants = {v["slug"]: v for v in rj.get("variants", [])}
        ctrl = variants.get(V_CTRL, {})
        test = variants.get(V_TEST, {})
        check("8. varyant ctrl 2/1/1 · test 2/1/0",
              ctrl.get("sessions") == 2 and ctrl.get("signups") == 1 and ctrl.get("paid") == 1
              and test.get("sessions") == 2 and test.get("signups") == 1 and test.get("paid") == 0,
              f"ctrl={ctrl} test={test}")

        # 9. teacher → 403
        r = teacher_client.get("/api/v2/admin/conversion")
        check("9. teacher GET → 403", r.status_code == 403, f"status={r.status_code}")

        # 10. anonim → 401
        r = TestClient(app).get("/api/v2/admin/conversion")
        check("10. anonim GET → 401", r.status_code == 401, f"status={r.status_code}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for fl in failed:
        print(f"  FAIL: {fl}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
