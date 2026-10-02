"""Migration zinciri bekçisi — tek head olmalı.

İki oturum/dal aynı tabana migration yazarsa alembic iki head görür ve web
açılışındaki `alembic upgrade head` hata verip konteyneri düşürür. Bu betik
DB'ye bağlanmadan yalnız dosyalardan bakar; deploy'dan ÖNCE koşulur
(deploy/redeploy.sh) ve CI/elle çalıştırılabilir.

Çıkış kodu: 0 = tek head · 1 = sorun (çoklu head / kopuk down_revision).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

VERSIONS = Path(__file__).resolve().parent.parent / "alembic" / "versions"
REV_RE = re.compile(r"""^revision(?:\s*:\s*[^=]+)?\s*=\s*["']([^"']+)["']""", re.M)
DOWN_RE = re.compile(r"""^down_revision(?:\s*:\s*[^=]+)?\s*=\s*(.+)$""", re.M)


def main() -> int:
    revs: dict[str, list[str]] = {}
    for f in sorted(VERSIONS.glob("*.py")):
        txt = f.read_text(encoding="utf-8")
        m = REV_RE.search(txt)
        if not m:
            continue
        d = DOWN_RE.search(txt)
        downs = re.findall(r'["\']([^"\']+)["\']', d.group(1)) if d else []
        revs[m.group(1)] = downs
    parents = {p for ds in revs.values() for p in ds}
    heads = sorted(r for r in revs if r not in parents)
    missing = sorted({p for p in parents if p not in revs})
    ok = len(heads) == 1 and not missing
    print(f"migration sayısı: {len(revs)} · head: {', '.join(heads) or '-'}")
    if missing:
        print(f"HATA: var olmayan down_revision: {', '.join(missing)}")
    if len(heads) > 1:
        print("HATA: birden fazla head — yeni migration'ın down_revision'ını en son head'e "
              "bağla (ya da `alembic merge` ile birleştir). Deploy DURDURULDU.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
