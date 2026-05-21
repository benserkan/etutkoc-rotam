"""Katman 9 — Sıralama stratejisi kayıt sistemi.

Anasayfa kart sıralaması için 3 strateji:
  - fuzzy_only      → Katman 5 (sadece Mamdani fuzzy)
  - hybrid_bandit   → Katman 5 + 7 (fuzzy + LinUCB, MMR YOK)
  - hybrid_full     → Katman 5 + 7 + 8 (fuzzy + bandit + MMR) — varsayılan

Her strateji aynı imzaya sahip: aday kart listesi, DB, viewer, now → sıralı liste.
Sert kurallar (PUBLISHED + mockup_type + not hidden) get_for_landing'de zaten
filtrelenmiş geldiği için STRATEJI'de tekrar uygulanmıyor.
Pin'liler de get_for_landing tarafında ayrı tutulur — strateji yalnız
non-pinned'a uygulanır.

A/B testte hangi strateji çağrılacağı `experiments.assign_variant` ile
belirlenir.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from app.models import FeatureCard


RankingStrategy = Callable[
    [list[FeatureCard], Session, object, datetime, int],
    list[FeatureCard],
]


# ============================================================
# 1) fuzzy_only — Katman 5 saf
# ============================================================


def fuzzy_only(
    candidates: list[FeatureCard],
    db: Session,
    viewer: object | None,
    now: datetime,
    k: int,
) -> list[FeatureCard]:
    """Sadece Mamdani fuzzy skoru — bandit/MMR YOK."""
    from app.services.feature_scoring import score_card

    role = (viewer.role.value if viewer is not None else None)
    scored = [
        (c, score_card(c, role=role, now=now).prominence)
        for c in candidates
    ]
    scored.sort(key=lambda pair: (-pair[1], pair[0].introduced_at))
    return [c for c, _ in scored[:k]]


# ============================================================
# 2) hybrid_bandit — Fuzzy + LinUCB (MMR YOK)
# ============================================================


def hybrid_bandit(
    candidates: list[FeatureCard],
    db: Session,
    viewer: object | None,
    now: datetime,
    k: int,
) -> list[FeatureCard]:
    """Fuzzy + bandit hibrit, MMR olmadan. Veri biriktikçe bandit ağırlığı artar."""
    from app.services.feature_scoring import score_card
    from app.services import bandit
    from app.models import FeatureBanditState

    role = (viewer.role.value if viewer is not None else None)

    fuzzy_norm = {
        c.id: score_card(c, role=role, now=now).prominence / 100.0
        for c in candidates
    }
    context = bandit.extract_context(viewer, now=now)
    states = {
        s.card_id: s
        for s in db.query(FeatureBanditState)
        .filter(FeatureBanditState.card_id.in_([c.id for c in candidates]))
        .all()
    }

    bandit_raw: dict[int, float | None] = {}
    obs_counts: list[int] = []
    for c in candidates:
        st = states.get(c.id)
        if st is None:
            bandit_raw[c.id] = None
            continue
        _, ucb = bandit.score(st, context)
        bandit_raw[c.id] = ucb
        obs_counts.append(st.reward_count or 0)

    avg_obs = (sum(obs_counts) / len(obs_counts)) if obs_counts else 0.0
    w = min(0.5, avg_obs / 50.0)
    valid = [v for v in bandit_raw.values() if v is not None]
    if not valid or w == 0.0:
        bandit_norm = {c.id: 0.0 for c in candidates}
        w = 0.0
    else:
        lo, hi = min(valid), max(valid)
        span = (hi - lo) or 1.0
        bandit_norm = {
            cid: ((v - lo) / span) if v is not None else 0.0
            for cid, v in bandit_raw.items()
        }

    final = {
        c.id: (1.0 - w) * fuzzy_norm[c.id] + w * bandit_norm[c.id]
        for c in candidates
    }
    out = list(candidates)
    out.sort(key=lambda c: (-final[c.id], c.introduced_at))
    return out[:k]


# ============================================================
# 3) hybrid_full — Fuzzy + bandit + MMR (varsayılan)
# ============================================================


def hybrid_full(
    candidates: list[FeatureCard],
    db: Session,
    viewer: object | None,
    now: datetime,
    k: int,
) -> list[FeatureCard]:
    """Fuzzy + bandit harman + MMR çeşitlilik (mevcut varsayılan)."""
    from app.services.feature_scoring import score_card
    from app.services import bandit
    from app.services import diversity as dv
    from app.models import FeatureBanditState

    role = (viewer.role.value if viewer is not None else None)

    fuzzy_norm = {
        c.id: score_card(c, role=role, now=now).prominence / 100.0
        for c in candidates
    }
    context = bandit.extract_context(viewer, now=now)
    states = {
        s.card_id: s
        for s in db.query(FeatureBanditState)
        .filter(FeatureBanditState.card_id.in_([c.id for c in candidates]))
        .all()
    }
    bandit_raw: dict[int, float | None] = {}
    obs_counts: list[int] = []
    for c in candidates:
        st = states.get(c.id)
        if st is None:
            bandit_raw[c.id] = None
            continue
        _, ucb = bandit.score(st, context)
        bandit_raw[c.id] = ucb
        obs_counts.append(st.reward_count or 0)

    avg_obs = (sum(obs_counts) / len(obs_counts)) if obs_counts else 0.0
    w = min(0.5, avg_obs / 50.0)
    valid = [v for v in bandit_raw.values() if v is not None]
    if not valid or w == 0.0:
        bandit_norm = {c.id: 0.0 for c in candidates}
        w = 0.0
    else:
        lo, hi = min(valid), max(valid)
        span = (hi - lo) or 1.0
        bandit_norm = {
            cid: ((v - lo) / span) if v is not None else 0.0
            for cid, v in bandit_raw.items()
        }

    final = {
        c.id: (1.0 - w) * fuzzy_norm[c.id] + w * bandit_norm[c.id]
        for c in candidates
    }

    # MMR rerank (Katman 8)
    return dv.mmr_rerank(
        candidates,
        relevance=final,
        k=k,
        lambda_param=dv.DEFAULT_LAMBDA,
    )


# ============================================================
# Kayıt + Türkçe etiketler
# ============================================================


REGISTRY: dict[str, RankingStrategy] = {
    "fuzzy_only": fuzzy_only,
    "hybrid_bandit": hybrid_bandit,
    "hybrid_full": hybrid_full,
}

STRATEGY_LABELS_TR: dict[str, str] = {
    "fuzzy_only": "Sadece skor (sade)",
    "hybrid_bandit": "Skor + öğrenen seçici",
    "hybrid_full": "Skor + öğrenen + çeşitlilik (varsayılan)",
}

STRATEGY_DESCRIPTIONS_TR: dict[str, str] = {
    "fuzzy_only":
        "Bulanık mantık ile hesaplanan vitrin skoru sırasıyla. "
        "Hızlı, basit, deterministik. Ziyaretçi davranışını dikkate almaz.",
    "hybrid_bandit":
        "Vitrin skoru + ziyaretçi davranışından öğrenen sıralayıcı "
        "(LinUCB). Çeşitlilik düzeltmesi YOK — yüksek skorlu kartlar "
        "üst üste gelebilir.",
    "hybrid_full":
        "Skor + öğrenen + çeşitlilik filtresi (MMR). Benzer temalardan "
        "ardışık kart yığılmasını engeller. Şu anki varsayılan davranış.",
}

DEFAULT_STRATEGY = "hybrid_full"


def get_strategy(key: str | None) -> RankingStrategy:
    """Kayıttan stratejiyi getir; geçersizse varsayılana düş."""
    if key and key in REGISTRY:
        return REGISTRY[key]
    return REGISTRY[DEFAULT_STRATEGY]
