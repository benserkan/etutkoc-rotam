"""CANLI "Koça ilet" akışı — gerçek çalışan sunucuya HTTP + cookie jar.

Tarayıcı yolunu sürer: POST /api/v2/auth/login → cookie → /api/v2/... (Next.js
:3000 → rewrite → FastAPI :8081). Her kullanıcı ayrı httpx.Client (ayrı oturum).

Akış: Kurum yöneticisi tükenmişlik/risk panosundan riskli öğrenci için ilgili
koça müdahale talebi açar (POST /institution/notify-coach) → koç bunu "Gelen
Talepler"de görür → cevaplar (rozeti düşer) → yönetici cevabı izler → çözülür.

Kullanım:  python scripts/live_notify_coach_flow.py [BASE_URL]
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
from app.models import (
    Institution, SupportRequest, SupportRequestMessage, User, UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
PFX = f"livenc_{secrets.token_hex(3)}"
PWD = hash_password("LiveNotify!23")
PWDH = "LiveNotify!23"
now = datetime.now(timezone.utc)

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


def traffic(line: str):
    print(f"     ↪ {line}")


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k", plan="etut_standart", is_active=True)
        db.add(inst); db.flush()

        def mk(local, role, name):
            return User(email=f"{PFX}_{local}@test.invalid", password_hash=PWD, full_name=name,
                        role=role, institution_id=inst.id, is_active=True,
                        password_changed_at=now, must_change_password=False, email_verified_at=now)

        adm = mk("adm", UserRole.INSTITUTION_ADMIN, f"{PFX} Yönetici")
        coach = mk("coach", UserRole.TEACHER, f"{PFX} Koç Bir")
        coach2 = mk("coach2", UserRole.TEACHER, f"{PFX} Koç İki")
        db.add_all([adm, coach, coach2]); db.flush()
        ctx.update(inst_id=inst.id, coach_id=coach.id, coach2_id=coach2.id)
        db.commit()


def login(local) -> httpx.Client:
    get_login_limiter().reset()
    c = httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=False)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{local}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {local} @ {BASE}: {r.status_code} {r.text[:200]}")
    return c


def ids(items):
    return {it["id"] for it in items}


def main() -> int:
    print(f"\n=== CANLI KOÇA İLET AKIŞI — BASE={BASE} — {PFX} ===\n")
    setup()
    rid = None
    try:
        adm = login("adm"); coach = login("coach"); coach2 = login("coach2")

        # 0. tazelik: koç badges'inde yeni alan var mı (stale backend tespiti)
        r = coach.get("/api/v2/teacher/badges")
        fresh = r.status_code == 200 and "support_inbox_pending" in r.json()
        check("0. backend güncel (support_inbox_pending alanı mevcut)", fresh,
              f"status={r.status_code} — :8081 STALE olabilir")

        # 1. yönetici koça ilet (tükenmişlik panosu bağlamı)
        r = adm.post("/api/v2/institution/notify-coach", json={
            "teacher_id": ctx["coach_id"], "student_name": "Yiğit Eren",
            "context": "burnout", "note": "Son haftalarda tempo düştü, görüşün.",
        })
        ok = r.status_code == 200 and r.json()["data"]["teacher_id"] == ctx["coach_id"]
        check("1. Yönetici → notify-coach 200 (talep oluştu)", ok, f"{r.status_code} {r.text[:160]}")
        rid = r.json()["data"]["request_id"] if ok else None
        traffic(f"Yönetici → Koç Bir #{rid} talep açtı (Yiğit Eren / tükenmişlik)")

        # 2. koç gelen kutusunda görür + badge ≥1
        inbox = coach.get("/api/v2/support/inbox").json()
        check("2. Koç gelen kutusunda görür", rid in ids(inbox["items"]), f"items={ids(inbox['items'])}")
        b = coach.get("/api/v2/teacher/badges").json()
        check("2b. Koç badge support_inbox_pending ≥1", b.get("support_inbox_pending", 0) >= 1,
              f"badge={b.get('support_inbox_pending')}")
        traffic("Koç Bir 'Gelen Talepler'de görüyor + rozet yandı")

        # 3. ilgisiz koç görmez
        inbox2 = coach2.get("/api/v2/support/inbox").json()
        check("3. İlgisiz koç görmez", rid not in ids(inbox2["items"]), f"items={ids(inbox2['items'])}")

        # 4. koç detay: can_manage + audience teacher + kategori
        d = coach.get(f"/api/v2/support/requests/{rid}").json()
        check("4. Koç detay (can_manage + audience=teacher + student_risk)",
              d.get("can_manage") is True and d.get("audience") == "teacher"
              and d.get("category") == "student_risk", str(d)[:160])

        # 5. koç cevaplar → answered; badge düşer (işleyince azalır)
        r = coach.post(f"/api/v2/support/requests/{rid}/reply",
                       json={"body": "Öğrenciyle görüştüm, programı hafiflettim."})
        check("5. Koç cevaplar → answered", r.json()["data"]["status"] == "answered", f"{r.text[:120]}")
        b = coach.get("/api/v2/teacher/badges").json()
        check("5b. Cevaplayınca badge düşer (support_inbox_pending=0)",
              b.get("support_inbox_pending", 9) == 0, f"badge={b.get('support_inbox_pending')}")
        traffic("Koç cevap yazdı → rozet söndü (işleyince azalır)")

        # 6. yönetici cevabı görür (Taleplerim)
        mine = adm.get("/api/v2/support/requests").json()
        row = next((i for i in mine["items"] if i["id"] == rid), None)
        check("6. Yönetici Taleplerim'de görür (is_mine + target_user_name)",
              row is not None and row["is_mine"] and row.get("target_user_name"), str(row)[:160])
        traffic("Yönetici cevabı izliyor")

        # 7. koç çözümler
        r = coach.post(f"/api/v2/support/requests/{rid}/resolve")
        check("7. Koç çözümler → resolved", r.json()["data"]["status"] == "resolved", f"{r.text[:120]}")

        # 8. panolar + koç gelen kutusu sayfası render
        if BASE.endswith(":3000"):
            print("\nSayfa render (Next.js :3000):")
            for path, who in [("/institution/burnout", adm), ("/institution/at-risk", adm),
                              ("/teacher/support-inbox", coach)]:
                rr = who.get(path, follow_redirects=True)
                check(f"PAGE {path} → 200", rr.status_code == 200, f"{rr.status_code}")

        for c in (adm, coach, coach2):
            c.close()

    finally:
        with SessionLocal() as db:
            uids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if uids:
                rids = [r[0] for r in db.query(SupportRequest.id).filter(
                    SupportRequest.requester_id.in_(uids)).all()]
                if rids:
                    db.execute(sa_delete(SupportRequestMessage).where(
                        SupportRequestMessage.request_id.in_(rids)))
                    db.execute(sa_delete(SupportRequest).where(SupportRequest.id.in_(rids)))
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
