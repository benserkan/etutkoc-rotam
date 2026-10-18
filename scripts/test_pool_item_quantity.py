"""Havuz kalemi miktar düzeltme — rehber 7 testi 5'e indirir (2026-10-18).

  Q1 4 → 6 büyütme: kalem 6, kalan 6
  Q2 öğrenci 2'sini kaba alır (açık) → en az 2; 1 → 422 below_done
  Q3 2'si işaretlenir (kap tamam) → 2'ye indirme olur, kalan 0
  Q4 başka koç 404 · Q5 kaldırılmış kalem 422 · Q6 kapalı dönem 422

Çalıştır: PYTHONPATH=. python scripts/test_pool_item_quantity.py
"""
from __future__ import annotations

import sys

from scripts import test_api_v2_pool_student as base
from app.database import SessionLocal
from app.models import PoolItem, StudyPeriod, TaskBookItem
from app.services.rate_limit import get_login_limiter

check = base.check


def main() -> int:
    get_login_limiter().reset()
    d = base.seed()
    print(f"\n=== havuz kalemi miktar düzeltme — {base.PFX} ===\n")
    try:
        t = base.login(f"{base.PFX}_t@test.invalid")
        url = lambda iid: f"/api/v2/teacher/students/{d['st']}/pool/items/{iid}/quantity"  # noqa: E731
        r = t.post(url(d["i1"]), json={"quantity": 6})
        it = next((i for i in r.json()["data"]["period"]["items"] if i["id"] == d["i1"]), {}) if r.status_code == 200 else {}
        check("Q1 4 → 6: kalem 6 test, kalan 6", it.get("quantity") == 6 and it.get("remaining") == 6, r.text[:200])

        s = base.login(f"{base.PFX}_s@test.invalid")
        r = s.post("/api/v2/student/pool/cup", json={"item_id": d["i1"], "count": 2})
        tid = next(c["task_id"] for c in r.json()["data"]["cup"] if c["item_id"] == d["i1"])
        r = t.post(url(d["i1"]), json={"quantity": 1})
        check("Q2 kapta açık 2 test varken 1 → 422 below_done",
              r.status_code == 422 and r.json()["detail"]["code"] == "below_done", r.text[:200])

        with SessionLocal() as db:
            bi = db.query(TaskBookItem).filter(TaskBookItem.task_id == tid).one()
        s.post(f"/api/v2/student/tasks/{tid}/items/{bi.id}/set-completed", json={"completed": 2})
        r = t.post(url(d["i1"]), json={"quantity": 2})
        it = next((i for i in r.json()["data"]["period"]["items"] if i["id"] == d["i1"]), {}) if r.status_code == 200 else {}
        check("Q3 2'si yapılmış → 2'ye indirilir, kalan 0", it.get("quantity") == 2 and it.get("remaining") == 0, r.text[:200])

        g = base.login(f"{base.PFX}_g@test.invalid")
        r = g.post(url(d["i2"]), json={"quantity": 2})
        check("Q4 başka kullanıcı erişemez (403/404)", r.status_code in (403, 404), r.text[:120])

        t.post(f"/api/v2/teacher/students/{d['st']}/pool/items/{d['i2']}/delete", json={})
        r = t.post(url(d["i2"]), json={"quantity": 2})
        check("Q5 kaldırılmış kalem 422 item_removed",
              r.status_code == 422 and r.json()["detail"]["code"] == "item_removed", r.text[:150])

        with SessionLocal() as db:
            from datetime import date
            p = db.get(StudyPeriod, d["pid"])
            p.status, p.closed_on = "kapandi", date.today()
            db.commit()
        r = t.post(url(d["i1"]), json={"quantity": 3})
        check("Q6 kapalı dönem 422 period_closed",
              r.status_code == 422 and r.json()["detail"]["code"] == "period_closed", r.text[:150])
        with SessionLocal() as db:
            check("Q7 kapalı dönemde miktar değişmedi", db.get(PoolItem, d["i1"]).quantity == 2)
    finally:
        base.cleanup()
    print(f"\n{base.passed if hasattr(base, 'passed') else ''}")
    return base.summary() if hasattr(base, "summary") else 0


if __name__ == "__main__":
    sys.exit(main())
