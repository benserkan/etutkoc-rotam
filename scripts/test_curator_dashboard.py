"""Katman 10 — Süper Admin Yönetim Paneli (Curator Dashboard) smoke test.

Senaryolar:
  1) get_dashboard_data sections (summary, landing_health, last_7d, anomalies, audit)
  2) Anomali tetikleri:
     - Landing'de < 3 kart → "anasayfa zayıf"
     - queue_pending ≥ 10 → "kuyrukta birikme"
     - last 7d impressions=0 → "trafik yok"
     - Aktif deney 200+ impr + 7+ gün + anlamlı fark yok → uyarı
  3) Aktif deney özeti: variants, total_impressions, has_significance
  4) humanize_ago doğru Türkçe etiketler
  5) GET /admin/feature-catalog/dashboard 200 + tüm section'lar
  6) Liste sayfasından "Yönetim Paneli" link
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
    AuditAction,
    AuditLog,
    ExperimentStatus,
    FeatureCard,
    FeatureCardEvent,
    FeatureExperiment,
    User,
    UserRole,
)
from app.services.curator_dashboard import (
    get_dashboard_data,
    humanize_ago,
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
    print("=== Katman 10 (Yönetim Paneli) smoke ===")

    # ---- 1) humanize_ago sanity ----
    check("humanize 30sn → 'az önce'", humanize_ago(30) == "az önce")
    check("humanize 5dk", humanize_ago(300) == "5 dk önce")
    check("humanize 2 saat", humanize_ago(7200) == "2 saat önce")
    check("humanize 3 gün", humanize_ago(86400 * 3) == "3 gün önce")
    check("humanize 2 hafta", humanize_ago(86400 * 14) == "2 hafta önce")

    # ---- 2) Default DB üzerinde data sections ----
    with SessionLocal() as db:
        data = get_dashboard_data(db)
        check("summary anahtarları",
              set(data["summary"].keys()) >= {
                  "total", "published", "draft", "landing", "queue_pending",
                  "hidden", "active_experiment",
              })
        check("landing_health anahtarları",
              set(data["landing_health"].keys()) >= {
                  "landing_count", "diversity_pct", "learning_count",
              })
        check("last_7d anahtarları",
              set(data["last_7d"].keys()) >= {
                  "impressions", "views", "demo_clicks", "ctr_pct",
                  "new_discoveries", "bandit_updates",
              })
        check("data.generated_at zaman", isinstance(data["generated_at"], datetime))
        check("data.window_days = 7", data["window_days"] == 7)
        # Mevcut seed: 5 anasayfa kartı → landing >= 5
        check("landing sayısı ≥ 5 (seed)",
              data["summary"]["landing"] >= 5)
        check("published sayısı ≥ 9 (seed)",
              data["summary"]["published"] >= 9)

    # ---- 3) Anomali tetikleri ----
    pfx = f"dash-{secrets.token_hex(3)}"

    with SessionLocal() as db:
        # Senaryo A: queue_pending ≥ 10 → "kuyrukta birikme"
        # (Gerçek DB'de zaten ~66 keşif draft var, anomali tetiklemeli)
        data_a = get_dashboard_data(db)
        anomaly_titles = [a["title"] for a in data_a["anomalies"]]
        has_queue_anomaly = any("kuyruğunda" in t for t in anomaly_titles)
        if data_a["summary"]["queue_pending"] >= 10:
            check("queue >= 10 → anomali tetiklendi", has_queue_anomaly,
                  f"got titles: {anomaly_titles}")

        # Senaryo B: trafik 0 ise traffic-zero anomalisi
        has_traffic_anomaly = any("ziyaret" in t.lower() for t in anomaly_titles)
        if data_a["last_7d"]["impressions"] == 0:
            check("trafik 0 → anomali", has_traffic_anomaly,
                  f"got titles: {anomaly_titles}")

        # Senaryo C: aktif deney + 200+ impr + 7+ gün + anlamlı yok → uyarı
        # Sentetik kuralım: bir deney + sahte event'ler
        now = datetime.now(timezone.utc)
        exp = FeatureExperiment(
            slug=f"{pfx}-stale",
            name="Eski deney",
            status=ExperimentStatus.RUNNING.value,
            start_at=now - timedelta(days=10),
            created_at=now - timedelta(days=10),
            updated_at=now,
        )
        exp.variants = [
            {"slug": f"{pfx}-c", "label": "Kontrol", "strategy": "hybrid_full",
             "weight": 50, "is_control": True},
            {"slug": f"{pfx}-t", "label": "Test",    "strategy": "fuzzy_only",
             "weight": 50, "is_control": False},
        ]
        db.add(exp)
        db.commit()
        # 250 impr / 13 click both — CTR yakın, anlamlı değil
        dp = db.query(FeatureCard).filter(FeatureCard.slug == "daily-plan").first()
        for variant_slug in [f"{pfx}-c", f"{pfx}-t"]:
            for i in range(250):
                db.add(FeatureCardEvent(
                    card_id=dp.id, card_slug="daily-plan",
                    event_type="impression",
                    session_id=f"{pfx}-{variant_slug}-{i}",
                    created_at=now - timedelta(days=1),
                    variant_slug=variant_slug,
                ))
                if i < 13:
                    db.add(FeatureCardEvent(
                        card_id=dp.id, card_slug="daily-plan",
                        event_type="demo_click",
                        session_id=f"{pfx}-{variant_slug}-{i}",
                        created_at=now - timedelta(days=1),
                        variant_slug=variant_slug,
                    ))
        db.commit()

        data_b = get_dashboard_data(db)
        check("aktif deney özeti dict döner",
              data_b["experiment"] is not None and
              data_b["experiment"]["slug"] == f"{pfx}-stale")
        if data_b["experiment"]:
            check("deney variants sayısı 2",
                  len(data_b["experiment"]["variants"]) == 2)
            check("total_impressions ≥ 500",
                  data_b["experiment"]["total_impressions"] >= 500)
            check("anlamlı fark YOK (CTR'lar eşit)",
                  not data_b["experiment"]["has_significance"])
        anomaly_titles_b = [a["title"] for a in data_b["anomalies"]]
        check("eski-anlamsız deney anomalisi tetiklendi",
              any("Eski deney" in t for t in anomaly_titles_b),
              f"got titles: {anomaly_titles_b}")

        # Cleanup
        db.query(FeatureCardEvent).filter(
            FeatureCardEvent.variant_slug.like(f"{pfx}%")
        ).delete(synchronize_session=False)
        db.query(FeatureExperiment).filter(
            FeatureExperiment.slug.like(f"{pfx}%")
        ).delete(synchronize_session=False)
        db.commit()

    # ---- 5) HTTP dashboard sayfası ----
    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa is None:
            print("  (super_admin yok — HTTP testi atlandı)")
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
                r = c.get("/admin/feature-catalog/dashboard")
                check("dashboard GET 200", r.status_code == 200,
                      f"got {r.status_code}")
                check("'Vitrin Yönetim Paneli' başlığı",
                      "Vitrin Yönetim Paneli" in r.text)
                check("'Anasayfa Sağlığı' section",
                      "Anasayfa Sağlığı" in r.text)
                check("'Son 7 Gün' section",
                      "Son 7 Gün" in r.text)
                check("'Dikkat Gerekli' section",
                      "Dikkat Gerekli" in r.text)
                check("'Son Hareketler' section",
                      "Son Hareketler" in r.text)
                # Üst sayım kartları
                check("'Toplam kart' rozet",
                      "Toplam kart" in r.text)
                check("'Onay bekliyor' rozet",
                      "Onay bekliyor" in r.text)
                # CTR rozet
                check("'CTR' metni",
                      "CTR" in r.text)

                # Liste sayfasından dashboard link
                r2 = c.get("/admin/feature-catalog")
                check("liste sayfası 200", r2.status_code == 200)
                check("'Yönetim Paneli' link butonu",
                      "Yönetim Paneli" in r2.text)
                check("link href doğru",
                      '/admin/feature-catalog/dashboard' in r2.text)
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
