"""Katman 3 — Otomatik Keşif CLI.

Alembic migration ve git commit kaynaklarını tarayıp DRAFT FeatureCard
adayları üretir. Yeni ise DB'ye yazar (status=DRAFT); zaten varsa atlar.

Kullanım:
    python -m scripts.discover_features                    # son 60 gün, hepsi
    python -m scripts.discover_features --since 2026-04-01 # özel tarih
    python -m scripts.discover_features --source migration # sadece migration
    python -m scripts.discover_features --source commit    # sadece commit
    python -m scripts.discover_features --dry-run          # yazma, sadece listele
    python -m scripts.discover_features --limit 10         # en yeni 10 adayı uygula

Üretilen kartlar Süper Admin panelinde DRAFT filtresinde görünür
(Katman 4'te ayrı bir onay kuyruğu paneliyle ele alınacak). Tüm yazımlar
AuditAction.FEATURE_CARD_AUTO_DISCOVERED ile audit'lenir.
"""

from __future__ import annotations

import argparse
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.services import feature_discovery as fd


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Otomatik Özellik Keşfi — migration ve commit'leri tara, DRAFT kartlar üret.",
    )
    p.add_argument(
        "--since",
        type=str,
        default=None,
        help="YYYY-MM-DD biçiminde başlangıç tarihi. Varsayılan: son 60 gün.",
    )
    p.add_argument(
        "--source",
        type=str,
        default="both",
        choices=("both", "migration", "commit"),
        help="Tarama kaynağı. Varsayılan: her ikisi.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="DB'ye yazma, sadece adayları listele.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="En yeniden geriye doğru en fazla N aday uygula.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"!! Geçersiz --since: {args.since!r} (YYYY-MM-DD biçimi bekleniyor)")
            return 2
    else:
        since = datetime.now(timezone.utc) - timedelta(days=60)

    if args.source == "both":
        sources = ("migration", "commit")
    else:
        sources = (args.source,)

    print(f"=== Özellik Keşfi ===")
    print(f"  başlangıç tarihi : {since:%Y-%m-%d}")
    print(f"  kaynaklar        : {', '.join(sources)}")
    print(f"  dry-run          : {args.dry_run}")
    if args.limit is not None:
        print(f"  limit            : {args.limit}")
    print()

    candidates = fd.discover_all(since=since, sources=sources)
    print(f"Bulunan aday sayısı: {len(candidates)}")
    print()

    # İlk 20 adayı listele (limit'siz mode için)
    preview = candidates[: (args.limit or 20)]
    print("Önizleme:")
    for c in preview:
        print(f"  {c.to_label()}")
    if len(candidates) > len(preview):
        print(f"  … ve {len(candidates) - len(preview)} aday daha")
    print()

    with SessionLocal() as db:
        result = fd.apply_candidates(
            db, candidates,
            actor_id=None,
            dry_run=args.dry_run,
            limit=args.limit,
        )

    print("=== Sonuç ===")
    print(f"  oluşturuldu : {result['created']}")
    print(f"  atlandı     : {result['skipped']}")
    errors = result.get("errors") or []
    if errors:
        print(f"  hatalar     : {len(errors)}")
        for err in errors[:10]:
            print(f"     ! {err}")
    print()
    if args.dry_run:
        print("(dry-run modunda DB'ye hiçbir şey yazılmadı)")
    else:
        print("Yeni kartlar /admin/feature-catalog → durum=Taslak filtresinde görünür.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
