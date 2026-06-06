"""API v2 Veli↔Koç talep (P3a) smoke — çift yönlü thread.

  1. Veli POST coach-request → 200 (audience=teacher, target=koç)
  2. Veli bağlı olmadığı çocuk → 404
  3. Veli GET /support/requests (mine) → talebi görür
  4. Koç GET /support/inbox → veli talebini görür
  5. Koç cevaplar → 200 (answered)
  6. Veli thread'i görür + cevabı okur
  7. Veli cevaplar → koç görür
  8. Koçsuz öğrenci → 404 coach_not_found
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

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import ParentRelation, ParentStudentLink, User, UserRole
from app.models.support_request import SupportRequest, SupportRequestMessage
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2pcr{secrets.token_hex(3)}"
PW = "ParCoach1!@xyz"

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
    pwd = hash_password(PW)
    with SessionLocal() as db:
        t = User(email=f"{PFX}_t@x.invalid", password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        t2 = User(email=f"{PFX}_t2@x.invalid", password_hash=pwd, full_name=f"{PFX} Koç2",
                  role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([t, t2]); db.flush()
        s = User(email=f"{PFX}_s@x.invalid", password_hash=pwd, full_name="Berra",
                 role=UserRole.STUDENT, is_active=True, grade_level=12, teacher_id=t.id)
        s_other = User(email=f"{PFX}_so@x.invalid", password_hash=pwd, full_name="Başka",
                       role=UserRole.STUDENT, is_active=True, grade_level=12, teacher_id=t2.id)
        s_nocoach = User(email=f"{PFX}_snc@x.invalid", password_hash=pwd, full_name="Koçsuz",
                         role=UserRole.STUDENT, is_active=True, grade_level=12, teacher_id=None)
        p = User(email=f"{PFX}_p@x.invalid", password_hash=pwd, full_name="Veli",
                 role=UserRole.PARENT, is_active=True)
        db.add_all([s, s_other, s_nocoach, p]); db.flush()
        db.add(ParentStudentLink(parent_id=p.id, student_id=s.id, relation=ParentRelation.ANNE, is_primary=True))
        db.add(ParentStudentLink(parent_id=p.id, student_id=s_nocoach.id, relation=ParentRelation.ANNE, is_primary=False))
        out = {"t_id": t.id, "s_id": s.id, "so_id": s_other.id, "snc_id": s_nocoach.id, "p_id": p.id}
        db.commit()
        return out


def _cleanup():
    with SessionLocal() as db:
        ids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}%")).all()]
        if ids:
            reqs = db.query(SupportRequest.id).filter(
                SupportRequest.requester_id.in_(ids)).subquery().select()
            db.execute(sa_delete(SupportRequestMessage).where(SupportRequestMessage.request_id.in_(reqs)))
            db.execute(sa_delete(SupportRequest).where(SupportRequest.requester_id.in_(ids)))
            db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.student_id.in_(ids)))
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PW})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {email} {r.status_code} {r.text[:120]}")
    return c


def main():
    print(f"\n=== Veli↔Koç talep smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()
        pc = _login(f"{PFX}_p@x.invalid")
        tc = _login(f"{PFX}_t@x.invalid")
        sid, soid, sncid = seed["s_id"], seed["so_id"], seed["snc_id"]

        # 1. veli talep oluştur
        r = pc.post(f"/api/v2/parent/students/{sid}/coach-request", json={
            "category": "exam_comment", "subject": "Son deneme hakkında",
            "body": "Berra'nın son TYT denemesini yorumlar mısınız?"})
        j = r.json()
        check("1. Veli coach-request → 200", r.status_code == 200 and j.get("data", {}).get("id"),
              f"status={r.status_code} {r.text[:140]}")
        req_id = j["data"]["id"] if r.status_code == 200 else None

        # 2. bağlı olmadığı çocuk
        r = pc.post(f"/api/v2/parent/students/{soid}/coach-request", json={
            "category": "other", "subject": "x", "body": "y"})
        check("2. Bağlı olmadığı çocuk → 404", r.status_code == 404, f"status={r.status_code}")

        # 3. veli kendi talepleri
        r = pc.get("/api/v2/support/requests")
        j = r.json()
        check("3. Veli /support/requests → talebi görür",
              r.status_code == 200 and any(it["id"] == req_id for it in j.get("items", [])),
              f"status={r.status_code} items={len(j.get('items', []))}")

        # 4. koç gelen kutusu
        r = tc.get("/api/v2/support/inbox")
        j = r.json()
        check("4. Koç /support/inbox → veli talebini görür",
              r.status_code == 200 and any(it["id"] == req_id for it in j.get("items", [])),
              f"status={r.status_code} items={len(j.get('items', []))}")

        # 5. koç cevaplar
        r = tc.post(f"/api/v2/support/requests/{req_id}/reply", json={"body": "Tabii, deneme gelişiminiz iyi."})
        check("5. Koç cevaplar → 200 (answered)",
              r.status_code == 200 and r.json()["data"]["status"] == "answered", f"status={r.status_code} {r.text[:120]}")

        # 6. veli thread + cevap
        r = pc.get(f"/api/v2/support/requests/{req_id}")
        j = r.json()
        msgs = j.get("messages", [])
        check("6. Veli thread'i + koç cevabını görür",
              r.status_code == 200 and any("gelişiminiz iyi" in (m.get("body") or "") for m in msgs),
              f"status={r.status_code} msgs={len(msgs)}")

        # 7. veli cevaplar → koç görür
        r = pc.post(f"/api/v2/support/requests/{req_id}/reply", json={"body": "Teşekkürler, peki matematik için?"})
        check("7. Veli cevaplar → 200", r.status_code == 200, f"status={r.status_code} {r.text[:120]}")
        r = tc.get(f"/api/v2/support/requests/{req_id}")
        check("7b. Koç veli cevabını görür",
              r.status_code == 200 and any("matematik için" in (m.get("body") or "") for m in r.json().get("messages", [])),
              f"status={r.status_code}")

        # 8. koçsuz öğrenci
        r = pc.post(f"/api/v2/parent/students/{sncid}/coach-request", json={
            "category": "other", "subject": "x", "body": "y"})
        check("8. Koçsuz öğrenci → 404 coach_not_found",
              r.status_code == 404 and r.json()["detail"]["code"] == "coach_not_found", f"status={r.status_code} {r.text[:120]}")

    finally:
        _cleanup()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
