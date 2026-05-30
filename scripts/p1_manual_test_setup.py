"""P1 manuel test hazırlığı — test koç + test veli oluştur ve giriş bilgileri ver.

Kullanım:
    python scripts/p1_manual_test_setup.py

Çıktı: 2 test kullanıcısı (koç + veli) — giriş bilgileri.
Bitirdikten sonra: python scripts/p1_manual_test_cleanup.py
"""
from __future__ import annotations

import os
import sys

# Proje kökünü sys.path'e ekle — PYTHONPATH ayarsız çalışabilsin
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
)
from app.services.security import hash_password


PFX = "p1man"
COACH_EMAIL = f"{PFX}_kocum@test.invalid"
PARENT_EMAIL = f"{PFX}_velim@test.invalid"
STUDENT_EMAIL = f"{PFX}_ogrencim@test.invalid"
PASSWORD = "TestP1Manuel!23"

BASE_URL = "http://127.0.0.1:3000"


def main() -> int:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)

    with SessionLocal() as db:
        # Idempotent temizlik — SQLite'da CASCADE her zaman çalışmaz, manuel sil
        prev_users = db.query(User).filter(
            User.email.in_([COACH_EMAIL, PARENT_EMAIL, STUDENT_EMAIL])
        ).all()
        prev_ids = [u.id for u in prev_users]
        if prev_ids:
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
            full_name="P1 Manuel Test Koc", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        parent = User(
            email=PARENT_EMAIL, password_hash=pwd,
            full_name="P1 Manuel Test Veli", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([coach, parent])
        db.flush()

        student = User(
            email=STUDENT_EMAIL, password_hash=pwd,
            full_name="P1 Manuel Test Ogrenci", role=UserRole.STUDENT,
            teacher_id=coach.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add(student)
        db.flush()

        link = ParentStudentLink(
            parent_id=parent.id, student_id=student.id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        db.add(link)
        db.commit()

        print()
        print("=" * 70)
        print("P1 MANUEL TEST HAZIR — TELEFON DOGRULAMA AKISI")
        print("=" * 70)
        print()
        print("Olusturulanlar:")
        print(f"  Koc (TEACHER)   id={coach.id}")
        print(f"  Veli (PARENT)   id={parent.id}  -> 2 telefon (anne+baba) testi")
        print(f"  Ogrenci         id={student.id}  (koc'a bagli, veli'ye bagli)")
        print()
        print("Sifre (her ikisi icin): " + PASSWORD)
        print()
        print("=" * 70)
        print("TARAYICIDA TEST AKISI:")
        print("=" * 70)
        print()
        print(f"1) {BASE_URL}/login")
        print(f"   Email: {COACH_EMAIL}")
        print(f"   Sifre: {PASSWORD}")
        print(f"   -> Koc paneline gir")
        print()
        print(f"2) {BASE_URL}/me/account")
        print(f"   -> 'Cep Telefonu' karti gorulur (Kapali durum)")
        print(f"   -> '0532 123 45 67' gir, 'Dogrulama Kodu Gonder'")
        print(f"   -> SMS_ENABLED=false oldugu icin DEV stub kutusu kodu gosterir")
        print(f"   -> Kodu input'a gir, 'Kodu Dogrula' -> 'Dogrulandi' yesil rozet")
        print()
        print(f"3) Cikis yap, veli ile giris:")
        print(f"   Email: {PARENT_EMAIL}")
        print(f"   Sifre: {PASSWORD}")
        print()
        print(f"4) {BASE_URL}/me/account")
        print(f"   -> 'Cep Telefonu' karti + EXTRA 'Ikinci Telefon (Veli)' karti gorulur")
        print(f"   -> Hem birincil hem ikinci numara icin SMS+dogrulama akisini dene")
        print()
        print("=" * 70)
        print()
        print("Testlerini bitirince temizleme:")
        print("  python scripts/p1_manual_test_cleanup.py")
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
