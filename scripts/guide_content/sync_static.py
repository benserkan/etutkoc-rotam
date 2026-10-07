"""Koç rehberi içeriğini sunucunun okuyabileceği statik kopyaya yazar.

/demos sayfası (FastAPI/Jinja) Kitaplık · Program · Denemeler videolarını
rehberin GERÇEK ekran görüntüleri + seslendirmesiyle oynatır. Web bileşenleri
Docker imajına girmediği için içerik + vurgu kutuları + varlık sürümü
`app/static/guide/coach-guide-demo.json`'a kopyalanır. Rehber içeriği ya da
GUIDE_ASSET_VERSION değişince yeniden koş (build.py bunu kendisi çağırır).

  python -m scripts.guide_content.sync_static
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE = ROOT / "web" / "components" / "guide"
OUT = ROOT / "app" / "static" / "guide" / "coach-guide-demo.json"
MODULES = ("Kitaplar", "Program", "Denemeler")


def main() -> int:
    content = json.loads((GUIDE / "coach-guide-content.json").read_text(encoding="utf-8"))
    boxes = json.loads((GUIDE / "shot-boxes.json").read_text(encoding="utf-8"))
    ts = (GUIDE / "coach-guide-data.ts").read_text(encoding="utf-8")
    m = re.search(r'GUIDE_ASSET_VERSION\s*=\s*"([^"]+)"', ts)
    version = m.group(1) if m else "1"
    chapters = []
    for ch in content["chapters"]:
        if ch.get("module") not in MODULES:
            continue
        steps = []
        for st in ch["steps"]:
            box = (boxes.get(st.get("shot"), {}).get("targets") or {}).get(st.get("target") or "")
            steps.append({"caption": st.get("caption", ""), "shot": st.get("shot"), "box": box})
        chapters.append({"key": ch["key"], "module": ch["module"], "title": ch.get("title", ""),
                         "subtitle": ch.get("subtitle", ""), "steps": steps})
    OUT.write_text(json.dumps({"version": version, "chapters": chapters}, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    n = sum(len(c["steps"]) for c in chapters)
    print(f"coach-guide-demo.json: {len(chapters)} bölüm, {n} adım, sürüm {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
