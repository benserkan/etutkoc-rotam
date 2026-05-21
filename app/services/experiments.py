"""Katman 9 — A/B Test deney servisi.

Tek seferde bir RUNNING deney kuralı. Variant ataması deterministik
hash ile (aynı ziyaretçi her zaman aynı variant). Variant'lar 0-100
toplam weight ile dağıtılır.

İstatistik:
  - CTR = (demo_click + cta_click) / impression
  - Wilson %95 güven aralığı (skor interval — düşük örneklemlerde de
    sağlam, "0/10" gibi durumda 0 vermez)
  - "Anlamlı fark" işareti: iki variant'ın CI'leri çakışmıyorsa
    (basit, akademik olmaktan ziyade pragmatik gösterge)

Kullanım:
    active = get_active_experiment(db)
    if active is not None:
        variant_slug, strategy_key = assign_variant(active, session_id)
        # → "ctrl" / "hybrid_full" gibi

    stats = compute_stats(db, experiment_id=active.id)
    # → {"ctrl": {"impression": 1000, "view": 850, "demo_click": 47,
    #             "cta_click": 12, "ctr": 0.059, "ctr_low": 0.044,
    #             "ctr_high": 0.078, ...}, ...}
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    ExperimentStatus,
    FeatureCardEvent,
    FeatureExperiment,
)


# Wilson %95 → z = 1.96 (~%95 güven)
_WILSON_Z_95 = 1.959963984540054
_DEFAULT_STRATEGY_FALLBACK = "hybrid_full"


# ============================================================
# Active experiment lookup
# ============================================================


def get_active_experiment(db: Session) -> FeatureExperiment | None:
    """Tek RUNNING deneyi döner; yoksa None.

    Aynı anda birden fazla RUNNING varsa en eski created_at olanı.
    """
    return (
        db.query(FeatureExperiment)
        .filter(FeatureExperiment.status == ExperimentStatus.RUNNING.value)
        .order_by(FeatureExperiment.created_at.asc())
        .first()
    )


# ============================================================
# Variant assignment (deterministik)
# ============================================================


def assign_variant(
    experiment: FeatureExperiment,
    session_id: str,
) -> tuple[str, str]:
    """Verilen session için (variant_slug, strategy_key) döner.

    Algoritma:
      bucket = sha256(experiment.slug + ":" + session_id).first_4_bytes % 100
      cumulative_weight üzerinden hangi variant'a düştüğünü bul.

    Aynı (experiment, session) → her zaman aynı sonuç (deterministik).
    Variant tanımları geçersizse fallback varsayılan stratejiye düşer.
    """
    variants = experiment.variants or []
    if not variants:
        return ("", _DEFAULT_STRATEGY_FALLBACK)

    # weight toplamı normalde 100; değilse de orantısal eşle
    total_weight = sum(int(v.get("weight", 0)) for v in variants)
    if total_weight <= 0:
        return (variants[0].get("slug", ""), variants[0].get("strategy", _DEFAULT_STRATEGY_FALLBACK))

    payload = f"{experiment.slug}:{session_id}".encode("utf-8")
    h = hashlib.sha256(payload).digest()
    # İlk 4 byte'ı int'e çevir → modulo total_weight
    bucket_int = int.from_bytes(h[:4], byteorder="big", signed=False)
    bucket = bucket_int % total_weight

    cum = 0
    for v in variants:
        cum += int(v.get("weight", 0))
        if bucket < cum:
            return (
                str(v.get("slug", "")),
                str(v.get("strategy", _DEFAULT_STRATEGY_FALLBACK)),
            )
    # Edge case (numerik): son variant'a düş
    last = variants[-1]
    return (
        str(last.get("slug", "")),
        str(last.get("strategy", _DEFAULT_STRATEGY_FALLBACK)),
    )


# ============================================================
# Wilson güven aralığı
# ============================================================


def wilson_interval(successes: int, n: int, z: float = _WILSON_Z_95) -> tuple[float, float, float]:
    """Wilson %95 güven aralığı.

    Returns (center, low, high). Tüm değerler 0..1.
    n == 0 → (0, 0, 0); CTR tanımsız.
    """
    if n <= 0:
        return (0.0, 0.0, 0.0)
    phat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2 * n)) / denom
    inner = phat * (1.0 - phat) / n + z2 / (4 * n * n)
    if inner < 0:
        inner = 0.0
    margin = z * math.sqrt(inner) / denom
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return (center, low, high)


# ============================================================
# Per-variant istatistik agregasyonu
# ============================================================


def compute_stats(db: Session, *, experiment_id: int) -> dict[str, dict]:
    """Deney bazlı variant istatistikleri.

    Returns:
        {
          "ctrl": {
            "label": ..., "strategy": ..., "weight": ...,
            "impression": int, "view": int, "demo_click": int, "cta_click": int,
            "total_clicks": int,   # demo + cta
            "ctr": float,          # total_clicks / impression
            "ctr_low": float,      # Wilson %95 alt sınır
            "ctr_high": float,
            "is_control": bool,
            "lift_pct": float | None,  # control'a göre yüzde fark (control için None)
            "vs_control_significant": bool,  # CI'ler çakışmıyor mu
          },
          ...
        }
    """
    exp = db.get(FeatureExperiment, experiment_id)
    if exp is None:
        return {}

    variants = exp.variants or []
    out: dict[str, dict] = {}

    # Her variant için SQL agregasyonu
    for v in variants:
        slug = str(v.get("slug", ""))
        rows = (
            db.query(FeatureCardEvent.event_type, func.count(FeatureCardEvent.id))
            .filter(FeatureCardEvent.variant_slug == slug)
            .group_by(FeatureCardEvent.event_type)
            .all()
        )
        counts = {et: 0 for et in ("impression", "view", "demo_click", "cta_click")}
        for et, n in rows:
            if et in counts:
                counts[et] = int(n)
        total_clicks = counts["demo_click"] + counts["cta_click"]
        impr = counts["impression"]
        ctr, ctr_lo, ctr_hi = wilson_interval(total_clicks, impr)

        out[slug] = {
            "label": str(v.get("label", slug)),
            "strategy": str(v.get("strategy", "")),
            "weight": int(v.get("weight", 0)),
            "is_control": bool(v.get("is_control", False)),
            "impression": impr,
            "view": counts["view"],
            "demo_click": counts["demo_click"],
            "cta_click": counts["cta_click"],
            "total_clicks": total_clicks,
            "ctr": ctr,
            "ctr_low": ctr_lo,
            "ctr_high": ctr_hi,
            "lift_pct": None,                    # control için dolacak
            "vs_control_significant": False,
        }

    # Lift + anlamlılık hesapla (control bazında)
    control = next((s for s, info in out.items() if info["is_control"]), None)
    if control and out[control]["ctr"] > 0:
        c_ctr = out[control]["ctr"]
        c_lo, c_hi = out[control]["ctr_low"], out[control]["ctr_high"]
        for slug, info in out.items():
            if slug == control:
                continue
            if c_ctr > 0:
                info["lift_pct"] = (info["ctr"] - c_ctr) / c_ctr * 100.0
            # CI'ler çakışmıyor mu — basit "anlamlı" işareti
            v_lo, v_hi = info["ctr_low"], info["ctr_high"]
            no_overlap = (v_hi < c_lo) or (v_lo > c_hi)
            info["vs_control_significant"] = bool(no_overlap and info["impression"] >= 30)

    return out


# ============================================================
# Tarih damgaları
# ============================================================


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
