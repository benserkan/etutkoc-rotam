"""Faz 2a doğrulama — birleşik iletişim log'u (communication_logs).

Dört kanalı da GERÇEK servis fonksiyonlarından geçirir (ağ çağrıları monkeypatch'li)
ve her gönderimin communication_logs'a doğru kanal/durum/alan ile yazıldığını
doğrular. Ayrıca best-effort izolasyon (loglama hatası akışı bozmaz) + maskeleme.

Çalıştır:  PYTHONPATH=. python scripts/test_comm_log.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import CommunicationLog, DevicePushToken, User, UserRole
from app.models.whatsapp_template import WhatsAppTemplate

PFX = "commlog-test"
passed = 0
failed = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {extra}")


def latest(channel: str, **filt):
    """Belirli kanalın en son log satırını döndür (test artefaktları için)."""
    with SessionLocal() as db:
        q = db.query(CommunicationLog).filter(CommunicationLog.channel == channel)
        for k, v in filt.items():
            q = q.filter(getattr(CommunicationLog, k) == v)
        return q.order_by(CommunicationLog.id.desc()).first()


# ----------------------------------------------------------------------
# 1) E-POSTA — sent / failed / disabled
# ----------------------------------------------------------------------
def test_email():
    print("\n[1] E-POSTA (send_email gerçek yol)")
    import app.services.email_service as es
    from app.config import settings

    # _render'ı sabitleyip şablon bağımlılığını dışla (loglama yolunu test ediyoruz)
    es._render = lambda name, ctx: ("Test Konu", "<p>x</p>", "x")

    class _FakeSMTP:
        def __init__(self, *a, **k): pass
        def starttls(self): pass
        def login(self, *a): pass
        def send_message(self, msg):
            if getattr(_FakeSMTP, "boom", False):
                raise RuntimeError("smtp patladı")
        def quit(self): pass

    es.smtplib.SMTP = _FakeSMTP  # type: ignore
    es.smtplib.SMTP_SSL = _FakeSMTP  # type: ignore

    old = (settings.email_enabled, settings.smtp_host, settings.smtp_use_ssl)
    settings.email_enabled = True
    settings.smtp_host = "smtp.zeptomail.com"
    settings.smtp_use_ssl = False

    # 1a sent
    _FakeSMTP.boom = False
    ok = es.send_email(f"{PFX}+sent@x.test", "tpl_sent", {})
    row = latest("email", to_address=f"{PFX}+sent@x.test")
    check("email sent → True", ok is True)
    check("email sent satırı yazıldı", row is not None and row.status == "sent",
          str(row and row.status))
    check("email provider=zeptomail", row is not None and row.provider == "zeptomail",
          str(row and row.provider))
    check("email Message-ID kaydedildi (bounce eşleşmesi)",
          row is not None and bool(row.provider_message_id))
    check("email category=template adı", row is not None and row.category == "tpl_sent")

    # 1b failed
    _FakeSMTP.boom = True
    ok = es.send_email(f"{PFX}+fail@x.test", "tpl_fail", {})
    row = latest("email", to_address=f"{PFX}+fail@x.test")
    check("email fail → False", ok is False)
    check("email failed satırı + error", row is not None and row.status == "failed"
          and bool(row.error), str(row and row.status))

    # 1c disabled
    settings.email_enabled = False
    ok = es.send_email(f"{PFX}+off@x.test", "tpl_off", {})
    row = latest("email", to_address=f"{PFX}+off@x.test")
    check("email disabled → suppressed", row is not None and row.status == "suppressed"
          and row.error == "email_disabled", str(row and row.status))

    settings.email_enabled, settings.smtp_host, settings.smtp_use_ssl = old


# ----------------------------------------------------------------------
# 2) PUSH — sent / no_device / failed
# ----------------------------------------------------------------------
def test_push():
    print("\n[2] PUSH (send_push_to_user gerçek yol)")
    import app.services.push_notifications as pn

    with SessionLocal() as db:
        u = User(email=f"{PFX}-push@x.test", password_hash="x",
                 full_name="Push User", role=UserRole.STUDENT)
        db.add(u); db.commit(); db.refresh(u)
        uid = u.id
        db.add(DevicePushToken(user_id=uid, token="ExponentPushToken[commlogTESTtoken123]",
                               platform="android"))
        db.commit()

    # 2a sent
    pn._expo_send = lambda messages: [{"status": "ok"} for _ in messages]
    n = pn.send_push_to_user(SessionLocal(), user_id=uid, title="Test Push",
                             body="gövde", data={"kind": "weekly_report"})
    row = latest("push", to_user_id=uid)
    check("push sent → gönderildi", n >= 1)
    check("push sent satırı", row is not None and row.status == "sent", str(row and row.status))
    check("push category=kind", row is not None and row.category == "weekly_report")
    check("push token maskeli (tam token saklanmaz)",
          row is not None and row.to_address and "…" in (row.to_address or ""),
          str(row and row.to_address))

    # 2b no_device (token'sız kullanıcı)
    with SessionLocal() as db:
        u2 = User(email=f"{PFX}-nodev@x.test", password_hash="x",
                  full_name="No Device", role=UserRole.STUDENT)
        db.add(u2); db.commit(); db.refresh(u2)
        uid2 = u2.id
    pn.send_push_to_user(SessionLocal(), user_id=uid2, title="T", body="b", data={})
    row = latest("push", to_user_id=uid2)
    check("push no_device → suppressed", row is not None and row.status == "suppressed"
          and row.error == "no_device", str(row and row.status))

    # 2c failed (expo exception)
    def _boom(messages): raise RuntimeError("expo down")
    pn._expo_send = _boom
    pn.send_push_to_user(SessionLocal(), user_id=uid, title="Fail Push", body="b",
                         data={"kind": "drop_alert"})
    row = latest("push", to_user_id=uid, subject="Fail Push")
    check("push fail → failed satırı", row is not None and row.status == "failed",
          str(row and row.status))


# ----------------------------------------------------------------------
# 3) SMS — disabled(dev) / sent / failed
# ----------------------------------------------------------------------
def test_sms():
    print("\n[3] SMS (send_sms gerçek yol)")
    import app.services.sms_provider as sp

    # 3a dev stub (sms kapalı → suppressed)
    sp.is_sms_enabled = lambda: False
    ok = sp.send_sms("905550000001", "kod 123456")
    row = latest("sms", to_address="905550000001")
    check("sms dev → True", ok is True)
    check("sms disabled → suppressed", row is not None and row.status == "suppressed"
          and row.error == "sms_disabled", str(row and row.status))

    # 3b sent
    sp.is_sms_enabled = lambda: True
    sp._send_via_vatansms = lambda phone, msg: True
    ok = sp.send_sms("905550000002", "kod 654321")
    row = latest("sms", to_address="905550000002")
    check("sms sent → True", ok is True)
    check("sms sent satırı", row is not None and row.status == "sent", str(row and row.status))
    check("sms category=otp", row is not None and row.category == "otp")

    # 3c failed
    sp._send_via_vatansms = lambda phone, msg: False
    ok = sp.send_sms("905550000003", "kod 000")
    row = latest("sms", to_address="905550000003")
    check("sms fail → False", ok is False)
    check("sms failed satırı", row is not None and row.status == "failed", str(row and row.status))


# ----------------------------------------------------------------------
# 4) WHATSAPP — build_wa_dispatch gerçek yol
# ----------------------------------------------------------------------
def test_whatsapp():
    print("\n[4] WHATSAPP (build_wa_dispatch gerçek yol)")
    from app.services import whatsapp_link_service as wl

    with SessionLocal() as db:
        coach = User(email=f"{PFX}-wacoach@x.test", password_hash="x",
                     full_name="WA Coach", role=UserRole.TEACHER)
        db.add(coach); db.commit(); db.refresh(coach)
        student = User(email=f"{PFX}-wastudent@x.test", password_hash="x",
                       full_name="WA Student", role=UserRole.STUDENT,
                       teacher_id=coach.id, phone="905551112233",
                       phone_verified_at=datetime.now(timezone.utc))
        db.add(student); db.commit(); db.refresh(student)
        tmpl = WhatsAppTemplate(
            key=f"{PFX}-tpl", category="ogrenci", target_role="any",
            name_tr="Test", content_template="Merhaba, bu bir test mesajidir.",
            variables_json="[]", is_active=True,
        )
        db.add(tmpl); db.commit(); db.refresh(tmpl)
        coach_id, student_id, tmpl_id = coach.id, student.id, tmpl.id

    with SessionLocal() as db:
        coach = db.get(User, coach_id)
        res = wl.build_wa_dispatch(db, sender=coach, template_id=tmpl_id,
                                   target_user_id=student_id)
        db.commit()
        check("wa dispatch URL üretildi", bool(res.wa_url))

    row = latest("whatsapp", to_user_id=student_id)
    check("wa log satırı yazıldı", row is not None and row.status == "sent",
          str(row and row.status))
    check("wa category=template key", row is not None and row.category == f"{PFX}-tpl")
    check("wa telefon maskeli", row is not None and row.to_address
          and "*" in (row.to_address or ""), str(row and row.to_address))


# ----------------------------------------------------------------------
# 5) Best-effort izolasyon + maskeleme
# ----------------------------------------------------------------------
def test_isolation():
    print("\n[5] İZOLASYON + maskeleme")
    from app.services import comm_log

    # record DB hatası fırlatsa bile None döner, raise ETMEZ
    import app.services.comm_log as cl
    orig = cl.SessionLocal
    cl.SessionLocal = lambda: (_ for _ in ()).throw(RuntimeError("db down"))
    try:
        r = comm_log.record("email", to_address="x@y.z")
        check("loglama hatası akışı bozmaz (None döner)", r is None)
    except Exception as e:  # noqa: BLE001
        check("loglama hatası akışı bozmaz (None döner)", False, repr(e))
    finally:
        cl.SessionLocal = orig

    check("mask_token kısa", comm_log.mask_token("abc") == "abc…" or
          comm_log.mask_token("abcdefghij") is not None)
    long_t = "ExponentPushToken[abcdefghijklmnop]"
    masked = comm_log.mask_token(long_t)
    check("mask_token uzun → tam token gizli", masked is not None
          and long_t not in masked and "…" in masked, str(masked))


def cleanup():
    with SessionLocal() as db:
        db.query(CommunicationLog).filter(
            CommunicationLog.to_address.like(f"{PFX}%")
            | CommunicationLog.category.like(f"{PFX}%")
            | CommunicationLog.to_address.in_(
                ["905550000001", "905550000002", "905550000003", "905551112233"]
            )
        ).delete(synchronize_session=False)
        # push/wa kullanıcılarına bağlı satırlar + test kullanıcıları
        ids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}%")).all()]
        if ids:
            db.query(CommunicationLog).filter(
                CommunicationLog.to_user_id.in_(ids)
            ).delete(synchronize_session=False)
            db.query(DevicePushToken).filter(DevicePushToken.user_id.in_(ids)).delete(
                synchronize_session=False)
            db.query(WhatsAppTemplate).filter(
                WhatsAppTemplate.key.like(f"{PFX}%")).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.commit()


if __name__ == "__main__":
    try:
        test_email()
        test_push()
        test_sms()
        test_whatsapp()
        test_isolation()
    finally:
        cleanup()
    print(f"\n{'='*50}\nSONUÇ: {passed} PASS · {failed} FAIL")
    sys.exit(1 if failed else 0)
