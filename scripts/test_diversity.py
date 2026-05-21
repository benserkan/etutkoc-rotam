"""Katman 8 — Çeşitlilik Filtresi (MMR) smoke test.

Senaryolar:
  1) Jaccard temel kontratları:
     - aynı küme → 1.0
     - boş ∩ → 0
     - disjoint küme → 0
  2) feature_set: domain/tier/role/cat/kw namespace prefix'leri
  3) similarity sentetik kartlarda doğru relatif sıralama
  4) mmr_rerank:
     - tek kart → tek-elemanlı liste
     - 2 benzer karttan farklı temayı 2. sıraya alır
     - alaka skorlarında büyük fark MMR'yi domine eder
  5) diversity_score: tek kart=1.0, 2 aynı=0.0, 2 farklı=1.0
  6) neighbor_similarity: ilk kart=0, ardışıklarda doğru hesap
  7) get_for_landing MMR sonrası ardışık benzerlik azalmış olmalı
  8) Admin sayfasında çeşitlilik banner'ı + komşu benzerliği alt rozet render
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
    FeatureCard,
    FeatureStatus,
    FeatureTier,
    User,
    UserRole,
)
from app.services import diversity as dv
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


def main() -> int:
    print("=== Katman 8 (Çeşitlilik / MMR) smoke ===")

    # ---- 1) Jaccard ----
    check("Jaccard aynı küme = 1.0",
          approx(dv.jaccard({"a", "b"}, {"a", "b"}), 1.0))
    check("Jaccard boş hiçbir şey = 0",
          approx(dv.jaccard(set(), set()), 0.0))
    check("Jaccard disjoint = 0",
          approx(dv.jaccard({"a"}, {"b"}), 0.0))
    check("Jaccard kısmi: {a,b} vs {b,c} = 1/3",
          approx(dv.jaccard({"a", "b"}, {"b", "c"}), 1/3))

    # ---- 2-3) feature_set + similarity ----
    pfx = f"dv-{secrets.token_hex(3)}"
    with SessionLocal() as db:
        # Önceki kalıntıyı sil
        for r in db.query(FeatureCard).filter(FeatureCard.slug.like(f"{pfx}%")).all():
            db.delete(r)
        db.commit()

        now_t = datetime.now(timezone.utc)
        # 4 kart farklı temalardan
        cards = {}
        cards["a"] = fc.create(
            db, actor_id=None,
            slug=f"{pfx}-a-pomodoro",
            title="Pomodoro Odak",
            category_icon="⏱️", category_label="Odak Modu",
            tagline="Tam ekran odak", description_md="",
            domain="genel", tier=FeatureTier.CORE.value,
            status=FeatureStatus.PUBLISHED.value,
            target_roles=[UserRole.STUDENT],
            introduced_at=now_t,
            strategic_priority=4,
            mockup_type="daily_schedule",
            benefits=["dikkat", "ödül", "streak"],
        )
        cards["b"] = fc.create(
            db, actor_id=None,
            slug=f"{pfx}-b-fsrs",
            title="FSRS Tekrar",
            category_icon="🧠", category_label="Aralıklı Tekrar",
            tagline="Hatırlama", description_md="",
            domain="genel", tier=FeatureTier.CORE.value,
            status=FeatureStatus.PUBLISHED.value,
            target_roles=[UserRole.STUDENT],
            introduced_at=now_t,
            strategic_priority=4,
            mockup_type="fsrs_rating",
            benefits=["hatırlama", "tekrar", "kart"],
        )
        cards["c"] = fc.create(
            db, actor_id=None,
            slug=f"{pfx}-c-veli",
            title="Veli Bildirim",
            category_icon="💬", category_label="Veli Kanalı",
            tagline="WhatsApp", description_md="",
            domain="veli", tier=FeatureTier.CORE.value,
            status=FeatureStatus.PUBLISHED.value,
            target_roles=[UserRole.PARENT],
            introduced_at=now_t,
            strategic_priority=3,
            mockup_type="whatsapp_chat",
            benefits=["whatsapp", "karne", "sessiz"],
        )
        # d: a'ya yakın klonu (aynı domain+tier+role; benzer kelimeler)
        cards["d"] = fc.create(
            db, actor_id=None,
            slug=f"{pfx}-d-pomodoro2",
            title="Pomodoro v2",
            category_icon="⏰", category_label="Odak Modu",
            tagline="Streak ödülü", description_md="",
            domain="genel", tier=FeatureTier.CORE.value,
            status=FeatureStatus.PUBLISHED.value,
            target_roles=[UserRole.STUDENT],
            introduced_at=now_t,
            strategic_priority=4,
            mockup_type="daily_schedule",
            benefits=["dikkat", "ödül", "streak"],
        )
        db.commit()

        a, b, c, d = cards["a"], cards["b"], cards["c"], cards["d"]

        # feature_set namespace prefix kontrolü
        fa = dv.feature_set(a)
        check("feature_set domain: prefix var",
              any(f.startswith("domain:") for f in fa))
        check("feature_set role: prefix var",
              any(f.startswith("role:") for f in fa))
        check("feature_set kw: prefix var",
              any(f.startswith("kw:") for f in fa))

        # similarity sıralama: d (klon) > b (aynı domain farklı kw) > c (uzak)
        sim_ad = dv.similarity(a, d)
        sim_ab = dv.similarity(a, b)
        sim_ac = dv.similarity(a, c)
        check("sim(a,d) > sim(a,b) > sim(a,c)",
              sim_ad > sim_ab > sim_ac,
              f"ad={sim_ad:.2f} ab={sim_ab:.2f} ac={sim_ac:.2f}")

        # ---- 4) mmr_rerank ----
        single = dv.mmr_rerank([a], relevance={a.id: 0.8})
        check("MMR tek kart → tek-elemanlı liste",
              len(single) == 1 and single[0] is a)

        # a (alaka 0.9), d (alaka 0.85, a'ya çok benzer), c (alaka 0.6, uzak)
        # MMR ile: 1. a (en alaka), 2. c (alakası düşük ama farklı), 3. d
        rel = {a.id: 0.9, d.id: 0.85, c.id: 0.6}
        order = dv.mmr_rerank([a, d, c], relevance=rel, lambda_param=0.6)
        check("MMR ilk seçim en alaka kart (a)",
              order[0] is a, f"got {order[0].slug}")
        check("MMR 2. sıra farklı temadan (c, d değil)",
              order[1] is c,
              f"got {order[1].slug}; sims a↔c={sim_ac:.2f} a↔d={sim_ad:.2f}")

        # lambda=1.0 → sadece alaka, MMR = pure relevance ranking
        order_pure = dv.mmr_rerank([a, d, c], relevance=rel, lambda_param=1.0)
        check("λ=1.0 sadece alaka: [a, d, c]",
              [x.id for x in order_pure] == [a.id, d.id, c.id],
              f"got {[x.slug for x in order_pure]}")

        # ---- 5) diversity_score ----
        check("diversity_score tek kart = 1.0",
              approx(dv.diversity_score([a]), 1.0))
        check("diversity_score boş = 1.0",
              approx(dv.diversity_score([]), 1.0))
        check("diversity_score [a, d (klon)] düşük (<0.5)",
              dv.diversity_score([a, d]) < 0.5,
              f"got {dv.diversity_score([a,d]):.3f}")
        check("diversity_score [a, c (uzak)] yüksek (>0.5)",
              dv.diversity_score([a, c]) > 0.5,
              f"got {dv.diversity_score([a,c]):.3f}")

        # ---- 6) neighbor_similarity ----
        ns = dv.neighbor_similarity([a, c, d])
        check("ilk kart neighbor=0", ns[a.id] == 0.0)
        check("ikinci kart neighbor = sim(a,c)",
              approx(ns[c.id], sim_ac))
        check("üçüncü kart neighbor = sim(c,d)",
              approx(ns[d.id], dv.similarity(c, d)))

        # ---- 7) get_for_landing sonrası komşu benzerliği düşük ----
        # Gerçek seed kartlar + test kartları landing'e girer; MMR uygulanır.
        landing = fc.get_for_landing(db, limit=5)
        landing_ns = dv.neighbor_similarity(landing)
        # Ardışık iki kart aynı tema değil — max neighbor < 0.5
        max_neighbor = max(v for k, v in landing_ns.items() if v > 0)
        check("MMR sonrası max komşu benzerliği < 0.5",
              max_neighbor < 0.5,
              f"got {max_neighbor:.3f}")

        # Cleanup
        for x in cards.values():
            db.delete(x)
        db.commit()

    # ---- 8) Admin sayfasında çeşitlilik banner + alt rozet ----
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
                client = TestClient(app)
                r = client.get("/admin/feature-catalog")
                check("admin liste 200", r.status_code == 200)
                check("'Çeşitlilik puanı' banner'da",
                      "Çeşitlilik puanı" in r.text)
                check("'Anasayfada' chip görünür",
                      "Anasayfada</span>" in r.text)
                # MMR ile en az 1 landing kartında 🎨 alt rozeti çıkar
                # (ilk kart hariç hepsi neighbor sim > 0)
                check("🎨 tema farklılık rozeti",
                      "🎨" in r.text)
                check("'Öğrenme aktif' metni",
                      "Öğrenme aktif" in r.text)
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
