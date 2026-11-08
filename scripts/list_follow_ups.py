# -*- coding: utf-8 -*-
"""Takip listesi — vadesi gelen/yaklaşan açık işleri düz metin basar (salt okuma).

Claude oturum başında prod'da koşar; kullanıcı hatırlatmasa da bekleyen işleri görür.
    python -m scripts.list_follow_ups [--days 7]
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.database import SessionLocal  # noqa: E402
from app.services import follow_up_service as fus  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    today = date.today()
    with SessionLocal() as db:
        items = [i for i in fus.list_items(db, status="open")
                 if i.effective_due <= today + timedelta(days=a.days)]
        if not items:
            print(f"Takip listesi: önümüzdeki {a.days} gün boş.")
            return 0
        for it in items:
            d = (it.effective_due - today).days
            when = f"{-d} gün gecikti" if d < 0 else ("BUGÜN" if d == 0 else f"{d} gün kaldı")
            print(f"#{it.id} [{when}] {it.title}")
            rep = fus.report_of(it)
            if rep:
                print(f"    ölçüm: {rep.get('summary')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
