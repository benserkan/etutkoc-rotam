"""Koyu tema: açık hover zemini (hover:bg-<c>-50/100/200) koyu tema karşılığı
olmadan → üzerine gelince açık zemin + açık (koyu tema) yazı = okunmaz
(2026-10-10, koç: Durum Özeti kartında "üzerine gelince yazı okunmuyor").

Her className string'inde: açık hover var, `dark:hover:bg-` yok, sabit beyaz
zeminli değil (bg-white + dark:bg- yok) → ` dark:hover:bg-<c>-500/25` eklenir;
`hover:text-<c>-…` varsa ve `dark:hover:text-` yoksa ` dark:hover:text-<c>-100`.
force-light dosyalar (her zaman açık tema) atlanır.

  python scripts/fix_dark_hover_classes.py          # kuru çalışma
  python scripts/fix_dark_hover_classes.py --apply
"""
from __future__ import annotations

import glob
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

C = "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose"
HOVER = re.compile(rf"(?<![:\w/-])hover:bg-({C})-(?:50|100|200)(?:/\d+)?(?![\w/])")
HOVER_TEXT = re.compile(rf"(?<![:\w/-])hover:text-({C})-\d+(?![\w/])")
STR = re.compile(r'"([^"\n]*)"|`([^`]*)`')


def fix_class(s: str) -> str:
    m = HOVER.search(s)
    if not m or "dark:hover:bg-" in s:
        return s
    if re.search(r"(?<![:\w/-])bg-white(?![\w/])", s) and "dark:bg-" not in s:
        return s
    out = s.rstrip() + f" dark:hover:bg-{m.group(1)}-500/25"
    mt = HOVER_TEXT.search(s)
    if mt and "dark:hover:text-" not in s:
        out += f" dark:hover:text-{mt.group(1)}-100"
    return out + s[len(s.rstrip()):]


def main() -> int:
    apply = "--apply" in sys.argv
    files = glob.glob("web/components/**/*.tsx", recursive=True) + glob.glob("web/app/**/*.tsx", recursive=True)
    n_files = n_str = 0
    for f in files:
        src = open(f, encoding="utf-8").read()
        if "force-light" in src:
            continue
        count = 0

        def rep(mm: re.Match) -> str:
            nonlocal count
            q = '"' if mm.group(1) is not None else "`"
            body = mm.group(1) if mm.group(1) is not None else mm.group(2)
            new = fix_class(body)
            if new != body:
                count += 1
            return f"{q}{new}{q}"

        out = STR.sub(rep, src)
        if count:
            n_files += 1
            n_str += count
            print(f"{count:3d}  {f}")
            if apply:
                open(f, "w", encoding="utf-8", newline="").write(out)
    print(f"\n{n_str} sınıf · {n_files} dosya {'DÜZELTİLDİ' if apply else '(kuru çalışma)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
