"""P2 — Süper admin WhatsApp şablon CRUD + preview smoke testleri.

Senaryolar (~15):
   1. GET /admin/whatsapp-templates → 200 + 35 seed (en az)
   2. GET ?category=veli → yalnız veli kategorisi
   3. GET ?target_role=teacher → yalnız teacher
   4. GET ?include_inactive=false → pasif olmayan
   5. GET ?category=invalid → 400 invalid_category
   6. POST /admin/whatsapp-templates → yeni şablon oluşturuldu
   7. POST tekrar aynı key → 409 key_taken
   8. POST geçersiz kategori → 400 invalid_category
   9. POST /admin/whatsapp-templates/{id} update → metni değişti
  10. POST toggle-active → is_active flip
  11. POST delete aktif şablon → 400 template_active
  12. POST delete pasif şablon → 200 silindi
  13. POST preview → değişkenler dolduruldu
  14. POST preview unknown_keys → warning listesi
  15. Rol guard: TEACHER → 403
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    SuspiciousIp,
    User,
    UserRole,
    WhatsAppTemplate,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2wat_{_secrets.token_hex(3)}"
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestWaTmpl!2345"
NEW_KEY = f"smoke_test_template_{_secrets.token_hex(3)}"

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
        admin = User(
            email=ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([admin, teacher])
        db.commit()
        return {"admin_id": admin.id, "teacher_id": teacher.id}


def _cleanup(seed: dict, extra_template_ids: list[int]) -> None:
    with SessionLocal() as db:
        if extra_template_ids:
            db.execute(sa_delete(WhatsAppTemplate).where(
                WhatsAppTemplate.id.in_(extra_template_ids)
            ))
        db.execute(sa_delete(User).where(
            User.id.in_([seed["admin_id"], seed["teacher_id"]])
        ))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def main() -> int:
    print(f"\n=== P2 WA templates smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    extra_ids: list[int] = []

    try:
        c = TestClient(app)
        assert _login(c, ADMIN_EMAIL), "admin login failed"

        # ===== 1. Tüm şablonlar listesi (35 seed dahil) =====
        r = c.get("/api/v2/admin/whatsapp-templates")
        items = r.json().get("items", []) if r.status_code == 200 else []
        ok = (
            r.status_code == 200
            and r.json().get("total", 0) >= 35
            and "categories" in r.json()
            and "target_roles" in r.json()
        )
        check(
            "1. GET liste → 200 + 35+ seed + categories meta",
            ok,
            f"status={r.status_code} total={r.json().get('total')}",
        )

        # ===== 2. ?category=veli =====
        r = c.get("/api/v2/admin/whatsapp-templates?category=veli")
        items = r.json().get("items", []) if r.status_code == 200 else []
        ok = (
            r.status_code == 200
            and len(items) >= 10
            and all(it.get("category") == "veli" for it in items)
        )
        check(
            "2. GET ?category=veli → yalnız veli kategorisi (≥10)",
            ok,
            f"status={r.status_code} count={len(items)}",
        )

        # ===== 3. ?target_role=teacher =====
        r = c.get("/api/v2/admin/whatsapp-templates?target_role=teacher")
        items = r.json().get("items", []) if r.status_code == 200 else []
        ok = (
            r.status_code == 200
            and all(it.get("target_role") == "teacher" for it in items)
        )
        check(
            "3. GET ?target_role=teacher → yalnız teacher hedefli",
            ok,
            f"status={r.status_code} count={len(items)}",
        )

        # ===== 4. include_inactive=false default rol aktifte hepsini gösterir =====
        r = c.get("/api/v2/admin/whatsapp-templates?include_inactive=false")
        items = r.json().get("items", []) if r.status_code == 200 else []
        ok = (
            r.status_code == 200
            and all(it.get("is_active") for it in items)
        )
        check(
            "4. GET ?include_inactive=false → tüm dönen aktif",
            ok,
        )

        # ===== 5. Geçersiz kategori =====
        r = c.get("/api/v2/admin/whatsapp-templates?category=bogus")
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_category"
        )
        check(
            "5. GET ?category=bogus → 400 invalid_category",
            ok,
            f"status={r.status_code}",
        )

        # ===== 6. POST yeni şablon =====
        new_body = {
            "key": NEW_KEY,
            "category": "veli",
            "target_role": "teacher",
            "name_tr": "Smoke Test Şablon",
            "description": "Smoke test için oluşturuldu.",
            "content_template": "Merhaba {{veli_adi}}, bu bir test mesajıdır.",
            "variables": [{"key": "veli_adi", "label_tr": "Veli", "example": "Ayşe"}],
            "requires_date": False,
            "allow_bulk": False,
            "allow_freeform_note": False,
            "sort_order": 200,
            "is_active": True,
        }
        r = c.post("/api/v2/admin/whatsapp-templates", json=new_body)
        new_id = None
        if r.status_code == 200:
            new_id = r.json().get("data", {}).get("id")
            if new_id:
                extra_ids.append(new_id)
        ok = r.status_code == 200 and new_id is not None
        check(
            "6. POST yeni şablon → 200 + id",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 7. POST tekrar aynı key → 409 =====
        r2 = c.post("/api/v2/admin/whatsapp-templates", json=new_body)
        ok = (
            r2.status_code == 409
            and r2.json().get("detail", {}).get("code") == "key_taken"
        )
        check(
            "7. POST aynı key → 409 key_taken",
            ok,
            f"status={r2.status_code}",
        )

        # ===== 8. POST geçersiz kategori =====
        bad_body = dict(new_body, key=NEW_KEY + "_x", category="bogus_cat")
        r3 = c.post("/api/v2/admin/whatsapp-templates", json=bad_body)
        ok = (
            r3.status_code == 400
            and r3.json().get("detail", {}).get("code") == "invalid_category"
        )
        check(
            "8. POST geçersiz kategori → 400 invalid_category",
            ok,
            f"status={r3.status_code}",
        )

        # ===== 9. PUT (POST) update =====
        if new_id:
            upd_body = {
                "category": "ogrenci",
                "target_role": "teacher",
                "name_tr": "Smoke Test Şablon (UPDATED)",
                "description": "Güncellendi.",
                "content_template": "{{ogrenci_adi}}, güncellenmiş mesaj.",
                "variables": [{"key": "ogrenci_adi", "label_tr": "Öğrenci", "example": "Mehmet"}],
                "requires_date": False,
                "allow_bulk": False,
                "allow_freeform_note": False,
                "sort_order": 300,
                "is_active": True,
            }
            r4 = c.post(f"/api/v2/admin/whatsapp-templates/{new_id}", json=upd_body)
            data4 = r4.json().get("data", {})
            ok = (
                r4.status_code == 200
                and data4.get("category") == "ogrenci"
                and data4.get("name_tr") == "Smoke Test Şablon (UPDATED)"
            )
            check(
                "9. POST update → 200 + güncel alanlar",
                ok,
                f"status={r4.status_code}",
            )

        # ===== 10. Toggle active =====
        if new_id:
            r5 = c.post(f"/api/v2/admin/whatsapp-templates/{new_id}/toggle-active")
            ok = (
                r5.status_code == 200
                and r5.json().get("data", {}).get("is_active") is False
            )
            check(
                "10. POST toggle-active → is_active=False",
                ok,
                f"status={r5.status_code}",
            )

        # ===== 11. Delete aktif → 400 =====
        # Önce tekrar aktif et
        if new_id:
            c.post(f"/api/v2/admin/whatsapp-templates/{new_id}/toggle-active")
            r6 = c.post(f"/api/v2/admin/whatsapp-templates/{new_id}/delete")
            ok = (
                r6.status_code == 400
                and r6.json().get("detail", {}).get("code") == "template_active"
            )
            check(
                "11. POST delete aktif → 400 template_active",
                ok,
                f"status={r6.status_code}",
            )

        # ===== 12. Delete pasif → 200 =====
        if new_id:
            c.post(f"/api/v2/admin/whatsapp-templates/{new_id}/toggle-active")  # pasife
            r7 = c.post(f"/api/v2/admin/whatsapp-templates/{new_id}/delete")
            ok = r7.status_code == 200
            check(
                "12. POST delete pasif → 200",
                ok,
                f"status={r7.status_code}",
            )
            extra_ids.remove(new_id)

        # ===== 13. Preview — değişkenler dolduruldu =====
        preview_body = {
            "content_template": "Merhaba {{veli_adi}}, {{ogrenci_adi}} için mesaj.",
            "variables": {"veli_adi": "Ayşe", "ogrenci_adi": "Mehmet"},
            "variable_defs": [
                {"key": "veli_adi", "label_tr": "Veli", "example": "DefaultVeli"},
                {"key": "ogrenci_adi", "label_tr": "Öğrenci", "example": "DefaultOgr"},
            ],
        }
        r8 = c.post("/api/v2/admin/whatsapp-templates/preview", json=preview_body)
        ok = (
            r8.status_code == 200
            and r8.json().get("rendered", "").startswith("Merhaba Ayşe, Mehmet")
            and len(r8.json().get("unknown_keys", [])) == 0
        )
        check(
            "13. POST preview → değişkenler doğru dolduruldu",
            ok,
            f"status={r8.status_code} rendered={r8.json().get('rendered', '')[:80]}",
        )

        # ===== 14. Preview unknown_keys uyarısı =====
        preview_body2 = {
            "content_template": "{{a}} ve {{tanim_yok}} var.",
            "variables": {"a": "X"},
            "variable_defs": [{"key": "a", "label_tr": "A", "example": "AAA"}],
        }
        r9 = c.post("/api/v2/admin/whatsapp-templates/preview", json=preview_body2)
        ok = (
            r9.status_code == 200
            and "tanim_yok" in r9.json().get("unknown_keys", [])
            and len(r9.json().get("warnings", [])) > 0
        )
        check(
            "14. Preview unknown_keys → warning listesi",
            ok,
            f"status={r9.status_code} warnings={r9.json().get('warnings', [])[:2]}",
        )

        # ===== 15. Rol guard — teacher 403 =====
        c_teacher = TestClient(app)
        assert _login(c_teacher, TEACHER_EMAIL), "teacher login failed"
        r10 = c_teacher.get("/api/v2/admin/whatsapp-templates")
        ok = r10.status_code == 403
        check(
            "15. TEACHER → /admin/whatsapp-templates → 403",
            ok,
            f"status={r10.status_code}",
        )

    finally:
        _cleanup(seed, extra_ids)
        get_login_limiter().reset()

    print(f"\n=== Result: {passed} passed, {len(failed)} failed ===\n")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
