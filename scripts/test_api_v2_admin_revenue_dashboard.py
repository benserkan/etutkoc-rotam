"""API v2 /admin/security-monitor/revenue (Ticari ana dashboard) smoke (D6 G1).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. dashboard happy (mrr/plan_distribution/payment_calendar/segment_counts)
   4. dashboard segment=institution
   5. dashboard segment=user
   6. dashboard geçersiz segment → 'all'a düşer
   7. drill happy (paying)
   8. drill plan:<code>
   9. drill bilinmeyen key → error
  10. invoices happy (rows + status_counts + statuses)
  11. invoices status_filter=pending
  12. drill plan_change:upgrade segment=all → koç + kurum karışık (Owner-pattern)
  13. drill plan_change:upgrade segment=user → yalnız koç rows
  14. drill plan_change:upgrade segment=institution → yalnız kurum rows
  15. drill row owner_type/owner_id/display_name + from/to_plan_label alanları dolu
  17-25. Kapsamlı drill × segment matrisi (paying/free/trial:expired/plan:solo_pro/etut_standart)
  26. SAYIM ↔ DRILL TUTARLILIK: plan_change_summary.upgrades == drill.count (her segment)
  27. trial_expired_30d sayım == drill row sayısı (her segment)
  28. Owner-pattern alanları (owner_type/id/display_name) tüm drill rows'ta dolu
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
    AuditLog,
    Institution,
    Invoice,
    InvoiceStatus,
    User,
    UserRole,
)
from app.models.plan_history import (
    PlanChangeHistory,
    PlanChangeReason,
    PlanOwnerType,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adg1{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassG1!23"

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
    """Kapsamlı seed:
      - 1 ödeyen kurum (etut_standart)
      - 1 ödeyen koç (solo_pro)
      - 1 ücretsiz kurum (institution_free)
      - 1 ücretsiz koç (solo_free)
      - 1 trial_expired kurum (kayıp fırsat)
      - 1 trial_expired koç (kayıp fırsat)
      - Plan değişimleri: 1 kurum upgrade + 1 koç upgrade + 2 trial_expired
    """
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        # Kurumlar
        paying_inst = Institution(
            name=f"{PFX} PayingInst", slug=f"{PFX}-pi",
            contact_email=f"{PFX}_pi@test.invalid", plan="etut_standart", is_active=True,
        )
        free_inst = Institution(
            name=f"{PFX} FreeInst", slug=f"{PFX}-fi",
            contact_email=f"{PFX}_fi@test.invalid", plan="institution_free", is_active=True,
        )
        expired_inst = Institution(
            name=f"{PFX} ExpiredInst", slug=f"{PFX}-ei",
            contact_email=f"{PFX}_ei@test.invalid", plan="institution_free", is_active=True,
        )
        db.add_all([paying_inst, free_inst, expired_inst])
        db.flush()

        # Kullanıcılar
        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
            role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        paying_coach = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} PayingCoach",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            plan="solo_pro",
            password_changed_at=now, must_change_password=False,
        )
        free_coach = User(
            email=f"{PFX}_freecoach@test.invalid", password_hash=pwd,
            full_name=f"{PFX} FreeCoach",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            plan="solo_free",
            password_changed_at=now, must_change_password=False,
        )
        expired_coach = User(
            email=f"{PFX}_expcoach@test.invalid", password_hash=pwd,
            full_name=f"{PFX} ExpiredCoach",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            plan="solo_free",
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, paying_coach, free_coach, expired_coach])
        db.flush()

        # Fatura (kurum-only, payment_calendar smoke için)
        inv = Invoice(
            owner_type="institution", institution_id=paying_inst.id, user_id=None,
            plan="etut_standart", amount_try=10000, status=InvoiceStatus.PENDING,
            period_start=now - timedelta(days=30), period_end=now,
            due_at=now + timedelta(days=5),
        )
        db.add(inv)
        db.flush()

        # Plan değişimleri (son 30 gün)
        inst_upgrade = PlanChangeHistory(
            owner_type=PlanOwnerType.INSTITUTION,
            owner_id=paying_inst.id,
            from_plan="institution_free", to_plan="etut_standart",
            reason=PlanChangeReason.UPGRADE,
            actor_user_id=super_admin.id,
            note="seed — kurum upgrade",
            occurred_at=now - timedelta(days=2),
        )
        user_upgrade = PlanChangeHistory(
            owner_type=PlanOwnerType.USER,
            owner_id=paying_coach.id,
            from_plan="solo_free", to_plan="solo_pro",
            reason=PlanChangeReason.UPGRADE,
            actor_user_id=paying_coach.id,
            note="seed — koç upgrade",
            occurred_at=now - timedelta(days=1),
        )
        inst_trial_exp = PlanChangeHistory(
            owner_type=PlanOwnerType.INSTITUTION,
            owner_id=expired_inst.id,
            from_plan="institution_trial", to_plan="institution_free",
            reason=PlanChangeReason.TRIAL_EXPIRED,
            actor_user_id=super_admin.id,
            note="seed — kurum trial bitti",
            occurred_at=now - timedelta(days=5),
        )
        user_trial_exp = PlanChangeHistory(
            owner_type=PlanOwnerType.USER,
            owner_id=expired_coach.id,
            from_plan="solo_trial", to_plan="solo_free",
            reason=PlanChangeReason.TRIAL_EXPIRED,
            actor_user_id=expired_coach.id,
            note="seed — koç trial bitti",
            occurred_at=now - timedelta(days=3),
        )
        db.add_all([inst_upgrade, user_upgrade, inst_trial_exp, user_trial_exp])
        db.flush()

        out = {
            "paying_inst_id": paying_inst.id,
            "free_inst_id": free_inst.id,
            "expired_inst_id": expired_inst.id,
            "inst_id": paying_inst.id,  # geri uyumluluk
            "super_id": super_admin.id,
            "teacher_id": paying_coach.id,
            "free_coach_id": free_coach.id,
            "expired_coach_id": expired_coach.id,
            "change_ids": [
                inst_upgrade.id, user_upgrade.id,
                inst_trial_exp.id, user_trial_exp.id,
            ],
        }
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(PlanChangeHistory).where(
            PlanChangeHistory.id.in_(seed.get("change_ids", []))
        ))
        inst_ids = [seed["paying_inst_id"], seed["free_inst_id"], seed["expired_inst_id"]]
        db.execute(sa_delete(Invoice).where(Invoice.institution_id.in_(inst_ids)))
        uids = [
            seed["super_id"], seed["teacher_id"],
            seed["free_coach_id"], seed["expired_coach_id"],
        ]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id.in_(inst_ids)))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin/security-monitor/revenue (G1) smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded inst={seed['inst_id']}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # 1. Teacher → 403
        r = tc.get("/api/v2/admin/security-monitor/revenue")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        # 2. Anonim → 401
        r = TestClient(app).get("/api/v2/admin/security-monitor/revenue")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. dashboard happy
        r = sc.get("/api/v2/admin/security-monitor/revenue")
        j = r.json()
        ok = (
            r.status_code == 200
            and "mrr" in j and "plan_distribution" in j and "payment_calendar" in j
            and "segment_counts" in j and j["segment"] == "all"
            and set(j["segment_counts"].keys()) == {"all", "institution", "user"}
        )
        check("3. dashboard happy", ok, f"status={r.status_code}")

        # 4. segment=institution
        r = sc.get("/api/v2/admin/security-monitor/revenue?segment=institution")
        check("4. segment=institution", r.status_code == 200 and r.json()["segment"] == "institution",
              f"status={r.status_code}")

        # 5. segment=user
        r = sc.get("/api/v2/admin/security-monitor/revenue?segment=user")
        check("5. segment=user", r.status_code == 200 and r.json()["segment"] == "user",
              f"status={r.status_code}")

        # 6. geçersiz segment → all
        r = sc.get("/api/v2/admin/security-monitor/revenue?segment=xyz")
        check("6. geçersiz segment → all", r.status_code == 200 and r.json()["segment"] == "all",
              f"status={r.status_code}")

        # 6b. change_summary_30d sayım segment'e göre filtrelenir
        # seed: 1 kurum upgrade + 1 koç upgrade
        r_all = sc.get("/api/v2/admin/security-monitor/revenue?segment=all").json()["change_summary_30d"]
        r_inst = sc.get("/api/v2/admin/security-monitor/revenue?segment=institution").json()["change_summary_30d"]
        r_user = sc.get("/api/v2/admin/security-monitor/revenue?segment=user").json()["change_summary_30d"]
        # ALL = kurum + koç upgrade'ini içerir; institution-only → ALL'dan KÜÇÜK (koç çıkarılır)
        check(
            "6b. change_summary_30d segment-aware sayım",
            r_all["upgrades"] >= 2
            and r_inst["upgrades"] >= 1
            and r_user["upgrades"] >= 1
            and r_inst["upgrades"] + r_user["upgrades"] == r_all["upgrades"],
            f"all={r_all['upgrades']} inst={r_inst['upgrades']} user={r_user['upgrades']}",
        )

        # 7. drill paying
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=paying")
        j = r.json()
        check("7. drill paying", r.status_code == 200 and "rows" in j and "count" in j and j["key"] == "paying",
              f"status={r.status_code}")

        # 8. drill plan:free
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=plan:free")
        check("8. drill plan:free", r.status_code == 200 and r.json()["plan"] == "free",
              f"status={r.status_code}")

        # 9. drill bilinmeyen key → error
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=not_real_key")
        j = r.json()
        check("9. drill bilinmeyen key → error", r.status_code == 200 and j.get("error") == "unknown_key",
              f"status={r.status_code} {r.text[:120]}")

        # 10. invoices happy
        r = sc.get("/api/v2/admin/security-monitor/revenue/invoices")
        j = r.json()
        ok = (
            r.status_code == 200
            and "rows" in j and "status_counts" in j and len(j["statuses"]) == 6
            and any(row["id"] for row in j["rows"])
        )
        check("10. invoices happy", ok, f"status={r.status_code}")

        # 11. invoices status_filter=pending
        r = sc.get("/api/v2/admin/security-monitor/revenue/invoices?status_filter=pending")
        j = r.json()
        ok = r.status_code == 200 and j["status_filter"] == "pending" and all(row["status"] == "pending" for row in j["rows"])
        check("11. invoices status_filter=pending", ok, f"status={r.status_code}")

        # 12. drill plan_change:upgrade segment=all — koç + kurum karışık
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=plan_change:upgrade&segment=all")
        j = r.json()
        seed_inst = seed["inst_id"]
        seed_user = seed["teacher_id"]
        has_inst = any(
            row.get("owner_type") == "institution" and row.get("owner_id") == seed_inst
            for row in j.get("rows", [])
        )
        has_user = any(
            row.get("owner_type") == "user" and row.get("owner_id") == seed_user
            for row in j.get("rows", [])
        )
        check(
            "12. drill plan_change:upgrade segment=all (kurum+koç)",
            r.status_code == 200 and has_inst and has_user,
            f"status={r.status_code} has_inst={has_inst} has_user={has_user} count={j.get('count')}",
        )

        # 13. segment=user → yalnız koç
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=plan_change:upgrade&segment=user")
        j = r.json()
        only_users = all(row.get("owner_type") == "user" for row in j.get("rows", []))
        has_seed_user = any(row.get("owner_id") == seed_user for row in j.get("rows", []))
        check(
            "13. segment=user → yalnız koç",
            r.status_code == 200 and only_users and has_seed_user,
            f"only_users={only_users} has_seed_user={has_seed_user}",
        )

        # 14. segment=institution → yalnız kurum
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=plan_change:upgrade&segment=institution")
        j = r.json()
        only_insts = all(row.get("owner_type") == "institution" for row in j.get("rows", []))
        has_seed_inst = any(row.get("owner_id") == seed_inst for row in j.get("rows", []))
        check(
            "14. segment=institution → yalnız kurum",
            r.status_code == 200 and only_insts and has_seed_inst,
            f"only_insts={only_insts} has_seed_inst={has_seed_inst}",
        )

        # 15. row alanları (owner_type/owner_id/display_name + from/to_plan_label)
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=plan_change:upgrade&segment=user")
        j = r.json()
        seed_row = next(
            (row for row in j.get("rows", []) if row.get("owner_id") == seed_user),
            None,
        )
        ok = (
            seed_row is not None
            and seed_row.get("display_name")
            and seed_row.get("from_plan") == "solo_free"
            and seed_row.get("to_plan") == "solo_pro"
            and seed_row.get("from_plan_label")
            and seed_row.get("to_plan_label")
            and seed_row.get("user_id") == seed_user
        )
        check(
            "15. row owner+plan_label alanları dolu",
            ok,
            f"seed_row={seed_row}",
        )

        # =================================================================
        # YENİ SUITE — UI tutarlılık (sayım = drill row count)
        # =================================================================
        seed_inst_p = seed["paying_inst_id"]
        seed_inst_f = seed["free_inst_id"]
        seed_inst_e = seed["expired_inst_id"]
        seed_coach_p = seed["teacher_id"]
        seed_coach_f = seed["free_coach_id"]
        seed_coach_e = seed["expired_coach_id"]

        # 17. drill paying segment=institution → ödeyen kurum seed'de
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=paying&segment=institution")
        j = r.json()
        ok = (
            r.status_code == 200
            and all(row["owner_type"] == "institution" for row in j["rows"])
            and any(row["owner_id"] == seed_inst_p for row in j["rows"])
        )
        check("17. paying segment=institution kurum seed'i içerir", ok,
              f"count={j.get('count')} status={r.status_code}")

        # 18. drill paying segment=user → koç seed'i
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=paying&segment=user")
        j = r.json()
        ok = (
            r.status_code == 200
            and all(row["owner_type"] == "user" for row in j["rows"])
            and any(row["owner_id"] == seed_coach_p for row in j["rows"])
        )
        check("18. paying segment=user koç seed'i içerir", ok,
              f"count={j.get('count')}")

        # 19. drill free segment=institution → ücretsiz kurum seed'i
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=free&segment=institution")
        j = r.json()
        ok = (
            r.status_code == 200
            and all(row["owner_type"] == "institution" for row in j["rows"])
            and any(row["owner_id"] == seed_inst_f for row in j["rows"])
        )
        check("19. free segment=institution ücretsiz kurum içerir", ok,
              f"count={j.get('count')}")

        # 20. drill free segment=user → ücretsiz koç seed'i
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=free&segment=user")
        j = r.json()
        ok = (
            r.status_code == 200
            and all(row["owner_type"] == "user" for row in j["rows"])
            and any(row["owner_id"] == seed_coach_f for row in j["rows"])
        )
        check("20. free segment=user ücretsiz koç içerir", ok, f"count={j.get('count')}")

        # 21. trial:expired_30d segment=institution → kurum trial expired seed
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=trial:expired_30d&segment=institution")
        j = r.json()
        ok = (
            r.status_code == 200
            and any(row["owner_id"] == seed_inst_e for row in j["rows"])
        )
        check("21. trial:expired_30d segment=institution kurum içerir", ok,
              f"count={j.get('count')}")

        # 22. trial:expired_30d segment=user → koç trial expired seed
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=trial:expired_30d&segment=user")
        j = r.json()
        ok = (
            r.status_code == 200
            and any(row["owner_id"] == seed_coach_e for row in j["rows"])
        )
        check("22. trial:expired_30d segment=user koç içerir", ok,
              f"count={j.get('count')}")

        # 23. plan:solo_pro segment=user → ödeyen koç seed'i (kurum-plan olmaz)
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=plan:solo_pro&segment=user")
        j = r.json()
        ok = (
            r.status_code == 200
            and all(row["owner_type"] == "user" for row in j["rows"])
            and any(row["owner_id"] == seed_coach_p for row in j["rows"])
        )
        check("23. plan:solo_pro segment=user koç içerir", ok, f"count={j.get('count')}")

        # 24. plan:solo_pro segment=institution → boş (kurum solo plana sahip olmaz)
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=plan:solo_pro&segment=institution")
        j = r.json()
        check("24. plan:solo_pro segment=institution → kurum yok", r.status_code == 200 and j["count"] == 0,
              f"count={j.get('count')}")

        # 25. plan:etut_standart segment=institution → ödeyen kurum
        r = sc.get("/api/v2/admin/security-monitor/revenue/drill?key=plan:etut_standart&segment=institution")
        j = r.json()
        ok = (
            r.status_code == 200
            and all(row["owner_type"] == "institution" for row in j["rows"])
            and any(row["owner_id"] == seed_inst_p for row in j["rows"])
        )
        check("25. plan:etut_standart segment=institution kurum içerir", ok,
              f"count={j.get('count')}")

        # 26. SAYIM ↔ DRILL TUTARLILIK (kritik: kullanıcının yaşadığı bug):
        #     plan_change_summary.upgrades == drill plan_change:upgrade.count (her segment için)
        for seg in ("all", "institution", "user"):
            dash = sc.get(f"/api/v2/admin/security-monitor/revenue?segment={seg}").json()
            drl = sc.get(f"/api/v2/admin/security-monitor/revenue/drill?key=plan_change:upgrade&segment={seg}").json()
            cs_upg = dash["change_summary_30d"]["upgrades"]
            drill_count = drl["count"]
            check(
                f"26.{seg}. upgrades sayım({cs_upg}) == drill count({drill_count}) [{seg}]",
                cs_upg == drill_count,
                f"sayım={cs_upg} drill={drill_count}",
            )

        # 27. trial_expired_30d (dashboard sayım) ↔ trial:expired_30d (drill) tutarlılık
        for seg in ("all", "institution", "user"):
            dash = sc.get(f"/api/v2/admin/security-monitor/revenue?segment={seg}").json()
            drl = sc.get(f"/api/v2/admin/security-monitor/revenue/drill?key=trial:expired_30d&segment={seg}").json()
            dash_count = dash["trial_expired_30d"]
            drill_count = drl["count"]
            # dash sayım TÜM trial_expired olayları, drill ise sadece ÜCRETLİYE GEÇMEYENLER
            # → drill_count <= dash_count olmalı (seed'de upgrade etmediler, eşit beklenebilir)
            check(
                f"27.{seg}. trial_expired_30d sayım({dash_count}) >= drill count({drill_count}) [{seg}]",
                dash_count >= drill_count,
                f"sayım={dash_count} drill={drill_count}",
            )

        # 28. Owner-pattern: tüm drill row'larda owner_type, owner_id, display_name dolu
        bad_rows: list[str] = []
        for key in ("paying", "free", "trial:expired_30d", "plan:solo_pro", "plan_change:upgrade"):
            r = sc.get(f"/api/v2/admin/security-monitor/revenue/drill?key={key}&segment=all")
            for row in r.json().get("rows", []):
                if not row.get("owner_type") or not row.get("owner_id") or not row.get("display_name"):
                    bad_rows.append(f"{key}: {row}")
                    break
        check(
            f"28. tüm drill rows owner-pattern alanları dolu",
            not bad_rows,
            f"bad={bad_rows[:3]}",
        )

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
