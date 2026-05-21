"""API v2 /admin/security-monitor/{alarms,abuse} smoke (D6 G4).

Senaryolar:
   1. alarms Teacher → 403
   2. alarms Anonim → 401
   3. alarms happy (rules + events + unack_count)
   4. alarms/scan happy → 200 + triggered/total_rules + invalidate
   5. alarms/{event}/ack happy → 200 + ack
   6. alarms/{event}/ack bilinmeyen → 404
   7. alarms/rules/{id}/update happy → 200 + threshold değişir
   8. alarms/rules/{id}/update bilinmeyen → 404
   9. abuse Teacher → 403
  10. abuse happy (signals + open_count + meta 5 dict)
  11. abuse kind filtre (mass_invitation)
  12. abuse/scan happy → 200 + summary
  13. abuse/{id}/resolve happy → 200 + resolved
  14. abuse/{id}/resolve bilinmeyen → 404
  15. abuse/{id}/remediate happy (mass_invitation, ok + otomatik resolve)
  16. abuse/{id}/remediate already_resolved → 400
  17. abuse/scan Teacher → 403
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    AbuseSignal,
    AlarmEvent,
    AlarmRule,
    AuditLog,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adg4{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassG4!23"

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


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
            role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.flush()
        rule = AlarmRule(
            key=f"{PFX}_rule", name=f"{PFX} Test Kuralı",
            description="smoke", threshold=5, cooldown_minutes=30,
            enabled=True, channels="email,in_app", last_value=0,
            created_at=now, updated_at=now,
        )
        db.add(rule)
        evt = AlarmEvent(
            rule_key=f"{PFX}_rule", rule_name=f"{PFX} Test Kuralı",
            value=10, threshold=5, severity="warn",
            channels_attempted="in_app", delivery_status="in_app:ok",
            triggered_at=now,
        )
        db.add(evt)
        sig_resolve = AbuseSignal(
            kind="mass_notification", severity="warn", tenant_id=None,
            count=12, window_start=now - timedelta(hours=1), window_end=now,
            detected_at=now, last_seen_at=now, details_json="{}",
        )
        sig_remediate = AbuseSignal(
            kind="mass_invitation", severity="warn",
            actor_user_id=teacher.id, count=20,
            window_start=now - timedelta(hours=1), window_end=now,
            detected_at=now, last_seen_at=now, details_json="{}",
        )
        db.add_all([sig_resolve, sig_remediate])
        db.flush()
        out = {
            "super_id": super_admin.id, "teacher_id": teacher.id,
            "rule_id": rule.id, "event_id": evt.id,
            "sig_resolve_id": sig_resolve.id, "sig_remediate_id": sig_remediate.id,
        }
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["super_id"], seed["teacher_id"]]
        db.execute(sa_delete(AbuseSignal).where(AbuseSignal.id.in_([seed["sig_resolve_id"], seed["sig_remediate_id"]])))
        db.execute(sa_delete(AlarmEvent).where(AlarmEvent.id == seed["event_id"]))
        db.execute(sa_delete(AlarmRule).where(AlarmRule.id == seed["rule_id"]))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin/security-monitor alarms+abuse (G4) smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded rule={seed['rule_id']} event={seed['event_id']}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # 1-2 guards
        r = tc.get("/api/v2/admin/security-monitor/alarms")
        check("1. alarms Teacher → 403", r.status_code == 403, f"status={r.status_code}")
        r = TestClient(app).get("/api/v2/admin/security-monitor/alarms")
        check("2. alarms Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. alarms happy
        r = sc.get("/api/v2/admin/security-monitor/alarms")
        j = r.json()
        ok = (
            r.status_code == 200
            and "rules" in j and "events" in j and isinstance(j["unack_count"], int)
            and any(rl["id"] == seed["rule_id"] for rl in j["rules"])
            and any(ev["id"] == seed["event_id"] for ev in j["events"])
        )
        check("3. alarms happy", ok, f"status={r.status_code} {r.text[:120]}")

        # 4. alarms/scan
        r = sc.post("/api/v2/admin/security-monitor/alarms/scan")
        j = r.json()
        ok = (
            r.status_code == 200 and "triggered" in j["data"]
            and "total_rules" in j["data"] and "admin:security:alarms" in j["invalidate"]
        )
        check("4. alarms/scan happy", ok, f"status={r.status_code} {r.text[:120]}")

        # 5. alarms ack
        r = sc.post(f"/api/v2/admin/security-monitor/alarms/{seed['event_id']}/ack")
        check("5. alarms ack happy", r.status_code == 200, f"status={r.status_code}")
        with SessionLocal() as db:
            e = db.get(AlarmEvent, seed["event_id"])
            check("5b. alarm acknowledged", e is not None and e.acknowledged_at is not None, "")

        # 6. ack bilinmeyen → 404
        r = sc.post("/api/v2/admin/security-monitor/alarms/99999999/ack")
        check("6. ack bilinmeyen → 404", r.status_code == 404, f"status={r.status_code}")

        # 7. rule update
        r = sc.post(f"/api/v2/admin/security-monitor/alarms/rules/{seed['rule_id']}/update",
                    json={"threshold": 42, "cooldown_minutes": 15, "enabled": False, "channels": "email"})
        check("7. rule update happy", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")
        with SessionLocal() as db:
            rl = db.get(AlarmRule, seed["rule_id"])
            check("7b. rule threshold güncellendi", rl is not None and rl.threshold == 42 and rl.enabled is False, "")

        # 8. rule update bilinmeyen → 404
        r = sc.post("/api/v2/admin/security-monitor/alarms/rules/99999999/update",
                    json={"threshold": 1, "cooldown_minutes": 1})
        check("8. rule update bilinmeyen → 404", r.status_code == 404, f"status={r.status_code}")

        # 9. abuse Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor/abuse")
        check("9. abuse Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 10. abuse happy
        r = sc.get("/api/v2/admin/security-monitor/abuse")
        j = r.json()
        ok = (
            r.status_code == 200 and "signals" in j and isinstance(j["open_count"], int)
            and set(j["meta"].keys()) == {"kind_labels", "kind_descriptions", "severity_labels", "severity_colors", "action_button_labels"}
            and "mass_invitation" in j["meta"]["kind_labels"]
        )
        check("10. abuse happy + meta", ok, f"status={r.status_code} {r.text[:120]}")

        # 11. abuse kind filtre
        r = sc.get("/api/v2/admin/security-monitor/abuse?kind=mass_invitation")
        j = r.json()
        ok = r.status_code == 200 and j["filter_kind"] == "mass_invitation" and all(s["kind"] == "mass_invitation" for s in j["signals"])
        check("11. abuse kind filtre", ok, f"status={r.status_code}")

        # 12. abuse/scan
        r = sc.post("/api/v2/admin/security-monitor/abuse/scan")
        j = r.json()
        ok = r.status_code == 200 and "summary" in j["data"] and "total" in j["data"] and "admin:security:abuse" in j["invalidate"]
        check("12. abuse/scan happy", ok, f"status={r.status_code} {r.text[:120]}")

        # 13. abuse resolve
        r = sc.post(f"/api/v2/admin/security-monitor/abuse/{seed['sig_resolve_id']}/resolve",
                    json={"note": "incelendi sorun yok"})
        check("13. abuse resolve happy", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")
        with SessionLocal() as db:
            s = db.get(AbuseSignal, seed["sig_resolve_id"])
            check("13b. signal resolved", s is not None and s.resolved_at is not None, "")

        # 14. resolve bilinmeyen → 404
        r = sc.post("/api/v2/admin/security-monitor/abuse/99999999/resolve", json={"note": ""})
        check("14. resolve bilinmeyen → 404", r.status_code == 404, f"status={r.status_code}")

        # 15. remediate happy (mass_invitation → ok, otomatik resolve)
        r = sc.post(f"/api/v2/admin/security-monitor/abuse/{seed['sig_remediate_id']}/remediate")
        j = r.json()
        ok = (
            r.status_code == 200 and j["data"]["ok"] is True
            and j["data"]["action"] == "cancel_invitations"
            and "admin:security:abuse" in j["invalidate"]
        )
        check("15. remediate happy (mass_invitation)", ok, f"status={r.status_code} {r.text[:140]}")
        with SessionLocal() as db:
            s = db.get(AbuseSignal, seed["sig_remediate_id"])
            check("15b. signal otomatik resolved", s is not None and s.resolved_at is not None, "")

        # 16. remediate already_resolved → 400
        r = sc.post(f"/api/v2/admin/security-monitor/abuse/{seed['sig_remediate_id']}/remediate")
        check("16. remediate already_resolved → 400", r.status_code == 400, f"status={r.status_code}")

        # 17. abuse/scan Teacher → 403
        r = tc.post("/api/v2/admin/security-monitor/abuse/scan")
        check("17. abuse/scan Teacher → 403", r.status_code == 403, f"status={r.status_code}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
