"""Koyu tema okunabilirlik taraması (2026-10-03) — SALT OKUMA, istenirse düzeltir.

Yakalanan desen (tekrarlayan hata): aynı className içinde
  * koyu temada zemini KOYULAŞTIRAN `dark:bg-<renk>-…/<saydamlık>` VAR,
  * metin KOYU bir ton (`text-<renk>-700|800|900|950`),
  * ama `dark:text-…` YOK  →  koyu zemin üstüne koyu yazı = okunmaz.

Kullanım:
    python scripts/audit_dark_contrast.py            # rapor
    python scripts/audit_dark_contrast.py --fix      # dark:text-<renk>-200 ekler
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1] / "web"
SKIP = ("node_modules", ".next")
STR_RE = re.compile(r'(["\'`])((?:(?!\1).)*?\b(?:dark:bg-[a-z]+-\d{2,3}/\d+|dark:bg-[a-z]+-(?:900|950))(?:(?!\1).)*?)\1')
TEXT_RE = re.compile(r'(?<![:\w-])text-([a-z]+)-(700|800|900|950)\b')


def scan(fix: bool) -> int:
    total = 0
    for p in ROOT.rglob("*.tsx"):
        if any(s in p.parts for s in SKIP):
            continue
        src = p.read_text(encoding="utf-8")
        out = src
        hits = []
        for m in STR_RE.finditer(src):
            cls = m.group(2)
            if "dark:text-" in cls:
                continue
            t = TEXT_RE.search(cls)
            if not t:
                continue
            hits.append((src[: m.start()].count("\n") + 1, cls[:110]))
            if fix:
                new = cls.replace(t.group(0), f"{t.group(0)} dark:text-{t.group(1)}-200", 1)
                out = out.replace(cls, new, 1)
        if hits:
            total += len(hits)
            print(f"{p.relative_to(ROOT.parent)}: {len(hits)}")
            for ln, c in hits[:4]:
                print(f"   L{ln}: {c}")
        if fix and out != src:
            p.write_text(out, encoding="utf-8")
    print(f"\nTOPLAM {total} okunmaz koyu-tema sınıfı{' — düzeltildi' if fix else ''}")
    return total


if __name__ == "__main__":
    scan("--fix" in sys.argv)
