"""API v2 /admin/security-monitor (Güvenlik Kamarası — Genel Bakış + Bütünlük +
Sistem + Bildirim) smoke (D6 G2a).

Senaryolar:
   1. Teacher → 403 (overview)
   2. Anonim → 401 (overview)
   3. overview happy (summary 6 alan + role_counts + listeler + attention + sayımlar)
   4. overview attention shape (by_severity 3 anahtar + items)
   5. integrity Teacher → 403
   6. integrity happy (migration/db_file/orphans/kvkk_sla/cron_drift)
   7. system Teacher → 403
   8. system happy (summary 4 alan + error_groups + endpoint_top + slow_requests)
   9. system resolve seed edilen hata → 200 + invalidate
  10. system resolve aynı hata tekrar → 200 (idempotent, zaten çözülü)
  11. system resolve bilinmeyen id → 404
  12. notifications Teacher → 403
  13. notifications happy (summary_24h/7d + matrisler + trend + failures)
  14. notifications matris şekli (channel rows + statuses + matrix)
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

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    ErrorEvent,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adg2a{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassG2a!23"

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
        err = ErrorEvent(
            signature=f"{PFX}-sig", endpoint=f"/test/{PFX}", method="GET",
            status_code=500, exception_type="ValueError",
            exception_message="boom", count=3,
            first_seen_at=now, last_seen_at=now,
        )
        db.add(err)
        db.flush()
        out = {"super_id": super_admin.id, "teacher_id": teacher.id, "err_id": err.id}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(ErrorEvent).where(ErrorEvent.id == seed["err_id"]))
        uids = [seed["super_id"], seed["teacher_id"]]
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
    print(f"\n=== API v2 /admin/security-monitor (G2a) smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded err={seed['err_id']}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # 1. Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 2. Anonim → 401
        r = TestClient(app).get("/api/v2/admin/security-monitor")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. overview happy
        r = sc.get("/api/v2/admin/security-monitor")
        j = r.json()
        ok = (
            r.status_code == 200
            and set(j["summary"].keys()) == {
                "active_sessions", "blocked_ips", "watched_ips",
                "failed_24h", "critical_24h", "super_admin_logins_24h",
            }
            and "role_counts" in j and "active_sessions" in j
            and "suspicious_ips" in j and "failed_login_buckets" in j
            and "critical_audits" in j and "super_admin_logins" in j
            and "active_impersonations" in j and "attention" in j
            and isinstance(j["abuse_open_count"], int)
            and isinstance(j["unack_alarm_count"], int)
            and "system_error_summary" in j
        )
        check("3. overview happy", ok, f"status={r.status_code} {r.text[:160]}")

        # 4. overview attention shape
        att = j.get("attention", {})
        ok = (
            set(att.get("by_severity", {}).keys()) == {"critical", "warn", "info"}
            and "items" in att and "total" in att
            and "top_severity" in att and "is_clean" in att
        )
        check("4. attention shape", ok, f"att={att}")

        # 5. integrity Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor/integrity")
        check("5. integrity Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 6. integrity happy
        r = sc.get("/api/v2/admin/security-monitor/integrity")
        j = r.json()
        ok = (
            r.status_code == 200
            and "migration" in j and "status" in j["migration"]
            and "db_file" in j and "level" in j["db_file"]
            and "orphans" in j and "total_findings" in j["orphans"]
            and "kvkk_sla" in j and "sla_days" in j["kvkk_sla"]
            and "cron_drift" in j and "summary" in j["cron_drift"]
        )
        check("6. integrity happy", ok, f"status={r.status_code} {r.text[:160]}")

        # 7. system Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor/system")
        check("7. system Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 8. system happy
        r = sc.get("/api/v2/admin/security-monitor/system")
        j = r.json()
        ok = (
            r.status_code == 200
            and set(j["summary"].keys()) == {
                "open_groups", "new_groups_24h", "total_events_24h", "window_hours",
            }
            and "error_groups" in j and "endpoint_top" in j and "slow_requests" in j
            and any(g["id"] == seed["err_id"] for g in j["error_groups"])
        )
        check("8. system happy", ok, f"status={r.status_code} {r.text[:160]}")

        # 9. resolve seed edilen hata → 200 + invalidate
        r = sc.post(f"/api/v2/admin/security-monitor/system/{seed['err_id']}/resolve",
                    json={"note": "test çözüm"})
        j = r.json()
        ok = (
            r.status_code == 200
            and j["data"]["error_id"] == seed["err_id"]
            and "admin:security:system" in j["invalidate"]
        )
        check("9. resolve happy + invalidate", ok, f"status={r.status_code} {r.text[:160]}")

        # 10. resolve aynı hata tekrar → 200 (zaten çözülü, no-op döner ama row var)
        r = sc.post(f"/api/v2/admin/security-monitor/system/{seed['err_id']}/resolve",
                    json={"note": ""})
        check("10. resolve idempotent → 200", r.status_code == 200, f"status={r.status_code}")

        # 11. resolve bilinmeyen id → 404
        r = sc.post("/api/v2/admin/security-monitor/system/99999999/resolve",
                    json={"note": ""})
        check("11. resolve bilinmeyen → 404", r.status_code == 404, f"status={r.status_code}")

        # 12. notifications Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor/notifications")
        check("12. notifications Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 13. notifications happy
        r = sc.get("/api/v2/admin/security-monitor/notifications")
        j = r.json()
        ok = (
            r.status_code == 200
            and "summary_24h" in j and "success_pct" in j["summary_24h"]
            and "summary_7d" in j
            and "channel_matrix_24h" in j and "kind_matrix_24h" in j
            and "suppress_distribution_24h" in j
            and len(j["daily_trend_7d"]) == 7
            and "recent_failures_24h" in j
        )
        check("13. notifications happy", ok, f"status={r.status_code} {r.text[:160]}")

        # 14. notifications matris şekli
        ch = j["channel_matrix_24h"]
        ok = (
            "rows" in ch and "statuses" in ch and "matrix" in ch
            and "rollups" in ch and ch["window_hours"] == 24
        )
        check("14. matris şekli (rows+statuses+matrix)", ok, f"ch_keys={list(ch.keys())}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
