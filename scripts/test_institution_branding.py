"""Kurumsal kimlik (co-branding) smoke (2026-09-30).

Kurum e-postaları + paneller kurumun markasını taşır; ETÜTKOÇ yalnız alt satırda
"altyapı". Kapsam: e-posta başlığı (logo / logo yoksa ad) · gönderen görünen
adı + adres ETÜTKOÇ'ta kalır · Yanıtla = kurum iletişim adresi · konu satırı ·
öğrenci (koç üzerinden) ve veli (çocuk üzerinden) marka çözümü · bağımsız koç
markasız · platform (ticari) e-postaları markasız · herkese açık logo ucu ·
/me brand · davet bilgi uçları.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Institution, Invitation, User, UserRole
from app.models.communication_log import CommunicationLog
from app.models.parent import ParentInvitation, ParentRelation, ParentStudentLink
from app.services import email_service
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"brd_{secrets.token_hex(3)}"
PASSWORD = "BrandTest!2345xyz"
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
       b"\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00"
       b"\x00\x00IEND\xaeB`\x82")

SENT: list = []
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
        SENT.append(msg)

    def quit(self):
        pass


def html_of(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_content()
    return ""


def send(to: str, template: str = "password_reset") -> object:
    SENT.clear()
    ok = email_service.send_email(to, template, {"full_name": "Test", "reset_url": "https://x/r",
                                                 "verify_url": "https://x/v", "days_left": 3})
    return SENT[-1] if (ok and SENT) else None


def main() -> int:
    print(f"\n=== Kurumsal kimlik smoke — {PFX} ===\n")
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    e = lambda k: f"{PFX}_{k}@test.invalid"  # noqa: E731
    with SessionLocal() as db:
        logo_inst = Institution(name=f"Açı Deneme {PFX}", slug=f"{PFX}-a", contact_email="iletisim@aci.invalid",
                                plan="etut_standart", is_active=True, logo_data=PNG,
                                logo_content_type="image/png", logo_updated_at=now)
        plain_inst = Institution(name=f"Logosuz Kurs {PFX}", slug=f"{PFX}-b", contact_email=None,
                                 plan="etut_standart", is_active=True)
        dead_inst = Institution(name=f"Pasif {PFX}", slug=f"{PFX}-c", plan="etut_standart", is_active=False,
                                logo_data=PNG, logo_content_type="image/png")
        db.add_all([logo_inst, plain_inst, dead_inst])
        db.flush()
        mk = lambda email, role, **kw: User(email=email, password_hash=pwd, full_name=kw.pop("name", "Kişi"),  # noqa: E731
                                            role=role, is_active=True, password_changed_at=now,
                                            must_change_password=False, **kw)
        coach = mk(e("koc"), UserRole.TEACHER, institution_id=logo_inst.id, name="Kurum Koçu")
        plain_coach = mk(e("koc2"), UserRole.TEACHER, institution_id=plain_inst.id)
        solo = mk(e("solo"), UserRole.TEACHER, name="Bağımsız Koç")
        db.add_all([coach, plain_coach, solo])
        db.flush()
        student = mk(e("ogr"), UserRole.STUDENT, teacher_id=coach.id, name="Öğrenci Bir")
        solo_student = mk(e("ogr2"), UserRole.STUDENT, teacher_id=solo.id)
        parent = mk(e("veli"), UserRole.PARENT, name="Veli Bir")
        db.add_all([student, solo_student, parent])
        db.flush()
        db.add(ParentStudentLink(parent_id=parent.id, student_id=student.id,
                                 relation=ParentRelation.ANNE, is_primary=True))
        pinv = ParentInvitation(invited_email=e("yeniveli"), student_id=student.id, invited_by_id=coach.id,
                                relation=ParentRelation.BABA, is_primary=False,
                                token=secrets.token_hex(16), expires_at=now + timedelta(days=7))
        tinv = Invitation(token=secrets.token_hex(16), email=e("yenikoc"), role=UserRole.TEACHER,
                          institution_id=logo_inst.id, expires_at=now + timedelta(days=7))
        db.add_all([pinv, tinv])
        db.commit()
        ids = {"logo": logo_inst.id, "plain": plain_inst.id, "dead": dead_inst.id,
               "users": [coach.id, plain_coach.id, solo.id, student.id, solo_student.id, parent.id]}
        ptoken, ttoken = pinv.token, tinv.token
        logo_name, plain_name = logo_inst.name, plain_inst.name

    saved = (settings.email_enabled, settings.smtp_host, settings.smtp_use_ssl,
             settings.smtp_use_tls, settings.smtp_user, settings.smtp_from)
    real = (email_service.smtplib.SMTP, email_service.smtplib.SMTP_SSL)
    settings.email_enabled = True
    settings.smtp_host = "fake.local"
    settings.smtp_use_ssl = False
    settings.smtp_use_tls = False
    settings.smtp_user = ""
    settings.smtp_from = "rotam@etutkoc.com"
    email_service.smtplib.SMTP = FakeSMTP
    email_service.smtplib.SMTP_SSL = FakeSMTP
    try:
        # --- e-posta: logolu kurum koçu
        m = send(e("koc"))
        check("1. e-posta gönderildi", m is not None)
        name, addr = parseaddr(m["From"]) if m else ("", "")
        check("2. gönderen görünen ad = kurum", name == logo_name, m["From"] if m else "")
        check("3. gönderen ADRES ETÜTKOÇ alan adında kalır", addr == "rotam@etutkoc.com", addr)
        check("4. Yanıtla = kurum iletişim adresi", m is not None and m["Reply-To"] == "iletisim@aci.invalid",
              str(m["Reply-To"] if m else None))
        h = html_of(m) if m else ""
        check("5. başlıkta kurum logosu (herkese açık uç)", f"/api/v2/brand/logo/{ids['logo']}?v=" in h)
        check("6. ETÜTKOÇ logosu YOK", "etutkoc-mark.png" not in h)
        check("7. alt satır: kurum adına + Altyapı: ETÜTKOÇ", "adına gönderildi" in h and "Altyapı" in h)
        check("8. konu satırı kurum adıyla", m is not None and logo_name in str(m["Subject"]),
              str(m["Subject"] if m else ""))

        # --- öğrenci (koç üzerinden) + veli (çocuk üzerinden)
        m = send(e("ogr"))
        check("9. öğrenci e-postası kurum markalı (koç üzerinden)",
              m is not None and parseaddr(m["From"])[0] == logo_name)
        m = send(e("veli"))
        check("10. veli e-postası kurum markalı (çocuk üzerinden)",
              m is not None and parseaddr(m["From"])[0] == logo_name)

        # --- logosuz kurum → ad
        m = send(e("koc2"))
        h = html_of(m) if m else ""
        check("11. logosuz kurum: başlıkta kurum adı, logo yok",
              plain_name in h and "/api/v2/brand/logo/" not in h and "etutkoc-mark.png" not in h)
        check("12. iletişim adresi yoksa Yanıtla başlığı yok", m is not None and m["Reply-To"] is None)

        # --- bağımsız koç + öğrencisi → ETÜTKOÇ markası
        m = send(e("solo"))
        h = html_of(m) if m else ""
        check("13. bağımsız koç markasız (ETÜTKOÇ başlığı, düz gönderen)",
              m is not None and "etutkoc-mark.png" in h and m["From"] == "rotam@etutkoc.com"
              and m["Reply-To"] is None)
        m = send(e("ogr2"))
        check("14. bağımsız koç öğrencisi markasız", m is not None and m["From"] == "rotam@etutkoc.com")

        # --- platform (ticari) e-postası kurum koçuna bile markasız
        m = send(e("koc"), "trial_reminder")
        check("15. platform e-postası (deneme hatırlatma) markasız",
              m is not None and m["From"] == "rotam@etutkoc.com" and m["Reply-To"] is None
              and "adına gönderildi" not in html_of(m) and logo_name not in str(m["Subject"]))

        # --- açık marka kurumu (ctx) alıcıdan bağımsız uygulanır
        SENT.clear()
        email_service.send_email(e("hicyok"), "password_reset",
                                 {"reset_url": "https://x", "brand_institution_id": ids["logo"]})
        check("16. ctx brand_institution_id ile (kayıtsız alıcı) kurum markası",
              bool(SENT) and parseaddr(SENT[-1]["From"])[0] == logo_name)

        # --- herkese açık logo ucu
        c = TestClient(app)
        r = c.get(f"/api/v2/brand/logo/{ids['logo']}")
        check("17. logo ucu çerezsiz 200 + image/png + önbellek",
              r.status_code == 200 and r.headers.get("content-type") == "image/png"
              and "public" in r.headers.get("cache-control", ""), str(r.status_code))
        check("18. logosuz kurum 404", c.get(f"/api/v2/brand/logo/{ids['plain']}").status_code == 404)
        check("19. pasif kurum logosu 404", c.get(f"/api/v2/brand/logo/{ids['dead']}").status_code == 404)

        # --- /me brand (öğrenci)
        c.post("/api/v2/auth/login", json={"email": e("ogr"), "password": PASSWORD})
        b = (c.get("/api/v2/me").json() or {}).get("brand") or {}
        check("20. /me brand: öğrenci koçunun kurumu + logo yolu",
              b.get("name") == logo_name and str(b.get("logo_url", "")).startswith(f"/api/v2/brand/logo/{ids['logo']}"),
              str(b))
        c2 = TestClient(app)
        c2.post("/api/v2/auth/login", json={"email": e("solo"), "password": PASSWORD})
        check("21. /me brand: bağımsız koç null", c2.get("/api/v2/me").json().get("brand") is None)

        # --- davet bilgi uçları
        pi = TestClient(app).get(f"/api/v2/parent/invitation/{ptoken}").json()
        check("22. veli davet bilgisi kurum markası",
              pi.get("brand_name") == logo_name and bool(pi.get("brand_logo_url")), str(pi)[:200])
        ti = TestClient(app).get(f"/api/v2/auth/signup/invite/{ttoken}").json()
        check("23. öğretmen davet bilgisi kurum logosu",
              ti.get("institution_name") == logo_name and bool(ti.get("institution_logo_url")), str(ti)[:200])
    finally:
        settings.email_enabled, settings.smtp_host, settings.smtp_use_ssl, \
            settings.smtp_use_tls, settings.smtp_user, settings.smtp_from = saved
        email_service.smtplib.SMTP, email_service.smtplib.SMTP_SSL = real
        with SessionLocal() as db:
            uids = ids["users"]
            db.execute(sa_delete(CommunicationLog).where(CommunicationLog.to_address.like(f"{PFX}%")))
            db.execute(sa_delete(ParentInvitation).where(ParentInvitation.student_id.in_(uids)))
            db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.parent_id.in_(uids)))
            db.execute(sa_delete(Invitation).where(Invitation.institution_id.in_([ids["logo"]])))
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(uids)))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.execute(sa_delete(Institution).where(Institution.id.in_([ids["logo"], ids["plain"], ids["dead"]])))
            db.commit()

    print(f"\n{passed} passed · {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
