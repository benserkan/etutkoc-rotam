"""P3 — Click-to-WhatsApp URL üretici + yetki + dispatch log smoke testleri.

Senaryolar (~13):
   1. Auth: anon → 401
   2. Auth: PARENT → 403 role_not_allowed
   3. Mevcut olmayan template_id → 404 template_not_found
   4. Mevcut olmayan target_user_id → 404 target_not_found
   5. Telefon doğrulanmamış hedef → 400 target_phone_not_verified
   6. Yabancı koç → başkasının öğrencisi → 404 target_not_found (yetki)
   7. Koç → kendi öğrencisi (happy) → 200 + wa.me URL + log yazıldı
   8. Koç → kendi velisi (ParentStudentLink) → 200
   9. Süper admin → herkese → 200
  10. allow_freeform_note=False + note → 400 freeform_not_allowed
  11. allow_freeform_note=True + note → metin sonunda not görünür
  12. Telefon maskeleme: "+90 532 *** ** 67" deseni
  13. URL: wa.me/905...?text=... + Türkçe karakter percent-encoded
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

import secrets as _secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    ParentRelation,
    ParentStudentLink,
    SuspiciousIp,
    User,
    UserRole,
    WhatsAppDispatchLog,
    WhatsAppTemplate,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2wal_{_secrets.token_hex(3)}"
COACH_EMAIL = f"{PFX}_coach@test.invalid"
COACH2_EMAIL = f"{PFX}_coach2@test.invalid"  # başka koç (yetki testi)
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
STUDENT_EMAIL = f"{PFX}_student@test.invalid"
PARENT_EMAIL = f"{PFX}_parent@test.invalid"
PARENT_NO_PHONE_EMAIL = f"{PFX}_parent_no_phone@test.invalid"
PASSWORD = "TestWaLink!2345"

VERIFIED_PHONE = "905321234567"
SECOND_PHONE = "905339998877"

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
        admin = User(
            email=ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Admin", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        coach = User(
            email=COACH_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Coach", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        coach2 = User(
            email=COACH2_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Coach2", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([admin, coach, coach2])
        db.flush()

        # Öğrenci — coach'a bağlı + telefonu doğrulu
        student = User(
            email=STUDENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Öğrenci",  # Türkçe karakter test
            role=UserRole.STUDENT,
            teacher_id=coach.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=VERIFIED_PHONE, phone_verified_at=now,
        )
        # Veli — student'in velisi + telefonu doğrulu
        parent = User(
            email=PARENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Veli",
            role=UserRole.PARENT, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=SECOND_PHONE, phone_verified_at=now,
        )
        # Telefonsuz veli
        parent_no_phone = User(
            email=PARENT_NO_PHONE_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Veli (telefonsuz)",
            role=UserRole.PARENT, is_active=True,
            password_changed_at=now, must_change_password=False,
            # phone yok
        )
        db.add_all([student, parent, parent_no_phone])
        db.flush()

        link = ParentStudentLink(
            parent_id=parent.id, student_id=student.id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        link2 = ParentStudentLink(
            parent_id=parent_no_phone.id, student_id=student.id,
            relation=ParentRelation.BABA, is_primary=False,
        )
        db.add_all([link, link2])

        # Test şablonları: biri freeform_note kapalı, biri açık
        tmpl_no_note = WhatsAppTemplate(
            key=f"{PFX}_test_no_note",
            category="veli", target_role="teacher",
            name_tr="Test (not yok)",
            description="",
            content_template="Merhaba {{veli_adi}}, {{ogrenci_adi}} için mesaj.",
            variables_json='[{"key":"veli_adi","label_tr":"Veli","example":"Ayşe"},'
                           '{"key":"ogrenci_adi","label_tr":"Öğrenci","example":"Mehmet"}]',
            requires_date=False, allow_bulk=False, allow_freeform_note=False,
            sort_order=100, is_active=True,
        )
        tmpl_with_note = WhatsAppTemplate(
            key=f"{PFX}_test_with_note",
            category="veli", target_role="teacher",
            name_tr="Test (not izinli)",
            description="",
            content_template="Tebrikler {{ogrenci_adi}}!",
            variables_json='[{"key":"ogrenci_adi","label_tr":"Öğrenci","example":"Mehmet"}]',
            requires_date=False, allow_bulk=False, allow_freeform_note=True,
            sort_order=110, is_active=True,
        )
        db.add_all([tmpl_no_note, tmpl_with_note])
        db.commit()

        return {
            "admin_id": admin.id,
            "coach_id": coach.id,
            "coach2_id": coach2.id,
            "student_id": student.id,
            "parent_id": parent.id,
            "parent_no_phone_id": parent_no_phone.id,
            "tmpl_no_note_id": tmpl_no_note.id,
            "tmpl_with_note_id": tmpl_with_note.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        all_user_ids = [
            seed["admin_id"], seed["coach_id"], seed["coach2_id"],
            seed["student_id"], seed["parent_id"], seed["parent_no_phone_id"],
        ]
        db.execute(sa_delete(WhatsAppDispatchLog).where(
            WhatsAppDispatchLog.sender_user_id.in_(all_user_ids)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(all_user_ids)
        ))
        db.execute(sa_delete(WhatsAppTemplate).where(
            WhatsAppTemplate.id.in_([seed["tmpl_no_note_id"], seed["tmpl_with_note_id"]])
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_user_ids)))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def main() -> int:
    print(f"\n=== P3 wa-link smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()

    try:
        # ===== 1. Anon → 401 =====
        c_anon = TestClient(app)
        r = c_anon.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["student_id"],
            "variables": {},
        })
        check(
            "1. Anon → 401",
            r.status_code == 401,
            f"status={r.status_code}",
        )

        # ===== 2. PARENT → 403 role_not_allowed =====
        # Önce parent için login (telefon doğrulu olanı) — şifre değişimi var mı?
        # Yok, direkt login
        c_parent = TestClient(app)
        assert _login(c_parent, PARENT_EMAIL), "parent login fail"
        r = c_parent.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["student_id"],
            "variables": {},
        })
        ok = (
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_not_allowed"
        )
        check(
            "2. PARENT → 403 role_not_allowed",
            ok,
            f"status={r.status_code}",
        )

        # Coach login (asıl test)
        c_coach = TestClient(app)
        assert _login(c_coach, COACH_EMAIL), "coach login fail"

        # ===== 3. Yok olan template → 404 template_not_found =====
        r = c_coach.post("/api/v2/messaging/wa-link", json={
            "template_id": 999_999,
            "target_user_id": seed["student_id"],
            "variables": {},
        })
        ok = (
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "template_not_found"
        )
        check(
            "3. Yok olan template → 404 template_not_found",
            ok,
            f"status={r.status_code}",
        )

        # ===== 4. Yok olan target → 404 target_not_found =====
        r = c_coach.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": 999_999,
            "variables": {},
        })
        ok = (
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "target_not_found"
        )
        check(
            "4. Yok olan target → 404 target_not_found",
            ok,
            f"status={r.status_code}",
        )

        # ===== 5. Telefonsuz hedef → 400 target_phone_not_verified =====
        r = c_coach.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["parent_no_phone_id"],
            "variables": {},
        })
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "target_phone_not_verified"
        )
        check(
            "5. Telefonsuz hedef → 400 target_phone_not_verified",
            ok,
            f"status={r.status_code}",
        )

        # ===== 6. Yabancı koç → başkasının öğrencisi → 404 (yetki sızıntı) =====
        c_coach2 = TestClient(app)
        assert _login(c_coach2, COACH2_EMAIL), "coach2 login fail"
        r = c_coach2.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["student_id"],
            "variables": {},
        })
        ok = (
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "target_not_found"
        )
        check(
            "6. Yabancı koç → başkasının öğrencisi → 404 target_not_found",
            ok,
            f"status={r.status_code}",
        )

        # ===== 7. Koç → kendi öğrencisi → 200 + log =====
        r = c_coach.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["student_id"],
            "variables": {"veli_adi": "Ayşe", "ogrenci_adi": "Mehmet"},
        })
        data = r.json() if r.status_code == 200 else {}
        wa_url = data.get("wa_url", "")
        log_id = data.get("log_id")
        ok = (
            r.status_code == 200
            and wa_url.startswith(f"https://wa.me/{VERIFIED_PHONE}?text=")
            and "Merhaba Ay" in data.get("rendered_text", "")
            and log_id is not None
        )
        check(
            "7. Koç → kendi öğrencisi → 200 + URL + log",
            ok,
            f"status={r.status_code} url={wa_url[:80]}",
        )

        # ===== 8. Koç → kendi velisi → 200 =====
        r = c_coach.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["parent_id"],
            "variables": {"veli_adi": "Anne Adı", "ogrenci_adi": "Mehmet"},
        })
        data = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and data.get("wa_url", "").startswith(f"https://wa.me/{SECOND_PHONE}")
        )
        check(
            "8. Koç → öğrenci velisi → 200",
            ok,
            f"status={r.status_code}",
        )

        # ===== 9. Süper admin → herkese →  200 =====
        c_admin = TestClient(app)
        assert _login(c_admin, ADMIN_EMAIL), "admin login fail"
        r = c_admin.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["student_id"],
            "variables": {"veli_adi": "X", "ogrenci_adi": "Y"},
        })
        ok = r.status_code == 200
        check(
            "9. Süper admin → herkese → 200",
            ok,
            f"status={r.status_code}",
        )

        # ===== 10. allow_freeform_note=False + note → 400 freeform_not_allowed =====
        r = c_coach.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["student_id"],
            "variables": {},
            "freeform_note": "Ekstra mesaj",
        })
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "freeform_not_allowed"
        )
        check(
            "10. note kapalı şablon + note → 400 freeform_not_allowed",
            ok,
            f"status={r.status_code}",
        )

        # ===== 11. allow_freeform_note=True + note → eklendi =====
        r = c_coach.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_with_note_id"],
            "target_user_id": seed["student_id"],
            "variables": {"ogrenci_adi": "Mehmet"},
            "freeform_note": "Geçen haftanın hedefini de geçtin!",
        })
        data = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and "Geçen haftanın hedefini" in data.get("rendered_text", "")
        )
        check(
            "11. note açık şablon + note → metin sonunda not",
            ok,
            f"status={r.status_code}",
        )

        # ===== 12. Telefon maskeleme deseni =====
        r = c_coach.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["student_id"],
            "variables": {},
        })
        data = r.json() if r.status_code == 200 else {}
        masked = data.get("target_phone_masked", "")
        ok = (
            r.status_code == 200
            and masked.startswith("+90 532")
            and "***" in masked
            and masked.endswith("67")
        )
        check(
            "12. Telefon maskeleme '+90 532 *** ** 67' deseni",
            ok,
            f"masked={masked}",
        )

        # ===== 13. Türkçe karakter URL encoding =====
        # rendered'ta "Merhaba Ay" var (Ayşe değişkeni). URL'de %C5%9F geçer mi?
        ok = (
            "Ay%C5%9Fe" in data.get("wa_url", "")  # ş encoded
            or "Ay%C5%9Fe" in (data.get("wa_url", "").replace("%20", " "))
        )
        # Test edilebilir: c_coach 7. testte "Ayşe" gönderdi → URL'de %C5%9F olmalı
        # Direkt yeniden çağıralım
        r = c_coach.post("/api/v2/messaging/wa-link", json={
            "template_id": seed["tmpl_no_note_id"],
            "target_user_id": seed["student_id"],
            "variables": {"veli_adi": "Ayşe", "ogrenci_adi": "Mehmet"},
        })
        url_with_tr = r.json().get("wa_url", "") if r.status_code == 200 else ""
        ok = "Ay%C5%9Fe" in url_with_tr
        check(
            "13. Türkçe karakter percent-encoded (Ayşe → Ay%C5%9Fe)",
            ok,
            f"url snippet: {url_with_tr[:120]}",
        )

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== Result: {passed} passed, {len(failed)} failed ===\n")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
