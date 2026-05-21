"""API v2 /admin/security-monitor/activity (Aktivite Kamerası) smoke (D6 G2b).

Senaryolar:
   1. Teacher → 403 (panel)
   2. Anonim → 401 (panel)
   3. panel happy segment=all (tüm anahtarlar + critical_summary + solo_special)
   4. panel segment=institution (solo_special yok)
   5. panel segment=solo (solo_special var)
   6. panel geçersiz segment → 'all'a düşer
   7. panel heatmap matrix str-key şekli (24 saat × 7 gün)
   8. panel owner-pattern: heartbeats owner_type alanı
   9. active-users drill happy (window=dau)
  10. active-users drill role filtresi (teacher)
  11. active-users drill window=wau label
  12. active-users Teacher → 403
  13. heatmap drill happy (institution_id)
  14. heatmap drill silinmiş kurum → boş matrix (patterns dahil)
  15. heatmap Teacher → 403
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
    AuditAction,
    AuditLog,
    Institution,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adg2b{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
SOLO_EMAIL = f"{PFX}_solo@test.invalid"
PASSWORD = "TestPassG2b!23"

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
        inst = Institution(
            name=f"{PFX} Inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="free", is_active=True,
        )
        db.add(inst)
        db.flush()
        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
            role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
            role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        solo = User(
            email=SOLO_EMAIL, password_hash=pwd, full_name=f"{PFX} Solo",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher, solo])
        db.flush()
        # Birkaç login audit — DAU/heatmap için
        for u in (super_admin, teacher, solo):
            db.add(AuditLog(
                actor_id=u.id, action=AuditAction.LOGIN_SUCCESS,
                created_at=now, ip_address="127.0.0.1",
            ))
        db.flush()
        out = {
            "inst_id": inst.id, "super_id": super_admin.id,
            "teacher_id": teacher.id, "solo_id": solo.id,
        }
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["super_id"], seed["teacher_id"], seed["solo_id"]]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


PANEL_KEYS = {
    "generated_at", "segment", "totals", "per_tenant", "heatmap",
    "dau_trend_14d", "silent_tenants_7d", "role_breakdown", "heartbeats",
    "heartbeat_summary", "wow", "stickiness", "stickiness_trend_30d",
    "week1", "day30", "resurrected", "decay_rates", "plan_activity",
    "session_duration", "teacher_student_ratios", "power_users",
    "feature_popularity", "feature_matrix", "onboarding", "plan_benchmark",
    "champions", "action_suggestions", "critical_summary",
}


def main() -> int:
    print(f"\n=== API v2 /admin/security-monitor/activity (G2b) smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded inst={seed['inst_id']}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # 1. Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor/activity")
        check("1. panel Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 2. Anonim → 401
        r = TestClient(app).get("/api/v2/admin/security-monitor/activity")
        check("2. panel Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. panel happy segment=all
        r = sc.get("/api/v2/admin/security-monitor/activity?segment=all")
        j = r.json()
        ok = (
            r.status_code == 200
            and PANEL_KEYS.issubset(set(j.keys()))
            and j["segment"] == "all"
            and j.get("solo_special") is not None
            and set(j["totals"].keys()) == {"dau", "wau", "mau"}
            and "stickiness_pct" in j["critical_summary"]
        )
        check("3. panel happy segment=all", ok, f"status={r.status_code} missing={PANEL_KEYS - set(j.keys()) if r.status_code==200 else r.text[:120]}")

        # 4. segment=institution → solo_special yok
        r = sc.get("/api/v2/admin/security-monitor/activity?segment=institution")
        j = r.json()
        check("4. segment=institution (solo_special None)",
              r.status_code == 200 and j["segment"] == "institution" and j.get("solo_special") is None,
              f"status={r.status_code}")

        # 5. segment=solo → solo_special var
        r = sc.get("/api/v2/admin/security-monitor/activity?segment=solo")
        j = r.json()
        ok = (
            r.status_code == 200 and j["segment"] == "solo"
            and j.get("solo_special") is not None
            and "parent_outreach" in j["solo_special"]
            and "discipline" in j["solo_special"]
            and "consistency" in j["solo_special"]
        )
        check("5. segment=solo (solo_special dolu)", ok, f"status={r.status_code}")

        # 6. geçersiz segment → all
        r = sc.get("/api/v2/admin/security-monitor/activity?segment=xyz")
        check("6. geçersiz segment → all", r.status_code == 200 and r.json()["segment"] == "all",
              f"status={r.status_code}")

        # 7. heatmap matrix str-key 24×7
        r = sc.get("/api/v2/admin/security-monitor/activity?segment=all")
        hm = r.json()["heatmap"]
        ok = (
            len(hm["matrix"]) == 24
            and all(len(hm["matrix"][h]) == 7 for h in hm["matrix"])
            and "0" in hm["matrix"] and "23" in hm["matrix"]
            and len(hm["day_labels"]) == 7
        )
        check("7. heatmap matrix 24×7 str-key", ok, f"keys={len(hm['matrix'])}")

        # 8. owner-pattern heartbeats
        hbs = r.json()["heartbeats"]
        ok = all("owner_type" in h and "detail_url" in h for h in hbs) if hbs else True
        check("8. heartbeats owner-pattern", ok, f"n={len(hbs)}")

        # 9. active-users drill happy
        r = sc.get("/api/v2/admin/security-monitor/activity/active-users?window=dau")
        j = r.json()
        ok = (
            r.status_code == 200 and j["window"] == "dau"
            and j["role_label"] == "Tüm roller" and "rows" in j
            and any(row["user_id"] == seed["super_id"] for row in j["rows"])
        )
        check("9. active-users drill dau happy", ok, f"status={r.status_code} {r.text[:120]}")

        # 10. active-users role filtresi
        r = sc.get("/api/v2/admin/security-monitor/activity/active-users?window=mau&role=teacher")
        j = r.json()
        ok = (
            r.status_code == 200 and j["role"] == "teacher"
            and j["role_label"] == "Öğretmen"
            and all(row["role"] == "teacher" for row in j["rows"])
        )
        check("10. active-users role=teacher filtre", ok, f"status={r.status_code}")

        # 11. active-users window=wau label
        r = sc.get("/api/v2/admin/security-monitor/activity/active-users?window=wau")
        check("11. active-users wau label", r.status_code == 200 and r.json()["window_label"] == "son 7 gün",
              f"status={r.status_code}")

        # 12. active-users Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor/activity/active-users?window=dau")
        check("12. active-users Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 13. heatmap drill happy
        r = sc.get(f"/api/v2/admin/security-monitor/activity/heatmap?institution_id={seed['inst_id']}")
        j = r.json()
        ok = (
            r.status_code == 200 and j["institution_id"] == seed["inst_id"]
            and len(j["matrix"]) == 24 and "patterns" in j
            and j["total"] >= 1
        )
        check("13. heatmap drill happy", ok, f"status={r.status_code} {r.text[:120]}")

        # 14. heatmap silinmiş kurum → boş
        r = sc.get("/api/v2/admin/security-monitor/activity/heatmap?institution_id=99999999")
        j = r.json()
        ok = (
            r.status_code == 200 and j["total"] == 0
            and len(j["matrix"]) == 24 and "patterns" in j
        )
        check("14. heatmap silinmiş kurum → boş matrix", ok, f"status={r.status_code}")

        # 15. heatmap Teacher → 403
        r = tc.get(f"/api/v2/admin/security-monitor/activity/heatmap?institution_id={seed['inst_id']}")
        check("15. heatmap Teacher → 403", r.status_code == 403, f"status={r.status_code}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
