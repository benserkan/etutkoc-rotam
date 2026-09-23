"""İçindekiler pilotu çıktısını (tek kitap JSON) katalog JSON'una çevirir.

Pilot şeması: sections[].confidence = exact | estimate | unknown.
Yalnız TÜM dolu satırları exact olan kitaplar dönüştürülür (tahmin kataloğa
girmez); test_count 0/None satırlar atılır (etkinlik-only konu vb.).

Kullanım: python scripts/lgs_toc_to_catalog.py <pilot_out_dir> <hedef_dir> <i> [<i> ...]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).translate(_TR).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:60]


def main() -> int:
    src, dst, *ids = sys.argv[1:]
    Path(dst).mkdir(parents=True, exist_ok=True)
    for i in ids:
        d = json.loads(Path(src, f"{i}.json").read_text(encoding="utf-8"))
        rows = [s for s in d["sections"] if s.get("test_count")]
        if any(s.get("confidence") != "exact" for s in rows):
            print(f"[{i}] ATLANDI — exact olmayan satır var")
            continue
        out = {
            "name": d["name"],
            "publisher": d.get("publisher"),
            "subject": d["subject"],
            "curriculum_model": "lgs",
            "type": d["type"],
            "target_grade_min": 8,
            "target_grade_max": 8,
            "target_graduate": False,
            "sections": [
                {"label": s["label"], "test_count": s["test_count"], "source": "toc_image",
                 "page": s.get("page_start")}
                for s in rows
            ],
            "warnings": [],
            "notes": [f"Kaynak: yalnız kapak + içindekiler fotoğrafı ({d['file']}); "
                      f"içindekiler türü {d['toc_kind']} — test sayıları içindekilerde tek tek "
                      f"listelenen testlerden birebir sayıldı."] + list(d.get("notes") or []),
        }
        name = f"lgs8_{slug(d['name'])}.json"
        Path(dst, name).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{i}] {name}: {len(rows)} satır · {sum(s['test_count'] for s in rows)} test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
