"""Katman 9 — A/B test çerçevesi smoke test.

Senaryolar:
  1) Wilson güven aralığı sanity
  2) assign_variant deterministik (aynı sid → aynı variant)
  3) Variant dağılımı 1000 random session için weight'lere yakın
  4) get_active_experiment yalnız RUNNING'i döner
  5) compute_stats event_type başına agregat + Wilson CI
  6) lift_pct + vs_control_significant doğru
  7) landing_strategies REGISTRY: 3 anahtar, get_strategy fallback
  8) HTTP /api/telemetry/event variant payload kabul + DB'ye yazar
  9) Admin sayfaları: list/new GET, create POST, detail GET, status change POST
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import (
    ExperimentStatus,
    FeatureCardEvent,
    FeatureExperiment,
    User,
    UserRole,
)
from app.services import experiments as exp_svc
from app.services import landing_strategies as ls
from app.services import feature_catalog as fc


passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def approx(a: float, b: float, tol: float = 0.01) -> bool:
    return abs(a - b) <= tol


def cleanup(db, pfx: str) -> int:
    n = 0
    for e in db.query(FeatureExperiment).filter(
        FeatureExperiment.slug.like(f"{pfx}%")
    ).all():
        # Bağlı event'leri de sil
        db.query(FeatureCardEvent).filter(
            FeatureCardEvent.variant_slug.in_([v["slug"] for v in (e.variants or [])])
        ).delete(synchronize_session=False)
        db.delete(e)
        n += 1
    # Tüm test variant_slug'lı event'leri sil (HTTP test'ler için)
    db.query(FeatureCardEvent).filter(
        FeatureCardEvent.variant_slug.like(f"{pfx}%")
    ).delete(synchronize_session=False)
    db.commit()
    return n


def main() -> int:
    print("=== Katman 9 (A/B Test Çerçevesi) smoke ===")

    pfx = f"abtest-{secrets.token_hex(3)}"

    # ---- 1) Wilson sanity ----
    c0, lo0, hi0 = exp_svc.wilson_interval(0, 0)
    check("Wilson n=0 → (0,0,0)", c0 == 0 and lo0 == 0 and hi0 == 0)
    c1, lo1, hi1 = exp_svc.wilson_interval(5, 10)
    check("Wilson 5/10 lo > 0", lo1 > 0)
    check("Wilson 5/10 hi < 1", hi1 < 1)
    check("Wilson 5/10 lo < center < hi",
          lo1 < c1 < hi1, f"{lo1:.3f}<{c1:.3f}<{hi1:.3f}")
    c_large, lo_large, hi_large = exp_svc.wilson_interval(500, 1000)
    check("Wilson 500/1000 CI darald", (hi_large - lo_large) < 0.10,
          f"width={hi_large-lo_large:.3f}")

    # ---- 2) assign_variant deterministik ----
    fake_exp = FeatureExperiment()
    fake_exp.slug = f"{pfx}-fake"
    fake_exp.variants = [
        {"slug": "ctrl", "strategy": "hybrid_full", "weight": 60, "is_control": True},
        {"slug": "test", "strategy": "fuzzy_only", "weight": 40, "is_control": False},
    ]
    v1, s1 = exp_svc.assign_variant(fake_exp, "sid-abc")
    v2, s2 = exp_svc.assign_variant(fake_exp, "sid-abc")
    check("aynı sid → aynı variant", v1 == v2 and s1 == s2)
    v3, _ = exp_svc.assign_variant(fake_exp, "sid-xyz")
    # Farklı sid farklı variant verebilir (deterministik ama dağıtık)
    # Toplu test:
    import random
    random.seed(42)
    counts = {"ctrl": 0, "test": 0}
    for _ in range(2000):
        sid = secrets.token_hex(8)
        v, _ = exp_svc.assign_variant(fake_exp, sid)
        if v in counts:
            counts[v] += 1
    # 60/40 weight → %5 tolerans ile
    ratio_ctrl = counts["ctrl"] / 2000
    check("variant dağılımı ~ %60 control", abs(ratio_ctrl - 0.6) < 0.05,
          f"got {ratio_ctrl:.3f}")

    # ---- 7) Strategy registry ----
    check("REGISTRY has 3 keys",
          set(ls.REGISTRY.keys()) == {"fuzzy_only", "hybrid_bandit", "hybrid_full"})
    check("get_strategy('xx') → fallback",
          ls.get_strategy("xx") is ls.REGISTRY[ls.DEFAULT_STRATEGY])
    check("get_strategy('fuzzy_only') doğru",
          ls.get_strategy("fuzzy_only") is ls.REGISTRY["fuzzy_only"])

    # ---- 4) DB ile entegrasyon: deney oluştur ----
    with SessionLocal() as db:
        cleanup(db, pfx)
        now = datetime.now(timezone.utc)
        e = FeatureExperiment(
            slug=f"{pfx}-exp",
            name="Test deneyi",
            status=ExperimentStatus.DRAFT.value,
            created_at=now,
            updated_at=now,
        )
        e.variants = [
            {"slug": f"{pfx}-c", "label": "Kontrol", "strategy": "hybrid_full",
             "weight": 50, "is_control": True},
            {"slug": f"{pfx}-t", "label": "Test",    "strategy": "fuzzy_only",
             "weight": 50, "is_control": False},
        ]
        db.add(e)
        db.commit()
        db.refresh(e)
        exp_id = e.id

        # DRAFT iken get_active = None
        active = exp_svc.get_active_experiment(db)
        check("DRAFT iken active=None (varsa başka exp olmamalı)",
              active is None or active.id != e.id)

        # RUNNING'e al
        e.status = ExperimentStatus.RUNNING.value
        db.commit()
        active = exp_svc.get_active_experiment(db)
        check("RUNNING → active eşleşiyor", active is not None and active.id == exp_id)

        # ---- 5) Sentetik event'ler + compute_stats ----
        # ctrl: 500 impression, 50 demo_click → CTR %10 (CI ≈ [%7.7, %12.9])
        # test: 500 impression, 10 demo_click → CTR %2  (CI ≈ [%1.0, %3.4])
        # CI'ler çakışmaz → "anlamlı fark" işareti tetiklenir
        ctrl_slug = f"{pfx}-c"
        test_slug = f"{pfx}-t"
        from app.models import FeatureCard
        dp = db.query(FeatureCard).filter(FeatureCard.slug == "daily-plan").first()
        if dp:
            for i in range(500):
                db.add(FeatureCardEvent(
                    card_id=dp.id, card_slug="daily-plan",
                    event_type="impression",
                    session_id=f"{pfx}-c-sess-{i}",
                    created_at=now, variant_slug=ctrl_slug,
                ))
                if i < 50:
                    db.add(FeatureCardEvent(
                        card_id=dp.id, card_slug="daily-plan",
                        event_type="demo_click",
                        session_id=f"{pfx}-c-sess-{i}",
                        created_at=now, variant_slug=ctrl_slug,
                    ))
            for i in range(500):
                db.add(FeatureCardEvent(
                    card_id=dp.id, card_slug="daily-plan",
                    event_type="impression",
                    session_id=f"{pfx}-t-sess-{i}",
                    created_at=now, variant_slug=test_slug,
                ))
                if i < 10:
                    db.add(FeatureCardEvent(
                        card_id=dp.id, card_slug="daily-plan",
                        event_type="demo_click",
                        session_id=f"{pfx}-t-sess-{i}",
                        created_at=now, variant_slug=test_slug,
                    ))
            db.commit()

        stats = exp_svc.compute_stats(db, experiment_id=exp_id)
        check("stats 2 variant döner", len(stats) == 2,
              f"got {list(stats.keys())}")
        check(f"ctrl impression=500", stats[ctrl_slug]["impression"] == 500,
              f"got {stats[ctrl_slug]['impression']}")
        check(f"ctrl CTR ~ %10", approx(stats[ctrl_slug]["ctr"], 0.10, tol=0.02))
        check(f"test CTR ~ %2", approx(stats[test_slug]["ctr"], 0.02, tol=0.02))
        check(f"ctrl is_control=True", stats[ctrl_slug]["is_control"] is True)
        check(f"test lift_pct hesaplandı", stats[test_slug]["lift_pct"] is not None)
        check(f"test lift_pct negatif (test daha kötü)",
              stats[test_slug]["lift_pct"] < 0,
              f"got {stats[test_slug]['lift_pct']:.1f}")
        # 500 impression + 50vs10 → CI'ler net çakışmaz
        check("test vs control 'anlamlı fark' işareti",
              stats[test_slug]["vs_control_significant"] is True,
              f"low={stats[ctrl_slug]['ctr_low']:.3f}-{stats[ctrl_slug]['ctr_high']:.3f}"
              f" vs {stats[test_slug]['ctr_low']:.3f}-{stats[test_slug]['ctr_high']:.3f}")

        # Cleanup
        cleanup(db, pfx)

    # ---- 8) HTTP endpoint variant propagate ----
    client = TestClient(app)
    r = client.post(
        "/api/telemetry/event",
        json={"slug": "daily-plan", "event": "view", "variant": "ctrl-http-test"},
    )
    check("variant'lı POST → 204", r.status_code == 204)
    with SessionLocal() as db:
        ev = db.query(FeatureCardEvent).filter(
            FeatureCardEvent.variant_slug == "ctrl-http-test"
        ).first()
        check("variant_slug DB'ye yazıldı", ev is not None)
        if ev:
            db.delete(ev)
            db.commit()

    # ---- 9) Admin akışı ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (super_admin yok — admin test atlandı)")
        else:
            sa_id = sa.id

            def _ov():
                def factory():
                    db2 = SessionLocal()
                    try:
                        from sqlalchemy.orm import joinedload
                        u = (
                            db2.query(User)
                            .options(joinedload(User.institution))
                            .filter(User.id == sa_id).first()
                        )
                        _ = u.institution
                        db2.expunge_all()
                        return u
                    finally:
                        db2.close()
                return factory

            app.dependency_overrides[require_super_admin] = _ov()
            app.dependency_overrides[require_user] = _ov()
            app.dependency_overrides[get_current_user] = _ov()
            try:
                c = TestClient(app)
                r = c.get("/admin/feature-catalog/experiments")
                check("experiments list 200", r.status_code == 200)
                check("'A/B Deneyleri' başlık", "A/B Deneyleri" in r.text)

                r = c.get("/admin/feature-catalog/experiments/new")
                check("new form 200", r.status_code == 200)
                check("strateji select var", 'name="ctrl_strategy"' in r.text)

                # Create POST
                r = c.post(
                    "/admin/feature-catalog/experiments/new",
                    data={
                        "name": f"HTTP test deney {pfx}",
                        "slug": f"{pfx}-http",
                        "hypothesis": "Test",
                        "ctrl_strategy": "hybrid_full",
                        "test_strategy": "fuzzy_only",
                        "weight_ctrl": "60",
                        "weight_test": "40",
                    },
                    follow_redirects=False,
                )
                check("create POST 303", r.status_code == 303,
                      f"got {r.status_code} loc={r.headers.get('location','')}")
                # Yeni deney detay sayfasına yönlendirir
                with SessionLocal() as db2:
                    new_exp = db2.query(FeatureExperiment).filter(
                        FeatureExperiment.slug == f"{pfx}-http"
                    ).first()
                    check("yeni deney DB'de var", new_exp is not None)
                    if new_exp:
                        check("durum DRAFT", new_exp.status == "draft")
                        check("2 variant", len(new_exp.variants) == 2)

                        # Status değişimi: DRAFT → RUNNING
                        r = c.post(
                            f"/admin/feature-catalog/experiments/{new_exp.id}/status?status=running",
                            follow_redirects=False,
                        )
                        check("status RUNNING POST 303", r.status_code == 303)

                        with SessionLocal() as db3:
                            refreshed = db3.get(FeatureExperiment, new_exp.id)
                            check("status RUNNING'a geçti", refreshed.status == "running")
                            check("start_at dolduruldu", refreshed.start_at is not None)

                        # Geçersiz status query → err
                        r = c.post(
                            f"/admin/feature-catalog/experiments/{new_exp.id}/status?status=invalid",
                            follow_redirects=False,
                        )
                        check("geçersiz status err redirect",
                              r.status_code == 303 and "err=" in r.headers.get("location", ""))

                        # Detail sayfa
                        r = c.get(f"/admin/feature-catalog/experiments/{new_exp.id}")
                        check("detail GET 200", r.status_code == 200)
                        check("detail variant tablosu", "Variant İstatistikleri" in r.text)
                        check("detail status buton (Duraklat)", "Duraklat" in r.text)
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

        # Cleanup
        n = cleanup(db, pfx)
        print(f"  Cleanup: {n} deney silindi")

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
