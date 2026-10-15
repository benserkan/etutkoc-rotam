"""Kurum havuz panosu — gösterge doğrulaması (2026-10-13).

Adım 5 tohumu (test_pool_step5.seed) üstüne: ara (tatil) dönemi "son dönem %"ye girmez · randevu +
beklenen seans günü aynı öğrenciyi iki kez saymaz · şube sarı sayısı · katılım (kap/işaret) · tempo ·
kayıt kaynağı (öğrenci kaydı vs rehber seans işareti) · kalem yapısı · sinyal aileleri · ders bazında ·
eğilim · HTTP ucunun yeni alanları.

Çalıştır: PYTHONPATH=. python scripts/test_institution_pool_overview.py
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from scripts import test_pool_step5 as base  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import PoolItem, StudyPeriod  # noqa: E402
from app.models.pool import PERIOD_BREAK  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.institution_pool import build_overview, _last_closed_pct  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402

today = base.today
ok: list[bool] = []


def check(label, cond, detail=""):
    ok.append(bool(cond))
    print(("  [PASS] " if cond else "  [FAIL] ") + label + ("" if cond else f"  ({detail})"))


def main() -> int:
    get_login_limiter().reset()
    d = base.seed()
    try:
        with SessionLocal() as db:
            # s_today: eski bir ARA (tatil) dönemi tam dolu → "son dönem %"ye GİRMEMELİ
            ara = StudyPeriod(student_id=d["today"], coach_id=d["coach"], opened_on=today - timedelta(days=30),
                              closed_on=today - timedelta(days=23), status=PERIOD_BREAK)
            db.add(ara)
            db.flush()
            db.add(PoolItem(period_id=ara.id, student_id=d["today"], subject_id=d["tyt"], quantity=6, unit="test",
                            completed=6))
            # s_today: beklenen seans günü BUGÜN + bugün randevusu var → bugünkü görüşme 1 (2 değil)
            op = pm.get_open_period(db, d["today"])
            op.expected_next_on = today
            # s_late açık kalemine rehber seans işareti → kayıt kaynağında rehber payı
            it = db.query(PoolItem).filter(PoolItem.period_id == pm.get_open_period(db, d["late"]).id).first()
            it.session_marked = 2
            db.commit()

            check("1 ara dönemi son dönem %'sine girmez (s_today → None)",
                  _last_closed_pct(db, d["today"], today) is None, _last_closed_pct(db, d["today"], today))
            ov = build_overview(db, institution_id=d["inst"])
            c1 = next(r for r in ov.coach_rows if r["coach_id"] == d["coach"])
            check("2 bugünkü görüşme çift sayılmaz (randevu + beklenen gün aynı öğrenci → 1)",
                  c1["today_sessions"] == 1, c1)
            check("3 rehber yükü = bugün + geciken + kırmızı", c1["load"] == c1["today_sessions"] + c1["late_sessions"] + c1["red"], c1)
            g = {r["class_group"]: r for r in ov.groups}
            check("4 şube satırında sarı sayısı alanı var + toplam sarıyla tutarlı",
                  all("amber" in r for r in ov.groups) and sum(r["amber"] for r in ov.groups) == ov.amber_students,
                  ov.groups)
            check("5 şube 12-A son dönem % = s_main kapanmış dönem (ara dahil değil)",
                  g["12-A"]["last_pct"] is not None and g["12-A"]["last_pct"] < 100, g.get("12-A"))
            p = ov.participation
            check("6 katılım: bugün kap kuran 1 + işaretleyen 1 (s_main), öğrenci 3",
                  p["students"] == 3 and p["cup_today"] == 1 and p["ticked_today"] == 1, p)
            check("7 tempo sayıları açık dönem sayısıyla tutarlı", sum(ov.pace.values()) == ov.open_periods, (ov.pace, ov.open_periods))
            s = ov.sources
            check("8 kayıt kaynağı: öğrenci + rehber = biten birim; rehber payı > 0",
                  s["student_units"] + s["coach_units"] == s["done_units"] and s["coach_units"] >= 1, s)
            i = ov.items
            check("9 kalem yapısı: kitaplı + konulu + serbest = toplam; devir 2", i["book"] + i["topic"] + i["free"] == i["total"]
                  and i["carried"] == 2, i)
            keys = [x["key"] for x in ov.signals]
            check("10 sinyal aileleri sabit sırada (seans→toplu) ve seans ailesi ≥1 öğrenci",
                  keys[0] == "seans" and keys[-1] == "toplu" and ov.signals[0]["students"] >= 1, ov.signals)
            check("11 ders bazında: TYT Matematik satırı, yüzde 0-100", len(ov.subjects) == 1
                  and "TYT Matematik" in ov.subjects[0]["name"] and 0 <= ov.subjects[0]["pct"] <= 100, ov.subjects)
            check("12 eğilim 4 hafta, s_main'in kapanan dönemi bir haftada", len(ov.trend) == 4
                  and sum(t["periods"] for t in ov.trend) >= 1, ov.trend)
            check("13 geciken satırında açık dönem %", any(r["pct"] is not None for r in ov.late), ov.late)

        with TestClient(app) as c:
            r = c.post("/api/v2/auth/login", json={"email": f"{base.PFX}_admin@test.invalid", "password": base.PWD})
            r = c.get("/api/v2/institution/pool-overview")
            j = r.json()
            check("14 HTTP: yeni alanlar (participation/pace/sources/items/signals/subjects/trend)",
                  r.status_code == 200 and all(k in j for k in ("participation", "pace", "sources", "items", "signals",
                                                                "subjects", "trend", "avg_expected_pct")), j.keys())
            check("15 HTTP: rehber satırında onay bekleyen/toplu/kağıt + açık dönem ort.",
                  all(k in j["coaches_rows"][0] for k in ("pending_approval", "bulk", "paper", "avg_open_pct")), j["coaches_rows"][0])
    finally:
        with SessionLocal() as db:
            db.query(PoolItem).filter(PoolItem.student_id == d["today"]).delete()
            db.commit()
        base.cleanup()
    print(f"\n{sum(ok)}/{len(ok)} geçti")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
