"""API v2 — "Koça ilet" (kurum yöneticisi → koç, aşağı yönlü SupportRequest) smoke.

Senaryolar:
   1.  Teacher → notify-coach 403 (yalnız kurum yöneticisi)
   2.  Anonim → 401
   3.  notify-coach happy: talep oluşur (request_id + teacher_id)
   4.  Başka kurumun koçuna ilet → 404 (tenant izolasyonu)
   5.  Koç gelen kutusunda görür (GET /support/inbox) + pending_count
   6.  Koç detay görür (can_manage=True, audience=teacher, target_user_name)
   7.  İlgisiz koç (aynı kurum, hedef değil) gelen kutusunda GÖRMEZ
   8.  Koç cevaplar → status answered; yönetici (talep eden) cevabı görür
   9.  Yönetici "Taleplerim"de görür (is_mine=True, target_user_name dolu)
   10. Koç çözümler → resolved
   11. Başka kurumun koçu bu talebi GET edemez → 404 (cross-tenant)
   12. Sayım: notify sonrası koç pending_count düşer (cevaplayınca)
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
    AuditLog, Institution, SupportRequest, SupportRequestMessage, User, UserRole,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"nc{secrets.token_hex(3)}"
PASSWORD = "NotifyPass1!@xyz"

ADMIN = f"{PFX}_admin@test.invalid"
COACH = f"{PFX}_coach@test.invalid"        # hedef koç (A kurumu)
COACH2 = f"{PFX}_coach2@test.invalid"      # ilgisiz koç (A kurumu)
B_ADMIN = f"{PFX}_badmin@test.invalid"     # B kurumu yöneticisi
B_COACH = f"{PFX}_bcoach@test.invalid"     # B kurumu koçu

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
        a = Institution(name=f"{PFX} A", slug=f"{PFX}-a", contact_email=f"{PFX}a@t.invalid",
                        plan="etut_standart", is_active=True)
        b = Institution(name=f"{PFX} B", slug=f"{PFX}-b", contact_email=f"{PFX}b@t.invalid",
                        plan="etut_standart", is_active=True)
        db.add_all([a, b]); db.flush()

        def mk(email, role, inst, name):
            return User(email=email, password_hash=pwd, full_name=name, role=role,
                        institution_id=inst, is_active=True, password_changed_at=now,
                        must_change_password=False, email_verified_at=now)

        admin = mk(ADMIN, UserRole.INSTITUTION_ADMIN, a.id, f"{PFX} Admin")
        coach = mk(COACH, UserRole.TEACHER, a.id, f"{PFX} Koç Bir")
        coach2 = mk(COACH2, UserRole.TEACHER, a.id, f"{PFX} Koç İki")
        b_admin = mk(B_ADMIN, UserRole.INSTITUTION_ADMIN, b.id, f"{PFX} B Admin")
        b_coach = mk(B_COACH, UserRole.TEACHER, b.id, f"{PFX} B Koç")
        db.add_all([admin, coach, coach2, b_admin, b_coach]); db.flush()
        out = {
            "a_id": a.id, "b_id": b.id,
            "admin_id": admin.id, "coach_id": coach.id, "coach2_id": coach2.id,
            "b_admin_id": b_admin.id, "b_coach_id": b_coach.id,
        }
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        uids = [seed["admin_id"], seed["coach_id"], seed["coach2_id"],
                seed["b_admin_id"], seed["b_coach_id"]]
        # talepler + mesajlar
        reqs = db.query(SupportRequest).filter(
            SupportRequest.requester_id.in_(uids)
        ).all()
        rids = [r.id for r in reqs]
        if rids:
            db.execute(sa_delete(SupportRequestMessage).where(
                SupportRequestMessage.request_id.in_(rids)))
            db.execute(sa_delete(SupportRequest).where(SupportRequest.id.in_(rids)))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.execute(sa_delete(Institution).where(Institution.id.in_([seed["a_id"], seed["b_id"]])))
        db.commit()


def _login(email: str) -> TestClient:
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login fail {email} {r.status_code} {r.text[:120]}")
    return c


def main() -> int:
    print(f"\n=== Koça ilet (notify-coach) smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    req_id = None
    try:
        admin = _login(ADMIN)
        coach = _login(COACH)
        coach2 = _login(COACH2)
        b_admin = _login(B_ADMIN)
        b_coach = _login(B_COACH)

        # 1. teacher → notify-coach 403
        r = coach.post("/api/v2/institution/notify-coach",
                       json={"teacher_id": seed["coach_id"], "student_name": "X"})
        check("1. Teacher → notify-coach 403", r.status_code == 403, f"status={r.status_code}")

        # 2. anonim → 401
        r = TestClient(app).post("/api/v2/institution/notify-coach",
                                 json={"teacher_id": seed["coach_id"]})
        check("2. Anonim → 401", r.status_code == 401, f"status={r.status_code}")

        # 3. notify-coach happy
        r = admin.post("/api/v2/institution/notify-coach", json={
            "teacher_id": seed["coach_id"], "student_name": "Yiğit Eren",
            "context": "burnout", "note": "Tükenmişlik işareti var",
        })
        j = r.json()
        ok = r.status_code == 200 and j["data"]["teacher_id"] == seed["coach_id"] and j["data"]["request_id"]
        check("3. notify-coach happy (talep oluştu)", ok, f"status={r.status_code} {r.text[:160]}")
        req_id = j["data"]["request_id"] if ok else None

        # 4. başka kurumun koçuna ilet → 404
        r = admin.post("/api/v2/institution/notify-coach",
                       json={"teacher_id": seed["b_coach_id"], "student_name": "X"})
        check("4. Cross-tenant koça ilet → 404", r.status_code == 404, f"status={r.status_code}")

        # 5. koç gelen kutusunda görür
        r = coach.get("/api/v2/support/inbox")
        j = r.json()
        found = next((i for i in j["items"] if i["id"] == req_id), None)
        check("5. Koç gelen kutusunda görür + pending≥1",
              found is not None and j["pending_count"] >= 1,
              f"items={[i['id'] for i in j['items']]} pending={j.get('pending_count')}")

        # 6. koç detay: can_manage True, audience teacher, target_user_name
        r = coach.get(f"/api/v2/support/requests/{req_id}")
        j = r.json()
        ok = (r.status_code == 200 and j["can_manage"] is True
              and j["audience"] == "teacher" and j["category"] == "student_risk"
              and j["target_user_id"] == seed["coach_id"])
        check("6. Koç detay (can_manage + audience=teacher + target)", ok, f"{r.status_code} {r.text[:160]}")

        # 7. ilgisiz koç (aynı kurum, hedef değil) görmez
        r = coach2.get("/api/v2/support/inbox")
        j = r.json()
        check("7. İlgisiz koç gelen kutusunda görmez",
              all(i["id"] != req_id for i in j["items"]), f"items={[i['id'] for i in j['items']]}")
        # ve detayına erişemez → 404
        r = coach2.get(f"/api/v2/support/requests/{req_id}")
        check("7b. İlgisiz koç detay → 404", r.status_code == 404, f"status={r.status_code}")

        # 8. koç cevaplar → answered; yönetici görür
        r = coach.post(f"/api/v2/support/requests/{req_id}/reply",
                       json={"body": "Öğrenciyle görüştüm, programı hafiflettim."})
        check("8. Koç cevaplar → 200 + answered",
              r.status_code == 200 and r.json()["data"]["status"] == "answered",
              f"{r.status_code} {r.text[:120]}")

        # 9. yönetici "Taleplerim"de görür
        r = admin.get("/api/v2/support/requests")
        j = r.json()
        mine = next((i for i in j["items"] if i["id"] == req_id), None)
        check("9. Yönetici Taleplerim'de görür (is_mine + target_user_name)",
              mine is not None and mine["is_mine"] is True and mine["target_user_name"],
              f"{mine}")

        # 10. koç çözümler → resolved
        r = coach.post(f"/api/v2/support/requests/{req_id}/resolve")
        check("10. Koç çözümler → resolved",
              r.status_code == 200 and r.json()["data"]["status"] == "resolved",
              f"{r.status_code} {r.text[:120]}")

        # 11. başka kurum koçu bu talebi GET edemez → 404
        r = b_coach.get(f"/api/v2/support/requests/{req_id}")
        check("11. Cross-tenant koç detay → 404", r.status_code == 404, f"status={r.status_code}")

        # 12. çözülünce koç pending 0
        r = coach.get("/api/v2/support/inbox")
        check("12. Çözülünce koç pending_count=0", r.json()["pending_count"] == 0,
              f"pending={r.json().get('pending_count')}")

        # 13. P4b — müdahale geçmişi: yönetici "Koça ilet" geçmişini görür
        r = admin.get("/api/v2/institution/coach-interventions")
        j = r.json()
        hit = next((i for i in j["items"] if i["request_id"] == req_id), None)
        check("13. Müdahale geçmişi → Yiğit Eren + koç adı + status parse",
              hit is not None and hit["student_name"] == "Yiğit Eren"
              and hit["coach_name"] and hit["status"] == "resolved",
              f"{hit}")
        # 13b. başka kurum yöneticisi bu müdahaleyi görmez
        r = b_admin.get("/api/v2/institution/coach-interventions")
        check("13b. Cross-tenant yönetici müdahaleyi görmez",
              all(i["request_id"] != req_id for i in r.json()["items"]),
              f"items={[i['request_id'] for i in r.json()['items']]}")

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
