"""P0 manuel test hazırlığı — test öğretmen + öğrenci + veli daveti oluştur.

Kullanım:
    python scripts/p0_manual_test_setup.py

Çıktı: bir veli daveti URL'si (tarayıcıda aç).
Bitirdikten sonra: python scripts/p0_manual_test_cleanup.py
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

from app.database import SessionLocal
from sqlalchemy import delete as sa_delete

from app.models import (
    NotificationLog,
    ParentInvitation,
    ParentNotificationPref,
    ParentRelation,
    ParentSessionLog,
    ParentStudentLink,
    User,
    UserRole,
)
from app.services.parent_invitation import create_invitation
from app.services.security import hash_password


# Sabit prefix — cleanup için kolay bul
PFX = "p0man"
TEACHER_EMAIL = f"{PFX}_ogretmen@test.invalid"
STUDENT_EMAIL = f"{PFX}_ogrenci@test.invalid"
PARENT_EMAIL = f"{PFX}_veli@test.invalid"
PASSWORD = "TestP0Manuel!23"

# Tarayıcıda açacağın URL'nin base'i. Local'de 3000 (Next.js dev).
BASE_URL = "http://127.0.0.1:3000"


def main() -> int:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)

    with SessionLocal() as db:
        # Idempotent temizlik — SQLite'da CASCADE her zaman çalışmaz, manuel sil
        prev_users = db.query(User).filter(
            User.email.in_([TEACHER_EMAIL, STUDENT_EMAIL, PARENT_EMAIL])
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
            db.execute(sa_delete(ParentInvitation).where(
                ParentInvitation.invited_by_id.in_(prev_ids)
            ))
            db.execute(sa_delete(User).where(User.id.in_(prev_ids)))
            db.commit()

        teacher = User(
            email=TEACHER_EMAIL, password_hash=pwd,
            full_name="P0 Manuel Test Ogretmen", role=UserRole.TEACHER,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add(teacher)
        db.flush()

        student = User(
            email=STUDENT_EMAIL, password_hash=pwd,
            full_name="P0 Manuel Test Ogrenci", role=UserRole.STUDENT,
            teacher_id=teacher.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add(student)
        db.flush()

        # Veli daveti (henüz kabul edilmemiş — manuel test bunu açacak)
        inv = create_invitation(
            db,
            invited_email=PARENT_EMAIL,
            student_id=student.id,
            invited_by_id=teacher.id,
            relation=ParentRelation.ANNE,
            is_primary=True,
        )
        db.commit()

        invitation_url = f"{BASE_URL}/parent/invitation/{inv.token}"

        print()
        print("=" * 70)
        print("P0 MANUEL TEST HAZIR")
        print("=" * 70)
        print()
        print("Olusturulanlar:")
        print(f"  Ogretmen     : {teacher.email}  (id={teacher.id})")
        print(f"  Ogrenci      : {student.email}  (id={student.id})")
        print(f"  Veli e-posta : {PARENT_EMAIL}  (henuz hesap yok)")
        print(f"  Davet token  : {inv.token}")
        print()
        print("=" * 70)
        print("TARAYICIDA AC:")
        print("=" * 70)
        print()
        print(f"  {invitation_url}")
        print()
        print("=" * 70)
        print()
        print("Testlerini bitirince temizleme:")
        print("  python scripts/p0_manual_test_cleanup.py")
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
