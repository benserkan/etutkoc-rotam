"""API v2 /pricing (public) + pricing hesaplayıcı smoke (M1 — tek kaynak).

Senaryolar:
   1. GET /api/v2/pricing anonim → 200 + yapı (solo bantlar + kurum tier'lar)
   2. compute_solo_monthly bantları: 0/3/5/15/30/40
   3. compute_institution_monthly: 5/30/60 koç
   4. institution_tier_for_coaches: etut/dershane/enterprise eşleşmesi
   5. is_paid_plan_code: solo_free/solo_trial→False, solo_pro/etut→True
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient

from app.main import app
from app.services import pricing

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def main():
    print("\n=== API v2 /pricing smoke (M1) ===\n")
    c = TestClient(app)

    r = c.get("/api/v2/pricing")
    j = r.json() if r.status_code == 200 else {}
    check("1. anonim GET /pricing → 200", r.status_code == 200, f"status={r.status_code}")
    check("1b. solo bant + kurum tier yapısı",
          len(j.get("solo", {}).get("bands", [])) == 3 and len(j.get("institution", {}).get("tiers", [])) == 3
          and j.get("solo", {}).get("free", {}).get("students") == 3,
          f"{j}")
    cards = j.get("cards", [])
    card_keys = {c.get("key") for c in cards}
    solo_card = next((c for c in cards if c.get("key") == "solo"), {})
    check("1d. pazarlama kartları (free/solo/institution) + fayda metni",
          card_keys == {"free", "solo", "institution"}
          and solo_card.get("highlight") is True
          and len(solo_card.get("features", [])) >= 4
          and solo_card.get("plan") == "solo_pro",
          f"keys={card_keys} solo={solo_card.get('plan')}")
    check("1c. AI free=kapalı, ücretli=açık",
          j.get("solo", {}).get("free", {}).get("ai_included") is False
          and j.get("solo", {}).get("ai_included") is True, f"{j.get('solo')}")

    # 2. solo bantlar
    cases = [(0, 0), (3, 2000), (5, 2000), (6, 4000), (15, 4000), (16, 6000), (30, 6000), (40, 6000 + 10 * 200)]
    ok = all(pricing.compute_solo_monthly(n) == exp for n, exp in cases)
    check("2. compute_solo_monthly bantları", ok,
          str([(n, pricing.compute_solo_monthly(n), exp) for n, exp in cases]))

    # 3. kurum koç-başı
    inst = [(5, 5 * 4000), (10, 10 * 4000), (30, 30 * 3000), (60, 60 * 2500)]
    ok = all(pricing.compute_institution_monthly(n) == exp for n, exp in inst)
    check("3. compute_institution_monthly", ok,
          str([(n, pricing.compute_institution_monthly(n), exp) for n, exp in inst]))

    # 4. tier eşleşmesi
    check("4. tier eşleşmesi",
          pricing.institution_tier_for_coaches(5)["code"] == "etut_standart"
          and pricing.institution_tier_for_coaches(30)["code"] == "dershane_pro"
          and pricing.institution_tier_for_coaches(60)["code"] == "enterprise",
          "tier eşleşmedi")

    # 5. entitlement kodları
    check("5. is_paid_plan_code",
          pricing.is_paid_plan_code("solo_free") is False
          and pricing.is_paid_plan_code("solo_trial") is False
          and pricing.is_paid_plan_code("solo_pro") is True
          and pricing.is_paid_plan_code("etut_standart") is True,
          "kod eşleşmedi")

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
