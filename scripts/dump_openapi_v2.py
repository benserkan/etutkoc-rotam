"""FastAPI /api/v2/* yollarına filtrelenmiş OpenAPI spec'i web/openapi.v2.json'a yaz.

Next.js TypeScript codegen pipeline'ında ilk adım. Komut:
    python scripts/dump_openapi_v2.py

Sonra `web/` içinde:
    pnpm gen:types   # → lib/types/api.d.ts üretir

Bu yöntem FastAPI sunucusunun çalışmasını GEREKTİRMEZ — `app.openapi()`
import-time'da spec üretir.

NOT: Sadece v2 path'leri taşınır; v1 (mobile sözleşmesi, dondurulmuş) ayrı
codegen pipeline ihtiyacı olursa kendi script'i alacak.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main() -> int:
    from app.main import app

    spec = app.openapi()

    v2_paths = {
        p: ops for p, ops in spec.get("paths", {}).items() if p.startswith("/api/v2/")
    }
    if not v2_paths:
        print("⚠ v2 path bulunamadı — app.routes.api_v2 include edildi mi?", file=sys.stderr)
        return 1

    # Sadece v2 yollarında REFERANS verilen şemaları korumak için tüm components'i
    # taşıyoruz (boyut maliyeti ~küçük; codegen filterler).
    filtered = {
        "openapi": spec.get("openapi", "3.1.0"),
        "info": {
            **spec.get("info", {}),
            "title": "ETÜTKOÇ API v2",
            "description": "Next.js BFF için JSON-only endpoint katmanı. Mobile için /api/v1 ayrıdır.",
        },
        "paths": v2_paths,
        "components": spec.get("components", {}),
    }

    output = Path(__file__).resolve().parent.parent / "web" / "openapi.v2.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(filtered, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"✓ {output.relative_to(output.parent.parent)} yazıldı")
    print(f"  v2 endpoint sayısı: {len(v2_paths)}")
    for p in sorted(v2_paths.keys()):
        methods = sorted(v2_paths[p].keys())
        print(f"    {p} → {', '.join(methods).upper()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
