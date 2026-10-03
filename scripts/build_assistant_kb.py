"""Rehber (Rota) anlatımlarını site asistanı bilgi tabanına çevirir (2026-10-03).

Kaynak: web/components/guide/{coach,student,parent}-guide-content.json
Çıktı:  app/assistant_kb/guide_{teacher,student,parent}.json
Her rehber bölümü bir bilgi bölümü olur (başlık + adımların anlatımı).
Seslendirme yazımları ("L G S", "T Y T") metne çevrilir.

Rehber içeriği değişince yeniden koş:
    python scripts/build_assistant_kb.py
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "components" / "guide"
OUT = ROOT / "app" / "assistant_kb"
MAP = {"coach": "teacher", "student": "student", "parent": "parent"}

_SPELL = [
    (r"\bL G S\b", "LGS"), (r"\bT Y T\b", "TYT"), (r"\bA Y T\b", "AYT"),
    (r"\bY K S\b", "YKS"), (r"\bP D F\b", "PDF"), (r"\bK V K K\b", "KVKK"),
]


def clean(t: str) -> str:
    for a, b in _SPELL:
        t = re.sub(a, b, t)
    return re.sub(r"\s+", " ", t).strip()


def main() -> None:
    for src_key, aud in MAP.items():
        data = json.loads((SRC / f"{src_key}-guide-content.json").read_text(encoding="utf-8"))
        sections = []
        for ch in data.get("chapters", []):
            caps = [clean(s.get("caption", "")) for s in ch.get("steps", []) if s.get("caption")]
            base = clean(f"Rehber: {ch.get('title', '')}")
            # Uzun bölümler 6 adımlık parçalara bölünür (arama daha isabetli olsun).
            parts = [caps[i:i + 6] for i in range(0, len(caps), 6)] or []
            for n, part in enumerate(parts, 1):
                title = base if len(parts) == 1 else f"{base} ({n}/{len(parts)})"
                sections.append({"id": f"guide-{aud}-{ch.get('key')}-{n}", "title": title,
                                 "body": " ".join(part)})
        out = OUT / f"guide_{aud}.json"
        out.write_text(json.dumps(sections, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{out.name}: {len(sections)} bölüm")


if __name__ == "__main__":
    main()
