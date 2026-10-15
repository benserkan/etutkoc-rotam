"""Havuz kabı: öğrencinin kendi sayı düzeltmesi + toplu işaretleme sinyali (2026-10-13).

Saha soruları: (a) "Sayıyı değiştir" havuz öğrencisinde rehbere TALEP olmamalı — kabı öğrenci kurar, sayıyı
kendisi düzeltir; (b) öğrenci kaba çok alıp toplu "yaptım" derse (havuzu eritme) kontrol var mı?

  R1 kap görevi pool_item_id + pool_max_count taşır (Bugün ucu)
  R2 4 → 2 düzeltme: planlanan + başlık değişir, kalem kalanı aynı
  R3 kalandan fazlası 422 · R4 işaretlenenin altı 409 below_done · R5 tekrar büyütme → kısmi
  R6 kalemsiz etkinlik 422 not_resizable · R7 başkasının görevi 404
  B1-B4 bulk_marking birimi (10 dk'da ≥3 görev/≥12 test · günlük yoğun · alışkanlıkla eşik)
  B5 rapor: pool_bulk_mark rehbere (coach_only), öğrenci ipuçlarında YOK

Çalıştır: PYTHONPATH=. python scripts/test_pool_cup_resize_bulk.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from scripts import test_api_v2_pool_student as base  # seed / cleanup / login (aynı kurulum)
from app.database import SessionLocal
from app.models import PoolItem, Task, TaskBookItem, TaskStatus, TaskType, User
from app.services import pool_flags
from app.services.rate_limit import get_login_limiter

check = base.check
today = base.today


def _fake(item_id: int, minutes_ago: float, units: int, unit: str = "test"):
    it = PoolItem(id=item_id, unit=unit)
    t = Task(pool_item_id=item_id, date=today, completed_at=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
             book_items=[TaskBookItem(planned_count=units, completed_count=units)])
    return it, t


def main() -> int:
    get_login_limiter().reset()
    d = base.seed()
    print(f"\n=== kap düzeltme + toplu işaretleme — {base.PFX} ===\n")
    try:
        s = base.login(f"{base.PFX}_s@test.invalid")
        r = s.post("/api/v2/student/pool/cup", json={"item_id": d["i1"], "count": 4})
        tid = next(c["task_id"] for c in r.json()["data"]["cup"] if c["item_id"] == d["i1"])
        day = s.get(f"/api/v2/student/day?date={today.isoformat()}").json()
        t = next(x for x in day["tasks"] if x["id"] == tid)
        check("R1 kap görevi pool_item_id + pool_max_count=4", t["pool_item_id"] == d["i1"] and t["pool_max_count"] == 4, str(t)[:200])

        r = s.post(f"/api/v2/student/pool/cup/{tid}/resize", json={"count": 2})
        cup = next(c for c in r.json()["data"]["cup"] if c["task_id"] == tid)
        item = next(i for i in r.json()["data"]["items"] if i["id"] == d["i1"])
        with SessionLocal() as db:
            title = db.get(Task, tid).title
        check("R2 4→2: planlanan 2 + başlık '2 test', kalemin kalanı 4", r.status_code == 200 and cup["planned"] == 2
              and "2 test" in title and item["remaining"] == 4, f"{cup} {title} {item['remaining']}")

        r = s.post(f"/api/v2/student/pool/cup/{tid}/resize", json={"count": 5})
        check("R3 kalandan fazlası 422 bad_count", r.status_code == 422 and r.json()["detail"]["code"] == "bad_count", r.text[:150])

        with SessionLocal() as db:
            bi = db.query(TaskBookItem).filter(TaskBookItem.task_id == tid).one()
        r = s.post(f"/api/v2/student/tasks/{tid}/items/{bi.id}/set-completed", json={"completed": 2})
        r = s.post(f"/api/v2/student/pool/cup/{tid}/resize", json={"count": 1})
        check("R4 işaretlenenin (2) altına 409 below_done", r.status_code == 409 and r.json()["detail"]["code"] == "below_done", r.text[:150])

        r = s.post(f"/api/v2/student/pool/cup/{tid}/resize", json={"count": 3})
        with SessionLocal() as db:
            st = db.get(Task, tid).status
        check("R5 2 yapılmışken 3'e büyüt → kısmi (yapılan + kalan ≤ 4)", r.status_code == 200 and st == TaskStatus.PARTIAL, f"{r.status_code} {st}")

        r = s.post("/api/v2/student/pool/cup", json={"item_id": d["i3"]})
        etid = next(c["task_id"] for c in r.json()["data"]["cup"] if c["item_id"] == d["i3"])
        r = s.post(f"/api/v2/student/pool/cup/{etid}/resize", json={"count": 2})
        check("R6 kalemsiz etkinlik 422 not_resizable", r.status_code == 422 and r.json()["detail"]["code"] == "not_resizable", r.text[:150])

        g = base.login(f"{base.PFX}_g@test.invalid")
        r = g.post(f"/api/v2/student/pool/cup/{tid}/resize", json={"count": 2})
        check("R7 başka öğrenci 404", r.status_code == 404, r.text[:120])

        # ---- bulk_marking birimi
        a = [_fake(1, 6, 5), _fake(2, 3, 4), _fake(3, 1, 5)]
        res = pool_flags.bulk_marking([t for _, t in a], {i.id: i for i, _ in a}, None)
        check("B1 6 dk içinde 3 görev / 14 test → sinyal", res is not None and "3 görev" in res["detail"], str(res)[:200])
        a = [_fake(1, 200, 5), _fake(2, 100, 5), _fake(3, 1, 5)]
        res = pool_flags.bulk_marking([t for _, t in a], {i.id: i for i, _ in a}, None)
        check("B2 saatlere yayılmış 15 test → sinyal YOK", res is None, str(res)[:200])
        a = [_fake(i, 60 * i, 6) for i in range(1, 6)]
        res = pool_flags.bulk_marking([t for _, t in a], {i.id: i for i, _ in a}, None)
        check("B3 bir günde 30 test (alışkanlık yok, eşik 25) → yoğun gün", res is not None and "Yoğun gün" in str(res["evidence"]), str(res)[:200])
        res = pool_flags.bulk_marking([t for _, t in a], {i.id: i for i, _ in a}, 10.0)
        check("B4 alışkanlık 10/gün → eşik 30 → 30 test sinyal (≥)", res is not None)
        res = pool_flags.bulk_marking([t for _, t in a][:4], {i.id: i for i, _ in a}, 10.0)
        check("B4b alışkanlık 10/gün, 24 test → sinyal YOK", res is None, str(res)[:150])

        # ---- rapor: rehbere var, öğrenciye yok
        with SessionLocal() as db:
            st_user = db.get(User, d["st"])
            now = datetime.now(timezone.utc)
            for k, iid in enumerate((d["i1"], d["i2"], d["i1"])):
                db.add(Task(student_id=st_user.id, date=today, type=TaskType.TEST, title=f"bulk {k}", status=TaskStatus.COMPLETED,
                            order=50 + k, is_draft=False, published_at=now, pool_item_id=iid, completed_at=now - timedelta(minutes=k),
                            book_items=[TaskBookItem(label="x", planned_count=5, completed_count=5)]))
            db.commit()
            rep = pool_flags.evaluate_pool_flags(db, st_user, today)
            allf = rep.primary + rep.secondary
            bf = [w for w in allf if w.code == "pool_bulk_mark"]
            hints = pool_flags.student_hints(rep)
            check("B5 rapor: pool_bulk_mark rehbere (coach_only), öğrenci ipucunda yok",
                  bf and bf[0].coach_only and not any(h["code"] == "pool_bulk_mark" for h in hints),
                  str([w.code for w in allf]))
            db.rollback()
    finally:
        base.cleanup()
    print(f"\n{base.passed} passed · {len(base.failed)} failed")
    for f in base.failed:
        print("  -", f)
    return 1 if base.failed else 0


if __name__ == "__main__":
    sys.exit(main())
