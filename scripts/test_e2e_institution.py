"""E2E Test 2 — Kurumsal kayıt + admin akışı.

Senaryo:
  Super admin kurum oluşturur, kurum yöneticisi davet edilir/oluşturulur,
  kurum yöneticisi öğretmen ekler, öğretmen öğrenci ekler. 30 günlük pilot
  bittiğinde plan downgrade.

Test adımları:
  1. Super admin user oluştur (programatik — UI route yok)
  2. Super admin login + POST /admin/institutions → kurum oluş
  3. start_institution_trial → 30g pilot başlasın
  4. Institution admin oluştur + atama (institution_id)
  5. Admin login + GET /institution 200
  6. Admin öğretmen ekle (POST /institution/teachers)
  7. Yeni öğretmen DB'de + must_change_password=True
  8. Roster için bir öğrenci ekle
  9. Kohort/heatmap/burnout view 200
  10. 30g sonu simülasyon → expire_trials çağır
  11. Plan = institution_free
  12. Tenant isolation: başka kurum öğretmeni A kurumunu görmemeli
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    Institution,
    PlanChangeHistory,
    PlanChangeReason,
    User,
    UserRole,
)
from app.services.security import hash_password
from app.services.plans import (
    INSTITUTION_FREE,
    INSTITUTION_TRIAL,
    expire_trials,
    start_institution_trial,
)


PFX = f"e2e_inst_{secrets.token_hex(3)}"
STRONG_PASSWORD = "TestPass123!@xyz"

passed = 0
failed: list[str] = []
findings: list[dict] = []


def check(label: str, cond: bool, detail: str = "", severity: str = "high") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        findings.append({
            "test": "e2e_institution",
            "label": label,
            "detail": detail,
            "severity": severity,
        })
        print(f"  [FAIL] {label}  ({detail})")


def main() -> int:
    now = datetime.now(timezone.utc)

    # =================================================================
    # STEP 1: Super admin + 2 kurum + admin + öğretmen fixture
    # =================================================================
    print("\n=== STEP 1: Super admin + kurum fixture ===")
    with SessionLocal() as db:
        try:
            pwd_hash = hash_password(STRONG_PASSWORD)
        except Exception as e:
            check("hash_password çalışıyor", False,
                  f"bcrypt/passlib hatası: {e}",
                  "critical")
            return 1

        super_admin = User(
            email=f"{PFX}_super@test.invalid",
            password_hash=pwd_hash,
            full_name="E2E Super Admin",
            role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now,
        )
        db.add(super_admin); db.commit()
        super_admin_id = super_admin.id
    check("super admin oluştu", super_admin_id is not None)

    # =================================================================
    # STEP 2: Super admin login + kurum oluş
    # =================================================================
    print("\n=== STEP 2: Super admin login + kurum oluştur ===")
    super_client = TestClient(app)
    r = super_client.post("/login", data={
        "email": f"{PFX}_super@test.invalid",
        "password": STRONG_PASSWORD,
    }, follow_redirects=False)
    check("super admin login 303",
          r.status_code == 303, f"got {r.status_code}")

    r = super_client.get("/admin")
    check("/admin 200 (super admin)",
          r.status_code == 200, f"got {r.status_code}")

    # POST /admin/institutions
    inst_slug = f"e2e-inst-{secrets.token_hex(2)}"
    r = super_client.post("/admin/institutions", data={
        "name": "E2E Test Kurumu",
        "slug": inst_slug,
        "contact_email": "info@e2e-test.invalid",
        "plan": "institution_free",
    }, follow_redirects=False)
    check("kurum oluştur 303",
          r.status_code in (302, 303), f"got {r.status_code}",
          "high")
    inst_id = None
    with SessionLocal() as db:
        i = db.query(Institution).filter(Institution.slug == inst_slug).first()
        if i:
            inst_id = i.id
    check("kurum DB'de", inst_id is not None)

    # =================================================================
    # STEP 3: 30 günlük pilot başlat (programatik — UI muhtemelen
    #         super_admin'in plan değişimi üzerinden)
    # =================================================================
    print("\n=== STEP 3: 30g pilot başlat ===")
    if inst_id:
        with SessionLocal() as db:
            i = db.query(Institution).filter(Institution.id == inst_id).first()
            try:
                start_institution_trial(db, institution=i, actor_user_id=super_admin_id)
            except Exception as e:
                check("start_institution_trial hata vermedi", False, str(e),
                      "high")
        with SessionLocal() as db:
            i = db.query(Institution).filter(Institution.id == inst_id).first()
            check("kurum plan=institution_trial",
                  i.plan == INSTITUTION_TRIAL, f"got plan={i.plan}")
            check("trial_ends_at +30 gün civarı",
                  i.trial_ends_at is not None
                  and 29 < (i.trial_ends_at.replace(tzinfo=timezone.utc) - now).days <= 30,
                  f"trial_ends_at={i.trial_ends_at}")

    # =================================================================
    # STEP 4: Institution admin user oluştur (programatik — institution_id ile)
    # =================================================================
    print("\n=== STEP 4: Institution admin oluş ===")
    admin_email = f"{PFX}_admin@test.invalid"
    admin_id = None
    if inst_id:
        with SessionLocal() as db:
            admin = User(
                email=admin_email,
                password_hash=hash_password(STRONG_PASSWORD),
                full_name="E2E Kurum Admin",
                role=UserRole.INSTITUTION_ADMIN,
                institution_id=inst_id,
                is_active=True, password_changed_at=now,
            )
            db.add(admin); db.commit()
            admin_id = admin.id
        check("admin oluştu", admin_id is not None)

    # =================================================================
    # STEP 5: Admin login + /institution panel
    # =================================================================
    print("\n=== STEP 5: Admin login + panel ===")
    admin_client = TestClient(app)
    r = admin_client.post("/login", data={
        "email": admin_email,
        "password": STRONG_PASSWORD,
    }, follow_redirects=False)
    check("admin login 303",
          r.status_code == 303, f"got {r.status_code}")

    r = admin_client.get("/institution")
    check("/institution 200 (admin)",
          r.status_code == 200, f"got {r.status_code}")

    # =================================================================
    # STEP 6: Admin öğretmen ekle (/institution/teachers POST)
    # =================================================================
    print("\n=== STEP 6: Admin öğretmen ekle ===")
    teacher_email = f"{PFX}_teach@test.invalid"
    r = admin_client.post("/institution/teachers", data={
        "full_name": "E2E Kurum Öğretmeni",
        "email": teacher_email,
    }, follow_redirects=False)
    check("öğretmen ekle 303",
          r.status_code in (302, 303), f"got {r.status_code}",
          "high")
    teacher_id = None
    with SessionLocal() as db:
        t = db.query(User).filter(User.email == teacher_email).first()
        if t:
            teacher_id = t.id
            check("öğretmen role=TEACHER", t.role == UserRole.TEACHER)
            check("öğretmen institution_id eşleşiyor",
                  t.institution_id == inst_id)
            check("öğretmen must_change_password=True",
                  t.must_change_password is True,
                  "kurum tarafından eklenen öğretmen ilk girişte şifre değiştirmeli",
                  "high")

    # =================================================================
    # STEP 7: Roster — admin öğrenci ekleyebiliyor mu? (/institution/roster)
    # =================================================================
    print("\n=== STEP 7: /institution/roster ve diğer view'lar ===")
    for endpoint in [
        "/institution/teachers",
        "/institution/roster",
        "/institution/at-risk",
        "/institution/cohorts",
        "/institution/activity-heatmap",
        "/institution/burnout",
        "/institution/goals",
    ]:
        r = admin_client.get(endpoint)
        check(f"{endpoint} 200",
              r.status_code == 200, f"got {r.status_code}",
              "medium")

    # =================================================================
    # STEP 8: Tenant isolation — başka kurum admin'i A kurumunu görmemeli
    # =================================================================
    print("\n=== STEP 8: Tenant isolation ===")
    # B kurumu oluştur + B admin'i — FRESH session ile her commit ayrı
    inst_b_id = None
    admin_b_id = None
    with SessionLocal() as db:
        inst_b = Institution(name="E2E B Kurumu", slug=f"e2e-b-{secrets.token_hex(2)}")
        db.add(inst_b)
        db.commit()  # commit immediately
        inst_b_id = inst_b.id
    # Ayrı transaction'da admin_b — connection pool'a senkronizasyon
    fresh_pwd_hash = hash_password(STRONG_PASSWORD)  # her seferinde taze hash
    with SessionLocal() as db:
        admin_b = User(
            email=f"{PFX}_adminb@test.invalid",
            password_hash=fresh_pwd_hash,
            full_name="E2E B Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_b_id, is_active=True,
            password_changed_at=datetime.now(timezone.utc),
        )
        db.add(admin_b)
        db.commit()
        admin_b_id = admin_b.id

    # Yeni session/connection ile login deniyoruz
    admin_b_client = TestClient(app)
    r = admin_b_client.post("/login", data={
        "email": f"{PFX}_adminb@test.invalid",
        "password": STRONG_PASSWORD,
    }, follow_redirects=False)
    # DEBUG: fail durumunda DB'den user'ı oku
    if r.status_code != 303:
        with SessionLocal() as ddb:
            u = ddb.query(User).filter(User.id == admin_b_id).first()
            from app.services.security import verify_password
            print(f"  [DEBUG] user: failed={u.failed_login_count} locked={u.locked_until} active={u.is_active}")
            print(f"  [DEBUG] hash_len={len(u.password_hash)} starts={u.password_hash[:10]} verify={verify_password(STRONG_PASSWORD, u.password_hash)}")
            print(f"  [DEBUG] response body (first 200): {r.text[:200]}")
    check("B admin login 303",
          r.status_code == 303, f"got {r.status_code}; admin_b_id={admin_b_id}")

    # B admin /institution/teachers'da A kurumun öğretmeni görmemeli
    r = admin_b_client.get("/institution/teachers")
    check("B admin /institution/teachers 200",
          r.status_code == 200, f"got {r.status_code}")
    check("B admin A kurumun öğretmenini görmüyor",
          teacher_email not in r.text,
          "TENANT LEAK: B kurumu admin A kurumun öğretmenini listede görüyor",
          "critical")

    # =================================================================
    # STEP 9: Trial expire simülasyonu
    # =================================================================
    print("\n=== STEP 9: 30g pilot expire ===")
    if inst_id:
        with SessionLocal() as db:
            i = db.query(Institution).filter(Institution.id == inst_id).first()
            i.trial_ends_at = datetime.now(timezone.utc) - timedelta(hours=1)
            db.commit()
        try:
            with SessionLocal() as db:
                counts = expire_trials(db, now=datetime.now(timezone.utc))
            check("institutions_expired ≥ 1",
                  counts.get("institutions_expired", 0) >= 1, f"counts={counts}")
        except Exception as e:
            check("expire_trials kurum tarafı hata vermedi", False, str(e),
                  "high")
        with SessionLocal() as db:
            i = db.query(Institution).filter(Institution.id == inst_id).first()
            check("kurum plan=institution_free",
                  i.plan == INSTITUTION_FREE, f"got plan={i.plan}")
            check("trial_ends_at=None", i.trial_ends_at is None)

    # =================================================================
    # CLEANUP
    # =================================================================
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        ids = [uid for uid in [super_admin_id, admin_id, teacher_id, admin_b_id] if uid]
        if ids:
            db.execute(delete(PlanChangeHistory).where(
                PlanChangeHistory.owner_id.in_(ids)
            ))
            db.execute(delete(AuditLog).where(AuditLog.actor_id.in_(ids)))
        # Inst plan history
        for iid in [inst_id, inst_b_id]:
            if iid:
                db.execute(delete(PlanChangeHistory).where(
                    PlanChangeHistory.owner_id == iid
                ))
        if ids:
            db.execute(delete(User).where(User.id.in_(ids)))
        for iid in [inst_id, inst_b_id]:
            if iid:
                db.execute(delete(Institution).where(Institution.id == iid))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    if findings:
        import json
        with open("scripts/.e2e_findings_institution.json", "w", encoding="utf-8") as fh:
            json.dump(findings, fh, ensure_ascii=False, indent=2)
        print(f"\nFindings: scripts/.e2e_findings_institution.json")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
