"""M5 ext — Demo Sessions (list + delete) smoke.

Senaryolar (12):
   1. POST /admin/demo-seed + label="ABC Etüt" → 200, response'da seed_id + label
   2. GET /admin/demo-sessions → liste, az önceki seansı içerir
   3. Liste item: kind + label + user_count + student_count + created_at doğru
   4. İkinci seans (institution + farklı label) → liste 2 satır olur
   5. solo_coach kind → institution_id None
   6. AdminUserListItem.is_demo + demo_label dolu (rozet için)
   7. POST /demo-sessions/{seed_id}/delete → sayım: users+institutions+tasks+exams+sessions
   8. Silinen seansa ait kullanıcılar User tablosundan gitmiş
   9. Diğer demo seans bozulmamış (bağımsız silinmiş)
  10. Gerçek (is_demo=False) kullanıcılar etkilenmemiş
  11. Anon → 401 (list + delete)
  12. TEACHER → 403 role_required
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
from app.models import (
    Institution,
    SuspiciousIp,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2dl_{secrets.token_hex(3)}"
ADMIN_EMAIL = f"{PFX}_a@test.invalid"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
REAL_USER_EMAIL = f"{PFX}_real@test.invalid"
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
        admin = User(
            email=ADMIN_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="DL Test Admin", role=UserRole.SUPER_ADMIN,
            is_active=True,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="DL Test Koç", role=UserRole.TEACHER,
            is_active=True, plan="solo_pro",
        )
        # Gerçek (non-demo) kullanıcı — silmediğimizi doğrulamak için
        real_user = User(
            email=REAL_USER_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Gerçek Kullanıcı", role=UserRole.STUDENT,
            is_active=True, grade_level=8,
            is_demo=False,
        )
        db.add_all([admin, teacher, real_user])
        db.commit()
        return {
            "admin_id": admin.id,
            "teacher_id": teacher.id,
            "real_user_id": real_user.id,
        }


def _cleanup(seed: dict, *, demo_seed_ids: list[str]) -> None:
    from app.services.demo_seed import delete_demo_session
    with SessionLocal() as db:
        # Henüz silinmemiş demo seansları sil
        for sid in demo_seed_ids:
            try:
                delete_demo_session(db, seed_id=sid)
            except Exception:
                pass
        db.commit()
        db.execute(sa_delete(User).where(User.email.in_([
            ADMIN_EMAIL, TEACHER_EMAIL, REAL_USER_EMAIL,
        ])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(client: TestClient, email: str) -> int:
    get_login_limiter().reset()
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    return r.status_code


def main() -> int:
    print(f"\n=== M5 ext demo sessions smoke — prefix: {PFX} ===\n")
    seed = _seed()
    created_seeds: list[str] = []

    try:
        client = TestClient(app)
        assert _login(client, ADMIN_EMAIL) == 200

        # ===== 1. POST + label =====
        r = client.post(
            "/api/v2/admin/demo-seed",
            json={"kind": "institution", "label": "ABC Etüt için"},
        )
        body = r.json() if r.text else {}
        seed_id_1 = body.get("seed_id", "")
        created_seeds.append(seed_id_1)
        ok = (
            r.status_code == 200
            and len(seed_id_1) == 32
            and body.get("label") == "ABC Etüt için"
        )
        check("1. POST + label → 200, seed_id + label",
              ok, f"status={r.status_code} seed_id={seed_id_1[:10]} label={body.get('label')}")

        # ===== 2. GET liste içerir =====
        r = client.get("/api/v2/admin/demo-sessions")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        match = next((it for it in items if it["seed_id"] == seed_id_1), None)
        check("2. GET /demo-sessions seed_id_1 içerir",
              r.status_code == 200 and match is not None,
              f"status={r.status_code} items={len(items)}")

        # ===== 3. item alanları doğru =====
        ok = (
            match is not None
            and match["kind"] == "institution"
            and match["label"] == "ABC Etüt için"
            and match["user_count"] == 4
            and match["student_count"] == 1
            and match.get("institution_id") is not None
            and match.get("institution_name") is not None
        )
        check("3. item kind/label/user_count/student_count/kurum dolu",
              ok, f"item={match}")

        # ===== 4. İkinci seans + label =====
        r = client.post(
            "/api/v2/admin/demo-seed",
            json={"kind": "institution", "label": "XYZ Dershane"},
        )
        seed_id_2 = r.json().get("seed_id", "")
        created_seeds.append(seed_id_2)

        r = client.get("/api/v2/admin/demo-sessions")
        items = r.json().get("items", [])
        ok = (
            len([it for it in items if it["seed_id"] in (seed_id_1, seed_id_2)]) == 2
            and seed_id_1 != seed_id_2
        )
        check("4. iki seans paralel listede",
              ok, f"matched={[it['seed_id'][:8] for it in items if it['seed_id'] in (seed_id_1, seed_id_2)]}")

        # ===== 5. solo_coach → institution_id None =====
        r = client.post(
            "/api/v2/admin/demo-seed",
            json={"kind": "solo_coach", "label": "Solo Demo"},
        )
        body = r.json()
        seed_id_3 = body.get("seed_id", "")
        created_seeds.append(seed_id_3)
        ok = (
            body.get("kind") == "solo_coach"
            and body.get("institution_id") is None
        )
        check("5. solo_coach kind → institution_id None",
              ok, f"inst_id={body.get('institution_id')} kind={body.get('kind')}")

        # ===== 6. AdminUserListItem.is_demo + demo_label =====
        # Demo kullanıcıyı user listesinden bul
        r = client.get(f"/api/v2/admin/users?q=demo-{seed_id_1[:8]}")
        body = r.json() if r.text else {}
        items = body.get("items", [])
        demo_user = items[0] if items else None
        ok = (
            demo_user is not None
            and demo_user.get("is_demo") is True
            and demo_user.get("demo_label") == "ABC Etüt için"
        )
        check("6. AdminUserListItem.is_demo + demo_label dolu",
              ok, f"items={len(items)} is_demo={demo_user.get('is_demo') if demo_user else None}")

        # ===== 7. DELETE seans + sayım =====
        r = client.post(f"/api/v2/admin/demo-sessions/{seed_id_1}/delete")
        body = r.json() if r.text else {}
        ok = (
            r.status_code == 200
            and body.get("users_deleted") == 4
            and body.get("institutions_deleted") == 1
            and body.get("tasks_deleted", 0) >= 1
            and body.get("exams_deleted", 0) >= 1
        )
        check("7. DELETE seans_1 → 4 user + 1 institution + görev/deneme",
              ok, f"body={body}")
        # Silindi, listeden çıkar
        created_seeds = [s for s in created_seeds if s != seed_id_1]

        # ===== 8. seans_1 kullanıcıları DB'de yok =====
        with SessionLocal() as db:
            remaining = db.query(User).filter(User.demo_seed_id == seed_id_1).count()
            inst_remaining = db.query(Institution).filter(
                Institution.demo_seed_id == seed_id_1
            ).count()
            ok = remaining == 0 and inst_remaining == 0
            check("8. seans_1 user + institution DB'de yok",
                  ok, f"users={remaining} insts={inst_remaining}")

        # ===== 9. seans_2 + seans_3 hâlâ var =====
        with SessionLocal() as db:
            s2_users = db.query(User).filter(User.demo_seed_id == seed_id_2).count()
            s3_users = db.query(User).filter(User.demo_seed_id == seed_id_3).count()
            ok = s2_users == 4 and s3_users == 5
            check("9. diğer iki seans bağımsız korundu",
                  ok, f"s2={s2_users} s3={s3_users}")

        # ===== 10. Gerçek kullanıcı etkilenmemiş =====
        with SessionLocal() as db:
            real = db.get(User, seed["real_user_id"])
            ok = real is not None and real.is_demo is False
            check("10. gerçek (non-demo) kullanıcı bozulmadı",
                  ok, f"real exists={real is not None} is_demo={real.is_demo if real else None}")

        # ===== 11. Anon → 401 =====
        anon = TestClient(app)
        r1 = anon.get("/api/v2/admin/demo-sessions")
        r2 = anon.post(f"/api/v2/admin/demo-sessions/{seed_id_2}/delete")
        ok = r1.status_code == 401 and r2.status_code == 401
        check("11. anon → 401 (list + delete)",
              ok, f"list={r1.status_code} delete={r2.status_code}")

        # ===== 12. TEACHER → 403 role_required =====
        tc = TestClient(app)
        assert _login(tc, TEACHER_EMAIL) == 200
        r1 = tc.get("/api/v2/admin/demo-sessions")
        r2 = tc.post(f"/api/v2/admin/demo-sessions/{seed_id_2}/delete")
        ok = (
            r1.status_code == 403
            and r2.status_code == 403
            and r1.json().get("detail", {}).get("code") == "role_required"
        )
        check("12. TEACHER → 403 role_required",
              ok, f"list={r1.status_code} delete={r2.status_code}")

    finally:
        _cleanup(seed, demo_seed_ids=created_seeds)

    total = passed + len(failed)
    print(f"\n=== Sonuç: {passed}/{total} geçti ===\n")
    if failed:
        print("Başarısız senaryolar:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
