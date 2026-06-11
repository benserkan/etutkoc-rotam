"""QA-1 — Hızlı erişim kartları smoke (davranıştan öğrenen panel kartları).

Senaryolar:
  1-2.  Anonim 401 (visits + cards)
  3.    Batch ziyaret: katalog-içi sayılır, katalog-dışı (/login) + rol-dışı
        (/admin/*) sessizce atlanır
  4.    Dakika-içi çift sayım koruması (dedup)
  5.    Eşik: tek günlük ziyaret kart ÖNERMEZ (days_seen < 3)
  6.    3 farklı günde ziyaret → ÖNERİLEN kart (entity etiketi + href doğru)
  7.    Karta 3 tıklama → KALICI (established)
  8.    Sabitle / sabitlemeyi kaldır
  9.    Erişim düşmesi: öğrenci pasifleşince kart düşer, aktifleşince döner
  10.   Kaldır (dismiss) → kart görünmez + kalıcılık sıfırlanır
  11.   Rol izolasyonu: başka koçun öğrencisi karta dönüşmez (skor olsa bile)
  12.   Veli: bağlı çocuğun haftalık raporu kart olur; bağsızda olmaz
  13.   Click 404 (olmayan kart)
  14.   Purge cron: 200 günlük olay + bayat satır silinir, sabitli satır yaşar
  15.   Cron kaydı: JOB_REGISTRY + cron_schedules seed
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    PanelRouteStat,
    PanelVisitEvent,
    ParentStudentLink,
    User,
    UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.services import panel_behavior as pb
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"qa_{secrets.token_hex(3)}"
PWD_HASH = hash_password("QuickAcc!23")
PWD = "QuickAcc!23"
now = datetime.now(timezone.utc)

passed = 0
failed: list[str] = []
ctx: dict = {}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _user(db, key, role, **kw):
    u = User(
        email=f"{PFX}_{key}@test.invalid",
        password_hash=PWD_HASH,
        full_name=f"{PFX} {key}",
        role=role,
        is_active=True,
        password_changed_at=now,
        must_change_password=False,
        **kw,
    )
    db.add(u)
    db.flush()
    return u


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        coach_a = _user(db, "coach_a", UserRole.TEACHER, plan="solo_pro")
        coach_b = _user(db, "coach_b", UserRole.TEACHER, plan="solo_pro")
        s1 = _user(db, "s1", UserRole.STUDENT, teacher_id=coach_a.id, grade_level=8)
        parent = _user(db, "parent", UserRole.PARENT)
        db.add(ParentStudentLink(parent_id=parent.id, student_id=s1.id))
        db.commit()
        ctx.update(
            coach_a=coach_a.id, coach_b=coach_b.id, s1=s1.id, parent=parent.id
        )


def login(key):
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post(
        "/api/v2/auth/login",
        json={"email": f"{PFX}_{key}@test.invalid", "password": PWD},
    )
    if r.status_code != 200:
        raise RuntimeError(f"login {key}: {r.status_code} {r.text}")
    return c


def simulate_visits(user_id, path, days_offsets):
    """Servisle farklı günlere yayılmış ziyaret simülasyonu."""
    with SessionLocal() as db:
        u = db.get(User, user_id)
        for d in days_offsets:
            pb.record_visits(
                db, u, [{"path": path, "dwell_ms": 5000}],
                now=now - timedelta(days=d),
            )
        db.commit()


def main() -> int:
    print(f"\n=== HIZLI ERİŞİM KARTLARI (QA-1) — {PFX} ===\n")
    setup()
    s1 = ctx["s1"]
    week_path = f"/teacher/students/{s1}/week"
    try:
        anon = TestClient(app)
        r = anon.post("/api/v2/me/panel-visits", json={"events": [{"path": "/teacher/billing"}]})
        check("1. anonim panel-visits → 401", r.status_code == 401, f"{r.status_code}")
        r = anon.get("/api/v2/me/quick-cards")
        check("2. anonim quick-cards → 401", r.status_code == 401, f"{r.status_code}")

        c = login("coach_a")
        r = c.post(
            "/api/v2/me/panel-visits",
            json={
                "events": [
                    {"path": week_path, "dwell_ms": 4000},
                    {"path": "/teacher/billing"},
                    {"path": "/login"},                # katalog dışı
                    {"path": "/admin/users"},          # rol dışı
                    {"path": "/payment/result"},       # katalog dışı
                ]
            },
        )
        check(
            "3. batch: 2 kabul (katalog-dışı + rol-dışı atlandı)",
            r.status_code == 200 and r.json()["accepted"] == 2,
            f"{r.status_code} {r.text[:120]}",
        )
        r = c.post("/api/v2/me/panel-visits", json={"events": [{"path": week_path}]})
        with SessionLocal() as db:
            stat = (
                db.query(PanelRouteStat)
                .filter_by(user_id=ctx["coach_a"], route_key="teacher.student_week", entity_id=s1)
                .first()
            )
            vc = stat.visit_count if stat else -1
        check(
            "4. dakika-içi tekrar ziyaret SAYILMADI (dedup, visit_count=1)",
            r.json()["accepted"] == 0 and vc == 1,
            f"accepted={r.json().get('accepted')} visit_count={vc}",
        )

        cards = c.get("/api/v2/me/quick-cards").json()["cards"]
        check("5. tek günlük ziyaret kart ÖNERMEZ (days_seen<3)", cards == [], f"{cards}")

        # mobil kaynak (QA-3): source=mobile kabul, geçersiz source 422
        r = c.post("/api/v2/me/panel-visits",
                   json={"events": [{"path": "/teacher/library"}], "source": "mobile"})
        with SessionLocal() as db:
            ev = (
                db.query(PanelVisitEvent)
                .filter_by(user_id=ctx["coach_a"], route_key="teacher.library")
                .first()
            )
        r2 = c.post("/api/v2/me/panel-visits",
                    json={"events": [{"path": "/teacher/library"}], "source": "hacker"})
        check(
            "5b. source=mobile kaydedildi, geçersiz source 422",
            r.status_code == 200 and ev is not None and ev.source == "mobile"
            and r2.status_code == 422,
            f"r={r.status_code} src={getattr(ev, 'source', None)} r2={r2.status_code}",
        )

        # 3 farklı güne yayılmış ziyaret → önerilen
        simulate_visits(ctx["coach_a"], week_path, [2, 1])  # bugünkü zaten var
        cards = c.get("/api/v2/me/quick-cards").json()["cards"]
        wk = next((x for x in cards if x["route_key"] == "teacher.student_week"), None)
        check(
            "6. 3 farklı gün → ÖNERİLEN kart (öğrenci adı + sayfa etiketi + href)",
            wk is not None
            and wk["state"] == "suggested"
            and wk["label"] == f"{PFX} s1"
            and wk["sublabel"] == "Haftalık Program"
            and wk["href"] == week_path
            and wk["entity_id"] == s1,
            f"{wk}",
        )

        # 3 kart tıkı → kalıcı
        body = {"route_key": "teacher.student_week", "entity_id": s1}
        for _ in range(2):
            c.post("/api/v2/me/quick-cards/click", json=body)
        r = c.post("/api/v2/me/quick-cards/click", json=body)
        d = r.json()["data"]
        check(
            "7. karta 3 tıklama → KALICI (established) + invalidate",
            d["state"] == "established"
            and d["card_clicks"] == 3
            and r.json()["invalidate"] == ["me:quick-cards"],
            f"{r.text[:160]}",
        )

        # sabitle / kaldır
        r = c.post("/api/v2/me/quick-cards/pin", json={**body, "pinned": True})
        cards = c.get("/api/v2/me/quick-cards").json()["cards"]
        check(
            "8. sabitle → state=pinned + ilk sırada",
            r.json()["data"]["state"] == "pinned"
            and cards and cards[0]["route_key"] == "teacher.student_week"
            and cards[0]["state"] == "pinned",
            f"{cards[:2]}",
        )
        c.post("/api/v2/me/quick-cards/pin", json={**body, "pinned": False})

        # erişim düşmesi: öğrenci pasif → kart düşer; aktif → döner
        with SessionLocal() as db:
            db.query(User).filter_by(id=s1).update({"is_active": False})
            db.commit()
        cards = c.get("/api/v2/me/quick-cards").json()["cards"]
        gone = all(x["route_key"] != "teacher.student_week" for x in cards)
        with SessionLocal() as db:
            db.query(User).filter_by(id=s1).update({"is_active": True})
            db.commit()
        back = any(
            x["route_key"] == "teacher.student_week"
            for x in c.get("/api/v2/me/quick-cards").json()["cards"]
        )
        check("9. öğrenci pasif → kart düştü; aktif → geri geldi", gone and back,
              f"gone={gone} back={back}")

        # dismiss
        r = c.post("/api/v2/me/quick-cards/dismiss", json=body)
        cards = c.get("/api/v2/me/quick-cards").json()["cards"]
        with SessionLocal() as db:
            stat = (
                db.query(PanelRouteStat)
                .filter_by(user_id=ctx["coach_a"], route_key="teacher.student_week", entity_id=s1)
                .first()
            )
            dis_ok = stat is not None and stat.dismissed_until is not None and stat.card_clicks == 0
        check(
            "10. kaldır → kart görünmez + 90g bastırma + kalıcılık sıfır",
            r.status_code == 200
            and all(x["route_key"] != "teacher.student_week" for x in cards)
            and dis_ok,
            f"cards={cards} dis_ok={dis_ok}",
        )

        # rol izolasyonu: koç B, A'nın öğrencisini gezse bile kart ÇIKMAZ
        simulate_visits(ctx["coach_b"], week_path, [2, 1, 0])
        cb = login("coach_b")
        cards_b = cb.get("/api/v2/me/quick-cards").json()["cards"]
        check(
            "11. başka koçun öğrencisi karta dönüşmez (erişim yok)",
            all(x["route_key"] != "teacher.student_week" for x in cards_b),
            f"{cards_b}",
        )

        # veli: bağlı çocuğun raporu kart olur
        report_path = f"/parent/students/{s1}/report"
        simulate_visits(ctx["parent"], report_path, [2, 1, 0])
        cp = login("parent")
        cards_p = cp.get("/api/v2/me/quick-cards").json()["cards"]
        rp = next((x for x in cards_p if x["route_key"] == "parent.child_report"), None)
        check(
            "12. veli: bağlı çocuğun Haftalık Rapor kartı (ad + href)",
            rp is not None and rp["label"] == f"{PFX} s1" and rp["href"] == report_path,
            f"{cards_p}",
        )

        r = c.post("/api/v2/me/quick-cards/click",
                   json={"route_key": "teacher.bulk_wa", "entity_id": None})
        check("13. olmayan karta click → 404 card_not_found",
              r.status_code == 404 and r.json()["detail"]["code"] == "card_not_found",
              f"{r.status_code} {r.text[:120]}")

        # purge: 200 günlük olay + bayat satır silinir; sabitli satır yaşar
        with SessionLocal() as db:
            old = now - timedelta(days=200)
            db.add(PanelVisitEvent(
                user_id=ctx["coach_a"], role="teacher", route_key="teacher.billing",
                entity_id=None, dwell_ms=0, source="web", created_at=old,
            ))
            db.add(PanelRouteStat(
                user_id=ctx["coach_a"], route_key="teacher.insights", entity_id=0,
                score=1.0, visit_count=2, days_seen=2, last_visit_at=old,
                last_visit_date=old.date(),
            ))
            db.add(PanelRouteStat(
                user_id=ctx["coach_a"], route_key="teacher.usage", entity_id=0,
                score=1.0, visit_count=2, days_seen=2, last_visit_at=old,
                last_visit_date=old.date(), pinned_at=old,
            ))
            db.commit()
        with SessionLocal() as db:
            res = pb.purge_old_events(db, now=now)
            stale_gone = (
                db.query(PanelRouteStat)
                .filter_by(user_id=ctx["coach_a"], route_key="teacher.insights")
                .first()
                is None
            )
            pinned_alive = (
                db.query(PanelRouteStat)
                .filter_by(user_id=ctx["coach_a"], route_key="teacher.usage")
                .first()
                is not None
            )
        check(
            "14. purge: eski olay+bayat satır silindi, SABİTLİ satır yaşıyor",
            res["deleted_events"] >= 1 and res["deleted_stats"] >= 1
            and stale_gone and pinned_alive,
            f"{res} stale_gone={stale_gone} pinned_alive={pinned_alive}",
        )

        from app.services.cron_jobs import JOB_REGISTRY
        with SessionLocal() as db:
            import sqlalchemy as sa
            row = db.execute(
                sa.text("SELECT enabled FROM cron_schedules WHERE job_key='panel_events_purge'")
            ).first()
        check(
            "15. cron kaydı: JOB_REGISTRY + cron_schedules seed (enabled)",
            "panel_events_purge" in JOB_REGISTRY and row is not None and row[0] == 1,
            f"registry={'panel_events_purge' in JOB_REGISTRY} row={row}",
        )
    finally:
        cleanup()

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f_ in failed:
        print(f"  FAIL: {f_}")
    return 0 if not failed else 1


def cleanup():
    with SessionLocal() as db:
        ids = [v for k, v in ctx.items()]
        db.query(PanelVisitEvent).filter(PanelVisitEvent.user_id.in_(ids)).delete(
            synchronize_session=False
        )
        db.query(PanelRouteStat).filter(PanelRouteStat.user_id.in_(ids)).delete(
            synchronize_session=False
        )
        db.query(ParentStudentLink).filter(
            ParentStudentLink.parent_id.in_(ids)
        ).delete(synchronize_session=False)
        db.query(SuspiciousIp).filter(SuspiciousIp.ip == "testclient").delete(
            synchronize_session=False
        )
        db.query(User).filter(User.id.in_(ids)).delete(synchronize_session=False)
        db.commit()


if __name__ == "__main__":
    sys.exit(main())
