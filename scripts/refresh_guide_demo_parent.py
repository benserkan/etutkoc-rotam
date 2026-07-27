# -*- coding: utf-8 -*-
"""Veli rehberi çekimleri öncesi Elif'in demo verisini BU haftaya taşı.

Hafta dündü bitti (Pazartesi'deyiz): geçen haftanın görevleri +7 gün ileri
taşınır (tarih taşıma — rezerv muhasebesi DEĞİŞMEZ), dünün karnesi korunur
(2 tamam + 1 eksik → sohbet karşılaması "dün eksik görev" adıyla dolar).
Elif'in Rota yorumları silinir → kart "Rota yorumlasın" boş hâliyle çekilir.
İdempotent değil — bir çekim turu öncesi BİR KEZ koşulur.

  PYTHONPATH=. python scripts/refresh_guide_demo_parent.py
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import date, timedelta

from app.database import SessionLocal
from app.models import ParentCommentary, Task

ELIF = 228


def main() -> int:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    prev_monday = monday - timedelta(days=7)
    yesterday = today - timedelta(days=1)

    with SessionLocal() as db:
        rows = (
            db.query(Task)
            .filter(Task.student_id == ELIF,
                    Task.date >= prev_monday, Task.date < monday)
            .all()
        )
        moved = kept = 0
        for t in rows:
            if t.date == yesterday:
                kept += 1  # dünün karnesi (2 tamam + 1 eksik + 1 taslak) korunur
                continue
            # Cuma'nın bekleyen görevi BUGÜNE (panel "bugün 1/2" gerçekçi olsun),
            # kalanlar +7 gün → bu haftanın programı.
            if t.date == prev_monday + timedelta(days=4) and t.status.value != "completed":
                t.date = today
            else:
                t.date = t.date + timedelta(days=7)
            moved += 1
        deleted = (
            db.query(ParentCommentary)
            .filter(ParentCommentary.student_id == ELIF)
            .delete(synchronize_session=False)
        )
        db.commit()
        print(f"taşınan görev: {moved} · dünde korunan: {kept} · silinen yorum: {deleted}")

        after = (
            db.query(Task)
            .filter(Task.student_id == ELIF, Task.date >= yesterday)
            .order_by(Task.date).all()
        )
        for t in after:
            print(" ", t.date, t.status.value, t.is_draft, (t.title or "")[:50])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
