"""P6 manuel test — spam guard banner görmek için dispatch log enjekte eder.

Kullanım:
    python scripts/p6_log_inject.py 70                    # 70 log p4man koçuna
    python scripts/p6_log_inject.py 120                   # rose "çok yoğun" eşiği
    python scripts/p6_log_inject.py 70 my@email.com       # belirli kullanıcıya
    python scripts/p6_log_inject.py clear                 # p4man koçunun tüm WA log'larını sil
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
from app.models import User, WhatsAppDispatchLog


DEFAULT_EMAIL = "p4man_kocum@test.invalid"


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    cmd = args[0]
    email = args[1] if len(args) > 1 else DEFAULT_EMAIL

    with SessionLocal() as db:
        u = db.query(User).filter(User.email == email).first()
        if u is None:
            print(f"HATA: Kullanıcı bulunamadı: {email}")
            print(f"Hazırlık scripti: python scripts/p4_manual_test_setup.py")
            return 1

        if cmd == "clear":
            n = (
                db.query(WhatsAppDispatchLog)
                .filter(WhatsAppDispatchLog.sender_user_id == u.id)
                .count()
            )
            db.execute(
                sa_delete(WhatsAppDispatchLog).where(
                    WhatsAppDispatchLog.sender_user_id == u.id
                )
            )
            db.commit()
            print(f"Silindi: {email} için {n} log temizlendi.")
            return 0

        try:
            count = int(cmd)
        except ValueError:
            print(f"HATA: Birinci argüman sayı veya 'clear' olmalı (alındı: {cmd})")
            return 1

        if count <= 0 or count > 500:
            print("HATA: count 1-500 aralığında olmalı")
            return 1

        now = datetime.now(timezone.utc)
        for _ in range(count):
            db.add(WhatsAppDispatchLog(
                sender_user_id=u.id,
                template_key="p6_manual_test_inject",
                character_count=50,
                created_at=now,
            ))
        db.commit()

        print(f"Eklendi: {email} için {count} log (bugün, template=p6_manual_test_inject)")
        print()
        print("Şimdi sayfayı yenileyin: http://127.0.0.1:3000/teacher/bulk-wa")
        if count >= 100:
            print("→ ROSE banner 'çok yoğun' bekleniyor")
        elif count >= 50:
            print("→ AMBER banner 'yoğun' bekleniyor")
        else:
            print("→ Eşik altı: yalnız küçük gri özet")
        print()
        print(f"Temizlemek için: python scripts/p6_log_inject.py clear {email}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
