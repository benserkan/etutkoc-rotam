"""Mevcut şube adlarını tek biçime çevirir (2026-09-29). Varsayılan KURU çalışma.

  python -m scripts.normalize_class_groups            # yalnız rapor
  python -m scripts.normalize_class_groups --apply    # yazar (idempotent)

'10 - A' / '10a' → '10-A' · '12 Mezun' / '12MEZUN' → '12-MEZUN' · 'mezun a' → 'Mezun-A'.
"""
from __future__ import annotations

import sys

from app.database import SessionLocal
from app.models import User, UserRole
from app.routes.api_v2.teacher import normalize_class_group


def main() -> None:
    apply = "--apply" in sys.argv
    changed = 0
    with SessionLocal() as db:
        for u in db.query(User).filter(User.role == UserRole.STUDENT, User.class_group.isnot(None)):
            new = normalize_class_group(u.class_group)
            if new != u.class_group:
                changed += 1
                print(f"#{u.id} {u.full_name}: {u.class_group!r} → {new!r}")
                if apply:
                    u.class_group = new
        if apply:
            db.commit()
    print(f"\n{changed} kayıt {'güncellendi' if apply else 'değişecek (kuru çalışma)'}")


if __name__ == "__main__":
    main()
