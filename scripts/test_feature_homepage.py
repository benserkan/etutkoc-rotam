"""Katman 2 — Anasayfa render smoke test.

Senaryolar:
 1. get_for_landing temel kontrat:
    - Yalnızca PUBLISHED + manual_hide=False + mockup_type DOLU kartlar
    - Sıralama: pin > priority > introduced_at ASC
    - limit=5 sınırı

 2. Manuel ayarların etkisi:
    - manual_pin=True low-priority kartı tepeye taşır
    - manual_hide=True yayından düşürür
    - status=DRAFT yayından düşürür
    - mockup_type=None yayından düşürür

 3. HTTP / (landing):
    - 200 + ilk kart md:col-span-2 hero
    - Hero "Demo İzle" + duration label
    - Standart kart demo_slug varsa küçük inline btn
    - 5 kart × 5 mockup partial (daily_schedule, fsrs_rating,
      burnout_gauge, books_progress, whatsapp_chat) render edildi

Kullanım:
    python -m scripts.test_feature_homepage
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    FeatureCard,
    FeatureDomain,
    FeatureStatus,
    FeatureTier,
    UserRole,
)
from app.services import feature_catalog as fc


PFX = f"fhtest{secrets.token_hex(3)}"
passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def cleanup_by_prefix(db, prefix: str) -> int:
    rows = db.query(FeatureCard).filter(FeatureCard.slug.like(f"{prefix}%")).all()
    n = len(rows)
    for c in rows:
        db.delete(c)
    db.commit()
    return n


def main() -> int:
    print(f"=== Katman 2 (anasayfa render) smoke ===  prefix={PFX}")

    with SessionLocal() as db:
        # Temiz baş — önceki PFX kayıtları varsa
        cleanup_by_prefix(db, PFX)

        # 1) Default ortamda get_for_landing() mevcut 5 seed kartını döndürür
        cards = fc.get_for_landing(db)
        check("5 kart döner (default seed)", len(cards) == 5, f"got {len(cards)}")
        if cards:
            check("ilk kart hero = daily-plan", cards[0].slug == "daily-plan",
                  f"got {cards[0].slug}")
            check("hero mockup_type doğru", cards[0].mockup_type == "daily_schedule")
            all_have_mockup = all(c.mockup_type for c in cards)
            check("hepsinin mockup_type'ı var", all_have_mockup)

        # 2) Yardımcı kartlar (mockup_type=None) yayında ama anasayfada YOK
        rotam = fc.get_by_slug(db, "rotam")
        check("rotam catalog'ta var", rotam is not None)
        if rotam:
            check("rotam mockup_type=None", rotam.mockup_type is None)
        slugs_on_landing = [c.slug for c in cards]
        check("rotam landing'de YOK", "rotam" not in slugs_on_landing)
        check("focus-pomodoro landing'de YOK", "focus-pomodoro" not in slugs_on_landing)

        # 3) manual_pin: low-priority kartı tepeye taşır
        veli = fc.get_by_slug(db, "veli-kanali")  # priority=4
        assert veli is not None, "veli-kanali seed eksik"
        original_pin = veli.manual_pin
        veli.manual_pin = True
        db.commit()

        cards_pinned = fc.get_for_landing(db)
        check("manual_pin tepe konumu", cards_pinned[0].slug == "veli-kanali",
              f"got {cards_pinned[0].slug if cards_pinned else 'empty'}")

        # Geri al
        veli.manual_pin = original_pin
        db.commit()

        # 4) manual_hide: yayından düşürür
        dna = fc.get_by_slug(db, "dna-risk")
        assert dna is not None
        dna.manual_hide = True
        db.commit()

        cards_hidden = fc.get_for_landing(db)
        check("manual_hide kartı düşürür",
              "dna-risk" not in [c.slug for c in cards_hidden],
              f"got {[c.slug for c in cards_hidden]}")
        check("hide sonrası 4 kart", len(cards_hidden) == 4)

        dna.manual_hide = False
        db.commit()

        # 5) status=DRAFT: yayından düşürür
        soru = fc.get_by_slug(db, "soru-bankasi")
        original_status = soru.status
        soru.status = FeatureStatus.DRAFT.value
        db.commit()

        cards_draft = fc.get_for_landing(db)
        check("DRAFT kart düşürülür",
              "soru-bankasi" not in [c.slug for c in cards_draft])

        soru.status = original_status
        db.commit()

        # 6) mockup_type=None: yayından düşürür — yeni test kartı ile
        try:
            test_no_mockup = fc.create(
                db,
                actor_id=None,
                slug=f"{PFX}-no-mockup",
                title="Test Kart (mockup'sız)",
                category_icon="🧪",
                category_label="Test",
                tagline="Sadece test amaçlı, mockup'sız.",
                description_md="Test.",
                domain=FeatureDomain.GENEL.value,
                tier=FeatureTier.CORE.value,
                status=FeatureStatus.PUBLISHED.value,
                target_roles=[UserRole.STUDENT],
                strategic_priority=5,  # En yüksek priority
                introduced_at=datetime.now(timezone.utc),
                mockup_type=None,
            )
            db.commit()
            cards_after = fc.get_for_landing(db)
            check("mockup_type=None kart landing'de YOK",
                  f"{PFX}-no-mockup" not in [c.slug for c in cards_after])
            check("hero hala daily-plan (priority eşitse)",
                  cards_after[0].slug == "daily-plan",
                  f"got {cards_after[0].slug}")
        finally:
            cleanup_by_prefix(db, PFX)

        # 7) limit parametresi
        cards_limit_2 = fc.get_for_landing(db, limit=2)
        check("limit=2 saygısı", len(cards_limit_2) == 2)

    # --- HTTP /  ---
    c = TestClient(app)
    r = c.get("/")
    check("/ status 200", r.status_code == 200, f"got {r.status_code}")
    html = r.text

    # Hero (daily-plan)
    check("hero md:col-span-2", 'md:col-span-2' in html)
    check("hero büyük demo btn URL", '/demos?play=daily-plan' in html)
    check("hero duration label", '2 dk · 8 sahne' in html)
    check("hero başlık", 'Saniyeler İçinde' in html)

    # 5 mockup partial render edildi (her birinden distinctive marker)
    check("daily_schedule partial", '09:00' in html, "ilk task slot")
    check("fsrs_rating partial", 'Bugünkü kart' in html)
    check("burnout_gauge partial", 'Burnout' in html)
    check("books_progress partial",
          'Matematik' in html or 'Türkçe' in html or 'Fen Bilimleri' in html)
    check("whatsapp_chat partial", 'WhatsApp' in html)

    # Standart kart: dna-risk demo küçük btn
    check("dna inline demo btn", '/demos?play=teacher-dna' in html)

    # Kategori rozetleri 5'i de var
    for label in ("Günlük Rota", "FSRS", "Risk Radarı", "Hedef Ağacı", "Veli Kanalı"):
        check(f"badge '{label}'", label in html)

    # Yardımcı kartlar (rotam/yks-mezun/focus/kurumsal) anasayfada YOK
    check("rotam landing HTML'de yok", "Rotam — Akıllı Haftalık Plan" not in html)
    check("focus-pomodoro landing HTML'de yok", "Pomodoro Odak Seansları" not in html)
    check("YKS mezun landing'de yok", "YKS Mezun Hazırlık" not in html)

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
