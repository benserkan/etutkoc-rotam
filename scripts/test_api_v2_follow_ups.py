# -*- coding: utf-8 -*-
"""Takip listesi + ölçüm listesi smoke (2026-11-08).

Asıl korunan sözleşmeler:
- Vadesi gelen iş unutulmaz: gece işi vade günü bildirir, gecikmişte 3 günde
  bir yeniden bildirir, aynı gün iki kez bildirmez.
- Ölçüye bağlı işte rapor ölçüm geçmişinden çıkar: başlangıç ↔ son değer,
  düşen/yükselen koç doğru ayrışır, az örnekli koç karar vermez.
- Tekrarlayan iş tamamlanınca sıradaki kendiliğinden açılır.
- Rozet = vadesi gelmiş açık iş; işleyince düşer.
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import FollowUp, MetricSnapshot, User, UserRole  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import follow_up_service as fus  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

settings.super_admin_require_2fa = False

PFX = f"fu{secrets.token_hex(3)}"
PASSWORD = "FollowUp1!@xyz"
TODAY = date.today()
BASE = TODAY - timedelta(days=21)
METRIC = "rec.shown"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _login(email):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text[:200]
    return c


def main() -> int:
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        sup = User(email=f"{PFX}_s@test.invalid", password_hash=pwd, full_name=f"{PFX} Süper",
                   role=UserRole.SUPER_ADMIN, is_active=True)
        t = User(email=f"{PFX}_t@test.invalid", password_hash=pwd, full_name=f"{PFX} Koç",
                 role=UserRole.TEACHER, is_active=True)
        c1 = User(email=f"{PFX}_c1@test.invalid", password_hash=pwd, full_name=f"{PFX} Düşen Koç",
                  role=UserRole.TEACHER, is_active=True)
        c2 = User(email=f"{PFX}_c2@test.invalid", password_hash=pwd, full_name=f"{PFX} Yükselen Koç",
                  role=UserRole.TEACHER, is_active=True)
        c3 = User(email=f"{PFX}_c3@test.invalid", password_hash=pwd, full_name=f"{PFX} Az Örnekli",
                  role=UserRole.TEACHER, is_active=True)
        db.add_all([sup, t, c1, c2, c3])
        db.flush()
        ids = {"sup": sup.id, "t": t.id, "c1": c1.id, "c2": c2.id, "c3": c3.id}
        # Ölçüm geçmişi: c1 60→48 (düşen), c2 40→55 (yükselen), c3 30→60 ama 20 örnek (az)
        for cid, b, l, n in ((c1.id, 60, 48, 400), (c2.id, 40, 55, 300), (c3.id, 30, 60, 20)):
            db.add(MetricSnapshot(metric_key=METRIC, owner_type="coach", owner_id=cid,
                                  measured_on=BASE, value=b, sample_n=n))
            db.add(MetricSnapshot(metric_key=METRIC, owner_type="coach", owner_id=cid,
                                  measured_on=TODAY - timedelta(days=1), value=l, sample_n=n))
        db.commit()
    created: list[int] = []
    try:
        URL = "/api/v2/admin/follow-ups"
        r = TestClient(app).get(URL)
        check("1. anonim → 401", r.status_code == 401, r.status_code)
        r = _login(f"{PFX}_t@test.invalid").get(URL)
        check("2. koç → 403", r.status_code == 403, r.status_code)

        sc = _login(f"{PFX}_s@test.invalid")
        badge0 = sc.get("/api/v2/admin/badges").json().get("follow_ups_due", 0)

        r = sc.post(URL, json={"title": f"{PFX} elle iş", "due_on": TODAY.isoformat(),
                               "category": "pazarlama"})
        manual = r.json()["data"]
        created.append(manual["id"])
        check("3. elle iş açılır, bugün vadeli → bucket today",
              r.status_code == 200 and manual["bucket"] == "today" and manual["days_left"] == 0, r.text[:200])

        b1 = sc.get("/api/v2/admin/badges").json()["follow_ups_due"]
        check("4. rozet +1", b1 == badge0 + 1, f"{badge0}→{b1}")

        r = sc.post(URL, json={"title": "x", "due_on": TODAY.isoformat(), "category": "yok"})
        check("5. geçersiz kategori → 422 invalid_category",
              r.status_code == 422 and r.json()["detail"]["code"] == "invalid_category", r.text[:160])
        r = sc.post(URL, json={"title": "x", "due_on": TODAY.isoformat(),
                               "check": {"metric_key": "yok.boyle"}})
        check("6. tanımsız ölçü → 422 invalid_metric",
              r.status_code == 422 and r.json()["detail"]["code"] == "invalid_metric", r.text[:160])
        r = sc.post(URL, json={"title": "x", "due_on": TODAY.isoformat(),
                               "check": {"metric_key": "email.delivery", "owner_type": "coach"}})
        check("7. ölçünün tutulmadığı kapsam → 422", r.status_code == 422, r.text[:160])

        r = sc.post(f"{URL}/{manual['id']}/snooze", json={"days": 3})
        it = r.json()["data"]
        check("8. erteleme → vade +3, bucket upcoming",
              it["effective_due"] == (TODAY + timedelta(days=3)).isoformat() and it["bucket"] == "upcoming",
              it)
        b2 = sc.get("/api/v2/admin/badges").json()["follow_ups_due"]
        check("9. ertelenince rozet düşer", b2 == badge0, f"{b2}")
        r = sc.post(f"{URL}/{manual['id']}/snooze", json={"until": TODAY.isoformat()})
        check("10. geçmiş/bugün erteleme → 422", r.status_code == 422, r.status_code)

        # Ölçüye bağlı iş — başlangıç 21 gün önce
        r = sc.post(URL, json={"title": f"{PFX} ölçüm", "due_on": (TODAY + timedelta(days=10)).isoformat(),
                               "category": "olcum", "priority": "high", "recurrence_days": 28,
                               "baseline_on": BASE.isoformat(),
                               "check": {"metric_key": METRIC, "owner_type": "coach", "min_change": 3}})
        mitem = r.json()["data"]
        created.append(mitem["id"])
        rep = mitem["report"] or {}
        rows = {row["owner_id"]: row for row in rep.get("rows", [])}
        check("11. oluştururken rapor üretilir", r.status_code == 200 and rep.get("metric_key") == METRIC, r.text[:200])
        check("12. düşen koç 'declined' (-12)",
              rows.get(ids["c1"], {}).get("verdict") == "declined" and rows[ids["c1"]]["delta"] == -12,
              rows.get(ids["c1"]))
        check("13. yükselen koç 'improved' (+15)",
              rows.get(ids["c2"], {}).get("verdict") == "improved", rows.get(ids["c2"]))
        check("14. az örnekli koç karar vermez → few_samples",
              rows.get(ids["c3"], {}).get("verdict") == "few_samples", rows.get(ids["c3"]))
        check("15. özet düşen koçu adıyla söyler + genel karar 'declined'",
              f"{PFX} Düşen Koç" in rep.get("summary", "") and rep.get("verdict") == "declined",
              rep.get("summary"))

        # Gece işi — bildirim ritmi
        with SessionLocal() as db:
            mine = db.get(FollowUp, mitem["id"])
            due = mine.effective_due
            others = db.query(FollowUp).filter(FollowUp.id != mitem["id"],
                                               FollowUp.status == "open").all()
            saved = {o.id: o.status for o in others}
            for o in others:
                o.status = "cancelled"  # yalnız kendi kayıtlarımız ölçülsün
            db.commit()
        try:
            with SessionLocal() as db:
                res = fus.run_daily(db, due - timedelta(days=1), send=False)
                check("16. vadeden önce bildirim yok", res["due"] == 0, res)
            with SessionLocal() as db:
                res = fus.run_daily(db, due, send=False)
                check("17. vade günü bildirilir", res["due"] == 1, res)
            with SessionLocal() as db:
                res = fus.run_daily(db, due, send=False)
                check("18. aynı gün ikinci kez bildirilmez", res["due"] == 0, res)
            with SessionLocal() as db:
                res = fus.run_daily(db, due + timedelta(days=2), send=False)
                check("19. gecikmişte 2. gün tekrar yok", res["due"] == 0, res)
            with SessionLocal() as db:
                res = fus.run_daily(db, due + timedelta(days=3), send=False)
                check("20. gecikmişte 3. gün yeniden hatırlatılır", res["due"] == 1, res)

            # Özet e-posta gerçek şablonla render + gönderim çağrısı
            sent: list[tuple[str, str, dict]] = []
            import app.services.email_service as es
            orig = es.send_email
            es.send_email = lambda to, tpl, ctx, **k: sent.append((to, tpl, ctx)) or True
            try:
                with SessionLocal() as db:
                    db.query(FollowUp).filter(FollowUp.id == mitem["id"]).update({"notified_on": None})
                    db.commit()
                    res = fus.run_daily(db, due + timedelta(days=4), send=True)
            finally:
                es.send_email = orig
            check("21. özet e-posta süper admine gider",
                  res.get("email_ok", 0) >= 1 and any(tpl == "follow_up_digest" for _, tpl, _ in sent), res)
            html = es.render_template_safe("follow_up_digest", sent[0][2]) if sent else None
            check("22. şablon render: başlık + gecikme + ölçüm özeti",
                  bool(html) and f"{PFX} ölçüm" in html[2] and "gün gecikti" in html[2]
                  and "Düşen Koç" in html[2], (html or ("", "", ""))[0])
        finally:
            with SessionLocal() as db:
                for oid, st in saved.items():
                    db.query(FollowUp).filter(FollowUp.id == oid).update({"status": st})
                db.commit()

        # Tamamla → tekrarlayan iş sıradakini açar
        r = sc.post(f"{URL}/{mitem['id']}/complete", json={"note": "Düşen koçla görüşüldü"})
        nxt = r.json()["data"]["next"]
        if nxt:
            created.append(nxt["id"])
        check("23. tamamla → sıradaki 28 gün sonra, başlangıç bugün",
              r.status_code == 200 and nxt and nxt["effective_due"] == (TODAY + timedelta(days=28)).isoformat()
              and nxt["baseline_on"] == TODAY.isoformat() and nxt["check"]["metric_key"] == METRIC, r.text[:300])
        r = sc.post(f"{URL}/{mitem['id']}/complete", json={})
        check("24. kapalı iş tekrar tamamlanmaz → 422", r.status_code == 422, r.status_code)

        r = sc.get(URL + "?status=closed")
        closed = [i for i in r.json()["items"] if i["id"] == mitem["id"]]
        check("25. kapalılarda sonuç notu + tamamlayan görünür",
              closed and closed[0]["result_note"] == "Düşen koçla görüşüldü"
              and closed[0]["completed_by_name"] == f"{PFX} Süper", closed)

        r = sc.post(f"{URL}/{manual['id']}/delete")
        check("26. açık iş silinmez → 422 still_open",
              r.status_code == 422 and r.json()["detail"]["code"] == "still_open", r.text[:160])
        sc.post(f"{URL}/{manual['id']}/cancel", json={"note": "gerek kalmadı"})
        r = sc.post(f"{URL}/{manual['id']}/delete")
        check("27. iptal edilen iş silinir", r.status_code == 200, r.status_code)
        created.remove(manual["id"])

        r = sc.get("/api/v2/admin/metrics")
        keys = {m["key"] for m in r.json().get("metrics", [])}
        check("28. ölçüm listesi tüm tanımlı ölçüleri döner",
              r.status_code == 200 and {"rec.shown", "skeleton.acceptance", "email.delivery"} <= keys, keys)
        r = sc.get(f"/api/v2/admin/metrics/{METRIC}?days=60")
        own = {o["owner_id"]: o for o in r.json().get("owners", [])}
        check("29. ölçü detayı: koç serisi + 21 gün değişim + az örnek işareti",
              own.get(ids["c1"], {}).get("delta_21d") == -12 and own[ids["c3"]]["enough_sample"] is False,
              own.get(ids["c1"]))
        r = sc.get("/api/v2/admin/metrics/yok.boyle")
        check("30. tanımsız ölçü → 404", r.status_code == 404, r.status_code)
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(FollowUp).where(FollowUp.id.in_(created)))
            db.execute(sa_delete(FollowUp).where(FollowUp.title.like(f"{PFX}%")))
            db.execute(sa_delete(MetricSnapshot).where(MetricSnapshot.owner_id.in_(list(ids.values())),
                                                       MetricSnapshot.owner_type == "coach"))
            db.execute(sa_delete(User).where(User.id.in_(list(ids.values()))))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print("  -", f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
