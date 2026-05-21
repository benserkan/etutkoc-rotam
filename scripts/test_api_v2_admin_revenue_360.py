"""API v2 /admin/revenue 360 + CRM smoke (D6 P7b).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. GET institutions/{id} happy (identity/health/usage/billing/crm/meta)
   4. GET institutions/999999 → 404
   5. GET users/{id} happy (owner/student_health/student_rows/meta)
   6. GET users/999999 → 404
   7. CRM note add (institution) happy
   8. CRM note pin happy
   9. CRM note delete happy
  10. CRM action add (user) happy
  11. CRM action add geçersiz kind → 400
  12. CRM action complete happy
  13. CRM action delete happy
  14. contact save (institution) happy
  15. tag add (institution) happy
  16. tag add geçersiz kind → 400
  17. tag delete happy
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
    CrmAction,
    CrmNote,
    Institution,
    OwnerContact,
    OwnerTag,
    User,
    UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2adp7b{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
STUDENT_EMAIL = f"{PFX}_student@test.invalid"
PASSWORD = "TestPassP7b!23"

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
        inst = Institution(
            name=f"{PFX} Inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="free", is_active=True,
        )
        db.add(inst)
        db.flush()
        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
            role=UserRole.SUPER_ADMIN, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
            role=UserRole.TEACHER, institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add_all([super_admin, teacher])
        db.flush()
        student = User(
            email=STUDENT_EMAIL, password_hash=pwd, full_name=f"{PFX} Student",
            role=UserRole.STUDENT, teacher_id=teacher.id, is_active=True,
            grade_level=8, password_changed_at=now, must_change_password=False,
        )
        db.add(student)
        db.flush()
        out = {
            "inst_id": inst.id, "super_id": super_admin.id,
            "teacher_id": teacher.id, "student_id": student.id,
        }
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        ids = [seed["inst_id"]]
        uids = [seed["super_id"], seed["teacher_id"], seed["student_id"]]
        db.execute(sa_delete(CrmNote).where(
            (CrmNote.institution_id == seed["inst_id"]) | (CrmNote.user_id.in_(uids))
        ))
        db.execute(sa_delete(CrmAction).where(
            (CrmAction.institution_id == seed["inst_id"]) | (CrmAction.user_id.in_(uids))
        ))
        db.execute(sa_delete(OwnerTag).where(
            (OwnerTag.institution_id == seed["inst_id"]) | (OwnerTag.user_id.in_(uids))
        ))
        db.execute(sa_delete(OwnerContact).where(
            (OwnerContact.institution_id == seed["inst_id"]) | (OwnerContact.user_id.in_(uids))
        ))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id.in_(ids)))
        db.commit()


def _login_v2(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== API v2 /admin/revenue 360+CRM smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    iid, tid = seed["inst_id"], seed["teacher_id"]
    print(f"  seeded inst={iid} teacher={tid} student={seed['student_id']}\n")

    try:
        sc = _login_v2(SUPER_EMAIL)
        tc = _login_v2(TEACHER_EMAIL)

        # 1. Teacher → 403
        r = tc.get(f"/api/v2/admin/revenue/institutions/{iid}")
        check("1. Teacher → 403", r.status_code == 403
              and r.json().get("detail", {}).get("code") == "role_required", f"status={r.status_code}")

        # 2. Anonim → 401
        r = TestClient(app).get(f"/api/v2/admin/revenue/institutions/{iid}")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. institution 360 happy
        r = sc.get(f"/api/v2/admin/revenue/institutions/{iid}")
        j = r.json()
        ok = (
            r.status_code == 200
            and j["identity"]["id"] == iid
            and "health" in j and "usage_30d" in j and "billing" in j
            and "crm_notes" in j and "meta" in j
            and len(j["meta"]["action_kinds"]) == 7
            and len(j["meta"]["tag_kinds"]) == 8
        )
        check("3. institution 360 happy", ok, f"status={r.status_code}")

        # 4. institution 404
        r = sc.get("/api/v2/admin/revenue/institutions/999999")
        check("4. institution 404", r.status_code == 404
              and r.json().get("detail", {}).get("code") == "institution_not_found", f"status={r.status_code}")

        # 5. user 360 happy
        r = sc.get(f"/api/v2/admin/revenue/users/{tid}")
        j = r.json()
        ok = (
            r.status_code == 200
            and j["owner"]["owner_id"] == tid
            and j["owner"]["owner_type"] == "user"
            and j["student_count"] == 1
            and len(j["student_rows"]) == 1
            and "meta" in j
        )
        check("5. user 360 happy", ok, f"status={r.status_code} {r.text[:160]}")

        # 6. user 404
        r = sc.get("/api/v2/admin/revenue/users/999999")
        check("6. user 404", r.status_code == 404
              and r.json().get("detail", {}).get("code") == "teacher_not_found", f"status={r.status_code}")

        # 7. note add (institution)
        r = sc.post(f"/api/v2/admin/revenue/institution/{iid}/crm/notes",
                    json={"content": "Test görüşme notu", "pinned": True})
        ok = r.status_code == 200 and "Not eklendi" in r.json().get("data", {}).get("message", "")
        check("7. note add (institution)", ok, f"status={r.status_code} {r.text[:160]}")
        # note id'yi al
        r2 = sc.get(f"/api/v2/admin/revenue/institutions/{iid}")
        note_id = r2.json()["crm_notes"][0]["id"]

        # 8. note pin
        r = sc.post(f"/api/v2/admin/revenue/crm/notes/{note_id}/pin")
        check("8. note pin", r.status_code == 200, f"status={r.status_code}")

        # 9. note delete
        r = sc.post(f"/api/v2/admin/revenue/crm/notes/{note_id}/delete")
        ok = r.status_code == 200 and "silindi" in r.json().get("data", {}).get("message", "")
        check("9. note delete", ok, f"status={r.status_code}")

        # 10. action add (user)
        r = sc.post(f"/api/v2/admin/revenue/user/{tid}/crm/actions",
                    json={"kind": "call", "summary": "Arama yapıldı", "result": "pending", "follow_up_at": "2026-06-01"})
        ok = r.status_code == 200 and "Aksiyon eklendi" in r.json().get("data", {}).get("message", "")
        check("10. action add (user)", ok, f"status={r.status_code} {r.text[:160]}")
        r2 = sc.get(f"/api/v2/admin/revenue/users/{tid}")
        action_id = r2.json()["crm_actions"][0]["id"]

        # 11. action add invalid kind
        r = sc.post(f"/api/v2/admin/revenue/user/{tid}/crm/actions",
                    json={"kind": "not_real", "summary": "x"})
        check("11. action invalid kind → 400", r.status_code == 400
              and r.json().get("detail", {}).get("code") == "invalid_action_kind", f"status={r.status_code}")

        # 12. action complete
        r = sc.post(f"/api/v2/admin/revenue/crm/actions/{action_id}/complete",
                    json={"result": "success", "notes": "Olumlu"})
        ok = r.status_code == 200 and "tamamlandı" in r.json().get("data", {}).get("message", "")
        check("12. action complete", ok, f"status={r.status_code}")

        # 13. action delete
        r = sc.post(f"/api/v2/admin/revenue/crm/actions/{action_id}/delete")
        check("13. action delete", r.status_code == 200, f"status={r.status_code}")

        # 14. contact save (institution)
        r = sc.post(f"/api/v2/admin/revenue/institution/{iid}/contact",
                    json={"responsible_person_name": "Hasan Bey", "phone": "5551112233"})
        ok = r.status_code == 200 and "kaydedildi" in r.json().get("data", {}).get("message", "")
        check("14. contact save", ok, f"status={r.status_code}")
        r2 = sc.get(f"/api/v2/admin/revenue/institutions/{iid}")
        ok2 = r2.json()["owner_contact"]["responsible_person_name"] == "Hasan Bey"
        check("14b. contact persisted", ok2, "kayıt görünmüyor")

        # 15. tag add (institution)
        r = sc.post(f"/api/v2/admin/revenue/institution/{iid}/tags",
                    json={"kind": "vip", "note": "önemli"})
        ok = r.status_code == 200 and "Etiket eklendi" in r.json().get("data", {}).get("message", "")
        check("15. tag add", ok, f"status={r.status_code}")
        r2 = sc.get(f"/api/v2/admin/revenue/institutions/{iid}")
        tag_id = r2.json()["owner_tags"][0]["id"]

        # 16. tag add invalid kind
        r = sc.post(f"/api/v2/admin/revenue/institution/{iid}/tags", json={"kind": "not_real"})
        check("16. tag invalid kind → 400", r.status_code == 400
              and r.json().get("detail", {}).get("code") == "invalid_tag_kind", f"status={r.status_code}")

        # 17. tag delete
        r = sc.post(f"/api/v2/admin/revenue/tags/{tag_id}/delete")
        check("17. tag delete", r.status_code == 200, f"status={r.status_code}")

    finally:
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
