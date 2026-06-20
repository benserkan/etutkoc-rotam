"""API v2 /admin/communication-health + /communication-log smoke (Faz 2c).

Senaryolar:
   1. Anonim → 401 (overview)
   2. Teacher → 403 (overview)
   3. overview happy: 4 kanal + her kanalda window/last24h + success_pct
   4. overview success_pct doğru (email 3 sent / 1 failed → %75)
   5. log list happy: items + total + sayfalama alanları
   6. log filtre channel=push → yalnız push
   7. log filtre status=failed → yalnız failed
   8. log arama q=alıcı adresi → eşleşen
   9. log Teacher → 403
  10. pagination limit=2 → 2 item + pages hesap
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
from app.models import AuditLog, CommunicationLog, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2commh{secrets.token_hex(3)}"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
TEACHER_EMAIL = f"{PFX}_teacher@test.invalid"
PASSWORD = "TestCommH!23"
ADDR = f"{PFX}-hedef@x.test"

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


def _row(channel, status, **kw):
    return CommunicationLog(
        channel=channel, status=status, created_at=datetime.now(timezone.utc), **kw
    )


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        sa = User(email=SUPER_EMAIL, password_hash=pwd, full_name=f"{PFX} Super",
                  role=UserRole.SUPER_ADMIN, is_active=True,
                  password_changed_at=now, must_change_password=False)
        tc = User(email=TEACHER_EMAIL, password_hash=pwd, full_name=f"{PFX} Teacher",
                  role=UserRole.TEACHER, is_active=True,
                  password_changed_at=now, must_change_password=False)
        db.add_all([sa, tc]); db.flush()
        rows = [
            _row("email", "sent", to_address=ADDR, category=f"{PFX}-wr", subject="rapor"),
            _row("email", "sent", to_address=ADDR, category=f"{PFX}-wr"),
            _row("email", "sent", to_address=ADDR, category=f"{PFX}-wr"),
            _row("email", "failed", to_address=ADDR, category=f"{PFX}-wr", error="boom"),
            _row("push", "sent", to_address="ExponentPushToken[ab…cd]",
                 category=f"{PFX}-p", subject=f"{PFX} push1"),
            _row("push", "suppressed", category=f"{PFX}-p", subject=f"{PFX} push2",
                 error="no_device"),
            _row("whatsapp", "sent", to_address="+90 555 *** ** 33",
                 category=f"{PFX}-wa", subject=f"{PFX} wa"),
            _row("sms", "sent", to_address="905550000001", category=f"{PFX}-sms",
                 subject=f"{PFX} sms"),
        ]
        db.add_all(rows); db.flush()
        out = {"super_id": sa.id, "teacher_id": tc.id,
               "row_ids": [r.id for r in rows]}
        db.commit()
        return out


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        db.execute(sa_delete(CommunicationLog).where(
            CommunicationLog.id.in_(seed["row_ids"])))
        uids = [seed["super_id"], seed["teacher_id"]]
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== /admin/communication-health smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    try:
        sc = _login(SUPER_EMAIL)
        tc = _login(TEACHER_EMAIL)

        # 1. anon 401
        r = TestClient(app).get("/api/v2/admin/communication-health")
        check("1. anon → 401", r.status_code == 401, f"{r.status_code}")

        # 2. teacher 403
        r = tc.get("/api/v2/admin/communication-health")
        check("2. teacher → 403", r.status_code == 403, f"{r.status_code}")

        # 3. overview happy
        r = sc.get("/api/v2/admin/communication-health?days=7")
        j = r.json()
        chans = {c["channel"]: c for c in j.get("channels", [])}
        check("3. overview 4 kanal",
              r.status_code == 200 and set(chans) == {"email", "push", "whatsapp", "sms"},
              f"{r.status_code} {list(chans)}")

        # 4. email success_pct = 3 sent / (3+1) = %75
        em = chans.get("email", {}).get("window", {})
        check("4. email success_pct=75",
              em.get("success_pct") == 75.0 and em.get("sent") >= 3 and em.get("failed") >= 1,
              str(em))

        # 5. log list happy
        r = sc.get(f"/api/v2/admin/communication-log?days=7&q={PFX}")
        j = r.json()
        check("5. log list alanları",
              r.status_code == 200 and "items" in j and "total" in j
              and "pages" in j and j["total"] >= 1, f"{r.status_code} total={j.get('total')}")

        # 6. filtre channel=push
        r = sc.get(f"/api/v2/admin/communication-log?channel=push&q={PFX}")
        j = r.json()
        ok = all(it["channel"] == "push" for it in j["items"]) and len(j["items"]) >= 1
        check("6. channel=push filtresi", ok, str([it["channel"] for it in j["items"]]))

        # 7. filtre status=failed
        r = sc.get(f"/api/v2/admin/communication-log?status=failed&q={PFX}")
        j = r.json()
        ok = all(it["status"] == "failed" for it in j["items"]) and len(j["items"]) >= 1
        check("7. status=failed filtresi", ok, str([it["status"] for it in j["items"]]))

        # 8. arama q=ADDR
        r = sc.get(f"/api/v2/admin/communication-log?q={ADDR}")
        j = r.json()
        ok = j["total"] >= 4 and all(ADDR in (it["to_address"] or "") for it in j["items"])
        check("8. q=alıcı adresi araması", ok, f"total={j['total']}")

        # 9. teacher 403 (log)
        r = tc.get("/api/v2/admin/communication-log")
        check("9. teacher log → 403", r.status_code == 403, f"{r.status_code}")

        # 10. pagination limit=2
        r = sc.get(f"/api/v2/admin/communication-log?q={PFX}&limit=2&page=1")
        j = r.json()
        check("10. pagination limit=2",
              len(j["items"]) == 2 and j["limit"] == 2 and j["pages"] >= 1,
              f"items={len(j['items'])} pages={j['pages']}")

    finally:
        _cleanup(seed)

    print(f"\n=== Result: {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
