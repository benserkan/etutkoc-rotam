"""Sprint 6 — Uçtan uca tenant isolation testi.

İki ayrı kurum (ALPHA + BETA) oluşturur, her birinde admin + teacher + student
+ pending invitation hazırlar. Sonra ALPHA admin'i ile BETA verilerine
erişim denenir — hiçbiri sızdırmamalı.

Kullanım:
    .venv/Scripts/python.exe -m scripts.test_tenant_isolation

Test başarısızlık durumunda non-zero exit kodu döner. Tüm test verileri
sonunda temizlenir (commit edilen değişiklikler de geri alınır — DB'de
artifact bırakmaz).

Bu bir ad-hoc smoke testidir; pytest infra'sı yok. Migration sonrası veya
institution_admin route'u eklenirken/değiştirilirken çalıştırılması beklenir.
"""

from __future__ import annotations

import secrets
import sys
from datetime import datetime, timezone

# Windows console UTF-8 zorla — Türkçe karakter ve oklar için
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, TypeError):
    pass

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditLog,
    Institution,
    Invitation,
    User,
    UserRole,
    invitation_default_expiry,
)
from app.services.security import hash_password


# Test sabitleri — gerçek kullanıcılarla çakışmasın diye benzersiz prefix
PFX = f"_tenant_test_{secrets.token_hex(3)}"
PASSWORD = "TestPass!234567"  # tüm test kullanıcıları için ortak


# ---------------------------- Yardımcılar ----------------------------


class CheckFailed(Exception):
    """Test assertion'ı başarısız oldu."""


_passed = 0
_failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global _passed
    if cond:
        _passed += 1
        print(f"  [PASS] {label}")
    else:
        _failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def login(email: str) -> TestClient:
    """Yeni TestClient + /login POST → oturum cookie'siyle döner."""
    c = TestClient(app)
    r = c.post("/login", data={"email": email, "password": PASSWORD},
               follow_redirects=False)
    if r.status_code != 303:
        raise CheckFailed(f"login failed for {email}: {r.status_code} {r.text[:200]}")
    return c


# ---------------------------- Seed ----------------------------


def seed() -> dict:
    """İki tenant + 1 super_admin + 1 bağımsız teacher kurar.

    Returns: oluşturulan kayıtların id'leri (dict). Cleanup için lazım.
    """
    print("\n=== SEED ===")
    pwd = hash_password(PASSWORD)
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        ids: dict = {"users": [], "institutions": [], "invitations": []}

        for tag in ("ALPHA", "BETA"):
            tag_l = tag.lower()
            inst = Institution(
                name=f"{PFX}_{tag}",
                slug=f"{PFX}-{tag_l}",
                contact_email=f"{tag_l}@test.invalid",
                plan="free",
                is_active=True,
            )
            db.add(inst)
            db.flush()
            ids["institutions"].append(inst.id)

            admin = User(
                email=f"{PFX}_{tag_l}_admin@test.invalid",
                password_hash=pwd, full_name=f"{tag} Admin",
                role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id,
                is_active=True, password_changed_at=now,
                must_change_password=False,
            )
            teacher = User(
                email=f"{PFX}_{tag_l}_teacher@test.invalid",
                password_hash=pwd, full_name=f"{tag} Teacher",
                role=UserRole.TEACHER, institution_id=inst.id,
                is_active=True, password_changed_at=now,
                must_change_password=False,
            )
            db.add_all([admin, teacher])
            db.flush()

            student = User(
                email=f"{PFX}_{tag_l}_student@test.invalid",
                password_hash=pwd, full_name=f"{tag} Student",
                role=UserRole.STUDENT, institution_id=inst.id,
                teacher_id=teacher.id,
                is_active=True, password_changed_at=now,
                must_change_password=False,
            )
            db.add(student)
            db.flush()
            ids["users"] += [admin.id, teacher.id, student.id]

            inv = Invitation(
                token=secrets.token_urlsafe(32),
                email=None,
                full_name=f"{tag} davetli",
                role=UserRole.TEACHER,
                institution_id=inst.id,
                created_by_user_id=admin.id,
                expires_at=invitation_default_expiry(),
            )
            db.add(inv)
            db.flush()
            ids["invitations"].append(inv.id)

            ids[f"{tag}_inst_id"] = inst.id
            ids[f"{tag}_admin_email"] = admin.email
            ids[f"{tag}_admin_id"] = admin.id
            ids[f"{tag}_teacher_id"] = teacher.id
            ids[f"{tag}_student_id"] = student.id
            ids[f"{tag}_inv_id"] = inv.id
            ids[f"{tag}_inv_token"] = inv.token

        # Bağımsız (institution_id=NULL) teacher — hiçbir kuruma görünmemeli
        indep = User(
            email=f"{PFX}_indep_teacher@test.invalid",
            password_hash=pwd, full_name="Bağımsız Test Teacher",
            role=UserRole.TEACHER, institution_id=None,
            is_active=True, password_changed_at=now,
            must_change_password=False,
        )
        db.add(indep)
        db.flush()
        ids["users"].append(indep.id)
        ids["indep_teacher_id"] = indep.id

        db.commit()
        print(
            f"  iki kurum + 6 user + 1 bağımsız teacher + 2 invitation hazır "
            f"(ALPHA={ids['ALPHA_inst_id']}, BETA={ids['BETA_inst_id']})"
        )
        return ids


# ---------------------------- Test akışı ----------------------------


def run_isolation_checks(ids: dict) -> None:
    """ALPHA admin'i ile BETA verisine erişim denenir — hiçbiri sızmamalı."""
    print("\n=== TENANT ISOLATION CHECKS ===")

    alpha = login(ids["ALPHA_admin_email"])
    beta = login(ids["BETA_admin_email"])

    # 1. Dashboard agregaları yalnız kendi kurumu sayar
    print("\n[1] Dashboard — agrega sayım")
    r = alpha.get("/institution")
    check("ALPHA admin dashboard 200", r.status_code == 200, f"got {r.status_code}")
    check("ALPHA dashboard kendi kurum adı görünür",
          f"{PFX}_ALPHA" in r.text,
          "kurum adı görünmedi")
    check("ALPHA dashboard BETA kurum adını GÖRMEZ",
          f"{PFX}_BETA" not in r.text,
          "BETA kurum adı sızdı")
    check("ALPHA dashboard BETA teacher full_name'i GÖRMEZ",
          "BETA Teacher" not in r.text,
          "BETA teacher adı sızdı")

    # 2. Teachers list — sadece kendi kurumun teacher'ları
    print("\n[2] Teachers list — sadece kendi tenant")
    r = alpha.get("/institution/teachers")
    check("ALPHA teachers list 200", r.status_code == 200, f"got {r.status_code}")
    check("ALPHA teachers list ALPHA Teacher görünür",
          "ALPHA Teacher" in r.text)
    check("ALPHA teachers list BETA Teacher GÖZÜKMEZ",
          "BETA Teacher" not in r.text,
          "BETA teacher sızdı")
    check("ALPHA teachers list bağımsız teacher GÖZÜKMEZ",
          "Bağımsız Test Teacher" not in r.text,
          "bağımsız teacher sızdı")

    # 3. Cross-tenant teacher_card — 404 dönmeli
    print("\n[3] Cross-tenant teacher_card erişimi → 404")
    r = alpha.get(f"/institution/teachers/{ids['BETA_teacher_id']}",
                  follow_redirects=False)
    check("GET BETA teacher kartı 404",
          r.status_code == 404, f"got {r.status_code}")

    # Aynı endpoint — kendi teacher'ı için 200
    r = alpha.get(f"/institution/teachers/{ids['ALPHA_teacher_id']}",
                  follow_redirects=False)
    check("GET kendi teacher kartı 200",
          r.status_code == 200, f"got {r.status_code}")

    # 4. Cross-tenant deactivate/activate — 404
    print("\n[4] Cross-tenant deactivate/activate → 404")
    r = alpha.post(f"/institution/teachers/{ids['BETA_teacher_id']}/deactivate",
                   follow_redirects=False)
    check("POST BETA teacher deactivate 404",
          r.status_code == 404, f"got {r.status_code}")
    r = alpha.post(f"/institution/teachers/{ids['BETA_teacher_id']}/activate",
                   follow_redirects=False)
    check("POST BETA teacher activate 404",
          r.status_code == 404, f"got {r.status_code}")

    # Side-effect kontrolü: BETA teacher hâlâ aktif
    with SessionLocal() as db:
        bt = db.get(User, ids["BETA_teacher_id"])
        check("BETA teacher hâlâ aktif (yan etki yok)",
              bt is not None and bt.is_active,
              "BETA teacher state değişmiş!")

    # 5. Roster — sadece kendi öğrencileri
    print("\n[5] Roster — sadece kendi tenant öğrencileri")
    r = alpha.get("/institution/roster")
    check("ALPHA roster 200", r.status_code == 200, f"got {r.status_code}")
    check("ALPHA roster kendi öğrencisi görünür",
          "ALPHA Student" in r.text)
    check("ALPHA roster BETA Student GÖZÜKMEZ",
          "BETA Student" not in r.text,
          "BETA student sızdı")

    # 6. Davetiyeler listesi — sadece kendi kurum
    print("\n[6] Davetiye listesi — sadece kendi tenant")
    r = alpha.get("/institution/invitations")
    check("ALPHA invitations 200", r.status_code == 200, f"got {r.status_code}")
    check("ALPHA invitations ALPHA davetli görünür",
          "ALPHA davetli" in r.text)
    check("ALPHA invitations BETA davetli GÖZÜKMEZ",
          "BETA davetli" not in r.text,
          "BETA invitation sızdı")

    # 7. Cross-tenant davetiye iptali → 404
    print("\n[7] Cross-tenant davetiye iptali → 404")
    r = alpha.post(f"/institution/invitations/{ids['BETA_inv_id']}/revoke",
                   follow_redirects=False)
    check("POST BETA invitation revoke 404",
          r.status_code == 404, f"got {r.status_code}")

    # Side-effect kontrolü: BETA daveti hâlâ pending
    with SessionLocal() as db:
        binv = db.query(Invitation).filter(Invitation.id == ids["BETA_inv_id"]).first()
        check("BETA invitation hâlâ pending (yan etki yok)",
              binv is not None and binv.is_usable,
              "BETA invitation state değişmiş!")

    # 8. BETA admin için ters yön de çalışıyor mu?
    print("\n[8] Ters yön — BETA admin de ALPHA'yı görmemeli")
    r = beta.get("/institution/teachers")
    check("BETA teachers list 200", r.status_code == 200)
    check("BETA teachers list BETA Teacher görünür",
          "BETA Teacher" in r.text)
    check("BETA teachers list ALPHA Teacher GÖZÜKMEZ",
          "ALPHA Teacher" not in r.text,
          "ALPHA teacher sızdı")

    # 9. Anonim erişim — tüm institution route'ları redirect/deny
    print("\n[9] Anonim erişim → 303/403")
    anon = TestClient(app)
    for path in (
        "/institution",
        "/institution/teachers",
        "/institution/roster",
        "/institution/invitations",
    ):
        r = anon.get(path, follow_redirects=False)
        # require_user → 303 to /login; require_institution_admin role check
        # would 403 ama önce require_user koparır, yani 303 bekliyoruz.
        check(f"anon {path} 303",
              r.status_code in (303, 401, 403),
              f"got {r.status_code}")

    # 10. Header bağlam chip'i
    print("\n[10] Header bağlam göstergesi")
    r = alpha.get("/institution")
    check(f"ALPHA header chip kurum adı içerir",
          f"🏢 {PFX}_ALPHA" in r.text,
          "kurum chip'i görünmedi")


def cleanup(ids: dict) -> None:
    """Tüm test verisini sil — DB'de artifact bırakma."""
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        # Audit logs (FK SET NULL ama temiz olsun)
        target_ids = ids["users"] + ids["invitations"] + ids["institutions"]
        if target_ids:
            db.query(AuditLog).filter(
                AuditLog.target_id.in_(target_ids)
            ).delete(synchronize_session=False)
            db.query(AuditLog).filter(
                AuditLog.actor_id.in_(ids["users"])
            ).delete(synchronize_session=False)

        if ids["invitations"]:
            db.query(Invitation).filter(
                Invitation.id.in_(ids["invitations"])
            ).delete(synchronize_session=False)
        if ids["users"]:
            db.query(User).filter(
                User.id.in_(ids["users"])
            ).delete(synchronize_session=False)
        if ids["institutions"]:
            db.query(Institution).filter(
                Institution.id.in_(ids["institutions"])
            ).delete(synchronize_session=False)
        db.commit()
        print("  test artifact'ları silindi")


def main() -> int:
    print(f"Tenant isolation test — prefix: {PFX}")
    ids: dict | None = None
    try:
        ids = seed()
        run_isolation_checks(ids)
    except CheckFailed as e:
        print(f"\nFATAL: {e}")
        return 2
    finally:
        if ids is not None:
            try:
                cleanup(ids)
            except Exception as e:
                print(f"\n!!! cleanup hata: {e}")

    print(f"\n=== SONUÇ ===")
    print(f"  geçen: {_passed}, başarısız: {len(_failed)}")
    if _failed:
        print("\nbasarisiz check'ler:")
        for f in _failed:
            print(f"  - {f}")
        return 1
    print("  [OK] tum tenant isolation check'leri gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
