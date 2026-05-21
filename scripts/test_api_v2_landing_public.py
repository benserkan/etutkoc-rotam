"""API v2 public landing (anasayfa vitrin) smoke.

Senaryolar:
   1. GET /landing → 200 + kart listesi + session cookie set
   2. seed kart alanları doğru (title/mockup_type/benefits/accent)
   3. variant_slug alanı mevcut (deney yoksa None)
   4. limit param kabul
   5. POST /telemetry → 204 + FeatureCardEvent kaydı oluşur
   6. POST /telemetry boş slug → 422
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models.feature_card import FeatureCard
from app.models.feature_card_event import FeatureCardEvent

PFX = f"v2lp{secrets.token_hex(3)}"
SLUG = f"{PFX}-deneme-karti"

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


def _seed():
    with SessionLocal() as db:
        card = FeatureCard(
            slug=SLUG,
            title=f"{PFX} Günlük Program",
            tagline="Saniyeler içinde kişiselleştirilmiş program.",
            category_icon="📅",
            category_label="Günlük Rota",
            accent_color="#0EA5E9",
            status="published",
            mockup_type="daily_schedule",
            manual_pin=True,  # strateji sıralamasını baypas → deterministik
            manual_hide=False,
            demo_slug="daily-plan",
            demo_duration_label="2 dk",
        )
        card.benefits = ["Hızlı", "AI öneri", "Esnek"]
        db.add(card)
        db.commit()
        return card.id


def _cleanup(card_id):
    with SessionLocal() as db:
        db.execute(sa_delete(FeatureCardEvent).where(FeatureCardEvent.card_slug == SLUG))
        db.execute(sa_delete(FeatureCard).where(FeatureCard.id == card_id))
        db.commit()


def main():
    print(f"\n=== API v2 public landing smoke — prefix: {PFX} ===\n")
    card_id = _seed()
    try:
        c = TestClient(app)

        r = c.get("/api/v2/landing")
        j = r.json() if r.text else {}
        ok = r.status_code == 200 and "cards" in j and "variant_slug" in j
        check("1. GET /landing 200 + şekil", ok, f"status={r.status_code} {r.text[:120]}")
        # session cookie set edildi mi
        check("1b. session cookie set", any("fc_sid" in k or "session" in k.lower()
              for k in r.headers.get("set-cookie", "").split(";")) or "set-cookie" in r.headers,
              f"{r.headers.get('set-cookie')}")

        card = next((x for x in j.get("cards", []) if x["slug"] == SLUG), None)
        check("2. seed kart listede + alanlar",
              card is not None and card["title"] == f"{PFX} Günlük Program"
              and card["mockup_type"] == "daily_schedule"
              and card["accent_color"] == "#0EA5E9"
              and card["benefits"] == ["Hızlı", "AI öneri", "Esnek"]
              and card["demo_slug"] == "daily-plan", f"{card}")
        check("3. variant_slug alanı var (deney yoksa None)",
              "variant_slug" in j, f"{j.get('variant_slug')}")

        r = c.get("/api/v2/landing?limit=3")
        check("4. limit param kabul", r.status_code == 200, f"status={r.status_code}")

        # 5. telemetri — aynı client (session cookie taşınır)
        r = c.post("/api/v2/landing/telemetry",
                   json={"slug": SLUG, "event": "impression"})
        check("5. POST /telemetry → 204", r.status_code == 204, f"status={r.status_code}")
        with SessionLocal() as db:
            cnt = db.query(FeatureCardEvent).filter(
                FeatureCardEvent.card_slug == SLUG,
                FeatureCardEvent.event_type == "impression").count()
        check("5b. FeatureCardEvent kaydı oluştu", cnt >= 1, f"count={cnt}")

        # 6. geçersiz body
        r = c.post("/api/v2/landing/telemetry", json={"slug": "", "event": "x"})
        check("6. boş slug → 422", r.status_code == 422, f"status={r.status_code}")

    finally:
        _cleanup(card_id)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
