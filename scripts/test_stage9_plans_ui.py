"""Stage 9 (Faz 2.3) — Plan + Add-on UI HTTP smoke test.

Senaryolar:
1. /pricing public — 200, B2C+B2B sekmeleri + add-on katalog görünür
2. /plans/me anonim → 303 → /login
3. /plans/me bağımsız öğretmen → 200, plan adı + trial banner
4. /plans/me kurumlu institution_admin → 200, kurum adı görünür
5. /plans/me öğrenci → 303 → /
6. /plans/me super admin → 303 → /admin
7. /addons bağımsız öğretmen → 200, katalog 3 add-on
8. POST /addons/ai_plus/activate → 303 → /addons?activated=1; DB'de Addon
9. POST /addons/{id}/cancel → 303 → /addons?cancelled=1; cancelled_at SET
10. /addons öğrenci → 303 (yetki yok)
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, get_db
from app.main import app
from app.models import (
    Addon,
    AddonKind,
    CreditAccount,
    Institution,
    PlanChangeHistory,
    User,
    UserRole,
)
from app.services.plans import start_solo_trial


PFX = f"_ui9_{secrets.token_hex(3)}"
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
    now = datetime.now(timezone.utc)

    # --- SEED ---
    print("\n=== SEED ===")
    with SessionLocal() as db:
        # Bağımsız öğretmen + trial
        teacher = User(
            email=f"{PFX}_solo@test.invalid", password_hash="x" * 60,
            full_name="UI Solo Teacher", role=UserRole.TEACHER,
            institution_id=None, is_active=True, password_changed_at=now,
            plan="free",
        )
        # Kurum + admin + öğrenci
        inst = Institution(
            name=f"{PFX}_inst", slug=f"{PFX}-inst",
            plan="solo_trial",   # init plan
            is_active=True,
        )
        db.add_all([teacher, inst]); db.flush()
        teacher_id, inst_id = teacher.id, inst.id

        admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash="x" * 60,
            full_name="UI Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        student = User(
            email=f"{PFX}_stu@test.invalid", password_hash="x" * 60,
            full_name="UI Student", role=UserRole.STUDENT,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        super_admin = User(
            email=f"{PFX}_sa@test.invalid", password_hash="x" * 60,
            full_name="UI Super", role=UserRole.SUPER_ADMIN,
            institution_id=None, is_active=True, password_changed_at=now,
        )
        db.add_all([admin, student, super_admin]); db.commit()
        admin_id, student_id, sa_id = admin.id, student.id, super_admin.id

        # Bağımsız öğretmen için trial
        teacher = db.get(User, teacher_id)
        start_solo_trial(db, user=teacher)

    # --- HELPER: dependency override ---
    # joinedload + expunge — template lazy-load yapmasın
    def make_user_override(uid: int):
        def _ov():
            with SessionLocal() as _db:
                u = (
                    _db.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == uid)
                    .first()
                )
                if u is not None:
                    # Tüm ilişkili nesneleri merge ediyoruz; lazy load tetiklenmesin
                    if u.institution is not None:
                        _db.expunge(u.institution)
                    _db.expunge(u)
                return u
        return _ov

    client = TestClient(app)

    # ============ STEP 1: /pricing public ============
    print("\n=== STEP 1: /pricing public ===")
    app.dependency_overrides.clear()
    r = client.get("/pricing")
    check("pricing 200", r.status_code == 200, f"got {r.status_code}")
    body = r.text
    check("'Planlar ve Fiyatlar' başlığı", "Planlar ve Fiyatlar" in body)
    check("solo plan kartları (Solo Pro)", "Solo Pro" in body)
    check("kurum plan kartları (Etüt Standart)", "Etüt Standart" in body)
    check("60 gün performans garantisi", "60 Gün Performans" in body)
    check("akademik yıl banner'ı", "Akademik Yıl" in body)
    check("yaz pause banner'ı", "Yaz Pause" in body)
    check("add-on katalog (AI Plus)", "AI Plus" in body)
    check("add-on katalog (Veli Portalı)", "Veli Portalı" in body)
    check("hero CTA — 14 Gün Ücretsiz Başla", "14 Gün Ücretsiz" in body)

    # ============ STEP 2: /plans/me anonim ============
    print("\n=== STEP 2: /plans/me anonim → /login ===")
    r = client.get("/plans/me", follow_redirects=False)
    check("anonim → 303", r.status_code in (302, 303))
    check("redirect → /login", r.headers.get("location", "").endswith("/login"))

    # ============ STEP 3: /plans/me bağımsız öğretmen ============
    print("\n=== STEP 3: /plans/me bağımsız öğretmen ===")
    app.dependency_overrides[get_current_user] = make_user_override(teacher_id)
    r = client.get("/plans/me")
    check("solo teacher → 200", r.status_code == 200)
    body = r.text
    check("plan adı '14 Günlük Pro Deneme' veya 'Solo'",
          "Pro Deneme" in body or "Solo" in body)
    check("trial countdown banner görünür",
          "deneyiminiz aktif" in body or "kaldı" in body)
    check("Plan Değişim Geçmişi başlığı", "Plan Değişim Geçmişi" in body)
    app.dependency_overrides.clear()

    # ============ STEP 4: /plans/me kurum admin ============
    print("\n=== STEP 4: /plans/me kurum admin ===")
    app.dependency_overrides[get_current_user] = make_user_override(admin_id)
    r = client.get("/plans/me")
    check("admin → 200", r.status_code == 200)
    check("kurum adı görünür", PFX in r.text)
    app.dependency_overrides.clear()

    # ============ STEP 5: /plans/me öğrenci ============
    print("\n=== STEP 5: /plans/me öğrenci → / ===")
    app.dependency_overrides[get_current_user] = make_user_override(student_id)
    r = client.get("/plans/me", follow_redirects=False)
    check("öğrenci → 303", r.status_code in (302, 303))
    check("redirect → /", r.headers.get("location", "") == "/")
    app.dependency_overrides.clear()

    # ============ STEP 6: /plans/me super admin ============
    print("\n=== STEP 6: /plans/me super admin → /admin ===")
    app.dependency_overrides[get_current_user] = make_user_override(sa_id)
    r = client.get("/plans/me", follow_redirects=False)
    check("super admin → 303", r.status_code in (302, 303))
    check("redirect → /admin", r.headers.get("location", "") == "/admin")
    app.dependency_overrides.clear()

    # ============ STEP 7: /addons solo teacher ============
    print("\n=== STEP 7: /addons solo teacher ===")
    app.dependency_overrides[get_current_user] = make_user_override(teacher_id)
    r = client.get("/addons")
    check("solo teacher → 200", r.status_code == 200)
    body = r.text
    check("Ek Paketler başlığı", "Ek Paketler" in body)
    check("AI Plus katalog", "AI Plus" in body)
    check("WhatsApp Veli Paketi katalog", "WhatsApp Veli" in body)
    check("Veli Portalı katalog", "Veli Portalı" in body)
    check("aktive et butonu", "Aktive Et" in body)
    app.dependency_overrides.clear()

    # ============ STEP 8: POST /addons/ai_plus/activate ============
    print("\n=== STEP 8: POST /addons/ai_plus/activate ===")
    app.dependency_overrides[get_current_user] = make_user_override(teacher_id)
    r = client.post("/addons/ai_plus/activate", follow_redirects=False)
    check("activate → 303", r.status_code in (302, 303),
          f"got {r.status_code}")
    check("redirect → /addons?activated=1",
          r.headers.get("location", "").endswith("/addons?activated=1"))
    # DB'de var mı?
    with SessionLocal() as db:
        ad = (
            db.query(Addon)
            .filter(
                Addon.owner_type == "user",
                Addon.owner_id == teacher_id,
                Addon.addon_kind == AddonKind.AI_PLUS,
            )
            .first()
        )
        check("DB'de AI_PLUS Addon kaydı oluştu",
              ad is not None, "kayıt yok")
        if ad:
            ai_plus_id = ad.id
            check("price_try = 149", ad.price_try == 149)
            check("auto_renew = True", ad.auto_renew is True)
            check("note doğru", ad.note and "self-serve" in (ad.note or ""))

    # /addons GET — 'activated=1' query string ile başarı mesajı görünür
    r = client.get("/addons?activated=1")
    check("activated=1 ile sayfa 200", r.status_code == 200)
    check("aktive edildi mesajı", "aktive edildi" in r.text.lower())
    check("AI Plus 'Aktif' rozeti",
          "Aktif" in r.text or "✓" in r.text)
    app.dependency_overrides.clear()

    # ============ STEP 9: POST /addons/{id}/cancel ============
    print("\n=== STEP 9: POST /addons/{id}/cancel ===")
    app.dependency_overrides[get_current_user] = make_user_override(teacher_id)
    r = client.post(f"/addons/{ai_plus_id}/cancel", follow_redirects=False)
    check("cancel → 303", r.status_code in (302, 303))
    check("redirect → /addons?cancelled=1",
          r.headers.get("location", "").endswith("/addons?cancelled=1"))
    with SessionLocal() as db:
        ad = db.get(Addon, ai_plus_id)
        check("cancelled_at SET", ad.cancelled_at is not None)
        check("auto_renew=False", ad.auto_renew is False)
        check("cancelled_by_user_id = teacher_id",
              ad.cancelled_by_user_id == teacher_id)

    r = client.get("/addons?cancelled=1")
    check("cancelled=1 ile sayfa 200", r.status_code == 200)
    check("iptal mesajı", "iptal" in r.text.lower())
    app.dependency_overrides.clear()

    # ============ STEP 10: /addons öğrenci yetkisiz ============
    print("\n=== STEP 10: /addons öğrenci → / ===")
    app.dependency_overrides[get_current_user] = make_user_override(student_id)
    r = client.get("/addons", follow_redirects=False)
    check("öğrenci → 303", r.status_code in (302, 303))
    app.dependency_overrides.clear()

    # ============ STEP 11: Yetki — kurumlu öğretmen kurum add-on aktive edemez ============
    print("\n=== STEP 11: kurumlu teacher kurum add-on aktive edemez ===")
    # Kurum içine bir teacher ekle
    with SessionLocal() as db:
        inst_teacher = User(
            email=f"{PFX}_inst_t@test.invalid", password_hash="x" * 60,
            full_name="Inst Teacher", role=UserRole.TEACHER,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        db.add(inst_teacher); db.commit()
        inst_teacher_id = inst_teacher.id

    app.dependency_overrides[get_current_user] = make_user_override(inst_teacher_id)
    r = client.post("/addons/ai_plus/activate", follow_redirects=False)
    check("kurumlu teacher → 403",
          r.status_code == 403, f"got {r.status_code}")
    app.dependency_overrides.clear()

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        ids = [teacher_id, admin_id, student_id, sa_id, inst_teacher_id]
        db.execute(delete(Addon).where(Addon.owner_id.in_(ids + [inst_id])))
        db.execute(delete(PlanChangeHistory).where(PlanChangeHistory.owner_id.in_(ids + [inst_id])))
        db.execute(delete(CreditAccount).where(CreditAccount.owner_id.in_(ids + [inst_id])))
        db.execute(delete(User).where(User.id.in_(ids)))
        db.execute(delete(Institution).where(Institution.id == inst_id))
        db.commit()
    print("  cleanup OK")

    # --- Sonuç ---
    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
