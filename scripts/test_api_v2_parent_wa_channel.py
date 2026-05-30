"""P0 — Veli bildirim tercihleri kanal-aware (e-posta + WhatsApp ayrı) +
aktivasyon iletişim tercih matrisi + KVKK v2 audit + producer kanal-aware.

Senaryolar (~14):
   1. GET /settings → mevcut veli için 7 e-posta + 7 WA + child_consent default
   2. POST /settings/preferences (yeni body — WA + child_consent) → kaydedildi
   3. POST /settings/preferences ile child_whatsapp_consent=True → kaydedildi
   4. POST /settings/preferences eski body (WA alanları yok) → 422 (zorunlu alan)
      veya 200 (default False) — kontrol edelim
   5. Aktivasyon: yeni veli + notification_preferences body → pref kanal-bazlı
   6. Aktivasyon: child_whatsapp_consent=True → audit kvkk_consent_v2 + pref
   7. Aktivasyon: child_whatsapp_consent=False (yeni hesap) → audit yine kvkk_consent_v2
   8. Aktivasyon: notification_preferences yok (eski istemci) → defaults aktif
   9. Aktivasyon: quiet_start/quiet_end → pref'e doğru atanır
  10. Producer: kind=DAILY_SUMMARY + EMAIL + daily_summary_enabled=False → SUPPRESSED (pref:..._enabled)
  11. Producer: kind=DAILY_SUMMARY + EMAIL + daily_summary_enabled=True → QUEUED
  12. Producer: kind=DAILY_SUMMARY + WHATSAPP + daily_summary_wa_enabled=False → SUPPRESSED (pref:..._wa_enabled)
  13. Producer: kind=DAILY_SUMMARY + WHATSAPP + daily_summary_wa_enabled=True + whatsapp_enabled=False → SUPPRESSED (whatsapp_not_enabled)
  14. Producer: kind=DAILY_SUMMARY + WHATSAPP + tüm açık + telefon doğrulanmış → QUEUED
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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
from app.models import (
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentInvitation,
    ParentNotificationPref,
    ParentRelation,
    ParentSessionLog,
    ParentStudentLink,
    SuspiciousIp,
    User,
    UserRole,
)
from app.services.notification_producer import enqueue_notification
from app.services.parent_invitation import create_invitation
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2pwac_{secrets.token_hex(3)}"
TEACHER_EMAIL = f"{PFX}_t@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
PARENT_EMAIL = f"{PFX}_p@test.invalid"
NEW_PARENT_EMAIL = f"{PFX}_newp@test.invalid"
NEW_PARENT_EMAIL_2 = f"{PFX}_newp2@test.invalid"
NEW_PARENT_EMAIL_3 = f"{PFX}_newp3@test.invalid"
PASSWORD = "TestPassWaCh!23"

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


def _login(c: TestClient, email: str) -> bool:
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    return r.status_code == 200


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Teacher", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add(teacher)
        db.flush()

        student = User(
            email=STUDENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Student", role=UserRole.STUDENT,
            teacher_id=teacher.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        parent = User(
            email=PARENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Parent", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([student, parent])
        db.flush()

        # Parent-student link + pref (default açık e-posta, kapalı WA)
        link = ParentStudentLink(
            parent_id=parent.id, student_id=student.id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        pref = ParentNotificationPref(
            parent_id=parent.id,
            unsubscribe_token="UNSUB_" + secrets.token_hex(12),
        )
        db.add_all([link, pref])

        # 3 valid davet — aktivasyon senaryoları için
        valid_inv_1 = create_invitation(
            db, invited_email=NEW_PARENT_EMAIL,
            student_id=student.id, invited_by_id=teacher.id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        valid_inv_2 = create_invitation(
            db, invited_email=NEW_PARENT_EMAIL_2,
            student_id=student.id, invited_by_id=teacher.id,
            relation=ParentRelation.BABA, is_primary=False,
        )
        valid_inv_3 = create_invitation(
            db, invited_email=NEW_PARENT_EMAIL_3,
            student_id=student.id, invited_by_id=teacher.id,
            relation=ParentRelation.VASI, is_primary=False,
        )

        db.commit()

        return {
            "teacher_id": teacher.id,
            "student_id": student.id,
            "parent_id": parent.id,
            "valid_token_1": valid_inv_1.token,
            "valid_token_2": valid_inv_2.token,
            "valid_token_3": valid_inv_3.token,
        }


def _cleanup(seed: dict, extra_user_ids: list[int]) -> None:
    with SessionLocal() as db:
        parent_ids = [seed["parent_id"]] + extra_user_ids
        student_ids = [seed["student_id"]]
        all_user_ids = parent_ids + student_ids + [seed["teacher_id"]]

        db.execute(sa_delete(ParentSessionLog).where(
            ParentSessionLog.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(NotificationLog).where(
            NotificationLog.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(ParentNotificationPref).where(
            ParentNotificationPref.parent_id.in_(parent_ids)
        ))
        db.execute(sa_delete(ParentInvitation).where(
            ParentInvitation.invited_by_id == seed["teacher_id"]
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_user_ids)))
        # Auth p1 sertleşmesi: testclient IP'sinin SuspiciousIp kalıntılarını temizle
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def main() -> int:
    print(f"\n=== P0 WA channel + aktivasyon KVKK smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    extra_user_ids: list[int] = []

    try:
        c = TestClient(app)
        assert _login(c, PARENT_EMAIL), "parent login failed"

        # ===== 1. GET /settings — yeni alanlar mevcut =====
        r = c.get("/api/v2/parent/settings")
        prefs = r.json().get("preferences", {}) if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and prefs.get("daily_summary_enabled") is True
            and prefs.get("daily_summary_wa_enabled") is False
            and prefs.get("weekly_report_wa_enabled") is False
            and prefs.get("teacher_note_wa_enabled") is False
            and prefs.get("child_whatsapp_consent") is False
        )
        check(
            "1. GET /settings → 7 e-posta açık + 7 WA kapalı + child_consent=False",
            ok,
            f"status={r.status_code} prefs={list(prefs.keys())[:8]}",
        )

        # ===== 2. POST /settings/preferences (yeni body) =====
        body = {
            "daily_summary": True,
            "weekly_report": True,
            "empty_day": False,
            "new_program": True,
            "drop_alert": True,
            "teacher_note": True,
            "exam_approaching": True,
            "daily_summary_wa": True,
            "weekly_report_wa": True,
            "empty_day_wa": False,
            "new_program_wa": True,
            "drop_alert_wa": False,
            "teacher_note_wa": True,
            "exam_approaching_wa": True,
            "child_whatsapp_consent": True,
            "quiet_start": "23:00",
            "quiet_end": "08:00",
        }
        r = c.post("/api/v2/parent/settings/preferences", json=body)
        if r.status_code == 200:
            with SessionLocal() as db:
                p = db.query(ParentNotificationPref).filter(
                    ParentNotificationPref.parent_id == seed["parent_id"]
                ).first()
                ok = (
                    p is not None
                    and p.daily_summary_wa_enabled is True
                    and p.weekly_report_wa_enabled is True
                    and p.empty_day_alert_wa_enabled is False
                    and p.teacher_note_wa_enabled is True
                    and p.child_whatsapp_consent is True
                    and p.empty_day_alert_enabled is False
                )
        else:
            ok = False
        check(
            "2. POST /settings/preferences yeni body → kaydedildi",
            ok,
            f"status={r.status_code} body={r.text[:200]}",
        )

        # ===== 3. POST /settings/preferences child_whatsapp_consent off =====
        body_off = dict(body)
        body_off["child_whatsapp_consent"] = False
        r = c.post("/api/v2/parent/settings/preferences", json=body_off)
        if r.status_code == 200:
            with SessionLocal() as db:
                p = db.query(ParentNotificationPref).filter(
                    ParentNotificationPref.parent_id == seed["parent_id"]
                ).first()
                ok = p is not None and p.child_whatsapp_consent is False
        else:
            ok = False
        check(
            "3. POST /settings/preferences child_whatsapp_consent=False → kaydedildi",
            ok,
            f"status={r.status_code}",
        )

        # ===== 4. POST eski body (WA alanları yok) → 200 (default False) =====
        body_legacy = {
            "daily_summary": True,
            "weekly_report": True,
            "empty_day": True,
            "new_program": True,
            "drop_alert": True,
            "teacher_note": True,
            "exam_approaching": True,
            "quiet_start": "22:00",
            "quiet_end": "07:00",
        }
        r = c.post("/api/v2/parent/settings/preferences", json=body_legacy)
        if r.status_code == 200:
            with SessionLocal() as db:
                p = db.query(ParentNotificationPref).filter(
                    ParentNotificationPref.parent_id == seed["parent_id"]
                ).first()
                # Eski body WA alanlarını göndermez → Pydantic default False
                ok = (
                    p is not None
                    and p.daily_summary_wa_enabled is False
                    and p.weekly_report_wa_enabled is False
                    and p.child_whatsapp_consent is False
                )
        else:
            ok = False
        check(
            "4. POST /settings/preferences eski body → default False (geriye uyum)",
            ok,
            f"status={r.status_code}",
        )

        # ===== 5. Aktivasyon: yeni veli + notification_preferences =====
        c_new = TestClient(app)
        accept_body = {
            "full_name": f"{PFX} New Veli",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "kvkk_accept": True,
            "notification_preferences": {
                "daily_summary_email": True,
                "weekly_report_email": True,
                "empty_day_email": False,
                "drop_alert_email": True,
                "new_program_email": True,
                "teacher_note_email": True,
                "exam_approaching_email": True,
                "daily_summary_wa": True,
                "weekly_report_wa": False,
                "empty_day_wa": False,
                "drop_alert_wa": True,
                "new_program_wa": False,
                "teacher_note_wa": True,
                "exam_approaching_wa": False,
            },
            "quiet_start": "23:30",
            "quiet_end": "06:30",
            "child_whatsapp_consent": True,
        }
        r = c_new.post(
            f"/api/v2/parent/invitation/{seed['valid_token_1']}/accept",
            json=accept_body,
        )
        ok_act = r.status_code == 200 and r.json().get("is_new_account") is True
        if ok_act:
            with SessionLocal() as db:
                new_p = db.query(User).filter(User.email == NEW_PARENT_EMAIL).first()
                if new_p:
                    extra_user_ids.append(new_p.id)
                    new_pref = db.query(ParentNotificationPref).filter(
                        ParentNotificationPref.parent_id == new_p.id
                    ).first()
                    ok_act = (
                        new_pref is not None
                        and new_pref.daily_summary_enabled is True
                        and new_pref.empty_day_alert_enabled is False
                        and new_pref.daily_summary_wa_enabled is True
                        and new_pref.drop_alert_wa_enabled is True
                        and new_pref.weekly_report_wa_enabled is False
                        and new_pref.child_whatsapp_consent is True
                        and new_pref.quiet_hours_start.hour == 23
                        and new_pref.quiet_hours_start.minute == 30
                        and new_pref.quiet_hours_end.hour == 6
                        and new_pref.quiet_hours_end.minute == 30
                    )
        check(
            "5. Aktivasyon notification_preferences → pref kanal-bazlı kaydedildi",
            ok_act,
            f"status={r.status_code}",
        )

        # ===== 6. KVKK v2 audit — child_whatsapp_consent=True =====
        if r.status_code == 200:
            with SessionLocal() as db:
                new_p = db.query(User).filter(User.email == NEW_PARENT_EMAIL).first()
                if new_p:
                    audit_logs = db.query(ParentSessionLog).filter(
                        ParentSessionLog.parent_id == new_p.id,
                        ParentSessionLog.action == "kvkk_consent_v2",
                    ).all()
                    ok = len(audit_logs) == 1
                else:
                    ok = False
        else:
            ok = False
        check(
            "6. Aktivasyon child_consent=True → ParentSessionLog 'kvkk_consent_v2'",
            ok,
        )

        # ===== 7. Aktivasyon: child_consent=False, yine kvkk_consent_v2 audit =====
        c_new2 = TestClient(app)
        accept_body2 = {
            "full_name": f"{PFX} New Veli 2",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "kvkk_accept": True,
            "notification_preferences": {
                "daily_summary_email": True,
            },
            "child_whatsapp_consent": False,
        }
        r2 = c_new2.post(
            f"/api/v2/parent/invitation/{seed['valid_token_2']}/accept",
            json=accept_body2,
        )
        if r2.status_code == 200:
            with SessionLocal() as db:
                new_p2 = db.query(User).filter(User.email == NEW_PARENT_EMAIL_2).first()
                if new_p2:
                    extra_user_ids.append(new_p2.id)
                    # Yeni hesap olduğu için yine kvkk_consent_v2 audit'i bekleriz
                    audit_logs = db.query(ParentSessionLog).filter(
                        ParentSessionLog.parent_id == new_p2.id,
                        ParentSessionLog.action == "kvkk_consent_v2",
                    ).all()
                    new_pref2 = db.query(ParentNotificationPref).filter(
                        ParentNotificationPref.parent_id == new_p2.id
                    ).first()
                    ok = (
                        len(audit_logs) == 1
                        and new_pref2 is not None
                        and new_pref2.child_whatsapp_consent is False
                    )
                else:
                    ok = False
        else:
            ok = False
        check(
            "7. Aktivasyon yeni hesap child_consent=False → audit yine kvkk_consent_v2",
            ok,
            f"status={r2.status_code}",
        )

        # ===== 8. Aktivasyon: notification_preferences yok (eski istemci) =====
        c_new3 = TestClient(app)
        accept_body3 = {
            "full_name": f"{PFX} New Veli 3",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
            "kvkk_accept": True,
            # notification_preferences YOK — eski istemci simülasyonu
        }
        r3 = c_new3.post(
            f"/api/v2/parent/invitation/{seed['valid_token_3']}/accept",
            json=accept_body3,
        )
        if r3.status_code == 200:
            with SessionLocal() as db:
                new_p3 = db.query(User).filter(User.email == NEW_PARENT_EMAIL_3).first()
                if new_p3:
                    extra_user_ids.append(new_p3.id)
                    new_pref3 = db.query(ParentNotificationPref).filter(
                        ParentNotificationPref.parent_id == new_p3.id
                    ).first()
                    # Defaults: e-posta açık, WA kapalı, child_consent kapalı
                    ok = (
                        new_pref3 is not None
                        and new_pref3.daily_summary_enabled is True
                        and new_pref3.weekly_report_enabled is True
                        and new_pref3.daily_summary_wa_enabled is False
                        and new_pref3.weekly_report_wa_enabled is False
                        and new_pref3.child_whatsapp_consent is False
                    )
                else:
                    ok = False
        else:
            ok = False
        check(
            "8. Aktivasyon eski istemci (notif_prefs yok) → defaults aktif",
            ok,
            f"status={r3.status_code}",
        )

        # ===== 9. Quiet hours doğru parse edildi (test 5 ile birlikte) =====
        # Test 5'te 23:30/06:30 atadık → zaten doğrulandı (pref.quiet_hours_*)
        # Burada test 8'in defaults'unu kontrol edelim (22:00-07:00)
        if r3.status_code == 200:
            with SessionLocal() as db:
                new_p3 = db.query(User).filter(User.email == NEW_PARENT_EMAIL_3).first()
                if new_p3:
                    new_pref3 = db.query(ParentNotificationPref).filter(
                        ParentNotificationPref.parent_id == new_p3.id
                    ).first()
                    ok = (
                        new_pref3 is not None
                        and new_pref3.quiet_hours_start.hour == 22
                        and new_pref3.quiet_hours_end.hour == 7
                    )
                else:
                    ok = False
        else:
            ok = False
        check(
            "9. Aktivasyon eski istemci → quiet_hours default 22:00-07:00",
            ok,
        )

        # ===== 10. Producer EMAIL + daily_summary_enabled=False → SUPPRESSED =====
        # Önce mevcut parent_id için pref'i ayarla
        with SessionLocal() as db:
            p = db.query(ParentNotificationPref).filter(
                ParentNotificationPref.parent_id == seed["parent_id"]
            ).first()
            assert p is not None
            p.daily_summary_enabled = False
            p.daily_summary_wa_enabled = False
            p.whatsapp_enabled = False
            p.whatsapp_phone = None
            db.commit()

        with SessionLocal() as db:
            log = enqueue_notification(
                db,
                parent_id=seed["parent_id"],
                student_id=seed["student_id"],
                kind=NotificationKind.DAILY_SUMMARY,
                channel=NotificationChannel.EMAIL,
            )
            db.commit()
            ok = (
                log.status == NotificationStatus.SUPPRESSED
                and log.error is not None
                and "_enabled=False" in log.error
                and "_wa_" not in log.error
            )
        check(
            "10. Producer EMAIL + email kapalı → SUPPRESSED (pref:_enabled=False)",
            ok,
            f"status={log.status} error={log.error}",
        )

        # ===== 11. Producer EMAIL + daily_summary_enabled=True → QUEUED =====
        with SessionLocal() as db:
            p = db.query(ParentNotificationPref).filter(
                ParentNotificationPref.parent_id == seed["parent_id"]
            ).first()
            p.daily_summary_enabled = True
            db.commit()

        with SessionLocal() as db:
            log = enqueue_notification(
                db,
                parent_id=seed["parent_id"],
                student_id=seed["student_id"],
                kind=NotificationKind.DAILY_SUMMARY,
                channel=NotificationChannel.EMAIL,
            )
            db.commit()
            ok = log.status == NotificationStatus.QUEUED
        check(
            "11. Producer EMAIL + email açık → QUEUED",
            ok,
            f"status={log.status} error={log.error}",
        )

        # ===== 12. Producer WHATSAPP + wa_enabled=False → SUPPRESSED =====
        with SessionLocal() as db:
            log = enqueue_notification(
                db,
                parent_id=seed["parent_id"],
                student_id=seed["student_id"],
                kind=NotificationKind.DAILY_SUMMARY,
                channel=NotificationChannel.WHATSAPP,
            )
            db.commit()
            ok = (
                log.status == NotificationStatus.SUPPRESSED
                and log.error is not None
                and "_wa_enabled=False" in log.error
            )
        check(
            "12. Producer WHATSAPP + WA kapalı → SUPPRESSED (pref:_wa_enabled=False)",
            ok,
            f"status={log.status} error={log.error}",
        )

        # ===== 13. Producer WHATSAPP + wa_enabled=True + User.phone yok → SUPPRESSED phone_not_verified =====
        # P1: WA gönderim için User.phone + User.phone_verified_at dolu olmalı
        with SessionLocal() as db:
            p = db.query(ParentNotificationPref).filter(
                ParentNotificationPref.parent_id == seed["parent_id"]
            ).first()
            p.daily_summary_wa_enabled = True
            # User.phone yok
            db.commit()

        with SessionLocal() as db:
            log = enqueue_notification(
                db,
                parent_id=seed["parent_id"],
                student_id=seed["student_id"],
                kind=NotificationKind.DAILY_SUMMARY,
                channel=NotificationChannel.WHATSAPP,
            )
            db.commit()
            ok = (
                log.status == NotificationStatus.SUPPRESSED
                and log.error == "phone_not_verified"
            )
        check(
            "13. Producer WHATSAPP + WA açık + User.phone yok → SUPPRESSED phone_not_verified",
            ok,
            f"status={log.status} error={log.error}",
        )

        # ===== 14. Producer WHATSAPP + tüm açık + User.phone doğrulanmış → QUEUED =====
        with SessionLocal() as db:
            # P1: artık User.phone + User.phone_verified_at'e bakar
            u = db.query(User).filter(User.id == seed["parent_id"]).first()
            u.phone = "905321234567"
            u.phone_verified_at = datetime.now(timezone.utc)
            db.commit()

        with SessionLocal() as db:
            log = enqueue_notification(
                db,
                parent_id=seed["parent_id"],
                student_id=seed["student_id"],
                kind=NotificationKind.DAILY_SUMMARY,
                channel=NotificationChannel.WHATSAPP,
            )
            db.commit()
            ok = log.status == NotificationStatus.QUEUED
        check(
            "14. Producer WHATSAPP + tüm açık + telefon doğrulu → QUEUED",
            ok,
            f"status={log.status} error={log.error}",
        )

    finally:
        _cleanup(seed, extra_user_ids)
        get_login_limiter().reset()

    print(f"\n=== Result: {passed} passed, {len(failed)} failed ===\n")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
