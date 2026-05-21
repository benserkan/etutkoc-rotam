"""Sprint D.2 — Kohort & LTV Analizi (Faz G) smoke test.

Test ettiği:
  - signup_cohort_matrix: dict shape, cohorts liste, retention sırası
  - cohort retention: tarih ileride olan aylar future=True
  - cohort retention: tarihi geçmiş aylar count + pct mevcut
  - plan_churn_summary: dict shape + sayısal alanlar tutarlı
  - ltv_estimate: plan başına PlanLtv + total_ltv_try + ödeyen sayısı
  - HTTP GET /admin/revenue/cohort → 200 + matrix render
  - HTTP GET filtre parametreleri (months_back, horizon, churn_days)
"""

from __future__ import annotations

import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import (
    Institution,
    PlanChangeHistory,
    PlanChangeReason,
    User,
    UserRole,
)
from app.models.plan_history import PlanOwnerType
from app.services.revenue_cohort import (
    ltv_estimate,
    plan_churn_summary,
    signup_cohort_matrix,
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
    print("=== Sprint D.2 — Kohort & LTV Analizi smoke ===")
    tag = f"sprintd2-{secrets.token_hex(3)}"

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if not sa:
            print("  (SA yok — atlandı)")
            return 0
        sa_id = sa.id

    # ---- 1) signup_cohort_matrix: dict shape ----
    with SessionLocal() as db:
        m = signup_cohort_matrix(db, months_back=12, horizon_months=12)
        check("signup_cohort_matrix: dict shape",
              "cohorts" in m and "horizon_months" in m and "total_signups" in m)
        check("matrix: horizon_months=12", m["horizon_months"] == 12)
        check("matrix: months_back=12", m["months_back"] == 12)
        check("matrix: cohorts liste", isinstance(m["cohorts"], list))
        # Eğer cohort varsa, ilk olanın retention 12 hücreli olmalı
        if m["cohorts"]:
            c0 = m["cohorts"][0]
            check("cohort: retention 12 hücre",
                  len(c0["retention"]) == 12,
                  f"got {len(c0['retention'])}")
            check("cohort: signup_count > 0",
                  c0["signup_count"] > 0)
            check("cohort: cohort_label string",
                  isinstance(c0["cohort_label"], str)
                  and len(c0["cohort_label"]) > 0)
            check("cohort: cohort_key YYYY-MM",
                  len(c0["cohort_key"]) == 7 and c0["cohort_key"][4] == "-")

    # ---- 2) Cohort future flag: ileri aylar future=True ----
    with SessionLocal() as db:
        # En son ay'ın retention'ında future=True olan hücreler beklenir
        m = signup_cohort_matrix(db, months_back=3, horizon_months=12)
        if m["cohorts"]:
            last_cohort = m["cohorts"][-1]
            future_cells = [r for r in last_cohort["retention"] if r.get("future")]
            past_cells = [r for r in last_cohort["retention"] if not r.get("future")]
            check("son cohort: bazı aylar future",
                  len(future_cells) > 0 or last_cohort["signup_month_age"] >= 12,
                  f"signup_age={last_cohort['signup_month_age']}, future={len(future_cells)}")
            # past_cells dolu olan retention'lar count + pct'e sahip
            for cell in past_cells:
                if cell["count"] is None:
                    check(f"past cell month={cell['month']} count None değil",
                          False, str(cell))
                    break
            else:
                check("past cells: hepsinin count + pct değeri var", True)

    # ---- 3) Test kurumu oluştur — 6 ay önce + ücretli plan ----
    test_inst_ids: list[int] = []
    with SessionLocal() as db:
        from app.models import Institution
        for i in range(3):
            inst = Institution(
                name=f"{tag} cohort test #{i}",
                slug=f"{tag.lower()}-coh-{i}",
                contact_email=f"{tag}_{i}@test.local",
                plan="solo_pro",  # Ücretli plan
                is_active=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=180),
            )
            db.add(inst)
            db.flush()
            test_inst_ids.append(inst.id)
        db.commit()

    # ---- 4) Matrix'i tekrar çek — test kurumları 6 ay öncesi cohort'unda olmalı ----
    with SessionLocal() as db:
        m = signup_cohort_matrix(db, months_back=12, horizon_months=12)
        total_signups = m["total_signups"]
        check("matrix: test kurumları toplam signup'a dahil",
              total_signups >= 3,
              f"got total_signups={total_signups}")

    # ---- 5) plan_churn_summary: dict shape ----
    with SessionLocal() as db:
        ch = plan_churn_summary(db, days=90)
        check("plan_churn_summary: dict shape",
              "signup_count" in ch and "trial_expired_count" in ch
              and "upgrade_count" in ch and "downgrade_count" in ch)
        check("churn: window_days=90", ch["window_days"] == 90)
        check("churn: sayısal alanlar int",
              isinstance(ch["signup_count"], int)
              and isinstance(ch["upgrade_count"], int))
        check("churn: net_movement = upgrade - downgrade",
              ch["net_movement"] == ch["upgrade_count"] - ch["downgrade_count"])

    # ---- 6) Test PCH ekle: 1 UPGRADE + 1 DOWNGRADE + 1 TRIAL_EXPIRED ----
    pch_ids: list[int] = []
    if test_inst_ids:
        with SessionLocal() as db:
            now = datetime.now(timezone.utc)
            pchs = [
                PlanChangeHistory(
                    owner_type=PlanOwnerType.INSTITUTION,
                    owner_id=test_inst_ids[0],
                    from_plan="free", to_plan="solo_pro",
                    reason=PlanChangeReason.UPGRADE,
                    actor_user_id=sa_id,
                    note=f"{tag} upgrade",
                    occurred_at=now - timedelta(days=10),
                ),
                PlanChangeHistory(
                    owner_type=PlanOwnerType.INSTITUTION,
                    owner_id=test_inst_ids[1],
                    from_plan="solo_pro", to_plan="free",
                    reason=PlanChangeReason.DOWNGRADE,
                    actor_user_id=sa_id,
                    note=f"{tag} downgrade",
                    occurred_at=now - timedelta(days=10),
                ),
                PlanChangeHistory(
                    owner_type=PlanOwnerType.INSTITUTION,
                    owner_id=test_inst_ids[2],
                    from_plan="solo_pro", to_plan="solo_pro",
                    reason=PlanChangeReason.TRIAL_EXPIRED,
                    actor_user_id=None,
                    note=f"{tag} trialexp",
                    occurred_at=now - timedelta(days=5),
                ),
            ]
            for p in pchs:
                db.add(p)
            db.commit()
            pch_ids = [p.id for p in pchs]

    # ---- 7) churn summary: test PCH'ler dahil edildi ----
    with SessionLocal() as db:
        ch2 = plan_churn_summary(db, days=90)
        check("churn: yeni UPGRADE sayıldı",
              ch2["upgrade_count"] >= 1,
              f"got upgrade={ch2['upgrade_count']}")
        check("churn: yeni DOWNGRADE sayıldı",
              ch2["downgrade_count"] >= 1)
        check("churn: yeni TRIAL_EXPIRED sayıldı",
              ch2["trial_expired_count"] >= 1)
        # TRIAL_EXPIRED to_plan=solo_pro (paid) → converted
        check("churn: trial_converted_count >= 1",
              ch2["trial_converted_count"] >= 1)
        if ch2["trial_expired_count"] > 0:
            check("churn: trial_conversion_pct hesaplandı",
                  ch2["trial_conversion_pct"] is not None
                  and 0 <= ch2["trial_conversion_pct"] <= 100,
                  f"got {ch2['trial_conversion_pct']}")
        # downgrade_to_free (ücretsize indi) → cancel_count >= 1
        check("churn: cancel_count >= 1 (downgrade-to-free)",
              ch2["cancel_count"] >= 1)

    # ---- 8) ltv_estimate: dict shape ----
    with SessionLocal() as db:
        ltv = ltv_estimate(db)
        check("ltv_estimate: dict shape",
              "plans" in ltv and "total_ltv_try" in ltv
              and "paying_count" in ltv and "avg_ltv_per_paying" in ltv)
        check("ltv: plans liste", isinstance(ltv["plans"], list))
        check("ltv: total_ltv_try int", isinstance(ltv["total_ltv_try"], int))
        # Test kurumlarımız solo_pro'da → ödeyen sayısı en az 2 (1 tanesi downgrade ile free oldu)
        check("ltv: paying_count >= 1",
              ltv["paying_count"] >= 1,
              f"got paying={ltv['paying_count']}")
        # Her plan satırı PlanLtv dataclass
        if ltv["plans"]:
            p0 = ltv["plans"][0]
            check("ltv: plan PlanLtv attribs",
                  hasattr(p0, "plan") and hasattr(p0, "monthly_price_try")
                  and hasattr(p0, "estimated_ltv_try"))
            # Plan ücretli ise LTV > 0
            paid_plans = [p for p in ltv["plans"] if p.monthly_price_try > 0]
            if paid_plans:
                check("ltv: ücretli plan için LTV > 0",
                      paid_plans[0].estimated_ltv_try > 0,
                      f"got LTV={paid_plans[0].estimated_ltv_try}")

    # ---- 9) HTTP: route 200 + render ----
    with SessionLocal() as db:
        admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()

    def _admin():
        return admin

    app.dependency_overrides[require_super_admin] = _admin
    app.dependency_overrides[require_user] = _admin
    app.dependency_overrides[get_current_user] = _admin

    try:
        client = TestClient(app)
        res = client.get("/admin/revenue/cohort", follow_redirects=False)
        check("HTTP GET /admin/revenue/cohort: 200",
              res.status_code == 200, f"status={res.status_code}")
        if res.status_code == 200:
            body = res.text
            check("HTTP render: Kohort başlığı",
                  "Kohort" in body and "LTV" in body)
            check("HTTP render: matrix tablosu",
                  "Tutunma" in body or "M1" in body)
            check("HTTP render: churn KPI'ları",
                  "Yeni Kayıt" in body and "Yükseltme" in body)
            check("HTTP render: LTV bölümü",
                  "Müşteri Yaşam" in body or "LTV" in body)

        # Filtre parametreleri ile çağır
        res = client.get(
            "/admin/revenue/cohort?months_back=6&horizon=9&churn_days=60",
            follow_redirects=False,
        )
        check("HTTP GET with filters: 200",
              res.status_code == 200)
        if res.status_code == 200:
            check("HTTP filtre: months_back uygulandı",
                  '<option value="6" selected' in res.text)
            check("HTTP filtre: horizon uygulandı",
                  '<option value="9" selected' in res.text)
            check("HTTP filtre: churn_days uygulandı",
                  '<option value="60" selected' in res.text)

        # Bağlantı: revenue panel'den cohort'a link var mı
        res = client.get("/admin/security-monitor/revenue", follow_redirects=False)
        check("HTTP revenue panel: 200",
              res.status_code == 200)
        if res.status_code == 200:
            check("Revenue panel'de Kohort linki var",
                  '/admin/revenue/cohort' in res.text)
    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    # ---- Cleanup ----
    with SessionLocal() as db:
        if pch_ids:
            db.query(PlanChangeHistory).filter(
                PlanChangeHistory.id.in_(pch_ids),
            ).delete(synchronize_session=False)
        if test_inst_ids:
            db.query(Institution).filter(
                Institution.id.in_(test_inst_ids),
            ).delete(synchronize_session=False)
        db.commit()

    print()
    print(f"=== Toplam: {passed} PASS / {len(failed)} FAIL ===")
    if failed:
        print("\nFAIL'ler:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
