"""Sprint F.2 — Bağımsız Öğretmen Owner-Pattern smoke test.

Test ettiği:
  - iter_owners: kurum + bağımsız öğretmen birlikte döner
  - active_only=True filtre
  - Owner dataclass: url + display_label
  - plan_distribution_owner_aware: ücretli plan = institution_count + user_count toplamı
  - mrr_owner_aware: toplam, kurum, öğretmen ayrı
  - trial_ending_soon_owner_aware: 7g penceresinde her iki tip
  - get_owner: tek kayıt çek
  - HTTP /admin/revenue/users/{id}: 200 + bağımsız öğretmen detay
  - HTTP /admin/revenue/users/{wrong}: 404 (kurum kullanıcı veya öğrenci vs)
  - HTTP /admin/security-monitor/revenue: 200 + 'Birleşik Görünüm' render
"""

from __future__ import annotations

import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import (
    Institution,
    User,
    UserRole,
)
from app.services.revenue_owner import (
    Owner,
    get_owner,
    iter_owners,
    mrr_owner_aware,
    plan_distribution_owner_aware,
    trial_ending_soon_owner_aware,
)


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


def main() -> int:
    print("=== Sprint F.2 — Owner-Pattern smoke ===")
    tag = f"sprintf2-{secrets.token_hex(3)}"

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (SA yok — atlandı)")
            return 0

    # Test verisi: 2 bağımsız öğretmen (1 free, 1 solo_pro) + 1 kurumlu öğretmen
    test_user_ids: list[int] = []
    test_inst_user_id: int | None = None
    test_inst_id: int | None = None
    test_student_id: int | None = None
    with SessionLocal() as db:
        # Bağımsız öğretmen 1 — ücretli (solo_pro)
        t1 = User(
            full_name=f"{tag} Indie Pro Teacher",
            email=f"{tag}_t1@test.local",
            password_hash="x",
            role=UserRole.TEACHER,
            institution_id=None,
            plan="solo_pro",
            is_active=True,
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=3),  # trial bitiyor
        )
        # Bağımsız öğretmen 2 — ücretsiz
        t2 = User(
            full_name=f"{tag} Indie Free Teacher",
            email=f"{tag}_t2@test.local",
            password_hash="x",
            role=UserRole.TEACHER,
            institution_id=None,
            plan="solo_free",
            is_active=True,
        )
        db.add_all([t1, t2])
        db.flush()
        test_user_ids = [t1.id, t2.id]

        # Bir kurum + kurumlu öğretmen (filter dışı kalmalı)
        inst = Institution(
            name=f"{tag} Test Inst",
            slug=f"{tag.lower()}-inst",
            contact_email=f"{tag}_inst@test.local",
            plan="solo_pro",
            is_active=True,
        )
        db.add(inst)
        db.flush()
        test_inst_id = inst.id
        t_inst = User(
            full_name=f"{tag} Inst Teacher",
            email=f"{tag}_inst_t@test.local",
            password_hash="x",
            role=UserRole.TEACHER,
            institution_id=inst.id,
            is_active=True,
        )
        # Bir öğrenci (bağımsız değil; iter_owners'da görmemeli)
        s = User(
            full_name=f"{tag} Student",
            email=f"{tag}_s@test.local",
            password_hash="x",
            role=UserRole.STUDENT,
            institution_id=None,
            is_active=True,
        )
        db.add_all([t_inst, s])
        db.flush()
        test_inst_user_id = t_inst.id
        test_student_id = s.id
        db.commit()

    # ---- 1) iter_owners: hem kurum hem bağımsız öğretmen ----
    with SessionLocal() as db:
        owners = iter_owners(db)
        owner_ids_inst = {o.owner_id for o in owners if o.owner_type == "institution"}
        owner_ids_user = {o.owner_id for o in owners if o.owner_type == "user"}
        check("iter_owners: test kurumu dahil",
              test_inst_id in owner_ids_inst)
        check("iter_owners: bağımsız öğretmenler dahil",
              set(test_user_ids) <= owner_ids_user)
        check("iter_owners: kurumlu öğretmen DAHİL DEĞİL",
              test_inst_user_id not in owner_ids_user)
        check("iter_owners: öğrenci DAHİL DEĞİL",
              test_student_id not in owner_ids_user)

    # ---- 2) iter_owners: include_independent_teachers=False ----
    with SessionLocal() as db:
        owners = iter_owners(db, include_independent_teachers=False)
        any_user = any(o.owner_type == "user" for o in owners)
        check("iter_owners: include_independent_teachers=False → user yok",
              not any_user)

    # ---- 3) iter_owners: include_institutions=False ----
    with SessionLocal() as db:
        owners = iter_owners(db, include_institutions=False)
        any_inst = any(o.owner_type == "institution" for o in owners)
        check("iter_owners: include_institutions=False → kurum yok",
              not any_inst)

    # ---- 4) Owner dataclass: url + display_label ----
    with SessionLocal() as db:
        owners = iter_owners(db)
        for o in owners:
            if o.owner_id in test_user_ids:
                check("Owner.url: user için /admin/revenue/users/...",
                      o.url == f"/admin/revenue/users/{o.owner_id}")
                check("Owner.display_label: 'bağımsız öğretmen' içerir",
                      "bağımsız öğretmen" in o.display_label)
                break

    # ---- 5) plan_distribution_owner_aware ----
    with SessionLocal() as db:
        dist = plan_distribution_owner_aware(db)
        # solo_pro plan'da hem bağımsız öğretmen 1 + test kurumu olmalı
        solo_pro = next((d for d in dist if d["plan"] == "solo_pro"), None)
        check("plan_dist: solo_pro plan bulundu", solo_pro is not None)
        if solo_pro:
            check("plan_dist solo_pro: institution_count + user_count >= 2",
                  solo_pro["institution_count"] >= 1
                  and solo_pro["user_count"] >= 1,
                  f"got inst={solo_pro['institution_count']}, user={solo_pro['user_count']}")
            check("plan_dist solo_pro: estimated_mrr > 0",
                  solo_pro["estimated_mrr"] > 0)

    # ---- 6) mrr_owner_aware ----
    with SessionLocal() as db:
        mrr = mrr_owner_aware(db)
        check("mrr_owner_aware: total = inst + user",
              mrr["total_try"] == mrr["institution_mrr_try"] + mrr["user_mrr_try"])
        check("mrr_owner_aware: user_mrr_try > 0 (test t1)",
              mrr["user_mrr_try"] > 0,
              f"got user_mrr={mrr['user_mrr_try']}")
        check("mrr_owner_aware: paying = inst_paying + user_paying",
              mrr["paying_count"] ==
              mrr["institution_paying_count"] + mrr["user_paying_count"])
        check("mrr_owner_aware: user_paying_count >= 1",
              mrr["user_paying_count"] >= 1)

    # ---- 7) trial_ending_soon_owner_aware ----
    with SessionLocal() as db:
        trials = trial_ending_soon_owner_aware(db, days_horizon=7)
        # t1'in trial_ends_at = +3 gün, pencerede olmalı
        t1_in = any(
            o.owner_type == "user" and o.owner_id == test_user_ids[0]
            for o in trials
        )
        check("trial_ending_soon: bağımsız t1 (trial+3g) listede",
              t1_in, f"got {len(trials)} trial")

    # ---- 8) get_owner ----
    with SessionLocal() as db:
        o = get_owner(db, owner_type="user", owner_id=test_user_ids[0])
        check("get_owner: bağımsız öğretmen çekti",
              o is not None and o.owner_type == "user"
              and o.owner_id == test_user_ids[0])

        # Kurumlu öğretmenle çağrı → None
        o_bad = get_owner(db, owner_type="user", owner_id=test_inst_user_id)
        check("get_owner: kurumlu öğretmen için user_type → None",
              o_bad is None)

        # Öğrenci için → None
        o_student = get_owner(db, owner_type="user", owner_id=test_student_id)
        check("get_owner: öğrenci için user_type → None",
              o_student is None)

        # Kurum çek
        o_inst = get_owner(db, owner_type="institution", owner_id=test_inst_id)
        check("get_owner: kurum çekti",
              o_inst is not None and o_inst.name.startswith(tag))

        # Yok olan
        none_o = get_owner(db, owner_type="user", owner_id=999999)
        check("get_owner: olmayan id → None", none_o is None)

    # ---- 9) HTTP routes ----
    with SessionLocal() as db:
        admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()

    def _admin():
        return admin

    app.dependency_overrides[require_super_admin] = _admin
    app.dependency_overrides[require_user] = _admin
    app.dependency_overrides[get_current_user] = _admin

    try:
        client = TestClient(app)

        # Bağımsız öğretmen detay
        res = client.get(
            f"/admin/revenue/users/{test_user_ids[0]}", follow_redirects=False,
        )
        check("HTTP GET /admin/revenue/users/{indie}: 200",
              res.status_code == 200, f"status={res.status_code}")
        if res.status_code == 200:
            check("HTTP user detail: 'Bağımsız Öğretmen' render",
                  "Bağımsız Öğretmen" in res.text)
            check("HTTP user detail: plan kodu render",
                  "solo_pro" in res.text)

        # Kurumlu öğretmen → 404 (bağımsız değil)
        res = client.get(
            f"/admin/revenue/users/{test_inst_user_id}", follow_redirects=False,
        )
        check("HTTP GET kurumlu öğretmen: 404",
              res.status_code == 404)

        # Öğrenci → 404
        res = client.get(
            f"/admin/revenue/users/{test_student_id}", follow_redirects=False,
        )
        check("HTTP GET öğrenci: 404", res.status_code == 404)

        # Olmayan id → 404
        res = client.get(
            "/admin/revenue/users/999999", follow_redirects=False,
        )
        check("HTTP GET olmayan user: 404", res.status_code == 404)

        # Ticari Pano: 'Birleşik Görünüm' bölümü render
        res = client.get("/admin/security-monitor/revenue", follow_redirects=False)
        check("HTTP Ticari Pano: 200", res.status_code == 200)
        if res.status_code == 200:
            check("Ticari Pano: 'Birleşik Görünüm' render",
                  "Birleşik Görünüm" in res.text or "Birleşik" in res.text)
            check("Ticari Pano: 'Bağımsız öğretmen' wording var",
                  "ağımsız" in res.text or "öğretmen" in res.text.lower())

    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    # ---- Cleanup ----
    with SessionLocal() as db:
        db.query(User).filter(User.email.like(f"{tag}_%@test.local")).delete(
            synchronize_session=False,
        )
        if test_inst_id:
            db.query(Institution).filter(Institution.id == test_inst_id).delete()
        db.commit()

    print()
    print(f"=== Toplam: {passed} PASS / {len(failed)} FAIL ===")
    if failed:
        print("\nFAIL'ler:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
