"""Koyu tema sınıf düzeltmesi — sistem geneli kodmod (2026-10-03).

`audit_dark_theme_pages.py` ölçümünün çıkardığı tekrarlayan desenler:
  R1  açık renkli kutu (bg-<renk>-50/100/200) koyu tema zemini olmadan →
      dark:bg-<renk>-500/15 + dark:border-<renk>-500/30
  R2  uygulama içi beyaz kart (bg-white + kenarlık/gölge + rounded) → bg-card
  R3  koyu ton yazı (text-<renk>-600…950) koyu tema karşılığı olmadan →
      dark:text-<renk>-300 (600/700) / dark:text-<renk>-200 (800+)
      (aynı öğe koyu temada da AÇIK zeminli kalıyorsa dokunulmaz)
  R4  kehribar/sarı dolgu + beyaz yazı (her iki temada kontrast < 3) →
      koyu yazı (text-amber-950)
Her zaman açık temada kalan sayfalar (force-light), yazdırma ve e-posta
önizleme bileşenleri HARİÇ.

    python scripts/fix_dark_theme_classes.py          # kuru çalışma (sayılar)
    python scripts/fix_dark_theme_classes.py --apply
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

WEB = pathlib.Path(__file__).resolve().parents[1] / "web"
EXCLUDE_PARTS = {"node_modules", ".next", "(print)", "landing", "pricing", "payment", "contact", "emails"}
EXCLUDE_FILES = {
    "app/login/page.tsx", "app/signup/teacher/page.tsx", "app/signup/invite/[token]/page.tsx",
    "app/membership/[token]/page.tsx", "app/kampanya/[token]/page.tsx", "app/page.tsx",
}
COLORS = ("slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|"
          "blue|indigo|violet|purple|fuchsia|pink|rose")
STR_RE = re.compile(r'(["\'`])([^"\'`\n]*?\b(?:bg|text)-[a-z]+-?\d*[^"\'`\n]*?)\1')
LIGHT_BG = re.compile(rf'(?<![:\w/-])bg-({COLORS})-(50|100|200)(?![\w/])')
TEXT_DARK = re.compile(rf'(?<![:\w/-])text-({COLORS})-(600|700|800|900|950)(?![\w/])')
WHITE_CARD = re.compile(r'(?<![:\w/-])bg-white(?![\w/])')
AMBER_FILL = re.compile(r'(?<![:\w/-])bg-(amber|yellow)-(400|500)(?![\w/])')


def fix_class(cls: str, stats: collections.Counter) -> str:
    toks = cls.split()
    has = lambda pre: any(t.startswith(pre) for t in toks)  # noqa: E731
    out = cls
    # R4
    if AMBER_FILL.search(cls) and re.search(r'(?<![:\w/-])text-white(?![\w/])', cls):
        out = re.sub(r'(?<![:\w/-])text-white(?![\w/])', "text-amber-950", out, count=1)
        stats["R4 kehribar dolgu → koyu yazı"] += 1
    # R2
    if (WHITE_CARD.search(out) and not has("dark:bg-") and "rounded" in out
            and ("border" in out or "shadow" in out) and "text-white" not in out):
        out = WHITE_CARD.sub("bg-card", out, count=1)
        stats["R2 beyaz kart → bg-card"] += 1
    toks = out.split()
    has = lambda pre: any(t.startswith(pre) for t in toks)  # noqa: E731
    # R1
    m = LIGHT_BG.search(out)
    if m and not has("dark:bg-") and "hover:" + m.group(0) not in out.split() and "from-" not in out:
        c = m.group(1)
        add = f" dark:bg-{c}-500/15"
        if re.search(rf'(?<![:\w/-])border-{c}-\d{{3}}', out) and not has("dark:border-"):
            add += f" dark:border-{c}-500/30"
        out = out.replace(m.group(0), m.group(0) + add, 1)
        stats["R1 açık kutu → koyu zemin"] += 1
    toks = out.split()
    has = lambda pre: any(t.startswith(pre) for t in toks)  # noqa: E731
    # R3
    if not has("dark:text-"):
        t = TEXT_DARK.search(out)
        stays_light = (LIGHT_BG.search(out) or WHITE_CARD.search(out)) and not has("dark:bg-")
        if t and not stays_light:
            c, n = t.group(1), int(t.group(2))
            c2 = "slate" if c in ("gray", "zinc", "neutral", "stone") else c
            shade = 300 if n <= 700 else 200
            out = out.replace(t.group(0), f"{t.group(0)} dark:text-{c2}-{shade}", 1)
            stats["R3 koyu yazı → koyu tema açık tonu"] += 1
    return out


def main(apply: bool) -> None:
    stats: collections.Counter = collections.Counter()
    files = 0
    for p in WEB.rglob("*.tsx"):
        rel = p.relative_to(WEB).as_posix()
        if EXCLUDE_PARTS & set(p.relative_to(WEB).parts) or rel in EXCLUDE_FILES:
            continue
        src = p.read_text(encoding="utf-8")
        if "force-light" in src:
            continue

        def sub(m: re.Match) -> str:
            q, cls = m.group(1), m.group(2)
            new = fix_class(cls, stats)
            return f"{q}{new}{q}"

        out = STR_RE.sub(sub, src)
        if out != src:
            files += 1
            if apply:
                p.write_text(out, encoding="utf-8")
    print(f"{'UYGULANDI' if apply else 'KURU ÇALIŞMA'} · {files} dosya")
    for k, v in sorted(stats.items()):
        print(f"  {v:5d}  {k}")


if __name__ == "__main__":
    main("--apply" in sys.argv)
