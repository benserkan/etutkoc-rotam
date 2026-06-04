"""API v2 /admin/feature-catalog smoke (D6 P6).

Senaryolar:
   1. Teacher → 403 (başta)
   2. Anonim → 401
   3. /feature-catalog list happy (cards/counts/domains/statuses + skor dolu)
   4. /feature-catalog/new form meta (mockups/roles)
   5. POST /feature-catalog create happy
   6. POST create boş title → 400
   7. POST create duplicate slug → 400
   8. GET /feature-catalog/{id} detail happy
   9. POST /feature-catalog/{id} update happy
  10. POST /feature-catalog/{id}/status happy
  11. POST /feature-catalog/{id}/pin happy
  12. GET /feature-catalog/{99999} → 404
  13. /feature-catalog/dashboard happy
  14. /feature-catalog/discovery-queue happy (seed kesif-c-* DRAFT)
  15. POST /feature-catalog/{id}/reject happy
  16. POST /feature-catalog/discovery-queue/bulk delete happy
  17. /feature-catalog/experiments list happy
  18. /feature-catalog/experiments/new meta happy
  19. POST /feature-catalog/experiments create happy
  20. POST experiments create invalid weights → 400
  21. GET /feature-catalog/experiments/{id} detail happy
  22. POST experiments/{id}/status running happy
  23. POST /feature-catalog/{id}/delete happy
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
    FeatureBanditState,
    FeatureCard,
    FeatureCardEvent,
    FeatureExperiment,
    FeatureStatus,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adp6{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestPassP6!23"

passed = 0
failed: list[str] = []

# Oluşturulan kart slug'larını cleanup için topla
created_slugs: list[str] = []


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
            institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.flush()

        # PUBLISHED + mockup kart (skor hesaplanır)
        pub = FeatureCard(
            slug=f"{PFX}-pub",
            title=f"{PFX} Yayın Kartı",
            tagline="Test yayın",
            mockup_type="daily_schedule",
            domain="lgs",
            tier="core",
            status=FeatureStatus.PUBLISHED.value,
            strategic_priority=4,
            created_by=super_admin.id,
            updated_by=super_admin.id,
        )
        pub.target_roles = ["student", "teacher"]
        pub.benefits = ["⚡ Hızlı", "📚 Kapsamlı"]

        # Discovery aday (kesif-c-* DRAFT)
        disc = FeatureCard(
            slug=f"kesif-c-{PFX}aa-test-aday",
            title=f"{PFX} Keşif Adayı",
            tagline="(otomatik üretildi — admin düzenleyecek)",
            domain="genel",
            tier="enhancement",
            status=FeatureStatus.DRAFT.value,
            strategic_priority=2,
        )
        disc2 = FeatureCard(
            slug=f"kesif-c-{PFX}bb-test-aday2",
            title=f"{PFX} Keşif Adayı 2",
            tagline="ikinci aday",
            domain="genel",
            tier="enhancement",
            status=FeatureStatus.DRAFT.value,
            strategic_priority=2,
        )
        db.add_all([pub, disc, disc2])
        db.flush()
        out = {
            "super_id": super_admin.id,
            "teacher_id": teacher.id,
            "pub_id": pub.id,
            "disc_id": disc.id,
            "disc2_id": disc2.id,
        }
        created_slugs.extend([pub.slug, disc.slug, disc2.slug])
        db.commit()
        return out


def _cleanup() -> None:
    with SessionLocal() as db:
        # Tüm PFX kart + deneyleri sil (event/bandit cascade veya manuel)
        cards = db.query(FeatureCard).filter(
            FeatureCard.slug.like(f"%{PFX}%")
        ).all()
        card_ids = [c.id for c in cards]
        if card_ids:
            db.execute(sa_delete(FeatureCardEvent).where(
                FeatureCardEvent.card_id.in_(card_ids)
            ))
            db.execute(sa_delete(FeatureBanditState).where(
                FeatureBanditState.card_id.in_(card_ids)
            ))
            db.execute(sa_delete(FeatureCard).where(FeatureCard.id.in_(card_ids)))
        db.execute(sa_delete(FeatureExperiment).where(
            FeatureExperiment.slug.like(f"%{PFX}%")
        ))
        ids = []
        for email in (SUPER_EMAIL, TEACHER_EMAIL):
            u = db.query(User).filter(User.email == email).first()
            if u:
                ids.append(u.id)
        if ids:
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin/feature-catalog smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(f"  seeded super={seed['super_id']} pub={seed['pub_id']} disc={seed['disc_id']}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # ===== 1. Teacher → 403 =====
        r = tc.get("/api/v2/admin/feature-catalog")
        check(
            "1. Teacher /feature-catalog → 403",
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_required",
            f"status={r.status_code}",
        )

        # ===== 2. Anonim → 401 =====
        anon = TestClient(app)
        r = anon.get("/api/v2/admin/feature-catalog")
        check("2. Anonim /feature-catalog → 401", r.status_code == 401, f"status={r.status_code}")

        # ===== 3. list happy =====
        r = sc.get("/api/v2/admin/feature-catalog")
        j = r.json()
        ok = (
            r.status_code == 200
            and "cards" in j and "counts" in j
            and len(j["domains"]) == 6
            and len(j["statuses"]) == 4
        )
        check("3. list happy", ok, f"status={r.status_code}")
        # PUBLISHED+mockup kartta skor dolu olmalı
        pub_item = next((c for c in j.get("cards", []) if c["id"] == seed["pub_id"]), None)
        check(
            "3b. yayın kartında fuzzy skor var",
            pub_item is not None and pub_item.get("score") is not None
            and pub_item.get("score_inputs") is not None,
            f"item={pub_item}",
        )

        # ===== 4. new form meta =====
        r = sc.get("/api/v2/admin/feature-catalog/new")
        j = r.json()
        ok = (
            r.status_code == 200
            and j.get("card") is None
            and len(j["meta"]["mockups"]) == 6
            and len(j["meta"]["roles"]) >= 4
        )
        check("4. new form meta", ok, f"status={r.status_code}")

        # ===== 5. create happy =====
        new_slug = f"{PFX}-new-card"
        created_slugs.append(new_slug)
        r = sc.post("/api/v2/admin/feature-catalog", json={
            "slug": new_slug,
            "title": "Yeni Test Kartı",
            "tagline": "açıklama",
            "domain": "yks",
            "tier": "enhancement",
            "status": "draft",
            "target_roles": ["student"],
            "benefits": ["madde 1", "madde 2"],
            "strategic_priority": 3,
        })
        j = r.json()
        new_card_id = j.get("data", {}).get("card_id")
        ok = (
            r.status_code == 200
            and new_card_id is not None
            and "feature-catalog" in j.get("invalidate", [])[0]
        )
        check("5. create happy", ok, f"status={r.status_code} body={r.text[:200]}")

        # ===== 6. create boş title → 400 =====
        r = sc.post("/api/v2/admin/feature-catalog", json={
            "slug": f"{PFX}-empty", "title": "",
        })
        check("6. create boş title → 400", r.status_code == 400, f"status={r.status_code}")

        # ===== 7. create duplicate slug → 400 =====
        r = sc.post("/api/v2/admin/feature-catalog", json={
            "slug": new_slug, "title": "Çift slug",
        })
        check(
            "7. create duplicate slug → 400",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "feature_card_invalid",
            f"status={r.status_code}",
        )

        # ===== 8. detail happy =====
        r = sc.get(f"/api/v2/admin/feature-catalog/{new_card_id}")
        j = r.json()
        ok = (
            r.status_code == 200
            and j["card"]["slug"] == new_slug
            and j["card"]["benefits"] == ["madde 1", "madde 2"]
            and "meta" in j
        )
        check("8. detail happy", ok, f"status={r.status_code}")

        # ===== 9. update happy =====
        r = sc.post(f"/api/v2/admin/feature-catalog/{new_card_id}", json={
            "slug": new_slug,
            "title": "Güncellendi",
            "tagline": "yeni açıklama",
            "domain": "yks",
            "tier": "core",
            "status": "draft",
            "target_roles": ["student", "parent"],
            "benefits": ["x"],
            "strategic_priority": 5,
        })
        check("9. update happy", r.status_code == 200, f"status={r.status_code} {r.text[:200]}")

        # ===== 10. status change happy =====
        r = sc.post(f"/api/v2/admin/feature-catalog/{new_card_id}/status",
                    json={"status": "published"})
        check("10. status → published", r.status_code == 200, f"status={r.status_code}")

        # ===== 11. pin happy =====
        r = sc.post(f"/api/v2/admin/feature-catalog/{new_card_id}/pin",
                    json={"pinned": True})
        ok = r.status_code == 200 and "sabitlendi" in r.json().get("data", {}).get("message", "")
        check("11. pin happy", ok, f"status={r.status_code}")

        # ===== 12. detail 404 =====
        r = sc.get("/api/v2/admin/feature-catalog/999999")
        check(
            "12. detail 999999 → 404",
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "card_not_found",
            f"status={r.status_code}",
        )

        # ===== 13. dashboard happy =====
        r = sc.get("/api/v2/admin/feature-catalog/dashboard")
        j = r.json()
        ok = (
            r.status_code == 200
            and "summary" in j and "landing_health" in j
            and "last_7d" in j and "anomalies" in j and "recent_audit" in j
        )
        check("13. dashboard happy", ok, f"status={r.status_code}")

        # ===== 14. discovery queue happy =====
        r = sc.get("/api/v2/admin/feature-catalog/discovery-queue")
        j = r.json()
        ok = (
            r.status_code == 200
            and j["counts"]["total"] >= 2
            and any(c["id"] == seed["disc_id"] for c in j["cards"])
        )
        check("14. discovery queue happy", ok, f"status={r.status_code} counts={j.get('counts')}")

        # ===== 15. reject happy =====
        r = sc.post(f"/api/v2/admin/feature-catalog/{seed['disc_id']}/reject")
        ok = r.status_code == 200 and "reddedildi" in r.json().get("data", {}).get("message", "")
        check("15. reject happy", ok, f"status={r.status_code}")
        # reddedilen artık kuyrukta görünmemeli
        r = sc.get("/api/v2/admin/feature-catalog/discovery-queue")
        still = any(c["id"] == seed["disc_id"] for c in r.json()["cards"])
        check("15b. reddedilen kuyruktan düştü", not still, "hâlâ görünüyor")

        # ===== 16. bulk delete happy =====
        r = sc.post("/api/v2/admin/feature-catalog/discovery-queue/bulk",
                    json={"action": "delete", "ids": [seed["disc2_id"]]})
        ok = r.status_code == 200 and r.json().get("data", {}).get("affected") == 1
        check("16. bulk delete happy", ok, f"status={r.status_code}")

        # ===== 17. experiments list =====
        r = sc.get("/api/v2/admin/feature-catalog/experiments")
        check("17. experiments list happy", r.status_code == 200 and "experiments" in r.json(),
              f"status={r.status_code}")

        # ===== 18. experiments new meta =====
        r = sc.get("/api/v2/admin/feature-catalog/experiments/new")
        ok = r.status_code == 200 and len(r.json().get("strategies", [])) == 3
        check("18. experiments new meta", ok, f"status={r.status_code}")

        # ===== 19. experiments create happy =====
        r = sc.post("/api/v2/admin/feature-catalog/experiments", json={
            "name": f"{PFX} Deney",
            "ctrl_strategy": "hybrid_full",
            "test_strategy": "fuzzy_only",
            "weight_ctrl": 50,
            "weight_test": 50,
        })
        j = r.json()
        exp_id = j.get("data", {}).get("experiment_id")
        check("19. experiments create happy", r.status_code == 200 and exp_id is not None,
              f"status={r.status_code} {r.text[:200]}")

        # ===== 20. experiments invalid weights → 400 =====
        r = sc.post("/api/v2/admin/feature-catalog/experiments", json={
            "name": f"{PFX} Bad", "weight_ctrl": 60, "weight_test": 50,
        })
        check("20. experiments invalid weights → 400", r.status_code == 400, f"status={r.status_code}")

        # ===== 21. experiment detail happy =====
        r = sc.get(f"/api/v2/admin/feature-catalog/experiments/{exp_id}")
        j = r.json()
        ok = (
            r.status_code == 200
            and j["experiment"]["id"] == exp_id
            and len(j["stats"]) == 2
            and j["has_any_data"] is False
        )
        check("21. experiment detail happy", ok, f"status={r.status_code}")

        # ===== 22. experiment status running =====
        r = sc.post(f"/api/v2/admin/feature-catalog/experiments/{exp_id}/status",
                    json={"status": "running"})
        check("22. experiment status running", r.status_code == 200, f"status={r.status_code}")

        # ===== 23. card delete happy =====
        r = sc.post(f"/api/v2/admin/feature-catalog/{new_card_id}/delete")
        ok = r.status_code == 200 and "silindi" in r.json().get("data", {}).get("message", "")
        check("23. card delete happy", ok, f"status={r.status_code}")

    finally:
        _cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
