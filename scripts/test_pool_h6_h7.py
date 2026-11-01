"""Havuz H6–H7 (2026-11-01).

  H6  "Daha önce yaptım": öğrenci kalemi en çok 2 gün geriye (açık dönem içinde) yapıldı olarak
      kaydeder → o güne tamamlanmış kap görevi; işaretleme anı (completed_at) gerçek an kalır
  H7  dönem penceresinin gün listesi pool_metrics.period_ranges ile aynı kural: kapanış günü o gün
      yeni dönem açıldıysa yeni döneme aittir (iki dönemde birden görünmez)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import test_pool_h1_h5 as base  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Book, BookSection, Subject, Task, User  # noqa: E402
from app.models.pool import PoolItem, StudyPeriod  # noqa: E402
from app.models.task import TaskStatus  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402

today = base.today
check = base.check


def main() -> int:
    get_login_limiter().reset()
    d = base.seed()
    print(f"\n=== havuz H6–H7 — {base.PFX} ===\n")
    try:
        # ------------------------------------------------ H7
        with SessionLocal() as db:
            st = db.get(User, d["st"])
            coach = db.get(User, d["coach"])
            a = today - timedelta(days=20)
            close = today - timedelta(days=13)
            p1 = pm.open_period(db, student=st, coach=coach, opened_on=a, expected_next_on=close)
            pm.close_period(db, p1, closed_on=close)
            p2 = pm.open_period(db, student=st, coach=coach, opened_on=close, expected_next_on=close + timedelta(days=4))
            close2 = close + timedelta(days=5)
            pm.close_period(db, p2, closed_on=close2)       # sonrasında aynı gün yeni dönem YOK
            db.flush()
            d1 = [x for x, _ in pm.period_detail(db, p1, today=today).days]
            d2 = [x for x, _ in pm.period_detail(db, p2, today=today).days]
            check("H7a kapanış günü yeni dönem açıldıysa eski dönemde yok", d1[-1] == close - timedelta(days=1), d1[-3:])
            check("H7b o gün yeni dönemde var", d2[0] == close, d2[:2])
            check("H7c ardından dönem açılmadıysa kapanış günü dönemde kalır", d2[-1] == close2, d2[-2:])
            check("H7d iki dönemin günleri kesişmez", not (set(d1) & set(d2)), set(d1) & set(d2))

            # ------------------------------------------------ H6 kurgu: açık dönem 5 gün önce
            p3 = pm.open_period(db, student=st, coach=coach, opened_on=today - timedelta(days=5),
                                expected_next_on=today + timedelta(days=2))
            sub = db.get(Subject, d["subs"]["mat"])
            it = pm.add_item(db, period=p3, student=st, subject=sub, quantity=10, unit="test",
                             book=db.get(Book, d["books"]["mat"]), section=db.get(BookSection, d["secs"]["mat"]),
                             created_by=coach)
            sub_t = db.get(Subject, d["subs"]["tur"])
            it_tr = pm.add_item(db, period=p3, student=st, subject=sub_t, quantity=6, unit="test",
                                book=db.get(Book, d["books"]["tur"]), section=db.get(BookSection, d["secs"]["tur"]),
                                created_by=coach)
            act = pm.add_item(db, period=p3, student=st, subject=sub, quantity=None, unit="etkinlik",
                              label="Video izle", created_by=coach)
            db.commit()
            ids = {"it": it.id, "tr": it_tr.id, "act": act.id, "p3": p3.id}

        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{base.PFX}_s@test.invalid", "password": base.PWD})
        assert r.status_code == 200, r.text
        sp = c.get("/api/v2/student/pool").json()
        exp = [(today - timedelta(days=1)).isoformat(), (today - timedelta(days=2)).isoformat()]
        check("H6a seçilebilir günler dün + 2 gün önce", sp.get("earlier_days") == exp, sp.get("earlier_days"))

        y = today - timedelta(days=1)
        t0 = datetime.now(timezone.utc) - timedelta(seconds=5)
        r = c.post("/api/v2/student/pool/done-earlier",
                   json={"item_id": ids["it"], "day": y.isoformat(), "count": 3, "correct": 2, "wrong": 1})
        check("H6b dün 3 test → 200", r.status_code == 200, r.text[:200])
        with SessionLocal() as db:
            ts = db.query(Task).filter(Task.pool_item_id == ids["it"]).all()
            t = ts[0] if ts else None
            check("H6c görev dünün tarihinde ve tamamlanmış", t is not None and t.date == y and t.status == TaskStatus.COMPLETED,
                  [(x.date, x.status) for x in ts])
            bi = t.book_items[0] if t else None
            check("H6d 3 test + D/Y yazıldı", bi is not None and bi.completed_count == 3 and bi.correct_count == 2
                  and bi.wrong_count == 1, bi and (bi.completed_count, bi.correct_count, bi.wrong_count))
            ca = t.completed_at if t else None
            if ca is not None and ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            check("H6e işaretleme anı gerçek an (gün değil)", ca is not None and ca >= t0, ca)
            item = db.get(PoolItem, ids["it"])
            check("H6f kalem ilerlemesi 3", item.completed == 3, item.completed)

        r = c.post("/api/v2/student/pool/done-earlier", json={"item_id": ids["it"], "day": (today - timedelta(days=3)).isoformat(), "count": 1})
        check("H6g 3 gün önce → 422 bad_day", r.status_code == 422 and r.json()["detail"]["code"] == "bad_day", r.text[:150])
        r = c.post("/api/v2/student/pool/done-earlier", json={"item_id": ids["it"], "day": today.isoformat(), "count": 1})
        check("H6h bugün → 422 (bugün için Kaba al)", r.status_code == 422, r.text[:150])
        r = c.post("/api/v2/student/pool/done-earlier", json={"item_id": ids["it"], "day": y.isoformat(), "count": 2, "correct": 3})
        check("H6i doğru+yanlış sayıyı geçemez → 422", r.status_code == 422 and r.json()["detail"]["code"] == "result_exceeds", r.text[:150])

        r = c.post("/api/v2/student/pool/cup", json={"item_id": ids["tr"], "count": 2})
        assert r.status_code == 200, r.text
        r = c.post("/api/v2/student/pool/done-earlier", json={"item_id": ids["tr"], "day": y.isoformat(), "count": 1})
        check("H6j bugünün kabındaki kalem → 409 in_cup_today", r.status_code == 409 and r.json()["detail"]["code"] == "in_cup_today", r.text[:150])

        r = c.post("/api/v2/student/pool/done-earlier", json={"item_id": ids["act"], "day": (today - timedelta(days=2)).isoformat()})
        check("H6k etkinlik kalemi sayısız → 200", r.status_code == 200, r.text[:150])
        with SessionLocal() as db:
            ta = db.query(Task).filter(Task.pool_item_id == ids["act"]).first()
            check("H6l etkinlik görevi 2 gün önce tamamlanmış", ta is not None and ta.date == today - timedelta(days=2)
                  and ta.status == TaskStatus.COMPLETED, ta and (ta.date, ta.status))
            det = pm.period_detail(db, db.get(StudyPeriod, ids["p3"]), today=today)
            day_y = [len(ts) for dd, ts in det.days if dd == y]
            check("H6m dönem penceresi dünün satırında görevi gösterir", day_y == [1], day_y)
    finally:
        base.cleanup()
    print(f"\n{base.passed} geçti · {len(base.failed)} kaldı")
    if base.failed:
        print("KALAN:", base.failed)
    return 1 if base.failed else 0


if __name__ == "__main__":
    sys.exit(main())
