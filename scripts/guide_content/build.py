"""Koç rehberi içeriğini konu modüllerinden derler.

coach-guide-content.json içindeki bölümler konu (module) bazında yönetilir.
Bir modülün bölümleri burada tanımlı listeyle DEĞİŞTİRİLİR; diğer bölümlere
dokunulmaz. Sıra: Başlangıç → Kitaplar → Program → Denemeler.

  python -m scripts.guide_content.build
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "web" / "components" / "guide" / "coach-guide-content.json"
SERVICE = ROOT / "app" / "services" / "guide_service.py"

# Eski bölümler — yeni seri bunların yerini alır
REPLACED = {"kitap-ekle", "ogrenci-ata", "program-kur", "yayinla-duyur", "hafta-takip", "deneme-gir"}
# Henüz yeniden yazılmamış bölümlerin konusu
LEGACY_MODULE = {
    "hosgeldin": "Başlangıç",
    "program-kur": "Program",
    "yayinla-duyur": "Program",
    "hafta-takip": "Program",
    "deneme-gir": "Denemeler",
}
ORDER = ["Başlangıç", "Kitaplar", "Program", "Denemeler"]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from scripts.guide_content import denemeler, kitaplar, program

    modules = {kitaplar.MODULE: kitaplar.CHAPTERS, program.MODULE: program.CHAPTERS, denemeler.MODULE: denemeler.CHAPTERS}
    data = json.loads(CONTENT.read_text(encoding="utf-8"))
    kept = []
    for ch in data["chapters"]:
        if ch["key"] in REPLACED:
            continue
        mod = ch.get("module") or LEGACY_MODULE.get(ch["key"], "Başlangıç")
        if mod in modules:
            continue
        ch["module"] = mod
        kept.append(ch)
    for mod, chs in modules.items():
        for ch in chs:
            kept.append({"key": ch["key"], "module": mod, **{k: v for k, v in ch.items() if k != "key"}})
    kept.sort(key=lambda c: ORDER.index(c["module"]) if c["module"] in ORDER else 99)
    data["chapters"] = kept
    CONTENT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # Sunucu bölüm listesi (ilerleme doğrulaması) aynı sırayla
    keys = [c["key"] for c in kept]
    src = SERVICE.read_text(encoding="utf-8")
    start = src.index("COACH_CHAPTERS = [")
    end = src.index("]", start) + 1
    block = "COACH_CHAPTERS = [\n" + "".join(f'    "{k}",\n' for k in keys) + "]"
    SERVICE.write_text(src[:start] + block + src[end:], encoding="utf-8")

    # /demos sayfasının okuduğu statik kopya (Kitaplık/Program/Denemeler videoları)
    from scripts.guide_content import sync_static
    sync_static.main()

    total = sum(len(c["steps"]) for c in kept)
    print(f"{len(kept)} bölüm · {total} adım")
    for c in kept:
        print(f"  [{c['module']}] {c['key']} — {len(c['steps'])} adım")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
