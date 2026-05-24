"""CANLI test — kurum yöneticisi plan yükseltme TALEBİ akışı (:3000 → :8081).

Akış: kurum (free) + yönetici → /subscription (talep yok, 3 kademe) → talep
gönder (etut_standart) → /subscription (bekliyor + hedef etiket) → tekrar
(idempotent) → süper admin İletişim Talepleri'nde "Abonelik talebi (kurum)" +
kurum linki. Sonunda temizler. Şifrelere dokunmaz.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import Institution, User, UserRole, AuditLog
from app.models.contact_request import ContactRequest
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

B = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
PFX = f"upreq_{secrets.token_hex(3)}"
PWD = "Upgrade!2345aB"
now = datetime.now(timezone.utc)
passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def login(email):
    get_login_limiter().reset()
    c = httpx.Client(base_url=B, timeout=40.0)
    for attempt in range(2):
        r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
        if r.status_code == 200:
            return c
        if r.status_code == 429 and attempt == 0:
            try:
                wait = int(r.json().get("detail", {}).get("retry_after_seconds", 60))
            except Exception:
                wait = 60
            time.sleep(min(wait + 1, 62))
            continue
        raise RuntimeError(f"login {email}: {r.status_code} {r.text[:150]}")
    raise RuntimeError("login rate-limited")


def main() -> int:
    print(f"\n=== CANLI KURUM YÜKSELTME TALEBİ — BASE={B} — {PFX} ===\n")
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Kurum", slug=PFX, plan="free", is_active=True)
        db.add(inst); db.flush()
        iid = inst.id
        adm = User(email=f"{PFX}_adm@t.invalid", password_hash=hash_password(PWD),
                   full_name="Kurum Yon", role=UserRole.INSTITUTION_ADMIN, institution_id=iid,
                   is_active=True, must_change_password=False, password_changed_at=now)
        sadm = User(email=f"{PFX}_super@t.invalid", password_hash=hash_password(PWD),
                    full_name="Super", role=UserRole.SUPER_ADMIN, is_active=True,
                    must_change_password=False, password_changed_at=now)
        db.add_all([adm, sadm]); db.commit()
        aid, sid = adm.id, sadm.id
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_([aid, sid]))); db.commit()

    try:
        ac = login(f"{PFX}_adm@t.invalid")
        r = ac.get("/api/v2/institution/subscription").json()
        chk("1. /subscription: talep yok başlangıçta", r.get("pending_upgrade_request") is False, str(r.get("pending_upgrade_request")))
        chk("1b. 3 kurum kademesi listeleniyor", len(r.get("available_plans", [])) == 3, str([p["code"] for p in r.get("available_plans", [])]))
        chk("1c. plan_label 'Kurum Tanıma'", r.get("plan_label") == "Kurum Tanıma", r.get("plan_label"))

        r2 = ac.post("/api/v2/institution/subscription-request", json={"plan": "etut_standart", "note": "8 koçumuz var"})
        chk("2. talep gönder → 200 ok", r2.status_code == 200 and r2.json()["data"]["ok"] is True, f"{r2.status_code}")

        r3 = ac.get("/api/v2/institution/subscription").json()
        chk("3. /subscription: artık bekliyor", r3.get("pending_upgrade_request") is True, str(r3.get("pending_upgrade_request")))
        chk("3b. hedef paket etiketi 'Etüt Standart'", r3.get("requested_plan_label") == "Etüt Standart", r3.get("requested_plan_label"))

        r4 = ac.post("/api/v2/institution/subscription-request", json={"plan": "dershane_pro"})
        chk("4. tekrar talep → already_pending (idempotent)", r4.status_code == 200 and r4.json()["data"]["already_pending"] is True, str(r4.json().get("data")))

        # Süper admin tarafı
        sc = login(f"{PFX}_super@t.invalid")
        cr = sc.get("/api/v2/admin/contact-requests").json()
        items = [i for i in cr.get("items", []) if i.get("linked_institution_id") == iid]
        chk("5. süper admin İletişim Talepleri'nde görünüyor", len(items) == 1, f"eşleşen={len(items)}")
        if items:
            it = items[0]
            chk("5b. etiket 'Abonelik talebi (kurum)'", it.get("source_label") == "Abonelik talebi (kurum)", it.get("source_label"))
            chk("5c. kurum linki (linked_institution_id) doğru", it.get("linked_institution_id") == iid, str(it.get("linked_institution_id")))
            chk("5d. koç linki yok (linked_user_id None)", it.get("linked_user_id") is None, str(it.get("linked_user_id")))
            chk("5e. mevcut plan (canlı) görünüyor: Kurum Tanıma",
                it.get("institution_current_plan_label") == "Kurum Tanıma", str(it.get("institution_current_plan_label")))
            chk("5f. talep edilen plan görünüyor: Etüt Standart",
                it.get("requested_plan_label") == "Etüt Standart", str(it.get("requested_plan_label")))

        # 6. AKIŞIN DEVAMI: kurum detayı, talep edilen paketi ÖN-SEÇİM için döner
        # (admin tekrar seçmesin — kurum hangi paketi istediyse o gelir).
        det = sc.get(f"/api/v2/admin/institutions/{iid}").json()
        cur_name = det["institution"]["name"]
        pu = det.get("pending_upgrade")
        chk("6. kurum detayında bekleyen talep görünüyor", pu is not None, str(pu))
        if pu:
            chk("6a. talep edilen plan KODU etut_standart (PlanCard ön-seçer)",
                pu.get("requested_plan_code") == "etut_standart", str(pu.get("requested_plan_code")))
            chk("6b. talep edilen plan etiketi 'Etüt Standart'",
                pu.get("requested_plan_label") == "Etüt Standart", str(pu.get("requested_plan_label")))
            chk("6c. kurumun notu taşındı", pu.get("note") == "8 koçumuz var", str(pu.get("note")))
        # admin ön-seçili gelen planı uygular (tek tık karşılığı)
        r6 = sc.post(f"/api/v2/admin/institutions/{iid}", json={
            "name": cur_name, "contact_email": None,
            "plan": (pu or {}).get("requested_plan_code") or "etut_standart", "is_active": True})
        chk("6d. admin talep edilen planı uygular → 200", r6.status_code == 200, f"{r6.status_code} {r6.text[:120]}")
        det2 = sc.get(f"/api/v2/admin/institutions/{iid}").json()
        chk("6e. plan gerçekten etut_standart oldu", det2["institution"]["plan"] == "etut_standart", det2["institution"].get("plan"))

        # 7. REGRESYON: planSIZ edit (genel bilgi formu) planı SIFIRLAMAMALI (free'ye düşürme bug'ı)
        r7 = sc.post(f"/api/v2/admin/institutions/{iid}", json={
            "name": cur_name + " X", "contact_email": None, "is_active": True})
        chk("7. planSIZ edit → 200", r7.status_code == 200, f"{r7.status_code}")
        det3 = sc.get(f"/api/v2/admin/institutions/{iid}").json()
        chk("7b. plan KORUNDU (free'ye düşmedi)", det3["institution"]["plan"] == "etut_standart", det3["institution"].get("plan"))

    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(ContactRequest).where(ContactRequest.message.like(f"%kurum_id={iid}%")))
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_([aid, sid])))
            db.execute(sa_delete(User).where(User.id.in_([aid, sid])))
            db.execute(sa_delete(Institution).where(Institution.id == iid))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
