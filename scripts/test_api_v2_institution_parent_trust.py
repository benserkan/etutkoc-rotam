"""API v2 /institution/parent-trust (Veli Güveni Görünürlüğü) smoke (KP3).

Senaryolar:
   1. Teacher → 403
   2. Anonim → 401
   3. happy şekil (summary + channels)
   4. veli kapsaması doğru (2 öğrenciden 1'i bağlı → %50)
   5. bekleyen davet sayılır
   6. bildirim teslimat: sent/failed + success_pct + kanal kırılımı
   7. days parametresi kabul
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
    AuditLog, Institution, NotificationChannel, NotificationKind, NotificationLog,
    NotificationStatus, ParentInvitation, ParentStudentLink, User, UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2ipt{secrets.token_hex(3)}"
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
PASSWORD = "PtPass1!@xyz"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed():
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} K", slug=f"{PFX}-k", contact_email=f"{PFX}@t.invalid",
                           plan="free", is_active=True)
        db.add(inst); db.flush()
        admin = User(email=ADMIN_EMAIL, password_hash=pwd, full_name=f"{PFX} Admin",
                     role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id, is_active=True,
                     password_changed_at=now, must_change_password=False, email_verified_at=now)
        teacher = User(email=f"{PFX}_t@t.invalid", password_hash=pwd, full_name=f"{PFX} Koç",
                       role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
                       password_changed_at=now, must_change_password=False, email_verified_at=now)
        db.add_all([admin, teacher]); db.flush()
        s1 = User(email=f"{PFX}_s1@t.invalid", password_hash=pwd, full_name="Öğr Bir",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=teacher.id, is_active=True)
        s2 = User(email=f"{PFX}_s2@t.invalid", password_hash=pwd, full_name="Öğr İki",
                  role=UserRole.STUDENT, institution_id=inst.id, teacher_id=teacher.id, is_active=True)
        db.add_all([s1, s2]); db.flush()
        # Veli: s1'e bağlı (aktif), s2 bağsız (kapsama %50)
        parent = User(email=f"{PFX}_p@t.invalid", password_hash=pwd, full_name="Veli",
                      role=UserRole.PARENT, is_active=True, last_login_at=now,
                      password_changed_at=now, must_change_password=False, email_verified_at=now)
        db.add(parent); db.flush()
        db.add(ParentStudentLink(parent_id=parent.id, student_id=s1.id, relation="anne", is_primary=True))
        # s2 için bekleyen davet
        db.add(ParentInvitation(invited_email=f"{PFX}_veli2@t.invalid", student_id=s2.id,
                                invited_by_id=teacher.id, relation="baba", is_primary=True,
                                token=f"{PFX}_inv_{secrets.token_hex(5)}",
                                expires_at=now + timedelta(days=7)))
        # Bildirim: s1 velisine 3 sent + 1 failed (email)
        for i in range(3):
            db.add(NotificationLog(parent_id=parent.id, student_id=s1.id,
                                   kind=NotificationKind.DAILY_SUMMARY, channel=NotificationChannel.EMAIL,
                                   status=NotificationStatus.SENT, queued_at=now, sent_at=now))
        db.add(NotificationLog(parent_id=parent.id, student_id=s1.id,
                               kind=NotificationKind.DAILY_SUMMARY, channel=NotificationChannel.EMAIL,
                               status=NotificationStatus.FAILED, queued_at=now, error="smtp"))
        db.flush()
        out = {"inst_id": inst.id, "admin_id": admin.id, "teacher_id": teacher.id,
               "parent_id": parent.id, "s_ids": [s1.id, s2.id]}
        db.commit()
        return out


def _cleanup(seed):
    with SessionLocal() as db:
        db.execute(sa_delete(NotificationLog).where(NotificationLog.student_id.in_(seed["s_ids"])))
        db.execute(sa_delete(ParentInvitation).where(ParentInvitation.student_id.in_(seed["s_ids"])))
        db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(seed["s_ids"])))
        uids = [seed["admin_id"], seed["teacher_id"], seed["parent_id"], *seed["s_ids"]]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {r.status_code}")
    return c


def main():
    print(f"\n=== API v2 /institution/parent-trust smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        ac = _login(ADMIN_EMAIL)
        tc = _login(f"{PFX}_t@t.invalid")

        r = tc.get("/api/v2/institution/parent-trust")
        check("1. Teacher → 403", r.status_code == 403, f"status={r.status_code}")

        r = TestClient(app).get("/api/v2/institution/parent-trust")
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        r = ac.get("/api/v2/institution/parent-trust")
        j = r.json()
        ok = r.status_code == 200 and "summary" in j and "channels" in j
        check("3. happy şekil", ok, f"status={r.status_code} {r.text[:120]}")

        s = j["summary"]
        check("4. kapsama %50 (2 öğr, 1 bağlı)",
              s["total_students"] == 2 and s["covered_students"] == 1 and s["coverage_pct"] == 50,
              f"{s}")
        check("4b. aktif veli=1, parent_count=1",
              s["active_parents"] == 1 and s["parent_count"] == 1, f"{s}")
        check("5. bekleyen davet=1", s["pending_invites"] == 1, f"pending={s['pending_invites']}")
        check("6. bildirim 3 sent + 1 failed → %75",
              s["notif_sent"] == 3 and s["notif_failed"] == 1 and s["notif_success_pct"] == 75, f"{s}")

        email_ch = next((c for c in j["channels"] if c["channel"] == "email"), None)
        check("6b. email kanal kırılımı", email_ch is not None and email_ch["sent"] == 3 and email_ch["success_pct"] == 75,
              f"{email_ch}")

        r = ac.get("/api/v2/institution/parent-trust?days=7")
        check("7. days=7 kabul", r.status_code == 200 and r.json()["summary"]["days"] == 7, f"status={r.status_code}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
