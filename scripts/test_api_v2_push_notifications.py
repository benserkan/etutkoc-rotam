"""API v2 — Mobil push bildirim (Expo) smoke.

Cihaz token kaydı + gönderim servisi + dispatcher hook'u. Gerçek Expo çağrısı
YOK — `_expo_send` / `send_push_to_user` monkeypatch'lenir.

Senaryolar:
  1. anon POST /me/push-token → 401
  2. koç mobile login + token kaydet → 200, DB'de 1 satır
  3. aynı token tekrar (upsert) → hâlâ 1 satır
  4. token başka kullanıcıdayken kaydet → bu kullanıcıya taşınır
  5. send_push_to_user (mock _expo_send) → mesaj sayısı = token sayısı, gövde doğru
  6. DeviceNotRegistered receipt → token silinir
  7. tokensız kullanıcı → 0 (çağrı yok)
  8. DELETE /me/push-token → satır silinir
  9. dispatcher _maybe_push_parent → EMAIL bildiriminde push tetiklenir (kind→başlık)
"""
from __future__ import annotations

import sys

try:
    sys.path.insert(0, ".")
except Exception:
    pass
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    DevicePushToken,
    NotificationChannel,
    NotificationKind,
    User,
    UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.services import push_notifications as push
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"push_{secrets.token_hex(3)}"
PWDH = "Mobile!23456"
PWD = hash_password(PWDH)
now = datetime.now(timezone.utc)
ctx: dict = {}
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        a = User(email=f"{PFX}_a@test.invalid", password_hash=PWD, full_name=f"{PFX} A",
                 role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_pro",
                 password_changed_at=now, must_change_password=False)
        b = User(email=f"{PFX}_b@test.invalid", password_hash=PWD, full_name=f"{PFX} B",
                 role=UserRole.PARENT, institution_id=None, is_active=True,
                 password_changed_at=now, must_change_password=False)
        db.add(a); db.add(b); db.flush()
        ctx.update(a=a.id, b=b.id)
        db.commit()


def cleanup():
    with SessionLocal() as db:
        ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
        if ids:
            db.execute(sa_delete(DevicePushToken).where(DevicePushToken.user_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def login(c, suffix):
    get_login_limiter().reset()
    r = c.post("/api/v2/auth/login",
               json={"email": f"{PFX}_{suffix}@test.invalid", "password": PWDH, "mobile": True})
    return r.json().get("access_token") if r.status_code == 200 else None


def main() -> int:
    print(f"\n=== PUSH BİLDİRİM — {PFX} ===\n")
    setup()
    try:
        c = TestClient(app)

        # 1. anon → 401
        r = c.post("/api/v2/me/push-token", json={"token": "ExponentPushToken[anon]"})
        check("1. anon push-token → 401", r.status_code == 401, str(r.status_code))

        # 2. koç login + kaydet
        access = login(c, "a")
        hdr = {"Authorization": f"Bearer {access}"}
        tok_a = "ExponentPushToken[AAA111]"
        r = c.post("/api/v2/me/push-token", json={"token": tok_a, "platform": "ios"}, headers=hdr)
        with SessionLocal() as db:
            n = db.query(DevicePushToken).filter(DevicePushToken.token == tok_a).count()
        check("2. token kaydet → 200 + DB 1 satır", r.status_code == 200 and n == 1,
              f"{r.status_code} n={n}")

        # 3. upsert — aynı token tekrar
        r = c.post("/api/v2/me/push-token", json={"token": tok_a, "platform": "ios"}, headers=hdr)
        with SessionLocal() as db:
            n = db.query(DevicePushToken).filter(DevicePushToken.token == tok_a).count()
        check("3. aynı token tekrar → hâlâ 1 satır", r.status_code == 200 and n == 1, f"n={n}")

        # 4. token başka kullanıcıdayken → taşınır
        with SessionLocal() as db:
            db.add(DevicePushToken(user_id=ctx["b"], token="ExponentPushToken[SHARED]", platform="android"))
            db.commit()
        r = c.post("/api/v2/me/push-token", json={"token": "ExponentPushToken[SHARED]"}, headers=hdr)
        with SessionLocal() as db:
            row = db.query(DevicePushToken).filter(DevicePushToken.token == "ExponentPushToken[SHARED]").one()
            moved = row.user_id == ctx["a"]
        check("4. başka kullanıcının token'ı → bu kullanıcıya taşınır", r.status_code == 200 and moved,
              f"user_id={row.user_id} beklenen={ctx['a']}")

        # 5. send_push_to_user — mock _expo_send
        captured = {}

        def fake_send(messages):
            captured["messages"] = messages
            return [{"status": "ok"} for _ in messages]

        orig = push._expo_send
        push._expo_send = fake_send
        try:
            with SessionLocal() as db:
                cnt = push.send_push_to_user(db, user_id=ctx["a"], title="Test",
                                             body="Gövde", data={"type": "x"})
            msgs = captured.get("messages", [])
            ok5 = (cnt == 2 and len(msgs) == 2
                   and all(m["title"] == "Test" and m["body"] == "Gövde"
                           and m["data"] == {"type": "x"} for m in msgs)
                   and {m["to"] for m in msgs} == {tok_a, "ExponentPushToken[SHARED]"})
            check("5. send_push_to_user → 2 cihaza, gövde doğru", ok5,
                  f"cnt={cnt} msgs={len(msgs)}")

            # 6. DeviceNotRegistered → token silinir
            def fake_send_err(messages):
                out = []
                for m in messages:
                    if m["to"] == tok_a:
                        out.append({"status": "error", "details": {"error": "DeviceNotRegistered"}})
                    else:
                        out.append({"status": "ok"})
                return out

            push._expo_send = fake_send_err
            with SessionLocal() as db:
                push.send_push_to_user(db, user_id=ctx["a"], title="T", body="B")
                db.commit()
            with SessionLocal() as db:
                gone = db.query(DevicePushToken).filter(DevicePushToken.token == tok_a).count() == 0
                kept = db.query(DevicePushToken).filter(
                    DevicePushToken.token == "ExponentPushToken[SHARED]").count() == 1
            check("6. DeviceNotRegistered → geçersiz token silinir, geçerli kalır", gone and kept,
                  f"gone={gone} kept={kept}")

            # 7. tokensız kullanıcı → 0, _expo_send çağrılmaz
            called = {"n": 0}

            def count_send(messages):
                called["n"] += 1
                return [{"status": "ok"} for _ in messages]

            push._expo_send = count_send
            with SessionLocal() as db:
                cnt7 = push.send_push_to_user(db, user_id=ctx["b"], title="T", body="B")
            check("7. tokensız kullanıcı → 0 + çağrı yok", cnt7 == 0 and called["n"] == 0,
                  f"cnt={cnt7} called={called['n']}")
        finally:
            push._expo_send = orig

        # 8. DELETE → satır silinir
        r = c.request("DELETE", "/api/v2/me/push-token",
                      params={"token": "ExponentPushToken[SHARED]"}, headers=hdr)
        with SessionLocal() as db:
            left = db.query(DevicePushToken).filter(DevicePushToken.user_id == ctx["a"]).count()
        check("8. DELETE push-token → satır silinir", r.status_code == 200 and left == 0,
              f"{r.status_code} left={left}")

        # 9. dispatcher _maybe_push_parent → EMAIL bildiriminde push (kind→başlık)
        import app.services.notification_dispatcher as nd

        cap = {}
        orig_send = push.send_push_to_user

        def spy(db, *, user_id, title, body, data=None):
            cap.update(user_id=user_id, title=title, body=body, data=data)
            return 1

        push.send_push_to_user = spy
        try:
            fake_log = SimpleNamespace(
                kind=NotificationKind.WEEKLY_REPORT,
                subject="Haftalık Rapor — Test Öğrenci",
                parent_id=ctx["b"], student_id=999, channel=NotificationChannel.EMAIL,
            )
            with SessionLocal() as db:
                nd._maybe_push_parent(db, fake_log)
            ok9 = (cap.get("user_id") == ctx["b"] and cap.get("title") == "Haftalık rapor"
                   and "Test Öğrenci" in (cap.get("body") or "")
                   and cap.get("data", {}).get("type") == "parent_notification")
            check("9. dispatcher EMAIL bildirimi → push (kind→'Haftalık rapor')", ok9, str(cap))
        finally:
            push.send_push_to_user = orig_send

    finally:
        cleanup()

    print(f"\n=== SONUÇ: {passed} geçti, {len(failed)} kaldı ===")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
