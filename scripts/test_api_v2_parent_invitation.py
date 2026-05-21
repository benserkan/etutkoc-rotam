"""API v2 /parent/* davet & unsubscribe smoke (Dalga 5 Paket 2).

Senaryolar (~13):
   1. GET /invitation/{valid_token} → 200 + invited_email + relation_label
   2. GET /invitation/notfound → 400 not_found
   3. GET /invitation/{expired} → 400 expired
   4. GET /invitation/{consumed} → 400 consumed
   5. POST /invitation/{valid}/accept happy → 200 + cookie + new account
   6. /accept name too short → 400 name_required
   7. /accept password < 8 → 400 password_too_short
   8. /accept password mismatch → 400 password_mismatch
   9. /accept kvkk=False → 400 kvkk_not_accepted
  10. /accept email TEACHER ile → 400 email_in_use_other_role
  11. /accept mevcut PARENT (çoklu öğrenci senaryosu) → 200 is_new_account=False
  12. GET /unsubscribe/{token} → 200 unsubscribed
  13. GET /unsubscribe/{token} idempotent → 200 already
  14. GET /unsubscribe/notfound → 200 invalid (sızıntı yok)
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
    NotificationLog,
    ParentInvitation,
    ParentNotificationPref,
    ParentRelation,
    ParentSessionLog,
    ParentStudentLink,
    User,
    UserRole,
)
from app.services.parent_invitation import create_invitation
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2parinv_{secrets.token_hex(3)}"  # lowercase — find_user_by_email lowercase query yapar
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
S1_EMAIL = f"{PFX}_s1@test.invalid"
S2_EMAIL = f"{PFX}_s2@test.invalid"
NEW_PARENT_EMAIL = f"{PFX}_newparent@test.invalid"
EXISTING_PARENT_EMAIL = f"{PFX}_existingparent@test.invalid"
PASSWORD = "TestPassInvit!23"

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
    """1 öğretmen + 2 öğrenci + 1 mevcut PARENT + 4 davet token (valid/expired/consumed/for_existing)."""
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add(teacher)
        db.flush()

        s1 = User(
            email=S1_EMAIL, password_hash=pwd,
            full_name=f"{PFX} S1", role=UserRole.STUDENT,
            teacher_id=teacher.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        s2 = User(
            email=S2_EMAIL, password_hash=pwd,
            full_name=f"{PFX} S2", role=UserRole.STUDENT,
            teacher_id=teacher.id, grade_level=10, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # Mevcut PARENT — çoklu öğrenci senaryosu için
        existing_parent = User(
            email=EXISTING_PARENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Existing Parent", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([s1, s2, existing_parent])
        db.flush()

        # Existing parent zaten S1'e bağlı (anne); davetimiz onu S2'ye bağlayacak
        existing_link = ParentStudentLink(
            parent_id=existing_parent.id, student_id=s1.id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        existing_pref = ParentNotificationPref(
            parent_id=existing_parent.id,
            unsubscribe_token="UNSUB_TOKEN_" + secrets.token_hex(12),
        )
        db.add_all([existing_link, existing_pref])

        # 4 davet:
        # - valid: NEW_PARENT_EMAIL → S1, 7g geçerli
        # - expired: NEW_PARENT_EMAIL → S2, expires_at=past
        # - consumed: NEW_PARENT_EMAIL → S2, consumed_at=now
        # - for_existing: EXISTING_PARENT_EMAIL → S2, valid
        valid_inv = create_invitation(
            db, invited_email=NEW_PARENT_EMAIL,
            student_id=s1.id, invited_by_id=teacher.id,
            relation=ParentRelation.ANNE, is_primary=True,
        )

        # Expired token (manuel — expires_at past)
        expired_inv = ParentInvitation(
            invited_email=NEW_PARENT_EMAIL,
            student_id=s2.id,
            invited_by_id=teacher.id,
            relation=ParentRelation.BABA,
            is_primary=False,
            token=secrets.token_urlsafe(48),
            expires_at=now - timedelta(days=1),
        )
        consumed_inv = ParentInvitation(
            invited_email=NEW_PARENT_EMAIL,
            student_id=s2.id,
            invited_by_id=teacher.id,
            relation=ParentRelation.BABA,
            is_primary=False,
            token=secrets.token_urlsafe(48),
            expires_at=now + timedelta(days=7),
            consumed_at=now,
        )
        for_existing_inv = ParentInvitation(
            invited_email=EXISTING_PARENT_EMAIL,
            student_id=s2.id,
            invited_by_id=teacher.id,
            relation=ParentRelation.BABA,
            is_primary=False,
            token=secrets.token_urlsafe(48),
            expires_at=now + timedelta(days=7),
        )
        db.add_all([expired_inv, consumed_inv, for_existing_inv])
        db.commit()

        return {
            "teacher_id": teacher.id,
            "s1_id": s1.id, "s2_id": s2.id,
            "existing_parent_id": existing_parent.id,
            "unsub_token": existing_pref.unsubscribe_token,
            "valid_token": valid_inv.token,
            "expired_token": expired_inv.token,
            "consumed_token": consumed_inv.token,
            "for_existing_token": for_existing_inv.token,
        }


def _cleanup(seed: dict, extra_user_ids: list[int]) -> None:
    """Test verisini temizle."""
    with SessionLocal() as db:
        parent_ids = [seed["existing_parent_id"]] + extra_user_ids
        student_ids = [seed["s1_id"], seed["s2_id"]]
        all_user_ids = parent_ids + student_ids + [seed["teacher_id"]]

        db.execute(sa_delete(ParentSessionLog).where(
            ParentSessionLog.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(NotificationLog).where(
            NotificationLog.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(ParentNotificationPref).where(
            ParentNotificationPref.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(ParentInvitation).where(
            ParentInvitation.invited_by_id == seed["teacher_id"]
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_user_ids)))
        db.commit()


def main() -> int:
    print(f"\n=== API v2 /parent invitation+unsub smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    print(
        f"  seeded teacher={seed['teacher_id']} s1={seed['s1_id']} s2={seed['s2_id']} "
        f"existing_parent={seed['existing_parent_id']}\n"
    )

    extra_user_ids: list[int] = []
    try:
        c = TestClient(app)

        # ===== 1. GET /invitation/{valid} =====
        r = c.get(f"/api/v2/parent/invitation/{seed['valid_token']}")
        ok = (
            r.status_code == 200
            and r.json().get("invited_email") == NEW_PARENT_EMAIL
            and r.json().get("relation") == "anne"
            and r.json().get("relation_label") == "Anne"
            and r.json().get("is_primary") is True
        )
        check(
            "1. GET /invitation/{valid} → 200 + alanlar dolu",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )

        # ===== 2. GET /invitation/notfound =====
        r = c.get("/api/v2/parent/invitation/bogus_token_xyz")
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "not_found"
        )
        check(
            "2. GET /invitation/notfound → 400 not_found",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 3. GET /invitation/{expired} =====
        r = c.get(f"/api/v2/parent/invitation/{seed['expired_token']}")
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "expired"
        )
        check(
            "3. GET /invitation/{expired} → 400 expired",
            ok,
            f"status={r.status_code}",
        )

        # ===== 4. GET /invitation/{consumed} =====
        r = c.get(f"/api/v2/parent/invitation/{seed['consumed_token']}")
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "consumed"
        )
        check(
            "4. GET /invitation/{consumed} → 400 consumed",
            ok,
            f"status={r.status_code}",
        )

        # ===== 5. /accept name too short =====
        c5 = TestClient(app)
        r = c5.post(
            f"/api/v2/parent/invitation/{seed['valid_token']}/accept",
            json={
                "full_name": "Al",
                "password": "ValidPass123",
                "password_confirm": "ValidPass123",
                "kvkk_accept": True,
            },
        )
        check(
            "5. /accept name<3 → 400 name_required",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "name_required",
            f"status={r.status_code}",
        )

        # ===== 6. /accept password too short =====
        r = c5.post(
            f"/api/v2/parent/invitation/{seed['valid_token']}/accept",
            json={
                "full_name": "Ali Veli",
                "password": "short",
                "password_confirm": "short",
                "kvkk_accept": True,
            },
        )
        check(
            "6. /accept password<8 → 400 password_too_short",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "password_too_short",
            f"status={r.status_code}",
        )

        # ===== 7. /accept password mismatch =====
        r = c5.post(
            f"/api/v2/parent/invitation/{seed['valid_token']}/accept",
            json={
                "full_name": "Ali Veli",
                "password": "ValidPass123",
                "password_confirm": "DifferentPass456",
                "kvkk_accept": True,
            },
        )
        check(
            "7. /accept password mismatch → 400 password_mismatch",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "password_mismatch",
            f"status={r.status_code}",
        )

        # ===== 8. /accept kvkk=False =====
        r = c5.post(
            f"/api/v2/parent/invitation/{seed['valid_token']}/accept",
            json={
                "full_name": "Ali Veli",
                "password": "ValidPass123",
                "password_confirm": "ValidPass123",
                "kvkk_accept": False,
            },
        )
        check(
            "8. /accept kvkk=False → 400 kvkk_not_accepted",
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "kvkk_not_accepted",
            f"status={r.status_code}",
        )

        # ===== 9. /accept happy path — yeni hesap =====
        c9 = TestClient(app)
        r = c9.post(
            f"/api/v2/parent/invitation/{seed['valid_token']}/accept",
            json={
                "full_name": "Ayşe Yılmaz",
                "password": "ValidPass123",
                "password_confirm": "ValidPass123",
                "kvkk_accept": True,
            },
        )
        ok = (
            r.status_code == 200
            and r.json().get("is_new_account") is True
            and r.json().get("email") == NEW_PARENT_EMAIL
            and r.json().get("redirect_url") == "/parent"
        )
        check(
            "9. /accept happy → 200 + is_new_account=True + cookie",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )

        if ok:
            # Yeni veli ID'sini kaydet (cleanup için)
            from app.database import SessionLocal as _SL
            with _SL() as db:
                u = db.query(User).filter(User.email == NEW_PARENT_EMAIL).first()
                if u:
                    extra_user_ids.append(u.id)

            # Cookie kuruldu mu? client'ın oturumu /me'ye gitsin
            r_me = c9.get("/api/v2/me")
            check(
                "9b. /accept sonrası /api/v2/me oturum açık",
                r_me.status_code == 200,
                f"status={r_me.status_code}",
            )

        # ===== 10. /accept aynı token tekrar → consumed =====
        c10 = TestClient(app)
        r = c10.post(
            f"/api/v2/parent/invitation/{seed['valid_token']}/accept",
            json={
                "full_name": "Tekrar Deneme",
                "password": "ValidPass123",
                "password_confirm": "ValidPass123",
                "kvkk_accept": True,
            },
        )
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "consumed"
        )
        check(
            "10. /accept aynı token tekrar → 400 consumed",
            ok,
            f"status={r.status_code}",
        )

        # ===== 11. /accept email TEACHER ile çakışma =====
        # Yeni token üret — invited_email=TEACHER_EMAIL
        with SessionLocal() as db:
            conflict_inv = ParentInvitation(
                invited_email=TEACHER_EMAIL,
                student_id=seed["s1_id"],
                invited_by_id=seed["teacher_id"],
                relation=ParentRelation.DIGER,
                token=secrets.token_urlsafe(48),
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            db.add(conflict_inv)
            db.commit()
            conflict_token = conflict_inv.token

        c11 = TestClient(app)
        r = c11.post(
            f"/api/v2/parent/invitation/{conflict_token}/accept",
            json={
                "full_name": "Çakışma Veli",
                "password": "ValidPass123",
                "password_confirm": "ValidPass123",
                "kvkk_accept": True,
            },
        )
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "email_in_use_other_role"
        )
        check(
            "11. /accept email TEACHER ile → 400 email_in_use_other_role",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 12. /accept mevcut PARENT (çoklu öğrenci) =====
        c12 = TestClient(app)
        r = c12.post(
            f"/api/v2/parent/invitation/{seed['for_existing_token']}/accept",
            json={
                "full_name": "Yeni İsim (yoksayılmalı)",
                "password": "AnyPassword123",
                "password_confirm": "AnyPassword123",
                "kvkk_accept": True,
            },
        )
        ok = (
            r.status_code == 200
            and r.json().get("is_new_account") is False
            and r.json().get("email") == EXISTING_PARENT_EMAIL
        )
        check(
            "12. /accept mevcut PARENT → 200 is_new_account=False",
            ok,
            f"status={r.status_code} body={r.text[:300]}",
        )
        if ok:
            # Çoklu öğrenci: S2 bağlantısı eklendi mi?
            from app.database import SessionLocal as _SL
            with _SL() as db:
                links = db.query(ParentStudentLink).filter(
                    ParentStudentLink.parent_id == seed["existing_parent_id"]
                ).all()
                check(
                    "12b. mevcut PARENT artık 2 çocuğa bağlı",
                    len(links) == 2,
                    f"link_count={len(links)}",
                )

        # ===== 13. GET /unsubscribe/{token} → unsubscribed =====
        r = c.get(f"/api/v2/parent/unsubscribe/{seed['unsub_token']}")
        ok = r.status_code == 200 and r.json().get("status") == "unsubscribed"
        check(
            "13. /unsubscribe → status=unsubscribed",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 14. /unsubscribe idempotent → already =====
        r = c.get(f"/api/v2/parent/unsubscribe/{seed['unsub_token']}")
        ok = r.status_code == 200 and r.json().get("status") == "already"
        check(
            "14. /unsubscribe idempotent → status=already",
            ok,
            f"status={r.status_code}",
        )

        # ===== 15. /unsubscribe bogus → invalid =====
        r = c.get("/api/v2/parent/unsubscribe/bogus_xyz_token")
        ok = r.status_code == 200 and r.json().get("status") == "invalid"
        check(
            "15. /unsubscribe bogus → status=invalid (sızıntı yok)",
            ok,
            f"status={r.status_code}",
        )

    finally:
        _cleanup(seed, extra_user_ids)
        print("\n  test verileri temizlendi")

    print("\n=== SONUÇ ===")
    print(f"  PASSED: {passed}")
    print(f"  FAILED: {len(failed)}")
    if failed:
        for f in failed:
            print(f"    - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
