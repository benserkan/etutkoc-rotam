"""P1 manuel test temizliği — setup'ta oluşturulan test verisini siler."""
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
    ParentStudentLink,
    PhoneVerification,
    SuspiciousIp,
    User,
)


PFX = "p1man"
EMAILS = [
    f"{PFX}_kocum@test.invalid",
    f"{PFX}_velim@test.invalid",
    f"{PFX}_ogrencim@test.invalid",
]


def main() -> int:
    with SessionLocal() as db:
        users = db.query(User).filter(User.email.in_(EMAILS)).all()
        user_ids = [u.id for u in users]
        if not user_ids:
            print("Temizlenecek test verisi yok.")
            return 0
        db.execute(sa_delete(PhoneVerification).where(
            PhoneVerification.user_id.in_(user_ids)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(user_ids)
        ))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.execute(sa_delete(User).where(User.id.in_(user_ids)))
        db.commit()
        print(f"Temizlendi: {len(user_ids)} test hesabı + bağımlı kayıtlar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
