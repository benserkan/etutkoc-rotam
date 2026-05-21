"""API v2 /admin/audit + /kvkk + /system-health + /announcements smoke (D6 P4).

Senaryolar:
   1. /audit list happy (pagination + total + per_page=50)
   2. /audit ?action= filtre
   3. /audit ?start_date=&end_date= filtre
   4. /audit ?page=999 boş (out of range)
   5. /audit ?actor_id= filtre
   6. /system-health happy (3 alt-bileşen + overall_health)
   7. /announcements list happy + severities + audiences
   8. /announcements POST create happy
   9. /announcements POST boş message → 400 message_required
  10. /announcements POST invalid datetime → 400 invalid_datetime
  11. /announcements/{id}/delete happy
  12. /announcements/{id}/delete 404
  13. /kvkk dashboard happy (summary + inventory)
  14. /kvkk/requests/{id}/apply 404
  15. /kvkk/requests/{id}/reject 404
  16. /kvkk/requests/{id}/apply (export tipi) → 400 only_delete_can_be_applied
  17. Teacher rolü /audit → 403 role_required
  18. Anonim → 401
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
    DataRequestKind,
    DataRequestStatus,
    DataSubjectRequest,
    SystemAnnouncement,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adp4{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassP4!23"

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
            email=SUPER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Super", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.flush()
        # Bir export tipi KVKK talep — apply 400 testi için
        kvkk_req = DataSubjectRequest(
            kind=DataRequestKind.EXPORT,
            status=DataRequestStatus.PENDING,
            requester_user_id=teacher.id,
            target_user_id=teacher.id,
            reason="Test smoke export",
        )
        db.add(kvkk_req)
        db.commit()
        return {
            "super_id": super_admin.id,
            "teacher_id": teacher.id,
            "kvkk_export_id": kvkk_req.id,
        }


def _cleanup(seed: dict, extra_ann_ids: list[int]) -> None:
    with SessionLocal() as db:
        ids = [seed["super_id"], seed["teacher_id"]]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
        db.execute(sa_delete(DataSubjectRequest).where(
            DataSubjectRequest.id == seed["kvkk_export_id"]
        ))
        if extra_ann_ids:
            db.execute(sa_delete(SystemAnnouncement).where(
                SystemAnnouncement.id.in_(extra_ann_ids)
            ))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin P4 smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(
        f"  seeded super={seed['super_id']} teacher={seed['teacher_id']} "
        f"kvkk_export={seed['kvkk_export_id']}\n"
    )

    extra_ann_ids: list[int] = []
    try:
        sc = _login_v2(SUPER_EMAIL)
        # Teacher login'i en başta — role guard testi için
        tc = _login_v2(TEACHER_EMAIL)

        # ===== Teacher → 403 (test başına alındı) =====
        r = tc.get("/api/v2/admin/audit")
        check(
            "17. Teacher /audit → 403 role_required",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== Anonim → 401 =====
        anon = TestClient(app)
        r = anon.get("/api/v2/admin/audit")
        check(
            "18. Anonim /audit → 401",
            r.status_code == 401
            and r.json().get("detail", {}).get("code") == "missing_credentials",
            f"status={r.status_code}",
        )

        # ===== 1. /audit list happy =====
        r = sc.get("/api/v2/admin/audit")
        ok = (
            r.status_code == 200
            and "items" in r.json()
            and r.json().get("per_page") == 50
            and "total" in r.json()
            and "total_pages" in r.json()
            and "all_actions" in r.json()
        )
        check("1. /audit list happy", ok, f"status={r.status_code}")

        # ===== 2. /audit ?action filtre =====
        r = sc.get("/api/v2/admin/audit?action=login_success")
        ok = (
            r.status_code == 200
            and r.json().get("filter_action") == "login_success"
            and all(it["action"] == "login_success" for it in r.json()["items"])
        )
        check("2. /audit ?action=login_success", ok, f"status={r.status_code}")

        # ===== 3. /audit ?start_date+end_date =====
        r = sc.get("/api/v2/admin/audit?start_date=2024-01-01&end_date=2030-12-31")
        check(
            "3. /audit ?start_date+end_date filtre",
            r.status_code == 200
            and r.json().get("filter_start_date") == "2024-01-01"
            and r.json().get("filter_end_date") == "2030-12-31",
            f"status={r.status_code}",
        )

        # ===== 4. /audit ?page=999 boş =====
        r = sc.get("/api/v2/admin/audit?page=999")
        check(
            "4. /audit ?page=999 → boş ama 200",
            r.status_code == 200 and len(r.json()["items"]) == 0,
            f"status={r.status_code}",
        )

        # ===== 5. /audit ?actor_id filtre =====
        r = sc.get(f"/api/v2/admin/audit?actor_id={seed['super_id']}")
        check(
            "5. /audit ?actor_id filtre",
            r.status_code == 200
            and r.json().get("filter_actor_id") == seed["super_id"],
            f"status={r.status_code}",
        )

        # ===== 6. /system-health happy =====
        r = sc.get("/api/v2/admin/system-health")
        ok = (
            r.status_code == 200
            and "crons" in r.json()
            and "overall_health" in r.json()
            and r.json()["overall_health"] in ("ok", "warn", "crit")
        )
        check("6. /system-health happy", ok, f"status={r.status_code}")

        # ===== 7. /announcements list =====
        r = sc.get("/api/v2/admin/announcements")
        ok = (
            r.status_code == 200
            and "items" in r.json()
            and len(r.json().get("severities", [])) >= 3
            and len(r.json().get("audiences", [])) >= 6
        )
        check("7. /announcements list happy", ok, f"status={r.status_code}")

        # ===== 8. POST create happy =====
        r = sc.post(
            "/api/v2/admin/announcements",
            json={
                "title": f"{PFX} Test Duyuru",
                "message": "Test mesajı — smoke için",
                "severity": "info",
                "audience": "all",
                "dismissible": True,
            },
        )
        ok = (
            r.status_code == 200
            and r.json().get("data", {}).get("announcement", {}).get("message")
            == "Test mesajı — smoke için"
        )
        check("8. POST /announcements create", ok, f"status={r.status_code}")
        if ok:
            ann_id = r.json()["data"]["announcement"]["id"]
            extra_ann_ids.append(ann_id)

        # ===== 9. POST boş message =====
        r = sc.post(
            "/api/v2/admin/announcements",
            json={"message": "   "},
        )
        check(
            "9. POST boş message → 400",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "message_required",
            f"status={r.status_code}",
        )

        # ===== 10. POST invalid datetime =====
        r = sc.post(
            "/api/v2/admin/announcements",
            json={
                "message": "Test",
                "starts_at": "NOT_A_DATETIME",
            },
        )
        check(
            "10. POST invalid datetime → 400 invalid_datetime",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_datetime",
            f"status={r.status_code}",
        )

        # ===== 11. delete happy =====
        if extra_ann_ids:
            r = sc.post(
                f"/api/v2/admin/announcements/{extra_ann_ids[0]}/delete"
            )
            check(
                "11. /announcements/{id}/delete happy",
                r.status_code == 200
                and "silindi" in r.json().get("data", {}).get("message", ""),
                f"status={r.status_code}",
            )
            extra_ann_ids.pop(0)

        # ===== 12. delete 404 =====
        r = sc.post("/api/v2/admin/announcements/999999/delete")
        check(
            "12. /announcements/999999/delete → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "announcement_not_found",
            f"status={r.status_code}",
        )

        # ===== 13. /kvkk dashboard happy =====
        r = sc.get("/api/v2/admin/kvkk")
        ok = (
            r.status_code == 200
            and "summary" in r.json()
            and "data_inventory" in r.json()
            and len(r.json()["data_inventory"]) > 0
        )
        check(
            "13. /kvkk dashboard happy",
            ok,
            f"status={r.status_code}",
        )

        # ===== 14. /kvkk apply 404 =====
        r = sc.post("/api/v2/admin/kvkk/requests/999999/apply")
        check(
            "14. /kvkk apply 999999 → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "kvkk_request_not_found",
            f"status={r.status_code}",
        )

        # ===== 15. /kvkk reject 404 =====
        r = sc.post(
            "/api/v2/admin/kvkk/requests/999999/reject",
            json={"note": "test"},
        )
        check(
            "15. /kvkk reject 999999 → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "kvkk_request_not_found",
            f"status={r.status_code}",
        )

        # ===== 16. apply on export → 400 =====
        r = sc.post(
            f"/api/v2/admin/kvkk/requests/{seed['kvkk_export_id']}/apply"
        )
        check(
            "16. apply on export → 400 only_delete_can_be_applied",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "only_delete_can_be_applied",
            f"status={r.status_code}",
        )

    finally:
        _cleanup(seed, extra_ann_ids)
        print("\n  test verileri temizlendi")

    print("\n=== SONUÇ ===")
    print(f"  PASSED: {passed}")
    print(f"  FAILED: {len(failed)}")
    if failed:
        for f in failed:
            print(f"    - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
