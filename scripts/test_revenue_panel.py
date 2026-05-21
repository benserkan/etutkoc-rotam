"""Katman 11.G — Ticari Pano smoke test.

Senaryolar:
  1) plan_distribution: aktif kurumlar plan başına sayım + fiyat eklenmiş
  2) mrr: total_try int, paying/free counts tutarlı
  3) trial_ending_soon: trial_ends_at filtrelemesi
  4) plan_change_summary: signup/upgrade/downgrade/net_growth alanları
  5) daily_plan_changes: N gün bucket, descending değil bizim sırada günlük
  6) churn_proxy: dict şema
  7) get_revenue_panel_data: tüm anahtarlar
  8) HTTP GET /admin/security-monitor/revenue 200 + bölümler
  9) Ana panoda 'Ticari' linki
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
from app.deps import get_current_user, get_db, require_super_admin, require_user
from app.main import app
from app.models import (
    Institution,
    PlanChangeHistory,
    PlanChangeReason,
    PlanOwnerType,
    User,
    UserRole,
)
from app.services.revenue_panel import (
    churn_proxy,
    daily_plan_changes,
    get_revenue_panel_data,
    mrr,
    plan_change_summary,
    plan_distribution,
    trial_ending_soon,
    trial_expired_unconverted,
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


def main() -> int:
    print("=== Katman 11.G (Ticari Pano) smoke ===")
    pfx = f"rev-{secrets.token_hex(3)}"

    # ---- 1) plan_distribution ----
    with SessionLocal() as db:
        dist = plan_distribution(db)
        check("plan_distribution dict liste",
              isinstance(dist, list) and all(
                  {"plan", "label", "count", "monthly_price_try", "estimated_mrr"} <= set(d.keys())
                  for d in dist
              ))
        # En az 1 plan olmalı (mevcut seed)
        check("en az 1 plan kaydı", len(dist) >= 1)

    # ---- 2) mrr ----
    with SessionLocal() as db:
        m = mrr(db)
        check("mrr.total_try int",
              isinstance(m["total_try"], int))
        check("mrr.total_institutions = paying + free",
              m["total_institutions"] == m["paying_institutions"] + m["free_institutions"])
        check("mrr.avg_per_paying >= 0",
              m["avg_per_paying"] >= 0)

    # ---- 3) trial_ending_soon — sentetik kurum ----
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        # 4 gün sonra trial bitiyor
        test_inst = Institution(
            name=f"{pfx} test okulu",
            slug=f"{pfx}-okul-{secrets.token_hex(4)}",
            plan="institution_pilot",
            trial_ends_at=now + timedelta(days=4),
            post_trial_plan="etut_standart",
            is_active=True,
        )
        db.add(test_inst)
        db.commit()
        db.refresh(test_inst)
        test_inst_id = test_inst.id

        trials = trial_ending_soon(db, days_horizon=7)
        match = [t for t in trials if t.institution_id == test_inst_id]
        check("trial 4g kala listede", len(match) == 1)
        if match:
            check("days_left 3 veya 4", match[0].days_left in (3, 4))
            check("post_trial_plan doğru",
                  match[0].post_trial_plan == "etut_standart")

        # 14 gün sonra biten trial → 7g pencerede olmamalı
        far_inst = Institution(
            name=f"{pfx} uzak okul",
            slug=f"{pfx}-uzak-{secrets.token_hex(4)}",
            plan="institution_pilot",
            trial_ends_at=now + timedelta(days=14),
            is_active=True,
        )
        db.add(far_inst)
        db.commit()
        far_id = far_inst.id

        trials2 = trial_ending_soon(db, days_horizon=7)
        check("14g sonraki trial 7g penceresinde değil",
              not any(t.institution_id == far_id for t in trials2))

    # ---- 4) plan_change_summary ----
    with SessionLocal() as db:
        # Sentetik plan değişim kayıtları
        now = datetime.now(timezone.utc)
        for reason in [
            PlanChangeReason.SIGNUP, PlanChangeReason.UPGRADE,
            PlanChangeReason.UPGRADE, PlanChangeReason.DOWNGRADE,
        ]:
            db.add(PlanChangeHistory(
                owner_type=PlanOwnerType.INSTITUTION,
                owner_id=test_inst_id,
                from_plan="free", to_plan="etut_standart",
                reason=reason,
                note=f"{pfx}-test",
                occurred_at=now - timedelta(days=1),
            ))
        db.commit()

        cs = plan_change_summary(db, days=30)
        check("summary keys",
              {"days", "by_reason", "net_growth", "signups",
               "upgrades", "downgrades"} <= set(cs.keys()))
        check("signups >= 1", cs["signups"] >= 1)
        check("upgrades >= 2", cs["upgrades"] >= 2)
        check("net_growth = upgrades - downgrades",
              cs["net_growth"] == cs["upgrades"] - cs["downgrades"])

    # ---- 5) daily_plan_changes ----
    with SessionLocal() as db:
        tr = daily_plan_changes(db, days=7)
        check("daily 7 gün bucket", len(tr) == 7)
        check("dict şema",
              all({"day", "total"} <= set(d.keys()) for d in tr))

    # ---- 6) churn_proxy ----
    with SessionLocal() as db:
        cp = churn_proxy(db)
        check("churn_proxy dict",
              {"healthy", "watch", "risk", "critical", "unhealthy_total"}
              <= set(cp.keys()))

    # ---- 7) get_revenue_panel_data ----
    with SessionLocal() as db:
        d = get_revenue_panel_data(db)
        check("aggregator keys",
              {"generated_at", "mrr", "plan_distribution",
               "trial_ending_soon", "trial_expired_30d",
               "change_summary_30d", "daily_changes_30d", "churn_proxy"}
              <= set(d.keys()))

    # ---- 8-9) HTTP ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (super_admin yok — HTTP atlandı)")
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
                r = c.get("/admin/security-monitor/revenue")
                check("revenue pano GET 200",
                      r.status_code == 200, f"got {r.status_code}")
                check("'Ticari Pano' başlığı",
                      "Ticari Pano" in r.text)
                check("'Aylık Gelir (MRR)' kartı",
                      "Aylık Gelir (MRR)" in r.text)
                check("'Plan Dağılımı' bölümü",
                      "Plan Dağılımı" in r.text)
                check("'Trial Bitiş Yaklaşanlar' bölümü",
                      "Trial Bitiş Yaklaşanlar" in r.text)
                check("'Günlük Plan Değişim' bölümü",
                      "Günlük Plan Değişim" in r.text)
                # Test kurumu listede görünmeli
                check("test kurumu trial listesinde",
                      f"{pfx} test okulu" in r.text)

                # Ana panoda link
                r2 = c.get("/admin/security-monitor")
                check("ana panoda 'Ticari' linki",
                      "💰 Ticari" in r2.text or "Ticari" in r2.text)
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

    # Cleanup
    with SessionLocal() as db:
        db.query(PlanChangeHistory).filter(PlanChangeHistory.note.like(f"{pfx}%")).delete()
        db.query(Institution).filter(Institution.name.like(f"{pfx}%")).delete()
        db.commit()

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
