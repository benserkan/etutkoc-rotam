"""Anasayfa vitrin kartlarına demo videolarını bağla (idempotent).

Koç (audience=teacher) kartlarına /demos'taki ilgili demo slug'ını ekler →
kartta "Demo İzle" butonu çıkar → demo_click telemetrisi gerçek olur.

Güvenli: yalnız demo_slug BOŞ olan kartı günceller (admin'in elle bağladığı
demolar korunur). Tekrar çalıştırmak güvenli.

Çalıştır:  python -m scripts.bind_landing_demos
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal
from app.models import FeatureCard

# kart slug → (demo slug [/demos?play=...], süre etiketi)
DEMO_MAP: dict[str, tuple[str, str]] = {
    "kesfet-erken-uyari": ("dna-coach", "~2 dk"),
    "kesfet-ai-seans-hazirligi": ("sessions-coach", "~2 dk"),
    "kesfet-ai-sesli-foto-not": ("sessions-coach", "~2 dk"),
    "kesfet-surdurulebilir-plan": ("program-create-coach", "~2 dk"),
    "kesfet-veli-bilgilendirme": ("whatsapp-coach", "~2 dk"),
    "kesfet-tahsilat": ("billing-coach", "~2 dk"),
}


def main() -> int:
    updated = 0
    skipped = 0
    missing = 0
    with SessionLocal() as db:
        for slug, (demo_slug, duration) in DEMO_MAP.items():
            card = db.query(FeatureCard).filter(FeatureCard.slug == slug).first()
            if card is None:
                print(f"  [YOK] kart bulunamadı: {slug}")
                missing += 1
                continue
            if (card.demo_slug or "").strip():
                print(f"  [ATLA] {slug} → zaten demo bağlı: {card.demo_slug}")
                skipped += 1
                continue
            card.demo_slug = demo_slug
            card.demo_duration_label = duration
            updated += 1
            print(f"  [OK] {slug} → demo={demo_slug} ({duration})")
        db.commit()
    print(f"\n=== {updated} güncellendi, {skipped} atlandı, {missing} bulunamadı ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
