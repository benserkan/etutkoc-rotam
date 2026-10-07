"""/demos — Kitaplık · Program · Denemeler videoları rehber içeriğinden (2026-10-06).

Eski elle çizilmiş animasyonlar bu üç konuda arayüzün gerisinde kalmıştı. Bu
slug'lar artık Rota Rehberi'nin GERÇEK ekran görüntüleri + gelişmiş (Pro TTS)
seslendirmesiyle oynar; kaynak tek: `app/static/guide/coach-guide-demo.json`
(scripts/guide_content/sync_static.py üretir). Diğer demolar değişmez.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "static" / "guide" / "coach-guide-demo.json"

# slug → (rehber modülü, başlık, kısa açıklama)
GUIDE_DEMOS: dict[str, tuple[str, str, str]] = {
    "book-add-coach": ("Kitaplar", "Kitaplık ve Kitap Ekleme",
                       "Katalogdan ekle · taratarak ekle · elle tanımla · öğrenciye ata · ilerleme ve kapasite"),
    "program-create-coach": ("Program", "Haftalık Program",
                             "Görev ekle · yan panel · hafta ızgarası · iskelet · yayınla ve takip et"),
    "exams-coach": ("Denemeler", "Deneme Analizi",
                    "PDF'ten aktar · deneme listesi · konu analizi · gelişim raporu · veliyle paylaş"),
}


@lru_cache(maxsize=1)
def _load(mtime: float) -> dict:  # mtime: dosya değişince önbellek tazelenir
    return json.loads(DATA.read_text(encoding="utf-8"))


def build(slug: str | None) -> dict | None:
    if slug not in GUIDE_DEMOS or not DATA.exists():
        return None
    module, title, desc = GUIDE_DEMOS[slug]
    data = _load(DATA.stat().st_mtime)
    ver = data.get("version", "1")
    chapters, scenes = [], []
    for ch in data.get("chapters", []):
        if ch.get("module") != module:
            continue
        start = len(scenes)
        for i, st in enumerate(ch["steps"]):
            scenes.append({
                "img": f"/static/guide/shots/{st['shot']}.png?v={ver}" if st.get("shot") else None,
                "audio": f"/static/guide/audio/{ch['key']}/{i}.mp3?v={ver}",
                "caption": st["caption"],
                "box": st.get("box"),
                "chapter": ch["title"],
            })
        chapters.append({"title": ch["title"], "subtitle": ch.get("subtitle", ""),
                         "start": start, "end": len(scenes)})
    if not scenes:
        return None
    # süre tahmini (ses yüklenemezse sahne bekleme süresi): ~15 karakter/sn
    for s in scenes:
        s["ms"] = max(6000, int(len(s["caption"]) / 15 * 1000))
    minutes = max(1, round(sum(s["ms"] for s in scenes) / 60000))
    return {"slug": slug, "module": module, "title": title, "desc": desc,
            "chapters": chapters, "scenes": scenes, "minutes": minutes}
