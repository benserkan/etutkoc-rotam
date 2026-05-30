"""P0 manuel test temizliği — setup'ta oluşturulan tüm test verisini siler."""
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
    NotificationLog,
    ParentInvitation,
    ParentNotificationPref,
    ParentSessionLog,
    ParentStudentLink,
    SuspiciousIp,
    User,
)


PFX = "p0man"
EMAILS = [
    f"{PFX}_ogretmen@test.invalid",
    f"{PFX}_ogrenci@test.invalid",
    f"{PFX}_veli@test.invalid",
]


def main() -> int:
    with SessionLocal() as db:
        users = db.query(User).filter(User.email.in_(EMAILS)).all()
        user_ids = [u.id for u in users]

        if not user_ids:
            print("Temizlenecek test verisi yok.")
            return 0

        # Parent (veli) varsa onun bağımlı kayıtları
        parent_user = next((u for u in users if u.email == EMAILS[2]), None)
        if parent_user:
            db.execute(sa_delete(ParentSessionLog).where(
                ParentSessionLog.parent_id == parent_user.id
            ))
            db.execute(sa_delete(NotificationLog).where(
                NotificationLog.parent_id == parent_user.id
            ))
            db.execute(sa_delete(ParentStudentLink).where(
                ParentStudentLink.parent_id == parent_user.id
            ))
            db.execute(sa_delete(ParentNotificationPref).where(
                ParentNotificationPref.parent_id == parent_user.id
            ))

        # Öğretmenin oluşturduğu tüm davet token'ları
        teacher = next((u for u in users if u.email == EMAILS[0]), None)
        if teacher:
            db.execute(sa_delete(ParentInvitation).where(
                ParentInvitation.invited_by_id == teacher.id
            ))

        # Suspicious IP temizliği
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))

        # En son user satırlarını sil
        db.execute(sa_delete(User).where(User.id.in_(user_ids)))
        db.commit()

        print(f"Temizlendi: {len(user_ids)} test hesabı + bağımlı kayıtlar.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
