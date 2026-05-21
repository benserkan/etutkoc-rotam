"""API v2 /institution/* smoke — Dalga 4 Paket 3 (subscription / quota / usage / digest).

Senaryolar (16):
   1. /subscription happy → status + guarantee_evaluation
   2. /subscription/switch-academic-year → kind=academic_year, period_end set
   3. /subscription/switch tekrar idempotent → kind kalır
   4. /subscription/pause yaz penceresi dışındayken → 409 summer_window_required
   5. /subscription/resume zaten aktif → 200 idempotent
   6. /subscription/guarantee/enable → performance_guarantee=True
   7. /subscription/guarantee/enable idempotent → status değişmez
   8. /quota happy → 3 quota satırı (teachers/students/institution_admins) + plans listesi
   9. /quota mevcut kullanım gerçeği — teacher 1 olarak görünür
  10. /usage happy → account + breakdown + series + events
  11. /usage?days=15 → series 15 nokta
  12. /admin-digest list başlangıçta 0
  13. /admin-digest/send-now → digest yaratılır
  14. /admin-digest list → 1 digest
  15. /admin-digest/{id} detail → payload + emails
  16. /admin-digest/{99999} → 404
  17. Cross-tenant digest detail → 404
  18. Teacher rolü /subscription → 403
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete, or_ as sa_or

from app.database import SessionLocal
from app.main import app
from app.models import (
    AdminWeeklyDigest,
    Institution,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.services.subscription import is_summer_window


PFX = f"v2inst3_{secrets.token_hex(3)}"
ALPHA_NAME = f"{PFX}_ALPHA"
BETA_NAME = f"{PFX}_BETA"
ALPHA_ADMIN_EMAIL = f"{PFX}_alpha_admin@test.invalid"
ALPHA_T1_EMAIL = f"{PFX}_alpha_t1@test.invalid"
BETA_ADMIN_EMAIL = f"{PFX}_beta_admin@test.invalid"
PASSWORD = "TestPass!2345Inst"

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
        alpha = Institution(
            name=ALPHA_NAME, slug=f"{PFX}-alpha",
            contact_email="alpha@test.invalid", plan="starter", is_active=True,
        )
        beta = Institution(
            name=BETA_NAME, slug=f"{PFX}-beta",
            contact_email="beta@test.invalid", plan="free", is_active=True,
        )
        db.add_all([alpha, beta])
        db.flush()

        alpha_admin = User(
            email=ALPHA_ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Alpha Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=alpha.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        alpha_t1 = User(
            email=ALPHA_T1_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Alpha T1", role=UserRole.TEACHER,
            institution_id=alpha.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        beta_admin = User(
            email=BETA_ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Beta Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=beta.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([alpha_admin, alpha_t1, beta_admin])
        db.flush()

        # Beta için pre-existing digest (cross-tenant isolation testi için)
        today = date.today()
        beta_digest = AdminWeeklyDigest(
            institution_id=beta.id,
            week_start_date=today - timedelta(days=6),
            week_end_date=today,
            send_status="log_only",
            recipient_count=1,
            payload_json='{"foo": "bar"}',
            recipient_emails=BETA_ADMIN_EMAIL,
            sent_at=now,
        )
        db.add(beta_digest)
        db.flush()

        db.commit()
        return {
            "alpha_id": alpha.id,
            "beta_id": beta.id,
            "alpha_admin_id": alpha_admin.id,
            "alpha_t1_id": alpha_t1.id,
            "beta_admin_id": beta_admin.id,
            "beta_digest_id": beta_digest.id,
        }


def _cleanup(seed: dict, extra_digest_ids: list[int]) -> None:
    with SessionLocal() as db:
        user_ids = [
            seed["alpha_admin_id"], seed["alpha_t1_id"], seed["beta_admin_id"],
        ]
        digest_ids = [seed["beta_digest_id"]] + extra_digest_ids
        db.execute(sa_delete(AdminWeeklyDigest).where(
            sa_or(
                AdminWeeklyDigest.id.in_(digest_ids),
                AdminWeeklyDigest.institution_id.in_([seed["alpha_id"], seed["beta_id"]]),
            )
        ))
        # CreditAccount + UsageEvent — bu kuruma ait olanları temizle
        from app.models import CreditAccount, UsageEvent, UsageOwnerType
        db.execute(sa_delete(UsageEvent).where(
            UsageEvent.owner_type == UsageOwnerType.INSTITUTION,
            UsageEvent.owner_id.in_([seed["alpha_id"], seed["beta_id"]]),
        ))
        db.execute(sa_delete(CreditAccount).where(
            CreditAccount.owner_type == UsageOwnerType.INSTITUTION,
            CreditAccount.owner_id.in_([seed["alpha_id"], seed["beta_id"]]),
        ))
        # PlanChangeHistory artıkları
        from app.models import PlanChangeHistory, PlanOwnerType
        db.execute(sa_delete(PlanChangeHistory).where(
            PlanChangeHistory.owner_type == PlanOwnerType.INSTITUTION,
            PlanChangeHistory.owner_id.in_([seed["alpha_id"], seed["beta_id"]]),
        ))
        db.execute(sa_delete(User).where(User.id.in_(user_ids)))
        db.execute(sa_delete(Institution).where(
            Institution.id.in_([seed["alpha_id"], seed["beta_id"]])
        ))
        from app.models import AuditLog
        db.execute(sa_delete(AuditLog).where(sa_or(
            AuditLog.actor_id.in_(user_ids),
            AuditLog.target_id.in_(user_ids),
        )))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed for {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /institution P3 smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    summer = is_summer_window()
    print(
        f"  seeded alpha_inst={seed['alpha_id']} beta_inst={seed['beta_id']} "
        f"alpha_admin={seed['alpha_admin_id']} (summer_window={summer})\n"
    )

    extra_digest_ids: list[int] = []
    try:
        alpha_admin = _login_v2(ALPHA_ADMIN_EMAIL)

        # ===== 1. /subscription happy =====
        r = alpha_admin.get("/api/v2/institution/subscription")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("plan") == "starter"
            and "status" in body
            and "guarantee_evaluation" in body
            and body["status"].get("kind") == "monthly"  # default
        )
        check(
            "1. /subscription happy",
            ok,
            f"status={r.status_code} keys={list(body.keys())} plan={body.get('plan')}",
        )

        # ===== 2. /subscription/switch-academic-year =====
        r = alpha_admin.post("/api/v2/institution/subscription/switch-academic-year")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("kind") == "academic_year"
            and data.get("period_end") is not None
        )
        check(
            "2. /subscription/switch-academic-year",
            ok,
            f"status={r.status_code} kind={data.get('kind')} period_end={data.get('period_end')}",
        )

        # ===== 3. /subscription/switch tekrar idempotent =====
        r = alpha_admin.post("/api/v2/institution/subscription/switch-academic-year")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = r.status_code == 200 and data.get("kind") == "academic_year"
        check(
            "3. /subscription/switch idempotent",
            ok,
            f"status={r.status_code} kind={data.get('kind')}",
        )

        # ===== 4. /subscription/pause yaz penceresi DIŞINDAYKEN → 409 =====
        # Şu an Mayıs (2026-05-19) — summer_window=False beklenir
        if not summer:
            r = alpha_admin.post("/api/v2/institution/subscription/pause")
            body = r.json() if r.text else {}
            detail = body.get("detail", {})
            ok = (
                r.status_code == 409
                and detail.get("code") == "summer_window_required"
            )
            check(
                "4. /subscription/pause yaz dışı → 409",
                ok,
                f"status={r.status_code} detail={detail}",
            )
        else:
            check(
                "4. /subscription/pause yaz dışı testi atlandı (şu an yaz)",
                True,
                "yaz penceresi aktif",
            )

        # ===== 5. /subscription/resume zaten aktif → idempotent =====
        r = alpha_admin.post("/api/v2/institution/subscription/resume")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = r.status_code == 200 and data.get("kind") == "academic_year"
        check(
            "5. /subscription/resume idempotent (zaten aktif)",
            ok,
            f"status={r.status_code} kind={data.get('kind')}",
        )

        # ===== 6. /subscription/guarantee/enable =====
        r = alpha_admin.post("/api/v2/institution/subscription/guarantee/enable")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = (
            r.status_code == 200
            and data.get("performance_guarantee") is True
        )
        check(
            "6. /subscription/guarantee/enable",
            ok,
            f"status={r.status_code} guarantee={data.get('performance_guarantee')}",
        )

        # ===== 7. /subscription/guarantee/enable idempotent =====
        r = alpha_admin.post("/api/v2/institution/subscription/guarantee/enable")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        ok = r.status_code == 200 and data.get("performance_guarantee") is True
        check(
            "7. /subscription/guarantee/enable idempotent",
            ok,
            f"status={r.status_code}",
        )

        # ===== 8. /quota happy =====
        r = alpha_admin.get("/api/v2/institution/quota")
        body = r.json() if r.text else {}
        summary = body.get("summary", [])
        plans = body.get("plans", [])
        keys_in_summary = {s.get("key") for s in summary}
        ok = (
            r.status_code == 200
            and body.get("plan") == "starter"
            and len(summary) == 3
            and {"teachers", "students", "institution_admins"} == keys_in_summary
            and len(plans) >= 3
            and "warn_pct" in body
        )
        check(
            "8. /quota happy",
            ok,
            f"status={r.status_code} keys={keys_in_summary} plans={len(plans)}",
        )

        # ===== 9. /quota teachers current=1 =====
        teachers_row = next((s for s in summary if s.get("key") == "teachers"), None)
        ok = teachers_row is not None and teachers_row.get("current") == 1
        check(
            "9. /quota teachers current=1",
            ok,
            f"row={teachers_row}",
        )

        # ===== 10. /usage happy =====
        r = alpha_admin.get("/api/v2/institution/usage")
        body = r.json() if r.text else {}
        account = body.get("account", {})
        ok = (
            r.status_code == 200
            and "period_year_month" in account
            and "total_allocated" in account
            and isinstance(body.get("breakdown"), list)
            and isinstance(body.get("series"), list)
            and isinstance(body.get("events"), list)
            and "warn_threshold_pct" in body
        )
        check(
            "10. /usage happy",
            ok,
            f"status={r.status_code} keys={list(body.keys())} account_keys={list(account.keys())[:6]}",
        )

        # ===== 11. /usage?days=15 → 15 nokta =====
        r = alpha_admin.get("/api/v2/institution/usage?days=15")
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and len(body.get("series", [])) == 15
        check(
            "11. /usage?days=15 → 15 nokta",
            ok,
            f"status={r.status_code} series_len={len(body.get('series', []))}",
        )

        # ===== 12. /admin-digest list başlangıçta 0 =====
        r = alpha_admin.get("/api/v2/institution/admin-digest")
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("total") == 0
        check(
            "12. /admin-digest list başlangıçta 0",
            ok,
            f"status={r.status_code} total={body.get('total')}",
        )

        # ===== 13. /admin-digest/send-now =====
        r = alpha_admin.post("/api/v2/institution/admin-digest/send-now")
        body = r.json() if r.text else {}
        data = body.get("data", {})
        digest = data.get("digest", {})
        ok = (
            r.status_code == 200
            and digest.get("institution_id") == seed["alpha_id"]
            and digest.get("send_status") in {"sent", "failed", "log_only", "skipped_no_admin"}
        )
        check(
            "13. /admin-digest/send-now",
            ok,
            f"status={r.status_code} digest_status={digest.get('send_status')}",
        )
        digest_id = digest.get("id")
        if digest_id:
            extra_digest_ids.append(int(digest_id))

        # ===== 14. /admin-digest list → 1 digest =====
        r = alpha_admin.get("/api/v2/institution/admin-digest")
        body = r.json() if r.text else {}
        ok = r.status_code == 200 and body.get("total") == 1
        check(
            "14. /admin-digest list 1 digest",
            ok,
            f"status={r.status_code} total={body.get('total')}",
        )

        # ===== 15. /admin-digest/{id} detail =====
        if digest_id:
            r = alpha_admin.get(f"/api/v2/institution/admin-digest/{digest_id}")
            body = r.json() if r.text else {}
            ok = (
                r.status_code == 200
                and body.get("id") == digest_id
                and "payload" in body
                and "recipient_emails" in body
            )
            check(
                "15. /admin-digest/{id} detail",
                ok,
                f"status={r.status_code} keys={list(body.keys())[:8]}",
            )

        # ===== 16. /admin-digest/{99999} → 404 =====
        r = alpha_admin.get("/api/v2/institution/admin-digest/99999")
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = r.status_code == 404 and detail.get("code") == "digest_not_found"
        check(
            "16. /admin-digest/99999 → 404",
            ok,
            f"status={r.status_code} detail={detail}",
        )

        # ===== 17. /admin-digest BETA digest → 404 (tenant isolation) =====
        r = alpha_admin.get(
            f"/api/v2/institution/admin-digest/{seed['beta_digest_id']}"
        )
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = r.status_code == 404 and detail.get("code") == "digest_not_found"
        check(
            "17. /admin-digest cross-tenant → 404",
            ok,
            f"status={r.status_code} detail={detail}",
        )

        # ===== 18. Teacher rolü /subscription → 403 =====
        teacher_client = _login_v2(ALPHA_T1_EMAIL)
        r = teacher_client.get("/api/v2/institution/subscription")
        body = r.json() if r.text else {}
        detail = body.get("detail", {})
        ok = r.status_code == 403 and detail.get("code") == "role_required"
        check(
            "18. Teacher /subscription → 403 role_required",
            ok,
            f"status={r.status_code} detail={detail}",
        )

    finally:
        _cleanup(seed, extra_digest_ids)

    print(f"\n=== SONUÇ ===\n  PASSED: {passed}\n  FAILED: {len(failed)}")
    for f in failed:
        print(f"    - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
