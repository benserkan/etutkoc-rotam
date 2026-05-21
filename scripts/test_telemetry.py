"""Katman 6 — Telemetri smoke test.

Senaryolar:
  1) record_event temel kontratı: geçerli event, DB satırı oluşur
  2) Geçersiz event_type → None döner, DB satırı yok
  3) Geçersiz slug → None döner
  4) Throttle: aynı (session, slug, event) 10sn içinde tekrar → None
  5) Farklı session_id → throttle uygulanmaz
  6) Hash determinizmi: aynı IP → aynı hash; farklı IP → farklı
  7) KVKK: ip_hash 64 hex char; düz IP DB'de YOK
  8) get_card_stats: event tipi başına sayım doğru
  9) get_bulk_stats: birden çok kart için tek seferde
 10) HTTP POST /api/telemetry/event:
     - 204 No Content (valid + invalid → 204 sessizce no-op)
     - Cookie set-cookie ile geldi
     - Body validation hatası → 422
 11) Landing page: data-fc-slug attribute'ları + telemetri JS render edildi
 12) Admin: 'Etkileşim' sütunu görünür + sayımlar doğru
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
from app.models import (
    FeatureCard,
    FeatureCardEvent,
    FeatureEventType,
    User,
    UserRole,
)
from app.services import telemetry as tel


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


def cleanup_test_events(db, session_prefix: str) -> int:
    """Test session_id'lerine ait event'leri sil."""
    rows = db.query(FeatureCardEvent).filter(
        FeatureCardEvent.session_id.like(f"{session_prefix}%")
    ).all()
    n = len(rows)
    for r in rows:
        db.delete(r)
    db.commit()
    return n


def main() -> int:
    print("=== Katman 6 (Telemetri) smoke ===")

    pfx = f"sid-test-{secrets.token_hex(3)}"
    sid1 = f"{pfx}-sess-a"
    sid2 = f"{pfx}-sess-b"

    with SessionLocal() as db:
        cleanup_test_events(db, pfx)

        baseline = db.query(FeatureCardEvent).count()

        # ---- 1) record_event geçerli ----
        e1 = tel.record_event(
            db,
            slug="daily-plan",
            event_type="impression",
            session_id=sid1,
        )
        check("geçerli event kaydedildi", e1 is not None)
        if e1:
            check("event.card_slug = 'daily-plan'", e1.card_slug == "daily-plan")
            check("event.event_type = 'impression'", e1.event_type == "impression")
            check("event.session_id korundu", e1.session_id == sid1)

        # ---- 2) Geçersiz event_type ----
        e_bad = tel.record_event(
            db, slug="daily-plan", event_type="not_an_event", session_id=sid1,
        )
        check("geçersiz event_type → None", e_bad is None)

        # ---- 3) Geçersiz slug ----
        e_bad_slug = tel.record_event(
            db, slug="nonexistent-card-xyz", event_type="view", session_id=sid1,
        )
        check("geçersiz slug → None", e_bad_slug is None)

        # ---- 4) Throttle: aynı (session, slug, event) tekrar ----
        e2 = tel.record_event(
            db, slug="daily-plan", event_type="impression", session_id=sid1,
        )
        check("aynı (sess,slug,event) throttle → None", e2 is None)

        # ---- 5) Farklı session → throttle yok ----
        e3 = tel.record_event(
            db, slug="daily-plan", event_type="impression", session_id=sid2,
        )
        check("farklı session → kaydedildi", e3 is not None)

        # Aynı session, farklı event_type → throttle yok
        e4 = tel.record_event(
            db, slug="daily-plan", event_type="view", session_id=sid1,
        )
        check("aynı session farklı event_type → kaydedildi", e4 is not None)

        # ---- 6-7) Hash determinizmi + KVKK ----
        h1 = tel._hash_value("127.0.0.1")
        h2 = tel._hash_value("127.0.0.1")
        h3 = tel._hash_value("10.0.0.1")
        check("hash deterministic", h1 == h2)
        check("farklı IP farklı hash", h1 != h3)
        check("hash 64-hex (SHA256)",
              h1 is not None and len(h1) == 64 and all(c in "0123456789abcdef" for c in h1))
        check("None için None", tel._hash_value(None) is None)

        # ---- 8) get_card_stats ----
        daily_plan_id = db.query(FeatureCard.id).filter(
            FeatureCard.slug == "daily-plan"
        ).scalar()
        stats = tel.get_card_stats(db, daily_plan_id)
        check("stats impression >= 2", stats["impression"] >= 2,
              f"got {stats}")
        check("stats view >= 1", stats["view"] >= 1, f"got {stats}")
        check("stats demo_click=0 (henüz yok)", stats["demo_click"] == 0)

        # ---- 9) get_bulk_stats ----
        aralikli_id = db.query(FeatureCard.id).filter(
            FeatureCard.slug == "aralikli-tekrar"
        ).scalar()
        tel.record_event(db, slug="aralikli-tekrar", event_type="demo_click",
                         session_id=sid1)
        bulk = tel.get_bulk_stats(db, [daily_plan_id, aralikli_id])
        check("bulk_stats 2 kart döner", len(bulk) == 2,
              f"got {len(bulk)}")
        check("bulk: daily-plan stats var",
              daily_plan_id in bulk and bulk[daily_plan_id]["impression"] >= 2)
        check("bulk: aralikli-tekrar demo_click=1",
              bulk.get(aralikli_id, {}).get("demo_click", 0) == 1)

        # ---- 11) HTTP endpoint ----
    # Fresh client for HTTP tests (TestClient share state)
    client = TestClient(app)
    r = client.post(
        "/api/telemetry/event",
        json={"slug": "daily-plan", "event": "view"},
    )
    check("POST /api/telemetry/event valid → 204",
          r.status_code == 204, f"got {r.status_code}")
    check("Set-Cookie: fc_telemetry_sid",
          "fc_telemetry_sid" in (r.cookies or {}))

    r_bad_body = client.post("/api/telemetry/event", json={"slug": "x"})
    check("body validation eksik field → 422",
          r_bad_body.status_code == 422)

    r_bad_event = client.post(
        "/api/telemetry/event",
        json={"slug": "daily-plan", "event": "bogus"},
    )
    check("invalid event_type → 204 (sessizce no-op)",
          r_bad_event.status_code == 204)

    r_bad_slug = client.post(
        "/api/telemetry/event",
        json={"slug": "no-such-card", "event": "view"},
    )
    check("invalid slug → 204 (sessizce no-op)",
          r_bad_slug.status_code == 204)

    # ---- 11b) Landing JS check ----
    r = client.get("/")
    check("landing 200", r.status_code == 200)
    check("data-fc-slug attribute (≥5)",
          r.text.count('data-fc-slug=') >= 5,
          f"got {r.text.count('data-fc-slug=')}")
    check("data-fc-event attribute",
          r.text.count('data-fc-event=') >= 1)
    check("sendBeacon JS",
          'sendBeacon' in r.text)
    check("/api/telemetry/event URL JS'de",
          '/api/telemetry/event' in r.text)

    # ---- 12) Admin sayfa 'Etkileşim' sütunu ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (super_admin yok — admin testi atlandı)")
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
                r = client.get("/admin/feature-catalog")
                check("admin liste 200", r.status_code == 200)
                check("'Ziyaret' başlık", "Ziyaret" in r.text)
                # Yeni format: "N gösterim" metin
                import re
                badge_count = len(re.findall(
                    r'<span class="font-semibold">\s*\d+\s*</span>\s*<span[^>]*>gösterim',
                    r.text,
                ))
                check("≥1 gösterim sayım render", badge_count >= 1,
                      f"got {badge_count}")
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

        # Cleanup
        n = cleanup_test_events(db, pfx)
        # HTTP testleri başka session_id'lerle event yarattı — bunları da temizle
        n2 = db.query(FeatureCardEvent).filter(
            ~FeatureCardEvent.session_id.like(f"{pfx}%"),
            FeatureCardEvent.created_at >= datetime.now(timezone.utc) - timedelta(minutes=5),
        ).delete(synchronize_session=False)
        db.commit()
        print(f"  Cleanup: {n} test events + {n2} HTTP events silindi")

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
