"""P4 manuel test hazırlığı — koç + öğrenci + veli (HEPSİ TELEFON DOĞRULU).

WhatsApp gönderim dialog'unu test edebilmek için hedef kullanıcıların
telefonları önceden doğrulanmış olarak oluşturulur.

Kullanım:
    python scripts/p4_manual_test_setup.py

Bitirince: python scripts/p4_manual_test_cleanup.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    NotificationLog,
    ParentNotificationPref,
    ParentRelation,
    ParentSessionLog,
    ParentStudentLink,
    PhoneVerification,
    User,
    UserRole,
    WhatsAppDispatchLog,
)
from app.services.security import hash_password


PFX = "p4man"
COACH_EMAIL = f"{PFX}_kocum@test.invalid"
PARENT_EMAIL = f"{PFX}_velim@test.invalid"
STUDENT_EMAIL = f"{PFX}_ogrencim@test.invalid"
PARENT_NO_PHONE_EMAIL = f"{PFX}_velim2_telefonsuz@test.invalid"
PASSWORD = "TestP4Manuel!23"

PHONE_STUDENT = "905320000001"
PHONE_PARENT = "905320000002"

BASE_URL = "http://127.0.0.1:3000"


def main() -> int:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)

    with SessionLocal() as db:
        # Idempotent temizlik
        emails = [COACH_EMAIL, PARENT_EMAIL, STUDENT_EMAIL, PARENT_NO_PHONE_EMAIL]
        prev_users = db.query(User).filter(User.email.in_(emails)).all()
        prev_ids = [u.id for u in prev_users]
        if prev_ids:
            db.execute(sa_delete(WhatsAppDispatchLog).where(
                WhatsAppDispatchLog.sender_user_id.in_(prev_ids)
            ))
            db.execute(sa_delete(ParentSessionLog).where(
                ParentSessionLog.parent_id.in_(prev_ids)
            ))
            db.execute(sa_delete(NotificationLog).where(
                NotificationLog.parent_id.in_(prev_ids)
            ))
            db.execute(sa_delete(ParentStudentLink).where(
                ParentStudentLink.parent_id.in_(prev_ids)
                | ParentStudentLink.student_id.in_(prev_ids)
            ))
            db.execute(sa_delete(ParentNotificationPref).where(
                ParentNotificationPref.parent_id.in_(prev_ids)
            ))
            db.execute(sa_delete(PhoneVerification).where(
                PhoneVerification.user_id.in_(prev_ids)
            ))
            db.execute(sa_delete(User).where(User.id.in_(prev_ids)))
            db.commit()

        coach = User(
            email=COACH_EMAIL, password_hash=pwd,
            full_name="P4 Manuel Test Koc", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add(coach)
        db.flush()

        # Telefon doğrulu öğrenci
        student = User(
            email=STUDENT_EMAIL, password_hash=pwd,
            full_name="P4 Test Ogrencisi", role=UserRole.STUDENT,
            teacher_id=coach.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONE_STUDENT, phone_verified_at=now,
        )
        # Telefon doğrulu veli
        parent = User(
            email=PARENT_EMAIL, password_hash=pwd,
            full_name="P4 Test Velisi (Anne)", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
            phone=PHONE_PARENT, phone_verified_at=now,
        )
        # Telefon doğrulanmamış veli — "telefon yok" durumunu test için
        parent_no_phone = User(
            email=PARENT_NO_PHONE_EMAIL, password_hash=pwd,
            full_name="P4 Test Velisi (Baba — telefonsuz)", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([student, parent, parent_no_phone])
        db.flush()

        # 2 veli aynı öğrenciye bağlı
        db.add_all([
            ParentStudentLink(
                parent_id=parent.id, student_id=student.id,
                relation=ParentRelation.ANNE, is_primary=True,
            ),
            ParentStudentLink(
                parent_id=parent_no_phone.id, student_id=student.id,
                relation=ParentRelation.BABA, is_primary=False,
            ),
        ])
        db.commit()

        student_id = student.id
        parent_id = parent.id

    print()
    print("=" * 70)
    print("P4 MANUEL TEST HAZIR — WhatsApp Tekli Gonderim Dialog")
    print("=" * 70)
    print()
    print(f"Sifre (koc icin): {PASSWORD}")
    print()
    print("=" * 70)
    print("TARAYICIDA TEST AKISI:")
    print("=" * 70)
    print()
    print(f"1) {BASE_URL}/login")
    print(f"   Email: {COACH_EMAIL}")
    print(f"   Sifre: {PASSWORD}")
    print()
    print(f"2) Sol menude 'Ogrenciler' -> 'P4 Test Ogrencisi' tikla")
    print(f"   YA DA dogrudan:")
    print(f"   {BASE_URL}/teacher/students/{student_id}")
    print()
    print(f"3) Sayfanin saginda 'WA Gonder' EMERALD butona bas")
    print(f"   -> Dialog acilir, hedef = ogrenci (telefon dogrulu)")
    print(f"   -> Sablon sec, degisken doldur, 'Onizle'")
    print(f"   -> 'WhatsApp'i Ac' -> yeni sekmede wa.me linki acilir")
    print()
    print(f"4) Veliler sekmesine tikla")
    print(f"   -> Anne satirinda yesil MessageSquare ikon")
    print(f"   -> Tikla -> Anne icin dialog (telefon dogrulu)")
    print(f"   -> Baba satirinda da MessageSquare ikon")
    print(f"   -> Tikla -> 'Telefon dogrulanmamis' amber uyari (telefonsuz veli)")
    print()
    print("=" * 70)
    print()
    print("Bitirince:")
    print("  python scripts/p4_manual_test_cleanup.py")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
