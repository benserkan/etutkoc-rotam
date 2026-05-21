"""Katman 5 — Fuzzy skorlama smoke test.

Senaryolar:
  1) Fuzzy core: triangle/trapezoid sınır değerleri (a, b, c, d, between)
  2) Trivial Mamdani — basit kural seti beklenen skor üretir
  3) feature_scoring._days_since, _completeness, _role_match yardımcıları
  4) score_card "perfect" kart için yüksek skor (>=70)
  5) score_card "weak" kart için düşük skor (<40)
  6) Eski + düşük öncelik + zayıf düzey → "gizle" sınıfı (yaklaşık <25)
  7) get_for_landing sıralaması Mamdani'yi kullanır:
     - daily-plan tepede (en yüksek skor)
     - manual_pin sert kuralı skoru ezer
  8) Admin liste sayfasında skor rozeti render edilir
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
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import FeatureCard, FeatureStatus, FeatureTier, User, UserRole
from app.services import feature_catalog as fc
from app.services.feature_scoring import (
    score_card,
    _completeness,
    _days_since,
    _role_match,
)
from app.services.fuzzy_core import (
    FuzzyRule,
    FuzzyVariable,
    MamdaniInference,
    triangle,
    trapezoid,
)


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


def approx(actual: float, expected: float, tol: float = 0.01) -> bool:
    return abs(actual - expected) <= tol


def main() -> int:
    print("=== Katman 5 (Fuzzy Skorlama) smoke ===")

    # ---- 1) Üyelik fonksiyonu sınırları ----
    t = triangle(0, 5, 10)
    check("triangle peak at b", approx(t(5), 1.0))
    check("triangle 0 at a-1", approx(t(-1), 0.0))
    check("triangle 0 at c+1", approx(t(11), 0.0))
    check("triangle linear left", approx(t(2.5), 0.5))
    check("triangle linear right", approx(t(7.5), 0.5))
    # Degenerate left edge (a==b)
    tl = triangle(0, 0, 10)
    check("triangle a==b: x=0 → 1.0", approx(tl(0), 1.0))
    check("triangle a==b: x=5 → 0.5", approx(tl(5), 0.5))

    # Trapezoid
    tr = trapezoid(0, 2, 8, 10)
    check("trapezoid plateau", approx(tr(5), 1.0))
    check("trapezoid ramp up", approx(tr(1), 0.5))
    check("trapezoid ramp down", approx(tr(9), 0.5))
    check("trapezoid below a", approx(tr(-1), 0.0))
    check("trapezoid above d", approx(tr(11), 0.0))
    # Degenerate a==b case (left edge flat-top)
    trd = trapezoid(0, 0, 14, 45)
    check("trapezoid a==b: x=0 → 1.0", approx(trd(0), 1.0))
    check("trapezoid a==b: x=14 → 1.0", approx(trd(14), 1.0))
    check("trapezoid a==b: x=30 → ~0.48", approx(trd(30), (45-30)/(45-14), tol=0.01))
    check("trapezoid a==b: x=45 → 0.0", approx(trd(45), 0.0))

    # ---- 2) Trivial Mamdani inference ----
    fx = FuzzyVariable("x", (0, 10))
    fx.add_set("low", trapezoid(0, 0, 3, 5))
    fx.add_set("high", trapezoid(5, 7, 10, 10))
    fy = FuzzyVariable("y", (0, 100))
    fy.add_set("small", trapezoid(0, 0, 20, 40))
    fy.add_set("big", trapezoid(60, 80, 100, 100))
    eng = MamdaniInference(
        input_vars={"x": fx}, output_var=fy,
        rules=[
            FuzzyRule([("x", "low")], ("y", "small")),
            FuzzyRule([("x", "high")], ("y", "big")),
        ],
        resolution=200,
    )
    r_low = eng.infer({"x": 1.0})
    r_high = eng.infer({"x": 9.0})
    check("low input → small output (<40)", r_low.crisp < 40,
          f"got {r_low.crisp:.1f}")
    check("high input → big output (>60)", r_high.crisp > 60,
          f"got {r_high.crisp:.1f}")

    # ---- 3) Yardımcılar ----
    now = datetime(2026, 5, 15, tzinfo=timezone.utc)
    past = datetime(2026, 5, 14, tzinfo=timezone.utc)
    check("_days_since 1 gün", approx(_days_since(past, now), 1.0))
    very_old = datetime(2024, 1, 1, tzinfo=timezone.utc)
    check("_days_since uzun süre > 800",
          _days_since(very_old, now) > 800)

    # ---- 4-6) Sentetik kart skorları ----
    pfx = f"score-test-{secrets.token_hex(3)}"
    with SessionLocal() as db:
        # Temizle önceki test kalıntısı
        for r in db.query(FeatureCard).filter(FeatureCard.slug.like(f"{pfx}%")).all():
            db.delete(r)
        db.commit()

        # PERFECT: yeni + öncelik 5 + core + tüm zenginleştirme + role-match
        perfect = fc.create(
            db, actor_id=None,
            slug=f"{pfx}-perfect",
            title="perfect card",
            category_icon="🆕", category_label="Test",
            tagline="x", description_md="",
            domain="genel", tier=FeatureTier.CORE.value,
            status=FeatureStatus.PUBLISHED.value,
            target_roles=[UserRole.STUDENT, UserRole.TEACHER],
            introduced_at=now,
            strategic_priority=5,
            mockup_type="daily_schedule",
            benefits=["b1", "b2"],
            demo_slug="daily-plan",
        )
        # WEAK: eski + düşük öncelik + zayıf + eksik
        weak = fc.create(
            db, actor_id=None,
            slug=f"{pfx}-weak",
            title="weak card",
            category_icon="🆕", category_label="Test",
            tagline="x", description_md="",
            domain="genel", tier=FeatureTier.EXPERIMENTAL.value,
            status=FeatureStatus.PUBLISHED.value,
            target_roles=[],
            introduced_at=now - timedelta(days=500),
            strategic_priority=1,
        )
        # MID: yakın + orta öncelik + enhancement + yarı zengin
        mid = fc.create(
            db, actor_id=None,
            slug=f"{pfx}-mid",
            title="mid card",
            category_icon="🆕", category_label="Test",
            tagline="x", description_md="",
            domain="genel", tier=FeatureTier.ENHANCEMENT.value,
            status=FeatureStatus.PUBLISHED.value,
            target_roles=[UserRole.STUDENT],
            introduced_at=now - timedelta(days=45),
            strategic_priority=3,
            mockup_type="daily_schedule",
        )
        db.commit()

        sp = score_card(perfect, role="student", now=now)
        sw = score_card(weak,    role="student", now=now)
        sm = score_card(mid,     role="student", now=now)

        check("perfect skor >= 70", sp.prominence >= 70,
              f"got {sp.prominence:.1f}")
        check("weak skor < 40", sw.prominence < 40,
              f"got {sw.prominence:.1f}")
        check("mid skor 35-65 arası",
              35 <= sm.prominence <= 65,
              f"got {sm.prominence:.1f}")
        check("perfect > mid > weak",
              sp.prominence > sm.prominence > sw.prominence,
              f"{sp.prominence:.1f} > {sm.prominence:.1f} > {sw.prominence:.1f}")
        check("perfect en az 3 kural ateşledi",
              sum(1 for _, s in sp.fired_rules if s > 0) >= 3)

        # _completeness
        check("_completeness perfect = 1.0",
              approx(_completeness(perfect), 1.0))
        check("_completeness weak = 0.0",
              approx(_completeness(weak), 0.0))
        check("_completeness mid = 1/3",
              approx(_completeness(mid), 1/3.0, tol=0.001))

        # _role_match
        check("_role_match student in target → 1.0",
              approx(_role_match(perfect, "student"), 1.0))
        check("_role_match parent NOT in target → 0.0",
              approx(_role_match(perfect, "parent"), 0.0))
        check("_role_match empty target → 0.5 (nötr)",
              approx(_role_match(weak, "student"), 0.5))
        check("_role_match anonim + STUDENT in target → 1.0",
              approx(_role_match(perfect, None), 1.0))

        # ---- 7) get_for_landing sıralaması fuzzy kullanır ----
        landing = fc.get_for_landing(db, limit=10)
        # Mevcut 5 anasayfa kartı + perfect + mid (publish + mockup_type) = 7
        # weak: mockup_type yok, landing'e girmez
        slugs = [c.slug for c in landing]
        check(f"{pfx}-perfect landing'de", f"{pfx}-perfect" in slugs)
        check(f"{pfx}-mid landing'de", f"{pfx}-mid" in slugs)
        check(f"{pfx}-weak landing'de YOK (mockup_type yok)",
              f"{pfx}-weak" not in slugs)
        # perfect skor mid'den yüksek olduğu için landing'de mid'den önce
        idx_perfect = slugs.index(f"{pfx}-perfect")
        idx_mid = slugs.index(f"{pfx}-mid")
        check("perfect mid'den önce sıralı",
              idx_perfect < idx_mid)

        # daily-plan hala üst sıralarda (skoru en yüksek seed kart)
        if "daily-plan" in slugs:
            idx_daily = slugs.index("daily-plan")
            check("daily-plan landing'de", True)
            check("daily-plan perfect'ten ÖNCE (eski seed eşitlik kırıcı yok)",
                  idx_daily < idx_perfect or
                  abs(score_card(landing[idx_daily], role=None).prominence -
                      sp.prominence) < 5)

        # Manual_pin sert kuralı: weak kartı pinle → tepede
        weak.manual_pin = True
        weak.mockup_type = "daily_schedule"  # landing'e girebilmek için mockup şart
        db.commit()
        pinned_landing = fc.get_for_landing(db, limit=10)
        check("manual_pin sert kural: weak kartı tepede",
              pinned_landing[0].slug == f"{pfx}-weak",
              f"got {pinned_landing[0].slug}")
        weak.manual_pin = False
        weak.mockup_type = None
        db.commit()

        # Cleanup
        for r in db.query(FeatureCard).filter(FeatureCard.slug.like(f"{pfx}%")).all():
            db.delete(r)
        db.commit()

    # ---- 8) Admin liste sayfasında skor rozeti ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (super_admin yok — admin sayfa testi atlandı)")
        else:
            sa_id = sa.id

            def _ov():
                def factory():
                    db2 = SessionLocal()
                    try:
                        from sqlalchemy.orm import joinedload
                        u = db2.query(User).options(
                            joinedload(User.institution)
                        ).filter(User.id == sa_id).first()
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
                r = c.get("/admin/feature-catalog")
                check("admin liste 200", r.status_code == 200)
                check("Vitrin Skoru sütun başlığı", "Vitrin Skoru" in r.text)
                # Yeni rozet stili: bg-{tone}-50 + text-{tone}-700, içerik bir <div>
                import re
                count = len(re.findall(
                    r'bg-(emerald|amber|rose)-50 text-\1-700[^>]*?>\s*\d+\s*</div>',
                    r.text,
                ))
                check("≥3 skor rozeti render", count >= 3,
                      f"got {count}")
                check("breakdown tooltip 'Hesaplama girdileri' içerir",
                      "Hesaplama girdileri:" in r.text)
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
