"""P6 — Spam guard + admin dispatch log paneli smoke testleri (5-kullanıcı).

Senaryolar:
   1. Anon → /messaging/dispatch-stats → 401
   2. Veli → /messaging/dispatch-stats → 403 role_not_allowed
   3. Koç (0 log) → today=0 week=0 warning_level="ok"
   4. Koç (30 log bugün) → today=30 warning_level="ok" (< 50)
   5. Koç (60 log bugün) → today=60 warning_level="yogun" + warning_message dolu
   6. Koç (110 log bugün) → today=110 warning_level="cok_yogun" + amber mesaj
   7. Hafta sayım: önceki hafta logları sayım'a girmez
   8. Veli → /admin/whatsapp-dispatch-log → 403
   9. Koç → /admin/whatsapp-dispatch-log → 403
  10. Süper admin → /admin/whatsapp-dispatch-log → 200 + items + summary
  11. ?sender_id filter çalışır
  12. ?days=N geçerli aralık (1-90); 0/negatif → clamp 1
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    SuspiciousIp,
    User,
    UserRole,
    WhatsAppDispatchLog,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2spam_{_secrets.token_hex(3)}"
COACH_LIGHT_EMAIL = f"{PFX}_coach_light@test.invalid"   # 30 log
COACH_BUSY_EMAIL = f"{PFX}_coach_busy@test.invalid"     # 60 log
COACH_HEAVY_EMAIL = f"{PFX}_coach_heavy@test.invalid"   # 110 log
COACH_EMPTY_EMAIL = f"{PFX}_coach_empty@test.invalid"   # 0 log
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
PARENT_EMAIL = f"{PFX}_parent@test.invalid"
PASSWORD = "TestP6Spam!2345"

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


def _login(c: TestClient, email: str) -> bool:
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    return r.status_code == 200


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        light = User(
            email=COACH_LIGHT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Coach Light (30)", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        busy = User(
            email=COACH_BUSY_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Coach Busy (60)", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        heavy = User(
            email=COACH_HEAVY_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Coach Heavy (110)", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        empty = User(
            email=COACH_EMPTY_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Coach Empty (0)", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        admin = User(
            email=ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        parent = User(
            email=PARENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Parent", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([light, busy, heavy, empty, admin, parent])
        db.commit()
        db.refresh(light); db.refresh(busy); db.refresh(heavy)
        db.refresh(empty); db.refresh(admin); db.refresh(parent)

        # Log inject: bugünün tarihiyle yaz
        today = now.replace(hour=12, minute=0, second=0, microsecond=0)
        # Önceki hafta (test 7 için)
        old = now - timedelta(days=14)

        logs = []
        for _ in range(30):
            logs.append(WhatsAppDispatchLog(
                sender_user_id=light.id, target_user_id=parent.id,
                template_key="x", character_count=50, created_at=today,
            ))
        for _ in range(60):
            logs.append(WhatsAppDispatchLog(
                sender_user_id=busy.id, target_user_id=parent.id,
                template_key="x", character_count=50, created_at=today,
            ))
        for _ in range(110):
            logs.append(WhatsAppDispatchLog(
                sender_user_id=heavy.id, target_user_id=parent.id,
                template_key="x", character_count=50, created_at=today,
            ))
        # Önceki hafta: 5 log light için → bu hafta sayım'a girmez
        for _ in range(5):
            logs.append(WhatsAppDispatchLog(
                sender_user_id=light.id, target_user_id=parent.id,
                template_key="x", character_count=50, created_at=old,
            ))
        db.bulk_save_objects(logs)
        db.commit()

        return {
            "light_id": light.id, "busy_id": busy.id, "heavy_id": heavy.id,
            "empty_id": empty.id, "admin_id": admin.id, "parent_id": parent.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        all_uids = [
            seed["light_id"], seed["busy_id"], seed["heavy_id"],
            seed["empty_id"], seed["admin_id"], seed["parent_id"],
        ]
        db.execute(sa_delete(WhatsAppDispatchLog).where(
            WhatsAppDispatchLog.sender_user_id.in_(all_uids)
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_uids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def main() -> int:
    print(f"\n=== P6 spam guard + audit smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()

    try:
        # ===== 1. Anon → 401 =====
        c_anon = TestClient(app)
        r = c_anon.get("/api/v2/messaging/dispatch-stats")
        ok = r.status_code == 401
        check("1. Anon → /dispatch-stats → 401", ok, f"status={r.status_code}")

        # ===== 2. Veli → 403 =====
        cv = TestClient(app)
        assert _login(cv, PARENT_EMAIL), "parent login fail"
        r = cv.get("/api/v2/messaging/dispatch-stats")
        ok = (
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_not_allowed"
        )
        check(
            "2. Veli → /dispatch-stats → 403 role_not_allowed",
            ok, f"status={r.status_code}",
        )

        # ===== 3. Empty koç (0 log) =====
        c_empty = TestClient(app)
        assert _login(c_empty, COACH_EMPTY_EMAIL), "empty login fail"
        r = c_empty.get("/api/v2/messaging/dispatch-stats")
        body = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and body.get("today_count") == 0
            and body.get("week_count") == 0
            and body.get("warning_level") == "ok"
            and body.get("warning_message") is None
        )
        check(
            "3. Koç (0 log) → today=0 week=0 warning=ok",
            ok, f"body={body}",
        )

        # ===== 4. Light (30 log bugün) → ok =====
        c_light = TestClient(app)
        assert _login(c_light, COACH_LIGHT_EMAIL), "light login fail"
        r = c_light.get("/api/v2/messaging/dispatch-stats")
        body = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and body.get("today_count") == 30
            and body.get("warning_level") == "ok"
        )
        check(
            "4. Koç (30 log bugün) → today=30 warning=ok (<50)",
            ok, f"today={body.get('today_count')} level={body.get('warning_level')}",
        )

        # ===== 5. Busy (60 log bugün) → yogun =====
        c_busy = TestClient(app)
        assert _login(c_busy, COACH_BUSY_EMAIL), "busy login fail"
        r = c_busy.get("/api/v2/messaging/dispatch-stats")
        body = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and body.get("today_count") == 60
            and body.get("warning_level") == "yogun"
            and body.get("warning_message")
        )
        check(
            "5. Koç (60 log bugün) → today=60 warning=yogun + mesaj",
            ok, f"today={body.get('today_count')} level={body.get('warning_level')}",
        )

        # ===== 6. Heavy (110 log bugün) → cok_yogun =====
        c_heavy = TestClient(app)
        assert _login(c_heavy, COACH_HEAVY_EMAIL), "heavy login fail"
        r = c_heavy.get("/api/v2/messaging/dispatch-stats")
        body = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and body.get("today_count") == 110
            and body.get("warning_level") == "cok_yogun"
            and body.get("warning_message")
        )
        check(
            "6. Koç (110 log bugün) → today=110 warning=cok_yogun + mesaj",
            ok, f"today={body.get('today_count')} level={body.get('warning_level')}",
        )

        # ===== 7. Eski hafta logu sayım'a girmez =====
        # light için: 30 today + 5 eski (14 gün önce) → week_count <= 30 olmalı
        r = c_light.get("/api/v2/messaging/dispatch-stats")
        body = r.json() if r.status_code == 200 else {}
        ok = body.get("week_count") <= 30 and body.get("today_count") == 30
        check(
            "7. 14g önceki log bu hafta sayım'a girmez",
            ok, f"week={body.get('week_count')} today={body.get('today_count')}",
        )

        # ===== 8. Veli → admin dispatch-log → 403 =====
        r = cv.get("/api/v2/admin/whatsapp-dispatch-log")
        ok = r.status_code == 403
        check("8. Veli → admin dispatch-log → 403", ok, f"status={r.status_code}")

        # ===== 9. Koç → admin dispatch-log → 403 =====
        r = c_light.get("/api/v2/admin/whatsapp-dispatch-log")
        ok = r.status_code == 403
        check("9. Koç → admin dispatch-log → 403", ok, f"status={r.status_code}")

        # ===== 10. Süper admin → 200 + items + summary =====
        c_admin = TestClient(app)
        assert _login(c_admin, ADMIN_EMAIL), "admin login fail"
        r = c_admin.get("/api/v2/admin/whatsapp-dispatch-log?days=7")
        body = r.json() if r.status_code == 200 else {}
        items = body.get("items", [])
        summary = body.get("summary", {})
        top = summary.get("top_senders", [])
        ok = (
            r.status_code == 200
            and len(items) > 0
            and summary.get("total_today", 0) >= 200  # 30+60+110
            and summary.get("total_week", 0) >= 200
            and len(top) > 0
        )
        check(
            "10. Süper admin → 200 + items + summary + top_senders",
            ok,
            f"items={len(items)} today={summary.get('total_today')} "
            f"week={summary.get('total_week')} top={len(top)}",
        )

        # ===== 11. ?sender_id filter =====
        r = c_admin.get(
            f"/api/v2/admin/whatsapp-dispatch-log?days=7&sender_id={seed['busy_id']}"
        )
        body = r.json() if r.status_code == 200 else {}
        items = body.get("items", [])
        ok = (
            r.status_code == 200
            and len(items) > 0
            and all(it.get("sender_user_id") == seed["busy_id"] for it in items)
        )
        check(
            "11. ?sender_id filter → yalnız o sender'ın logları",
            ok, f"count={len(items)}",
        )

        # ===== 12. ?days=0 → clamp 1 =====
        r = c_admin.get("/api/v2/admin/whatsapp-dispatch-log?days=0")
        body = r.json() if r.status_code == 200 else {}
        ok = r.status_code == 200 and body.get("days") == 1
        check(
            "12. ?days=0 → clamp 1",
            ok, f"status={r.status_code} days={body.get('days')}",
        )

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== Result: {passed} passed, {len(failed)} failed ===\n")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
