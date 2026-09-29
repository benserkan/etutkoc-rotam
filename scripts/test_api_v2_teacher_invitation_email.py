"""Kurum → öğretmen davet e-postası smoke (2026-09-29).

Gönderim yolu el-sıkışmaya kadar GERÇEK: settings.email_enabled=True +
smtplib.SMTP sahte sınıfla değiştirilir (şablon render + mesaj kurulumu +
iletişim kaydı gerçek). Kapsam: oluştururken gönder / gönderme / e-postasız ·
bağlantı APP_BASE_URL'den · e-posta içeriği (kurum, davet eden, buton, bağlantı,
son geçerlilik) · tekrar gönder · SMTP hatası dürüst raporlanır · kapılar ·
davetle kayıt: bilgi ucu, e-posta kilidi, kurum bağlantısı, tek kullanım.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Institution, Invitation, User, UserRole
from app.models.communication_log import CommunicationLog
from app.services import email_service
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"tinv_{secrets.token_hex(3)}"
PASSWORD = "InvTest!2345xyz"
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
OTHER_ADMIN_EMAIL = f"{PFX}_other@test.invalid"
TEACHER_EMAIL = f"{PFX}_koc@test.invalid"
INV_EMAIL = f"{PFX}_yeni@example.com"
INV2_EMAIL = f"{PFX}_ikinci@example.com"
INV3_EMAIL = f"{PFX}_ucuncu@example.com"

SENT: list = []
FAIL = {"on": False}
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


class FakeSMTP:
    def __init__(self, host, port, timeout=None):
        pass

    def starttls(self):
        pass

    def login(self, u, p):
        pass

    def send_message(self, msg):
        if FAIL["on"]:
            raise RuntimeError("fake smtp down")
        SENT.append(msg)

    def quit(self):
        pass


def body_of(msg) -> str:
    out = []
    for part in msg.walk():
        if part.get_content_type() in ("text/plain", "text/html"):
            try:
                out.append(part.get_content())
            except Exception:
                pass
    return "\n".join(out)


def main() -> int:
    print(f"\n=== Öğretmen davet e-postası smoke — {PFX} ===\n")
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(name=f"Deneme Koleji {PFX}", slug=f"{PFX}-a", contact_email="a@test.invalid",
                           plan="etut_standart", is_active=True)
        other = Institution(name=f"Başka Kurum {PFX}", slug=f"{PFX}-b", contact_email="b@test.invalid",
                            plan="etut_standart", is_active=True)
        db.add_all([inst, other])
        db.flush()
        admin = User(email=ADMIN_EMAIL, password_hash=pwd, full_name="Ayşe Yönetici",
                     role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id, is_active=True,
                     password_changed_at=now, must_change_password=False)
        other_admin = User(email=OTHER_ADMIN_EMAIL, password_hash=pwd, full_name="Diğer Yönetici",
                           role=UserRole.INSTITUTION_ADMIN, institution_id=other.id, is_active=True,
                           password_changed_at=now, must_change_password=False)
        teacher = User(email=TEACHER_EMAIL, password_hash=pwd, full_name="Koç",
                       role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
                       password_changed_at=now, must_change_password=False)
        db.add_all([admin, other_admin, teacher])
        db.commit()
        ids = {"inst": inst.id, "other": other.id, "admin": admin.id,
               "other_admin": other_admin.id, "teacher": teacher.id}

    saved = (settings.email_enabled, settings.smtp_host, settings.smtp_use_ssl,
             settings.smtp_use_tls, settings.smtp_user)
    real = (email_service.smtplib.SMTP, email_service.smtplib.SMTP_SSL)
    settings.email_enabled = True
    settings.smtp_host = "fake.local"
    settings.smtp_use_ssl = False
    settings.smtp_use_tls = False
    settings.smtp_user = ""
    email_service.smtplib.SMTP = FakeSMTP
    email_service.smtplib.SMTP_SSL = FakeSMTP
    base = settings.app_base_url.rstrip("/")
    new_user_id = None
    try:
        c = TestClient(app)
        c.post("/api/v2/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})

        # 1. e-postalı davet → gönderildi
        SENT.clear()
        r = c.post("/api/v2/institution/invitations",
                   json={"full_name": "Mehmet Öğretmen", "email": INV_EMAIL})
        inv = r.json().get("data", {}) if r.status_code == 201 else {}
        check("1. davet oluşturuldu (201) + email_status=sent",
              r.status_code == 201 and inv.get("email_status") == "sent", r.text[:200])
        check("2. bağlantı APP_BASE_URL'den + token",
              inv.get("signup_url") == f"{base}/signup/invite/{inv.get('token')}", inv.get("signup_url", ""))
        mails = [m for m in SENT if m["To"] == INV_EMAIL]
        check("3. SMTP'ye tek mesaj, doğru alıcı", len(mails) == 1, str(len(SENT)))
        if mails:
            m = mails[0]
            body = body_of(m)
            check("4. konu: kurum adı + davet",
                  f"Deneme Koleji {PFX}" in m["Subject"] and "davet" in m["Subject"].lower(), m["Subject"])
            check("5. gövde: selamlama + davet eden + kurum + buton + bağlantı (2 kez) + e-posta",
                  "Merhaba Mehmet Öğretmen" in body and "Ayşe Yönetici" in body
                  and f"Deneme Koleji {PFX}" in body and "Daveti kabul et" in body
                  and body.count(inv.get("signup_url", "@@")) >= 2 and INV_EMAIL in body,
                  body[:400])
            check("6. gövde: son geçerlilik tarihi + emoji yok",
                  "geçerlidir" in body and not any(ord(ch) > 0x2600 and ord(ch) < 0x1FAFF for ch in body),
                  "")
        with SessionLocal() as db:
            log = (db.query(CommunicationLog)
                   .filter(CommunicationLog.to_address == INV_EMAIL,
                           CommunicationLog.category == "teacher_invitation").all())
        check("7. iletişim kaydı: teacher_invitation / sent", len(log) == 1 and log[0].status == "sent",
              str([(x.category, x.status) for x in log]))

        # 8. gönderme kutusu kapalı → mail yok
        SENT.clear()
        r = c.post("/api/v2/institution/invitations",
                   json={"email": INV2_EMAIL, "send_email": False})
        inv2 = r.json().get("data", {})
        check("8. send_email=false → gönderilmedi (status null, SMTP boş)",
              r.status_code == 201 and inv2.get("email_status") is None and not SENT, r.text[:150])
        # 9. e-postasız açık davet → mail yok
        r = c.post("/api/v2/institution/invitations", json={"full_name": "Açık"})
        inv_open = r.json().get("data", {})
        check("9. açık davet → mail yok", r.status_code == 201 and not SENT and inv_open.get("email") is None)

        # 10. sonradan gönder
        r = c.post(f"/api/v2/institution/invitations/{inv2['id']}/send-email")
        check("10. 'Gönder' → 200 + sent + SMTP'de 1 mesaj",
              r.status_code == 200 and r.json()["data"]["email_status"] == "sent"
              and len([m for m in SENT if m["To"] == INV2_EMAIL]) == 1, r.text[:150])

        # 11. SMTP hatası → 502 + liste 'failed'
        FAIL["on"] = True
        r = c.post(f"/api/v2/institution/invitations/{inv2['id']}/send-email")
        FAIL["on"] = False
        lst = c.get("/api/v2/institution/invitations").json()["items"]
        row2 = next((i for i in lst if i["id"] == inv2["id"]), {})
        check("11. SMTP hatası → 502 email_not_sent + listede 'failed' (dürüst)",
              r.status_code == 502 and r.json()["detail"]["code"] == "email_not_sent"
              and row2.get("email_status") == "failed", f"{r.status_code} {row2.get('email_status')}")
        row1 = next((i for i in lst if i["id"] == inv["id"]), {})
        check("12. listede ilk davet 'sent' + gönderim zamanı", row1.get("email_status") == "sent"
              and row1.get("emailed_at"), str(row1)[:150])

        # 13. kapılar
        r = c.post(f"/api/v2/institution/invitations/{inv_open['id']}/send-email")
        check("13. e-postasız davete gönder → 422 no_email",
              r.status_code == 422 and r.json()["detail"]["code"] == "no_email")
        c.post(f"/api/v2/institution/invitations/{inv2['id']}/revoke")
        r = c.post(f"/api/v2/institution/invitations/{inv2['id']}/send-email")
        check("14. iptal edilmiş davete gönder → 409", r.status_code == 409, str(r.status_code))
        oc = TestClient(app)
        oc.post("/api/v2/auth/login", json={"email": OTHER_ADMIN_EMAIL, "password": PASSWORD})
        r = oc.post(f"/api/v2/institution/invitations/{inv['id']}/send-email")
        check("15. başka kurumun yöneticisi → 404", r.status_code == 404, str(r.status_code))
        tc = TestClient(app)
        tc.post("/api/v2/auth/login", json={"email": TEACHER_EMAIL, "password": PASSWORD})
        r = tc.post(f"/api/v2/institution/invitations/{inv['id']}/send-email")
        check("16. öğretmen → 403", r.status_code == 403, str(r.status_code))

        # 17-21. davetle kayıt
        pub = TestClient(app)
        token = inv["token"]
        r = pub.get(f"/api/v2/auth/signup/invite/{token}")
        info = r.json() if r.status_code == 200 else {}
        check("17. davet bilgi ucu: geçerli + e-posta + kurum adı",
              info.get("valid") and info.get("email") == INV_EMAIL
              and info.get("institution_name") == f"Deneme Koleji {PFX}", str(info)[:200])
        body = {"full_name": "Mehmet Öğretmen", "password": "YeniSifre!2345ab",
                "password_confirm": "YeniSifre!2345ab", "accept_terms": True}
        r = pub.post(f"/api/v2/auth/signup/invite/{token}",
                     json={**body, "email": f"{PFX}_baska@example.com"})
        check("18. başka e-postayla kayıt → 422 email_mismatch (kilit sunucuda)",
              r.status_code == 422 and r.json()["detail"]["code"] == "email_mismatch", r.text[:200])
        r = pub.post(f"/api/v2/auth/signup/invite/{token}", json={**body, "email": INV_EMAIL})
        check("19. davetli adresle kayıt → 200", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            u = db.query(User).filter(User.email == INV_EMAIL).first()
            invr = db.get(Invitation, inv["id"])
            new_user_id = u.id if u else None
            check("20. öğretmen kuruma bağlı + davet kullanıldı",
                  u is not None and u.role == UserRole.TEACHER and u.institution_id == ids["inst"]
                  and invr.consumed_by_user_id == u.id)
        r = TestClient(app).post(f"/api/v2/auth/signup/invite/{token}", json={**body, "email": INV_EMAIL})
        check("21. aynı bağlantı ikinci kez kullanılamaz", r.status_code in (409, 410, 422), str(r.status_code))
    finally:
        settings.email_enabled, settings.smtp_host, settings.smtp_use_ssl, \
            settings.smtp_use_tls, settings.smtp_user = saved
        email_service.smtplib.SMTP, email_service.smtplib.SMTP_SSL = real
        with SessionLocal() as db:
            uids = [ids["admin"], ids["other_admin"], ids["teacher"]] + ([new_user_id] if new_user_id else [])
            db.execute(sa_delete(CommunicationLog).where(CommunicationLog.to_address.like(f"{PFX}%")))
            db.execute(sa_delete(Invitation).where(Invitation.institution_id.in_([ids["inst"], ids["other"]])))
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.execute(sa_delete(Institution).where(Institution.id.in_([ids["inst"], ids["other"]])))
            db.commit()
    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print("  FAIL:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
