"""Faz 1 manuel test temizliği — full_setup'ta oluşturulanları siler."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Institution,
    NotificationLog,
    ParentNotificationPref,
    ParentSessionLog,
    ParentStudentLink,
    PhoneVerification,
    SuspiciousIp,
    User,
    WhatsAppDispatchLog,
)


PFX = "faz1"

EMAILS = [
    f"{PFX}_admin@test.invalid",
    f"{PFX}_kocA_bagimsiz@test.invalid",
    f"{PFX}_kurum_yoneticisi@test.invalid",
    f"{PFX}_ogretmenB_kurum@test.invalid",
    f"{PFX}_ogrenci1_bagimsiz@test.invalid",
    f"{PFX}_ogrenci2_kurum@test.invalid",
    f"{PFX}_veli1A_anne@test.invalid",
    f"{PFX}_veli1B_baba_telefonsuz@test.invalid",
    f"{PFX}_veli2_anne@test.invalid",
]


def main() -> int:
    with SessionLocal() as db:
        users = db.query(User).filter(User.email.in_(EMAILS)).all()
        user_ids = [u.id for u in users]
        if not user_ids:
            print("Faz 1 test verisi yok — temizlemeye gerek yok.")
            return 0
        db.execute(sa_delete(WhatsAppDispatchLog).where(
            WhatsAppDispatchLog.sender_user_id.in_(user_ids)
        ))
        db.execute(sa_delete(ParentSessionLog).where(
            ParentSessionLog.parent_id.in_(user_ids)
        ))
        db.execute(sa_delete(NotificationLog).where(
            NotificationLog.parent_id.in_(user_ids)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(user_ids)
            | ParentStudentLink.student_id.in_(user_ids)
        ))
        db.execute(sa_delete(ParentNotificationPref).where(
            ParentNotificationPref.parent_id.in_(user_ids)
        ))
        db.execute(sa_delete(PhoneVerification).where(
            PhoneVerification.user_id.in_(user_ids)
        ))
        db.execute(sa_delete(User).where(User.id.in_(user_ids)))
        db.execute(sa_delete(Institution).where(Institution.slug == f"{PFX}-kurum-x"))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()
        print(f"Faz 1 temizlendi: {len(user_ids)} kullanıcı + kurum + bağımlı kayıtlar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
