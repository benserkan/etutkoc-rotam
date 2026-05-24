"""CANLI kurum logosu (co-branding) — gerçek çalışan sunucuya HTTP + cookie jar.

Tarayıcı yolu: POST /api/v2/auth/login → cookie → admin logo yükle → serve →
/me logo_url → sayfa render. (Next.js :3000 → rewrite → FastAPI :8081.)

Kullanım:  python scripts/live_institution_logo.py [BASE_URL]
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import AuditLog, Institution, User, UserRole
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
PFX = f"livelogo_{secrets.token_hex(3)}"
PWD = hash_password("LiveLogo!23")
PWDH = "LiveLogo!23"
now = datetime.now(timezone.utc)
PNG = b"\x89PNG\r\n\x1a\n" + b"LIVE-LOGO-" * 8

passed = 0
failed: list[str] = []
ctx: dict = {}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        sa = User(email=f"{PFX}_sa@test.invalid", password_hash=PWD, full_name=f"{PFX} SA",
                  role=UserRole.SUPER_ADMIN, institution_id=None, is_active=True,
                  password_changed_at=now, must_change_password=False, email_verified_at=now)
        db.add(sa); db.flush()
        inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k", plan="etut_standart", is_active=True)
        db.add(inst); db.flush()

        def mk(local, role):
            return User(email=f"{PFX}_{local}@test.invalid", password_hash=PWD, full_name=f"{PFX} {local}",
                        role=role, institution_id=inst.id, is_active=True, password_changed_at=now,
                        must_change_password=False, email_verified_at=now)

        adm = mk("adm", UserRole.INSTITUTION_ADMIN)
        tch = mk("tch", UserRole.TEACHER)
        db.add_all([adm, tch]); db.commit()
        ctx.update(inst_id=inst.id, sa_id=sa.id, adm_id=adm.id, tch_id=tch.id)


def login(local) -> httpx.Client:
    get_login_limiter().reset()
    c = httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=False)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{local}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {local} @ {BASE}: {r.status_code} {r.text[:200]}")
    return c


def main() -> int:
    print(f"\n=== CANLI KURUM LOGOSU — BASE={BASE} — {PFX} ===\n")
    setup()
    iid = ctx["inst_id"]
    try:
        sa = login("sa"); adm = login("adm"); tch = login("tch")

        # 0. tazelik: admin detayda has_logo alanı var mı
        r = sa.get(f"/api/v2/admin/institutions/{iid}")
        fresh = r.status_code == 200 and "has_logo" in r.json().get("institution", {})
        check("0. backend güncel (has_logo alanı mevcut)", fresh, f"{r.status_code} — :8081 STALE olabilir")

        # 1. süper admin logo yükler
        r = sa.post(f"/api/v2/admin/institutions/{iid}/logo",
                    files={"file": ("logo.png", PNG, "image/png")})
        check("1. Süper admin logo yükler → 200 + has_logo",
              r.status_code == 200 and r.json()["data"]["institution"]["has_logo"] is True, f"{r.status_code} {r.text[:140]}")

        # 2. /me kurum yöneticisi → logo_url
        r = adm.get("/api/v2/me")
        inst = r.json().get("institution") or {}
        check("2. Kurum yöneticisi /me → has_logo + logo_url",
              inst.get("has_logo") is True and inst.get("logo_url"), f"{inst}")

        # 3. öğretmen /me → logo_url (co-branding kaynağı)
        r = tch.get("/api/v2/me")
        tinst = r.json().get("institution") or {}
        check("3. Bağlı öğretmen /me → has_logo + logo_url",
              tinst.get("has_logo") is True and tinst.get("logo_url"), f"{tinst}")

        # 4. logo serve (öğretmen) → içerik birebir
        r = tch.get(f"/api/v2/institution/logo/{iid}")
        check("4. Öğretmen logo serve → 200 + içerik birebir",
              r.status_code == 200 and r.content == PNG, f"{r.status_code} len={len(r.content)}")

        # 5. sayfa render (co-branding header'lı paneller)
        if BASE.endswith(":3000"):
            print("\nSayfa render (Next.js :3000):")
            for path, who in [("/institution", adm), ("/teacher/dashboard", tch),
                              (f"/admin/institutions/{iid}", sa)]:
                rr = who.get(path, follow_redirects=True)
                check(f"PAGE {path} → 200", rr.status_code == 200, f"{rr.status_code}")

        # 6. kaldır → serve 404
        sa.post(f"/api/v2/admin/institutions/{iid}/logo/delete")
        r = adm.get(f"/api/v2/institution/logo/{iid}")
        check("6. Kaldırınca serve → 404", r.status_code == 404, f"{r.status_code}")

        for c in (sa, adm, tch):
            c.close()

    finally:
        with SessionLocal() as db:
            uids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if uids:
                db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
                db.execute(sa_delete(User).where(User.id.in_(uids)))
            if ctx.get("inst_id"):
                db.execute(sa_delete(Institution).where(Institution.id == ctx["inst_id"]))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
