"""3D AYT Fizik: bölüm-sonu setlerini ('Bire Bir ÖSYM (NN. BÖLÜM)' / 'Gündelik
Hayatta Fizik (NN. BÖLÜM)') bir önceki eşli bölümün konusuna bağla (bölüm-sonu
seti o ünitenin malzemesidir); TÜMEVARIM karma kalır (bilinçli boş). İdempotent."""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import BookTemplate

PREFIXES = ("Bire Bir ÖSYM (", "Gündelik Hayatta Fizik (")


def main() -> int:
    with SessionLocal() as db:
        e = (
            db.query(BookTemplate)
            .filter(BookTemplate.name == "3D AYT Fizik Soru Bankası", BookTemplate.teacher_id.is_(None))
            .first()
        )
        if e is None:
            print("kayıt yok")
            return 1
        secs = sorted(e.sections, key=lambda s: s.order)
        prev_topic = None
        n = 0
        for s in secs:
            if s.topic_id is not None:
                prev_topic = s.topic_id
            elif s.label.startswith(PREFIXES) and prev_topic is not None:
                s.topic_id = prev_topic
                n += 1
        db.commit()
        mapped = sum(1 for s in e.sections if s.topic_id is not None)
        print(f"+{n} bölüm-sonu seti bağlandı → {mapped}/{len(secs)} eşli")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
