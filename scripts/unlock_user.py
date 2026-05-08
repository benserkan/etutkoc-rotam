"""Bir kullanıcının lockout durumunu sıfırlar.

Kullanım:
    python -m scripts.unlock_user EMAIL
"""

import sys

from app.database import SessionLocal
from app.models import User


def main() -> None:
    if len(sys.argv) != 2:
        print("Kullanım: python -m scripts.unlock_user EMAIL")
        sys.exit(1)
    email = sys.argv[1].strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"Kullanıcı bulunamadı: {email}")
            sys.exit(1)
        user.failed_login_count = 0
        user.locked_until = None
        db.commit()
        print(f"OK: {email} kilidi açıldı, failed_login_count sıfırlandı.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
