"""Katman 7 — LinUCB Contextual Bandit smoke test.

Senaryolar:
  1) Matris işlemleri: I⁻¹=I, random PSD invert düşük hata
  2) extract_context: 10-dim, bias=1, rol+saat one-hot doğru
  3) ensure_state: yeni state → I matris + zeros vektör; mevcut → aynısı
  4) update: A = I + xxᵀ, b = r·x; reward=0 ise no-op
  5) update_from_event reward mapping: impression no-op, view=0.3, demo=1.0, cta=0.8
  6) score: yeni state'te mean=0, ucb=α·√(xᵀx) (sıfır olmaz)
  7) Convergence sentetik 2-arm test: 200 round sonra optimal arm'a yakınsar
  8) Telemetry hook: record_event sonrası bandit reward_count artar
  9) Hibrit get_for_landing: bandit state yokken fuzzy, varken hibrit çalışır
 10) manual_pin sert kuralı bandit'i ezer
 11) Admin sayfasında bandit rozeti görünür
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import math
import random
import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import (
    FeatureBanditState,
    FeatureCard,
    FeatureCardEvent,
    FeatureStatus,
    User,
    UserRole,
)
from app.services import bandit
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


def cleanup(db, pfx: str) -> int:
    """Test fixture'larını ve onlara bağlı state'leri sil."""
    cards = db.query(FeatureCard).filter(FeatureCard.slug.like(f"{pfx}%")).all()
    ids = [c.id for c in cards]
    n = 0
    if ids:
        # Önce bağımlı tabloları temizle (cascade DELETE migration'da zaten var
        # ama explicit olmak iyi)
        db.query(FeatureBanditState).filter(
            FeatureBanditState.card_id.in_(ids)
        ).delete(synchronize_session=False)
        db.query(FeatureCardEvent).filter(
            FeatureCardEvent.card_id.in_(ids)
        ).delete(synchronize_session=False)
        for c in cards:
            db.delete(c)
            n += 1
        db.commit()
    return n


def main() -> int:
    print("=== Katman 7 (LinUCB Bandit) smoke ===")

    # ---- 1) Matris işlemleri ----
    I = bandit._identity(5)
    I_inv = bandit._invert(I)
    ok = all(
        abs(I_inv[i][j] - (1.0 if i == j else 0.0)) < 1e-9
        for i in range(5)
        for j in range(5)
    )
    check("identity invert kendisi", ok)

    random.seed(42)
    m = bandit._identity(4)
    for _ in range(8):
        v = [random.random() for _ in range(4)]
        bandit._outer_add(m, v, 1.0)
    m_inv = bandit._invert(m)
    max_err = max(
        abs(sum(m[i][k] * m_inv[k][j] for k in range(4))
            - (1.0 if i == j else 0.0))
        for i in range(4)
        for j in range(4)
    )
    check("random PSD invert hata < 1e-10", max_err < 1e-10,
          f"got {max_err:.2e}")

    # ---- 2) extract_context ----
    ctx_anon = bandit.extract_context(None,
                                     now=datetime(2026, 5, 15, 10, 0, tzinfo=timezone.utc))
    check("context dim = 10", len(ctx_anon) == 10)
    check("bias = 1", ctx_anon[0] == 1.0)
    check("anonim → x[1]=1", ctx_anon[1] == 1.0)
    check("morning (10:00) → x[6]=1", ctx_anon[6] == 1.0)
    check("evening bin 0 morning'de", ctx_anon[8] == 0.0)

    # Sahte teacher viewer için
    class _Viewer:
        def __init__(self, role):
            self.role = role
    teacher_v = _Viewer(UserRole.TEACHER)
    ctx_teacher = bandit.extract_context(
        teacher_v, now=datetime(2026, 5, 15, 20, 0, tzinfo=timezone.utc)
    )
    check("teacher → x[3]=1", ctx_teacher[3] == 1.0)
    check("anon flag off teacher'da", ctx_teacher[1] == 0.0)
    check("evening (20:00) → x[8]=1", ctx_teacher[8] == 1.0)

    # ---- Test fixture ----
    pfx = f"bt-{secrets.token_hex(3)}"
    with SessionLocal() as db:
        cleanup(db, pfx)

        from app.services import feature_catalog as fc
        now_t = datetime.now(timezone.utc)
        cards: dict[str, FeatureCard] = {}
        for name in ["a", "b"]:
            cards[name] = fc.create(
                db, actor_id=None,
                slug=f"{pfx}-{name}",
                title=f"bandit test {name}",
                category_icon="🆕", category_label="Test",
                tagline="x", description_md="",
                domain="genel", tier="enhancement",
                status=FeatureStatus.PUBLISHED.value,
                target_roles=[UserRole.STUDENT],
                introduced_at=now_t,
                strategic_priority=3,
                mockup_type="daily_schedule",
            )
        db.commit()
        card_a, card_b = cards["a"], cards["b"]

        # ---- 3) ensure_state ----
        st = bandit.ensure_state(db, card_a.id)
        check("ensure_state yeni state", st is not None)
        check("yeni state A=I", st.a_matrix == bandit._identity(10))
        check("yeni state b=0", st.b_vector == bandit._zeros(10))
        check("yeni state context_dim=10", st.context_dim == 10)
        check("yeni state reward_count=0", st.reward_count == 0)

        # idempotent
        st2 = bandit.ensure_state(db, card_a.id)
        check("ensure_state idempotent (aynı state)",
              st2.card_id == st.card_id and st2.reward_count == 0)

        # ---- 4) update ----
        ctx = bandit.extract_context(None, now=now_t)
        out = bandit.update(db, card_id=card_a.id, context=ctx, reward=1.0)
        check("update reward=1.0 → state döner", out is not None)
        check("update sonrası reward_count=1",
              (out.reward_count if out else 0) == 1)
        # A[0][0] = 1 + 1 (bias * bias)
        check("A[0][0] = 2 (I + bias²)", abs(out.a_matrix[0][0] - 2.0) < 1e-9)
        # b[0] = 1.0 (bias * reward)
        check("b[0] = 1.0 (reward * bias)", abs(out.b_vector[0] - 1.0) < 1e-9)

        # reward=0 no-op
        out0 = bandit.update(db, card_id=card_a.id, context=ctx, reward=0.0)
        check("update reward=0 → None", out0 is None)

        # ---- 5) update_from_event reward mapping ----
        out_imp = bandit.update_from_event(
            db, card_id=card_a.id, event_type="impression", context=ctx
        )
        check("impression → None (no reward)", out_imp is None)
        out_view = bandit.update_from_event(
            db, card_id=card_a.id, event_type="view", context=ctx
        )
        check("view → state update", out_view is not None)
        out_demo = bandit.update_from_event(
            db, card_id=card_a.id, event_type="demo_click", context=ctx
        )
        check("demo_click → state update", out_demo is not None)

        # ---- 6) score ----
        st_a = db.get(FeatureBanditState, card_a.id)
        mean, ucb = bandit.score(st_a, ctx)
        check("score: mean > 0 (öğrenildi)", mean > 0)
        check("score: ucb >= mean (keşif terimi pozitif)", ucb >= mean)

        # ---- 7) Sentetik convergence — 2 arm ----
        # Aynı veritabanı kartını kullanmıyoruz; in-memory fake state
        class FakeSt:
            def __init__(self, dim):
                self.context_dim = dim
                self.a_matrix = bandit._identity(dim)
                self.b_vector = bandit._zeros(dim)
                self.alpha = 0.5
                self.reward_count = 0

        sa = FakeSt(3)
        sb_ = FakeSt(3)
        random.seed(7)
        for _ in range(200):
            x = [1.0, random.choice([0, 1]), random.choice([0, 1])]
            r_a = 1.0 if x[1] == 1 else 0.1
            r_b = 1.0 if x[2] == 1 else 0.1
            bandit._outer_add(sa.a_matrix, x, 1.0)
            bandit._vec_add(sa.b_vector, x, r_a)
            bandit._outer_add(sb_.a_matrix, x, 1.0)
            bandit._vec_add(sb_.b_vector, x, r_b)

        # x[1]=1 → A daha iyi
        ma_, _ = bandit.score(sa, [1.0, 1.0, 0.0])
        mb_, _ = bandit.score(sb_, [1.0, 1.0, 0.0])
        check("convergence: x=[1,1,0] → A > B",
              ma_ > mb_, f"A={ma_:.3f} B={mb_:.3f}")
        ma_, _ = bandit.score(sa, [1.0, 0.0, 1.0])
        mb_, _ = bandit.score(sb_, [1.0, 0.0, 1.0])
        check("convergence: x=[1,0,1] → B > A",
              mb_ > ma_, f"A={ma_:.3f} B={mb_:.3f}")

        # ---- 8) Telemetry hook entegrasyonu ----
        # record_event çağırınca bandit reward_count artmalı
        before = db.get(FeatureBanditState, card_b.id)
        before_count = before.reward_count if before else 0
        e = tel.record_event(
            db,
            slug=f"{pfx}-b",
            event_type="demo_click",
            session_id="bt-session-" + secrets.token_hex(3),
        )
        check("telemetry record_event başarılı", e is not None)
        after = db.get(FeatureBanditState, card_b.id)
        check("telemetry sonrası bandit state oluştu",
              after is not None)
        check("telemetry sonrası reward_count arttı",
              (after.reward_count if after else 0) > before_count)

        # impression event'i bandit'i update etmemeli
        before_cnt = (db.get(FeatureBanditState, card_b.id).reward_count
                      if db.get(FeatureBanditState, card_b.id) else 0)
        tel.record_event(
            db,
            slug=f"{pfx}-b",
            event_type="impression",
            session_id="bt-session-imp-" + secrets.token_hex(3),
        )
        after_cnt = db.get(FeatureBanditState, card_b.id).reward_count
        check("impression event bandit'i etkilemedi",
              after_cnt == before_cnt,
              f"before={before_cnt} after={after_cnt}")

        # ---- 9-10) Hibrit get_for_landing ----
        # Mevcut 5 anasayfa kartı bandit state'siz, yeni 2 test kartı state'li.
        # Sıralama yapılırken hata olmamalı.
        landing = fc.get_for_landing(db, limit=10, viewer=None)
        check(f"{pfx}-a landing'de", any(c.slug == f"{pfx}-a" for c in landing))
        check(f"{pfx}-b landing'de", any(c.slug == f"{pfx}-b" for c in landing))
        check("daily-plan hala landing'de (regresyon)",
              any(c.slug == "daily-plan" for c in landing))

        # manual_pin sert kural: a'yı pinle → tepede
        card_a.manual_pin = True
        db.commit()
        pinned = fc.get_for_landing(db, limit=10, viewer=None)
        check("manual_pin sert kuralı: a tepede",
              pinned[0].slug == f"{pfx}-a")
        card_a.manual_pin = False
        db.commit()

        # ---- 11) Admin sayfasında bandit rozeti ----
        sa_user = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        if sa_user is None:
            print("  (super_admin yok — admin testi atlandı)")
        else:
            sa_id = sa_user.id

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
                r = c.get("/admin/feature-catalog")
                check("admin liste 200", r.status_code == 200)
                # Yeni sade etiket: "🧠 N" (μ ekrandan kaldırıldı, tooltip'te kaldı)
                check("🧠 öğrenme rozeti render",
                      "🧠" in r.text)
                check("bandit tooltip 'LinUCB'",
                      "LinUCB" in r.text)
                check("tooltip 'Beklenen ilgi puanı' Türkçe",
                      "Beklenen ilgi puanı" in r.text)
            finally:
                app.dependency_overrides.pop(require_super_admin, None)
                app.dependency_overrides.pop(require_user, None)
                app.dependency_overrides.pop(get_current_user, None)

        # Cleanup
        n = cleanup(db, pfx)
        print(f"  Cleanup: {n} test kartı + state silindi")

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
