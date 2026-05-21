"""Sprint E.2 — Tahmin & Senaryo (Faz H) smoke test.

Test ettiği:
  - risk_at_mrr: dict shape (total/critical/risk/count + institutions liste)
  - mrr_projection: current_mrr + horizon + status_quo + intervention + delta
  - mrr_projection: save_rate=0 → delta=0 (intervention=status_quo)
  - mrr_projection: save_rate=1 → delta=expected_at_risk_loss
  - mrr_projection: horizon_days farklı ise projeksiyon farklı
  - scenario_comparison: 3 horizon (30/60/90) + save_rate
  - HTTP GET /admin/revenue/forecast: 200 + render
  - HTTP filter save_rate parametresi
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
    User,
    UserRole,
)
from app.services.revenue_forecast import (
    mrr_projection,
    risk_at_mrr,
    scenario_comparison,
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
    print("=== Sprint E.2 — Tahmin & Senaryo smoke ===")
    tag = f"sprinte2-{secrets.token_hex(3)}"

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if not sa:
            print("  (SA yok — atlandı)")
            return 0
        sa_id = sa.id

    # ---- 1) risk_at_mrr: dict shape ----
    with SessionLocal() as db:
        r = risk_at_mrr(db)
        check("risk_at_mrr: dict shape",
              "total_at_risk_mrr" in r and "critical_mrr" in r
              and "risk_mrr" in r and "institutions" in r)
        check("risk_at_mrr: total = critical + risk",
              r["total_at_risk_mrr"] == r["critical_mrr"] + r["risk_mrr"])
        check("risk_at_mrr: institutions liste",
              isinstance(r["institutions"], list))
        # Eğer institution varsa, AtRiskInstitution dataclass
        for inst in r["institutions"][:1]:
            check("risk_at_mrr: institution attribs",
                  hasattr(inst, "institution_id")
                  and hasattr(inst, "monthly_price_try")
                  and inst.severity in ("critical", "risk"))

    # ---- 2) mrr_projection: status_quo dict shape ----
    with SessionLocal() as db:
        p = mrr_projection(db, horizon_days=30, intervention_save_rate=0.0)
        check("mrr_projection: dict shape",
              all(k in p for k in [
                  "current_mrr", "horizon_days", "trial_conversion_rate",
                  "monthly_churn_rate", "projected_mrr_status_quo",
                  "projected_mrr_with_intervention", "delta_mrr",
              ]))
        check("mrr_projection: horizon=30 yansıdı", p["horizon_days"] == 30)
        check("mrr_projection: save_rate=0 → delta=0",
              p["delta_mrr"] == 0,
              f"got delta={p['delta_mrr']}")
        check("mrr_projection: status_quo == intervention (save_rate=0)",
              p["projected_mrr_status_quo"] == p["projected_mrr_with_intervention"])
        check("mrr_projection: current_mrr >= 0",
              p["current_mrr"] >= 0)
        check("mrr_projection: conversion rate 0-1",
              0.0 <= p["trial_conversion_rate"] <= 1.0)
        check("mrr_projection: churn rate >= 0",
              p["monthly_churn_rate"] >= 0)

    # ---- 3) mrr_projection: save_rate=1.0 → intervention = status_quo + at_risk_loss ----
    with SessionLocal() as db:
        p_full = mrr_projection(db, horizon_days=90, intervention_save_rate=1.0)
        check("mrr_projection: save_rate=1.0 → delta == at_risk_loss",
              p_full["delta_mrr"] == p_full["expected_at_risk_loss_mrr"],
              f"delta={p_full['delta_mrr']} vs loss={p_full['expected_at_risk_loss_mrr']}")
        check("mrr_projection: intervention >= status_quo",
              p_full["projected_mrr_with_intervention"]
              >= p_full["projected_mrr_status_quo"])

    # ---- 4) mrr_projection: 30 vs 90 gün farklı ----
    with SessionLocal() as db:
        p30 = mrr_projection(db, horizon_days=30, intervention_save_rate=0.5)
        p90 = mrr_projection(db, horizon_days=90, intervention_save_rate=0.5)
        check("mrr_projection: 30g vs 90g churn farklı",
              p30["expected_churn_mrr"] != p90["expected_churn_mrr"]
              or p30["monthly_churn_rate"] == 0
              or p30["current_mrr"] == 0,
              f"30={p30['expected_churn_mrr']}, 90={p90['expected_churn_mrr']}, churn_rate={p30['monthly_churn_rate']}")
        # 90g churn 30g'den 3x büyük olmalı (yaklaşık)
        if p30["current_mrr"] > 0 and p30["monthly_churn_rate"] > 0:
            ratio = p90["expected_churn_mrr"] / max(1, p30["expected_churn_mrr"])
            check("mrr_projection: 90g churn ~= 3 × 30g",
                  2.5 <= ratio <= 3.5,
                  f"got ratio={ratio:.2f}")

    # ---- 5) scenario_comparison: 3 horizon ----
    with SessionLocal() as db:
        s = scenario_comparison(db, save_rate=0.5)
        check("scenario_comparison: dict shape",
              "current_mrr" in s and "save_rate" in s and "horizons" in s)
        check("scenario_comparison: 3 horizon",
              len(s["horizons"]) == 3
              and [h["horizon_days"] for h in s["horizons"]] == [30, 60, 90])
        # Her horizon'da intervention >= status_quo (save_rate=0.5 ile)
        for h in s["horizons"]:
            check(f"scenario_comparison: {h['horizon_days']}g intervention >= status_quo",
                  h["intervention_mrr"] >= h["status_quo_mrr"])

    # ---- 6) scenario: save_rate clamping ----
    with SessionLocal() as db:
        s_high = scenario_comparison(db, save_rate=2.0)  # > 1.0
        check("scenario: save_rate clamp 1.0",
              s_high["save_rate"] == 1.0)
        s_neg = scenario_comparison(db, save_rate=-0.5)
        check("scenario: save_rate clamp 0.0",
              s_neg["save_rate"] == 0.0)

    # ---- 7) HTTP route ----
    with SessionLocal() as db:
        admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()

    def _admin():
        return admin

    app.dependency_overrides[require_super_admin] = _admin
    app.dependency_overrides[require_user] = _admin
    app.dependency_overrides[get_current_user] = _admin

    try:
        client = TestClient(app)
        res = client.get("/admin/revenue/forecast", follow_redirects=False)
        check("HTTP GET /admin/revenue/forecast: 200",
              res.status_code == 200, f"status={res.status_code}")
        if res.status_code == 200:
            body = res.text
            check("HTTP render: 'Tahmin & Senaryo' başlığı",
                  "Tahmin" in body and "Senaryo" in body)
            check("HTTP render: 'Risk Altında MRR' KPI",
                  "Risk Altında" in body)
            check("HTTP render: 30/60/90 projeksiyon",
                  "30 gün" in body and "60 gün" in body and "90 gün" in body)
            check("HTTP render: 'Status Quo' + 'Müdahale' kolonları",
                  "Status Quo" in body and "Müdahale" in body)
            check("HTTP render: senaryo karşılaştırma kartları",
                  "Hiçbir Şey Yapma" in body or "Hiçbir Şey" in body)

        # Save rate ile filtre
        res = client.get(
            "/admin/revenue/forecast?save_rate=0.75",
            follow_redirects=False,
        )
        check("HTTP GET ?save_rate=0.75: 200",
              res.status_code == 200)
        if res.status_code == 200:
            check("HTTP filtre: save_rate=0.75 yansıdı",
                  "%75" in res.text)

        # Ticari Pano'da 'Tahmin' linki var mı
        res = client.get("/admin/security-monitor/revenue", follow_redirects=False)
        if res.status_code == 200:
            check("Ticari Pano'da 'Tahmin' linki var",
                  "/admin/revenue/forecast" in res.text)
    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

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
