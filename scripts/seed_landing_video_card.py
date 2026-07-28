"""Anasayfa tanıtım videosu — telemetri taşıyıcı kart (GİZLİ).

Neden: landing telemetrisi (`telemetry.record_event`) yalnız DB'de var olan bir
slug'ı kabul eder. Video izleme davranışını (açıldı / oynatıldı / yarısını
izledi / CTA'ya bastı) mevcut ölçüm altyapısında toplamak için `tanitim-videosu`
slug'lı bir FeatureCard gerekir. Kart **HIDDEN** durumdadır → anasayfa kart
listesine GİRMEZ, yalnız telemetri kabul eder. Böylece dönüşüm hunisi
(conversion_service) videoyu izleyip üye olan ziyaretçiyi de ilişkilendirir.

Olay eşlemesi (mevcut FeatureEventType'lar):
  impression → karşılama modalı açıldı / bölüm göründü
  view       → video oynatıldı
  demo_click → videonun yarısı izlendi (anlamlı izleme)
  cta_click  → video altındaki "Ücretsiz dene" tıklandı

İdempotent: slug varsa ATLAR. Çalıştır:
  python -m scripts.seed_landing_video_card   [--delete]
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import FeatureDomain, FeatureStatus, FeatureTier
from app.services import feature_catalog as fc

SLUG = "tanitim-videosu"


def run(delete: bool = False) -> int:
    with SessionLocal() as db:
        existing = fc.get_by_slug(db, SLUG)
        if delete:
            if existing is None:
                print("yok")
                return 0
            fc.delete(db, existing)
            db.commit()
            print("silindi")
            return 0
        if existing is not None:
            print(f"  [atla] {SLUG} (zaten var)")
            return 0
        fc.create(
            db, actor_id=None, status=FeatureStatus.HIDDEN.value,
            introduced_at=datetime.now(timezone.utc),
            slug=SLUG,
            title="Tanıtım videosu (telemetri)",
            category_label="Vitrin", category_icon="🎬",
            accent_color="#0E7490",
            target_roles=["teacher", "institution_admin"],
            domain=FeatureDomain.GENEL.value,
            tier=FeatureTier.CORE.value,
            strategic_priority=1,
            tagline=(
                "Anasayfa karşılama videosunun izlenme ölçümü. Bu kart GİZLİ — "
                "anasayfada gösterilmez, yalnız telemetri taşır."
            ),
            benefits=["Modal açıldı (gösterim)", "Oynatıldı (görüntüleme)",
                      "Yarısı izlendi (demo tıklaması)"],
            cta_label="Ücretsiz dene",
        )
        db.commit()
        print(f"  [+] {SLUG} (gizli — telemetri taşıyıcı)")
    return 0


if __name__ == "__main__":
    raise SystemExit(run(delete="--delete" in sys.argv))
