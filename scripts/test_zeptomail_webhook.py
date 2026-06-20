"""Faz 2b doğrulama — ZeptoMail bounce/teslimat webhook + apply_email_event.

Senaryolar:
   1. apply_email_event: sent → bounced (reason yazılır)
   2. apply_email_event: sent → delivered
   3. apply_email_event: bounced'ı delivered EZMEZ
   4. apply_email_event: eşleşmeyen alıcı → 0
   5. webhook GET ping → 200
   6. webhook POST hardbounce → ilgili satır bounced + updated>=1
   7. webhook POST delivery → delivered
   8. webhook POST open → delivered (teslimat ima eder)
   9. webhook token: secret varken token yok → 403
  10. webhook token: secret varken doğru token → 200
  11. parser: 2 farklı payload biçimi de alıcı/sebep çözer
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

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import CommunicationLog
from app.services import comm_log
from app.routes.webhooks_zeptomail import _events, _search, _RECIPIENT_KEYS

PFX = f"zwh{secrets.token_hex(3)}"
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


def _seed_email(addr: str, status="sent") -> int:
    with SessionLocal() as db:
        r = CommunicationLog(
            channel="email", status=status, to_address=addr,
            category=f"{PFX}-cat", subject="x",
            created_at=datetime.now(timezone.utc),
        )
        db.add(r); db.commit()
        return r.id


def _status(rid: int) -> tuple[str, str | None]:
    with SessionLocal() as db:
        r = db.get(CommunicationLog, rid)
        return (r.status, r.error) if r else ("?", None)


def _cleanup():
    with SessionLocal() as db:
        db.execute(sa_delete(CommunicationLog).where(
            CommunicationLog.category == f"{PFX}-cat"))
        db.commit()


def main() -> int:
    print(f"\n=== ZeptoMail webhook smoke — prefix: {PFX} ===\n")
    c = TestClient(app)

    # 1. sent → bounced
    a1 = f"{PFX}-1@x.test"
    r1 = _seed_email(a1)
    n = comm_log.apply_email_event(a1, "bounced", reason="mailbox full")
    st, err = _status(r1)
    check("1. sent→bounced + reason", n == 1 and st == "bounced" and err == "mailbox full",
          f"{n} {st} {err}")

    # 2. sent → delivered
    a2 = f"{PFX}-2@x.test"
    r2 = _seed_email(a2)
    n = comm_log.apply_email_event(a2, "delivered")
    check("2. sent→delivered", n == 1 and _status(r2)[0] == "delivered", _status(r2)[0])

    # 3. bounced'ı delivered EZMEZ
    n = comm_log.apply_email_event(a1, "delivered")
    check("3. bounced korunur (delivered ezmez)", n == 0 and _status(r1)[0] == "bounced",
          f"{n} {_status(r1)[0]}")

    # 4. eşleşmeyen alıcı
    n = comm_log.apply_email_event(f"{PFX}-yok@x.test", "delivered")
    check("4. eşleşmeyen → 0", n == 0, str(n))

    # 5. GET ping
    r = c.get("/webhooks/zeptomail")
    check("5. GET ping 200", r.status_code == 200 and r.json().get("ok") is True,
          str(r.status_code))

    # 6. POST hardbounce
    a6 = f"{PFX}-6@x.test"
    r6 = _seed_email(a6)
    payload = {"event_message": [{"event_name": "hardbounce",
               "details": [{"bounced_recipient": a6, "bounce_reason": "user unknown"}]}]}
    r = c.post("/webhooks/zeptomail", json=payload)
    check("6. POST hardbounce → bounced",
          r.status_code == 200 and r.json().get("updated") >= 1
          and _status(r6)[0] == "bounced", f"{r.status_code} {r.json()} {_status(r6)}")

    # 7. POST delivery
    a7 = f"{PFX}-7@x.test"
    r7 = _seed_email(a7)
    payload = {"event_message": [{"event_name": "email_delivery",
               "details": [{"recipient": a7}]}]}
    r = c.post("/webhooks/zeptomail", json=payload)
    check("7. POST delivery → delivered",
          r.json().get("updated") >= 1 and _status(r7)[0] == "delivered",
          f"{r.json()} {_status(r7)}")

    # 8. POST open → delivered
    a8 = f"{PFX}-8@x.test"
    r8 = _seed_email(a8)
    payload = {"event_message": [{"event_name": "email_open",
               "details": [{"email_address": a8}]}]}
    r = c.post("/webhooks/zeptomail", json=payload)
    check("8. POST open → delivered",
          _status(r8)[0] == "delivered", f"{r.json()} {_status(r8)}")

    # 9-10. token güvenliği
    old = settings.zeptomail_webhook_secret
    settings.zeptomail_webhook_secret = "topsecret"
    try:
        r = c.post("/webhooks/zeptomail", json={})
        check("9. secret varken token yok → 403", r.status_code == 403, str(r.status_code))
        r = c.post("/webhooks/zeptomail?token=topsecret", json={})
        check("10. doğru token → 200", r.status_code == 200, str(r.status_code))
    finally:
        settings.zeptomail_webhook_secret = old

    # 11. parser iki biçim
    p_a = {"event_message": [{"event_name": "softbounce",
           "details": [{"bounced_recipient": "a@b.com", "bounce_reason": "full"}]}]}
    p_b = {"event_name": "hardbounce", "email": "c@d.com", "reason": "nope"}
    ra = next(iter(_events(p_a)), None)
    rb = next(iter(_events(p_b)), None)
    ok = (ra and _search(ra[1], _RECIPIENT_KEYS, want_email=True) == "a@b.com"
          and rb and _search(rb[1], _RECIPIENT_KEYS, want_email=True) == "c@d.com")
    check("11. parser 2 biçim alıcı çözer", bool(ok), f"{ra} {rb}")

    _cleanup()
    print(f"\n=== Result: {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
