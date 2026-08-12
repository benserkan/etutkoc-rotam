"""Öğrenci e-posta fallback smoke — SMTP el-sıkışmasına kadar GERÇEK yol.

"Gidiyor görünüp gitmemesi olamaz" ilkesi: send_email kısa devre YAPMAZ —
settings geçici olarak email_enabled=True yapılır, smtplib.SMTP sahte sınıfla
değiştirilir; böylece şablon RENDER edilir, mesaj kurulur, sahte SMTP'ye
teslim edilir ve comm_log'a 'sent' YALNIZ teslimden sonra yazılır. Asıl
gönderim yolunun her adımı (guard'lar dahil) test edilir.

Senaryolar (14):
   1. publish-week → cihazsız öğrenciye e-posta: SMTP'de mesaj + doğru alıcı
   2. ...içerik: öğrenci adı + görev bilgisi + /student/week CTA
   3. ...comm_log satırı (category=student_new_program, status=sent)
   4. Dedup: ikinci publish 24s içinde → YENİ mail yok
   5. Cihazlı öğrenci → mail YOK (push kanalı esas)
   6. "Veliye duyur" (notify-parents) da öğrenci e-postasını tetikler (dedup ayrı öğrenci)
   7. Haftalık özet: cihazsız + görevli → SMTP mesajı + oran içerikte
   8. ...comm_log satırı (category=student_weekly_summary)
   9. ...VELİSİZ öğrenci de alır (velisiz kurgu zaten — kanıt)
  10. Haftalık özet dedup (6 gün) → ikinci koşuda yeni mail yok
  11. Cihazlı öğrenci haftalık özet ALMAZ
  12. Görevsiz öğrenci haftalık özet almaz (no_tasks)
  13. SMTP hatası → comm_log 'failed' + fonksiyon 'failed' döner (dürüstlük)
  14. Cron kaydı: JOB_REGISTRY + migration seed job_key eşleşir
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Task, TaskStatus, TaskType, User, UserRole
from app.models.communication_log import CommunicationLog
from app.models.device_push_token import DevicePushToken
from app.services import email_service
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from app.services.student_email_fallback import (
    CATEGORY_NEW_PROGRAM,
    CATEGORY_WEEKLY_SUMMARY,
    run_student_weekly_emails,
    send_student_weekly_summary,
)

PFX = f"sef_{secrets.token_hex(3)}"
PASSWORD = "TestPass123!@xyz"
T_EMAIL = f"{PFX}_koc@test.invalid"
S1_EMAIL = f"{PFX}_ogr1@test.invalid"   # cihazsız — mail almalı
S2_EMAIL = f"{PFX}_ogr2@test.invalid"   # cihazlı — mail ALMAMALI
S3_EMAIL = f"{PFX}_ogr3@test.invalid"   # notify-parents senaryosu
S4_EMAIL = f"{PFX}_ogr4@test.invalid"   # görevsiz

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


# --------------------------------------------------------------------------
# Sahte SMTP — gerçek send_email yolunun teslim noktası
# --------------------------------------------------------------------------
SENT: list = []
FAIL_MODE = {"on": False}


class FakeSMTP:
    def __init__(self, host, port, timeout=None):
        pass

    def starttls(self):
        pass

    def login(self, u, p):
        pass

    def send_message(self, msg):
        if FAIL_MODE["on"]:
            raise RuntimeError("fake smtp down")
        SENT.append(msg)

    def quit(self):
        pass


def _mail_bodies(msg) -> str:
    parts = []
    for part in msg.walk():
        if part.get_content_type() in ("text/plain", "text/html"):
            try:
                parts.append(part.get_content())
            except Exception:
                pass
    return "\n".join(parts)


def _seed() -> dict:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    with SessionLocal() as db:
        t = User(email=T_EMAIL, password_hash=hash_password(PASSWORD),
                 full_name=f"{PFX} Koç", role=UserRole.TEACHER, is_active=True)
        db.add(t)
        db.flush()
        students = {}
        for key, em in (("s1", S1_EMAIL), ("s2", S2_EMAIL), ("s3", S3_EMAIL), ("s4", S4_EMAIL)):
            s = User(email=em, password_hash=hash_password(PASSWORD),
                     full_name=f"{PFX} Öğrenci {key}", role=UserRole.STUDENT,
                     teacher_id=t.id, is_active=True, grade_level=8)
            db.add(s)
            db.flush()
            students[key] = s.id
        # s2'nin kayıtlı cihazı var → e-posta atlanmalı
        db.add(DevicePushToken(user_id=students["s2"], token=f"ExponentPushToken[{PFX}]",
                               platform="android"))
        # s1+s2+s3: bu haftaya taslak görevler (publish-week yayınlayacak);
        # geçen haftaya da yayınlanmış görevler (weekly summary penceresi)
        for key in ("s1", "s2", "s3"):
            sid = students[key]
            db.add(Task(student_id=sid, title="Matematik · Konu Testi", type=TaskType.OTHER,
                        date=monday, status=TaskStatus.PENDING, is_draft=True))
            db.add(Task(student_id=sid, title="Fen · Tekrar", type=TaskType.OTHER,
                        date=monday + timedelta(days=2), status=TaskStatus.PENDING, is_draft=True))
            db.add(Task(student_id=sid, title="Türkçe · Paragraf", type=TaskType.OTHER,
                        date=today - timedelta(days=3), status=TaskStatus.COMPLETED,
                        is_draft=False, completed_at=datetime.now(timezone.utc)))
            db.add(Task(student_id=sid, title="Sosyal · Test", type=TaskType.OTHER,
                        date=today - timedelta(days=2), status=TaskStatus.PENDING,
                        is_draft=False))
        db.commit()
        return {"teacher": t.id, "monday": monday.isoformat(), **students}


def _cleanup(ids: dict) -> None:
    with SessionLocal() as db:
        uids = [v for k, v in ids.items() if k not in ("monday",)]
        db.execute(sa_delete(DevicePushToken).where(DevicePushToken.user_id.in_(uids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(uids)))
        emails = [T_EMAIL, S1_EMAIL, S2_EMAIL, S3_EMAIL, S4_EMAIL]
        db.execute(sa_delete(CommunicationLog).where(CommunicationLog.to_address.in_(emails)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _comm_rows(db, to, category):
    return (
        db.query(CommunicationLog)
        .filter(CommunicationLog.to_address == to, CommunicationLog.category == category)
        .all()
    )


def main() -> int:
    ids = _seed()
    client = TestClient(app)
    get_login_limiter().reset()

    # settings'i gerçek-gönderim moduna al + SMTP'yi sahteyle değiştir
    saved = (settings.email_enabled, settings.smtp_host, settings.smtp_use_ssl,
             settings.smtp_use_tls, settings.smtp_user)
    settings.email_enabled = True
    settings.smtp_host = "fake.local"
    settings.smtp_use_ssl = False
    settings.smtp_use_tls = False
    settings.smtp_user = ""
    real_smtp = email_service.smtplib.SMTP
    real_smtp_ssl = email_service.smtplib.SMTP_SSL
    email_service.smtplib.SMTP = FakeSMTP
    email_service.smtplib.SMTP_SSL = FakeSMTP

    try:
        r = client.post("/api/v2/auth/login", json={"email": T_EMAIL, "password": PASSWORD})
        assert r.status_code == 200, f"login {r.status_code}"

        # ---- 1-3: publish-week → cihazsız s1'e e-posta
        SENT.clear()
        r = client.post(f"/api/v2/teacher/students/{ids['s1']}/publish-week",
                        json={"week_start": ids["monday"]})
        check("0. publish-week 200", r.status_code == 200, str(r.status_code))
        s1_mails = [m for m in SENT if m["To"] == S1_EMAIL]
        check("1. cihazsız öğrenciye SMTP'de mesaj var", len(s1_mails) == 1,
              f"{len(s1_mails)} mesaj (SENT={[(m['To'], str(m['Subject'])) for m in SENT]})")
        if s1_mails:
            body = _mail_bodies(s1_mails[0])
            check("2. içerik: ad + görev + CTA",
                  f"{PFX} Öğrenci s1" in body and "görev" in body and "/student/week" in body,
                  body[:200])
        else:
            check("2. içerik: ad + görev + CTA", False, "mesaj yok")
        with SessionLocal() as db:
            rows = _comm_rows(db, S1_EMAIL, CATEGORY_NEW_PROGRAM)
            check("3. comm_log sent satırı", len(rows) == 1 and rows[0].status == "sent",
                  f"{[(r2.status,) for r2 in rows]}")

        # ---- 4: dedup — tekrar publish → yeni mail yok
        SENT.clear()
        client.post(f"/api/v2/teacher/students/{ids['s1']}/publish-week",
                    json={"week_start": ids["monday"]})
        check("4. dedup 24s — ikinci publish mail üretmez",
              len([m for m in SENT if m["To"] == S1_EMAIL]) == 0, f"{len(SENT)}")

        # ---- 5: cihazlı s2 mail almaz (s2'nin publish'i 0. adımda değil — kendi publish'i)
        SENT.clear()
        client.post(f"/api/v2/teacher/students/{ids['s2']}/publish-week",
                    json={"week_start": ids["monday"]})
        check("5. cihazlı öğrenciye mail YOK",
              len([m for m in SENT if m["To"] == S2_EMAIL]) == 0,
              f"{[(m['To'],) for m in SENT]}")
        with SessionLocal() as db:
            check("5b. cihazlıda comm_log kaydı da yok",
                  len(_comm_rows(db, S2_EMAIL, CATEGORY_NEW_PROGRAM)) == 0, "")

        # ---- 6: notify-parents ("Veliye duyur") da öğrenci e-postasını tetikler
        SENT.clear()
        r = client.post(f"/api/v2/teacher/students/{ids['s3']}/program/notify-parents",
                        json={"week_start": ids["monday"]})
        check("6. Veliye-duyur cihazsız öğrenciye de mail",
              r.status_code == 200 and len([m for m in SENT if m["To"] == S3_EMAIL]) == 1,
              f"{r.status_code} / {[(m['To'],) for m in SENT]}")

        # ---- 7-9: haftalık özet (servis + cron yolu)
        SENT.clear()
        with SessionLocal() as db:
            counts = run_student_weekly_emails(db, now=datetime.now(timezone.utc))
        s1_sum = [m for m in SENT if m["To"] == S1_EMAIL]
        check("7. haftalık özet cihazsız öğrenciye SMTP mesajı", len(s1_sum) == 1,
              f"counts={counts}")
        if s1_sum:
            body = _mail_bodies(s1_sum[0])
            check("8a. içerik: başlık + görev sayıları",
                  "Gelişim Özeti" in body and "görev" in body, body[:200])
        with SessionLocal() as db:
            rows = _comm_rows(db, S1_EMAIL, CATEGORY_WEEKLY_SUMMARY)
            check("8. comm_log satırı (weekly_summary, sent)",
                  len(rows) == 1 and rows[0].status == "sent", f"{[(x.status,) for x in rows]}")
        check("9. VELİSİZ öğrenci de aldı (kurguda hiç veli yok)", len(s1_sum) == 1, "")

        # ---- 10: dedup 6 gün
        SENT.clear()
        with SessionLocal() as db:
            counts2 = run_student_weekly_emails(db, now=datetime.now(timezone.utc))
        check("10. haftalık dedup — ikinci koşu mail üretmez",
              len(SENT) == 0 and counts2.get("recent", 0) >= 1, f"{counts2}")

        # ---- 11: cihazlı s2 özet almadı (7. adımın koşusunda)
        with SessionLocal() as db:
            check("11. cihazlı öğrenci haftalık özet ALMAZ",
                  len(_comm_rows(db, S2_EMAIL, CATEGORY_WEEKLY_SUMMARY)) == 0,
                  f"counts={counts}")

        # ---- 12: görevsiz s4 almadı
        with SessionLocal() as db:
            check("12. görevsiz öğrenci özet almaz",
                  len(_comm_rows(db, S4_EMAIL, CATEGORY_WEEKLY_SUMMARY)) == 0,
                  f"counts={counts}")

        # ---- 13: SMTP hatası → comm_log failed + 'failed' döner (dürüstlük)
        with SessionLocal() as db:  # s3 7. adımda özet aldı — dedup'ı temizle
            db.execute(sa_delete(CommunicationLog).where(
                CommunicationLog.to_address == S3_EMAIL,
                CommunicationLog.category == CATEGORY_WEEKLY_SUMMARY))
            db.commit()
        FAIL_MODE["on"] = True
        with SessionLocal() as db:
            s3 = db.get(User, ids["s3"])
            res = send_student_weekly_summary(
                db, student=s3,
                week_start=date.today() - timedelta(days=7),
                week_end=date.today() - timedelta(days=1),
            )
        FAIL_MODE["on"] = False
        with SessionLocal() as db:
            rows = _comm_rows(db, S3_EMAIL, CATEGORY_WEEKLY_SUMMARY)
            check("13. SMTP hatası → 'failed' + comm_log failed satırı",
                  res == "failed" and len(rows) == 1 and rows[0].status == "failed",
                  f"res={res} rows={[(x.status,) for x in rows]}")

        # ---- 14: cron kaydı tutarlılığı
        from app.services.cron_jobs import JOB_REGISTRY
        mig = (Path(__file__).resolve().parent.parent / "alembic" / "versions" /
               "o5p8s1u2u55o_student_weekly_email_cron.py").read_text(encoding="utf-8")
        check("14. cron JOB_REGISTRY + migration seed eşleşir",
              "student_weekly_email" in JOB_REGISTRY and '"student_weekly_email"' in mig, "")

    finally:
        (settings.email_enabled, settings.smtp_host, settings.smtp_use_ssl,
         settings.smtp_use_tls, settings.smtp_user) = saved
        email_service.smtplib.SMTP = real_smtp
        email_service.smtplib.SMTP_SSL = real_smtp_ssl
        _cleanup(ids)

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print("  FAIL:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
