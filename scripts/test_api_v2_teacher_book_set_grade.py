"""API v2 öğretmen 3.5d.8 smoke — BookSet target_grade alanları.

Senaryolar (10):
   1. POST /book-sets — name + target_grade 5-8 → 200, label "5-8. sınıf"
   2. POST /book-sets — graduate only → label "Mezun"
   3. POST /book-sets — target alanları yok → label "Tüm seviyeler"
   4. POST /book-sets — invalid range (min>max) → 422 invalid_target_grade_range
   5. POST /book-sets — min=2 → 422 invalid_target_grade_min
   6. GET /book-sets — listede target alanları + label_tr dolu
   7. PATCH /book-sets/{id} — target_graduate=True ekle
   8. PATCH /book-sets/{id} — clear_target_grade=True → tüm alanlar null
   9. GET /book-sets/{id} — detail target alanları dolu
  10. Cross-tenant patch → 404
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import BookSet, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2_5d8_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
OTHER_TEACHER_EMAIL = f"{PFX}_t2@test.invalid"
PASSWORD = "TestPass123!@xyz"

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
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="V2 5d8 Öğretmen", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        other_teacher = User(
            email=OTHER_TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Diğer 5d8", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        db.add_all([teacher, other_teacher])
        db.commit()
        return {
            "teacher_id": teacher.id,
            "other_teacher_id": other_teacher.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(BookSet).where(
            BookSet.teacher_id.in_([seed["teacher_id"], seed["other_teacher_id"]])
        ))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["teacher_id"], seed["other_teacher_id"],
        ])))
        db.commit()


def _login(client: TestClient, email: str) -> int:
    return client.post(
        "/api/v2/auth/login", json={"email": email, "password": PASSWORD}
    ).status_code


def main() -> int:
    print(f"\n=== API v2 /teacher 5d.8 (book-set target_grade) — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()

    try:
        client = TestClient(app)
        assert _login(client, TEACHER_EMAIL) == 200

        # 1) LGS aralığı
        r = client.post(
            "/api/v2/teacher/library/book-sets",
            json={
                "name": f"LGS Paketi {PFX}",
                "target_grade_min": 5,
                "target_grade_max": 8,
            },
        )
        data = r.json().get("data", {}) if r.text else {}
        set_lgs_id = data.get("id")
        ok = (
            r.status_code == 200
            and data.get("target_grade_min") == 5
            and data.get("target_grade_max") == 8
            and data.get("target_graduate") is False
            and data.get("target_grade_label_tr") == "5-8. sınıf"
        )
        check("1. POST LGS aralığı + label '5-8. sınıf'", ok,
              f"status={r.status_code} label={data.get('target_grade_label_tr')!r}")

        # 2) Sadece mezun
        r = client.post(
            "/api/v2/teacher/library/book-sets",
            json={
                "name": f"Mezun {PFX}",
                "target_graduate": True,
            },
        )
        data = r.json().get("data", {})
        set_grad_id = data.get("id")
        ok = (
            r.status_code == 200
            and data.get("target_graduate") is True
            and data.get("target_grade_label_tr") == "Mezun"
        )
        check("2. POST mezun + label 'Mezun'", ok,
              f"label={data.get('target_grade_label_tr')!r}")

        # 3) Tüm seviyeler (alan yok)
        r = client.post(
            "/api/v2/teacher/library/book-sets",
            json={"name": f"Genel {PFX}"},
        )
        data = r.json().get("data", {})
        set_any_id = data.get("id")
        ok = (
            r.status_code == 200
            and data.get("target_grade_min") is None
            and data.get("target_grade_max") is None
            and data.get("target_grade_label_tr") == "Tüm seviyeler"
        )
        check("3. POST alan yok + label 'Tüm seviyeler'", ok,
              f"label={data.get('target_grade_label_tr')!r}")

        # 4) Invalid range (min>max)
        r = client.post(
            "/api/v2/teacher/library/book-sets",
            json={
                "name": f"Invalid {PFX}",
                "target_grade_min": 10,
                "target_grade_max": 5,
            },
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "invalid_target_grade_range"
        )
        check("4. POST min>max → 422 invalid_target_grade_range", ok,
              f"status={r.status_code}")

        # 5) Min=2 (aralık dışı)
        r = client.post(
            "/api/v2/teacher/library/book-sets",
            json={"name": f"Invalid2 {PFX}", "target_grade_min": 2},
        )
        ok = (
            r.status_code == 422
            and r.json().get("detail", {}).get("code") == "invalid_target_grade_min"
        )
        check("5. POST min=2 → 422 invalid_target_grade_min", ok,
              f"status={r.status_code}")

        # 6) Listede alanlar görünür
        r = client.get("/api/v2/teacher/library/book-sets")
        items = (r.json() or {}).get("items", [])
        lgs_item = next((it for it in items if it["id"] == set_lgs_id), None)
        grad_item = next((it for it in items if it["id"] == set_grad_id), None)
        any_item = next((it for it in items if it["id"] == set_any_id), None)
        ok = (
            r.status_code == 200
            and lgs_item and lgs_item["target_grade_label_tr"] == "5-8. sınıf"
            and grad_item and grad_item["target_grade_label_tr"] == "Mezun"
            and any_item and any_item["target_grade_label_tr"] == "Tüm seviyeler"
        )
        check("6. Listede target alanları + label_tr dolu", ok,
              f"lgs={lgs_item and lgs_item.get('target_grade_label_tr')!r}")

        # 7) PATCH target_graduate ekle (LGS setine "5-8 + Mezun")
        r = client.patch(
            f"/api/v2/teacher/library/book-sets/{set_lgs_id}",
            json={"target_graduate": True},
        )
        data = r.json().get("data", {})
        ok = (
            r.status_code == 200
            and data.get("target_graduate") is True
            and "Mezun" in (data.get("target_grade_label_tr") or "")
        )
        check("7. PATCH target_graduate=True → label içerir 'Mezun'", ok,
              f"label={data.get('target_grade_label_tr')!r}")

        # 8) PATCH clear_target_grade
        r = client.patch(
            f"/api/v2/teacher/library/book-sets/{set_lgs_id}",
            json={"clear_target_grade": True},
        )
        data = r.json().get("data", {})
        ok = (
            r.status_code == 200
            and data.get("target_grade_min") is None
            and data.get("target_grade_max") is None
            and data.get("target_graduate") is False
            and data.get("target_grade_label_tr") == "Tüm seviyeler"
        )
        check("8. PATCH clear_target_grade → 'Tüm seviyeler'", ok,
              f"label={data.get('target_grade_label_tr')!r}")

        # 9) GET detail
        r = client.get(f"/api/v2/teacher/library/book-sets/{set_grad_id}")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("target_graduate") is True
            and body.get("target_grade_label_tr") == "Mezun"
        )
        check("9. GET detail target alanları", ok,
              f"label={body.get('target_grade_label_tr')!r}")

        # 10) Cross-tenant patch
        assert _login(client, OTHER_TEACHER_EMAIL) == 200
        r = client.patch(
            f"/api/v2/teacher/library/book-sets/{set_lgs_id}",
            json={"target_grade_min": 9},
        )
        ok = r.status_code == 404
        check("10. Cross-tenant patch → 404", ok, f"status={r.status_code}")

    finally:
        _cleanup(seed)
        print("\n  cleanup OK\n")

    total = passed + len(failed)
    print(f"\n=== SONUÇ: {passed}/{total} PASS ===")
    if failed:
        for f in failed:
            print(f"  ✗ {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
