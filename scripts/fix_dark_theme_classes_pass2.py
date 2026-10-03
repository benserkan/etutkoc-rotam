"""Koyu tema kodmodu — 2. geçiş (2026-10-03, yeniden ölçüm sonrası).

  R5  saydamlıklı açık zemin (bg-<renk>-50/40 vb.) koyu tema zemini olmadan →
      dark:bg-<renk>-500/10 (ilk geçişin regex'i '/' içerenleri atlıyordu)
  R6  düz açık-orta dolgu (bg-amber|yellow|lime-300..500, koyu temada da açık)
      üstündeki yazıya ilk geçişin eklediği dark:text-…-200/300 kaldırılır
      (açık dolgu + açık yazı = okunmaz)

    python scripts/fix_dark_theme_classes_pass2.py [--apply]
"""
from __future__ import annotations

import collections
import re
import sys

sys.path.insert(0, ".")
from scripts.fix_dark_theme_classes import COLORS, EXCLUDE_FILES, EXCLUDE_PARTS, STR_RE, WEB  # noqa: E402

ALPHA_LIGHT = re.compile(rf'(?<![:\w/-])bg-({COLORS})-(50|100|200)/(\d+)(?![\w/])')
SOLID_LIGHT = re.compile(r'(?<![:\w/-])bg-(amber|yellow|lime)-(300|400|500)(?![\w/])')
DARK_LIGHT_TEXT = re.compile(r'\s*(?<![\w-])dark:text-[a-z]+-(200|300)(?![\w/])')


def fix(cls: str, st: collections.Counter) -> str:
    out = cls
    has_dark_bg = "dark:bg-" in out
    m = ALPHA_LIGHT.search(out)
    if m and not has_dark_bg and "from-" not in out and not out.lstrip().startswith("hover:"):
        out = out.replace(m.group(0), f"{m.group(0)} dark:bg-{m.group(1)}-500/10", 1)
        st["R5 saydam açık zemin → koyu zemin"] += 1
    if SOLID_LIGHT.search(out) and "dark:bg-" not in out and DARK_LIGHT_TEXT.search(out):
        out = DARK_LIGHT_TEXT.sub("", out)
        st["R6 açık dolgu üstü açık yazı kaldırıldı"] += 1
    return out


def main(apply: bool) -> None:
    st: collections.Counter = collections.Counter()
    files = 0
    for p in WEB.rglob("*.tsx"):
        rel = p.relative_to(WEB).as_posix()
        if EXCLUDE_PARTS & set(p.relative_to(WEB).parts) or rel in EXCLUDE_FILES:
            continue
        src = p.read_text(encoding="utf-8")
        if "force-light" in src:
            continue
        out = STR_RE.sub(lambda m: f"{m.group(1)}{fix(m.group(2), st)}{m.group(1)}", src)
        if out != src:
            files += 1
            if apply:
                p.write_text(out, encoding="utf-8")
    print(f"{'UYGULANDI' if apply else 'KURU'} · {files} dosya")
    for k, v in st.items():
        print(f"  {v:5d}  {k}")


if __name__ == "__main__":
    main("--apply" in sys.argv)
