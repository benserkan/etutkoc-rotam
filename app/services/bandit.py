"""Katman 7 — LinUCB Contextual Bandit (öğrenen kart seçici).

Saf Python (sıfır external dep). Küçük matris (10×10) için Gauss-Jordan
matris tersi yeterli; numpy zorunluluğu yok.

Algoritma — her kart için bir "arm" durumu (A, b):
  Başlangıç: A = I_d (identity), b = 0
  Bağlam x ∈ R^d için:
    θ = A⁻¹·b
    mean = θᵀx
    ucb  = mean + α·√(xᵀA⁻¹x)
  Gözlem geldikten sonra:
    A = A + x·xᵀ
    b = b + r·x

Bizim sistemde:
  d = 10:
    [bias=1, is_anon, is_student, is_teacher, is_parent, is_other,
     hour_morning, hour_afternoon, hour_evening, hour_night]
  reward: impression=0 (skip), view=0.3, demo_click=1.0, cta_click=0.8
  α = 0.5 (orta keşif)

Online güncelleme: `telemetry.record_event` içinden çağrılır.
Hibrit sıralama: `feature_catalog.get_for_landing` w = min(0.5, obs/50)
ile fuzzy + bandit harmanı yapar.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import FeatureBanditState, FeatureCardEvent, User, UserRole


logger = logging.getLogger(__name__)


# ============================================================
# Sabitler
# ============================================================

CONTEXT_DIM = 10
DEFAULT_ALPHA = 0.5

# Event türünden reward; impression yalnız bağlam gözlemi (no reward update)
REWARD_BY_EVENT: dict[str, float] = {
    "impression": 0.0,
    "view": 0.3,
    "demo_click": 1.0,
    "cta_click": 0.8,
}


# ============================================================
# Matrix yardımcıları (saf Python)
# ============================================================


def _zeros(n: int) -> list[float]:
    return [0.0] * n


def _identity(n: int) -> list[list[float]]:
    return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]


def _matvec(m: list[list[float]], v: list[float]) -> list[float]:
    """m·v"""
    n = len(m)
    return [sum(m[i][j] * v[j] for j in range(n)) for i in range(n)]


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _outer_add(m: list[list[float]], v: list[float], coef: float = 1.0) -> None:
    """m += coef · v·vᵀ — in-place."""
    n = len(v)
    for i in range(n):
        vi = v[i] * coef
        if vi == 0.0:
            continue
        row = m[i]
        for j in range(n):
            row[j] += vi * v[j]


def _vec_add(b: list[float], v: list[float], coef: float = 1.0) -> None:
    """b += coef · v — in-place."""
    for i in range(len(b)):
        b[i] += coef * v[i]


def _invert(m: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan eliminasyonla matris tersi. Tekil ise RuntimeError."""
    n = len(m)
    # Augmented [m | I], deep copy çünkü in-place modifiye edilecek
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)]
           for i, row in enumerate(m)]
    for i in range(n):
        # Partial pivot — sayısal stabilite için
        pivot = abs(aug[i][i])
        pivot_row = i
        for k in range(i + 1, n):
            if abs(aug[k][i]) > pivot:
                pivot = abs(aug[k][i])
                pivot_row = k
        if pivot < 1e-12:
            raise RuntimeError("Matris tekil — invert edilemez")
        if pivot_row != i:
            aug[i], aug[pivot_row] = aug[pivot_row], aug[i]
        # Normalize: row i'yi pivot ile böl
        div = aug[i][i]
        for j in range(2 * n):
            aug[i][j] /= div
        # Diğer satırları temizle
        for k in range(n):
            if k == i:
                continue
            factor = aug[k][i]
            if factor == 0.0:
                continue
            row_i = aug[i]
            row_k = aug[k]
            for j in range(2 * n):
                row_k[j] -= factor * row_i[j]
    return [row[n:] for row in aug]


# ============================================================
# Context vector
# ============================================================


def extract_context(viewer: User | None, now: datetime | None = None) -> list[float]:
    """Ziyaretçi + zaman bağlamından 10-dim feature vector üret."""
    x = _zeros(CONTEXT_DIM)
    x[0] = 1.0  # bias

    # Role one-hot
    if viewer is None:
        x[1] = 1.0  # anonim
    else:
        role = viewer.role.value if hasattr(viewer.role, "value") else str(viewer.role)
        if role == UserRole.STUDENT.value:
            x[2] = 1.0
        elif role == UserRole.TEACHER.value:
            x[3] = 1.0
        elif role == UserRole.PARENT.value:
            x[4] = 1.0
        else:
            x[5] = 1.0  # institution_admin / super_admin / diğer

    # Saat bini (UTC; Türkiye için günde aynı binler işe yarar)
    if now is None:
        now = datetime.now(timezone.utc)
    h = now.hour
    if 6 <= h < 12:
        x[6] = 1.0
    elif 12 <= h < 18:
        x[7] = 1.0
    elif 18 <= h < 22:
        x[8] = 1.0
    else:
        x[9] = 1.0

    return x


# ============================================================
# State CRUD (DB ↔ Python matrix)
# ============================================================


def ensure_state(db: Session, card_id: int, *, commit: bool = True) -> FeatureBanditState:
    """Kart için bandit durumu yoksa A=I, b=0 ile başlat. Mevcut ise döner.

    Boyut uyumsuzluğu (örn. CONTEXT_DIM değişti) → reset.
    """
    state = db.get(FeatureBanditState, card_id)
    if state is not None and state.context_dim == CONTEXT_DIM:
        return state

    # Yeni veya boyut uyumsuzluğunda reset
    now = datetime.now(timezone.utc)
    if state is None:
        state = FeatureBanditState(
            card_id=card_id,
            context_dim=CONTEXT_DIM,
            alpha=DEFAULT_ALPHA,
            reward_count=0,
            updated_at=now,
        )
        state.a_matrix = _identity(CONTEXT_DIM)
        state.b_vector = _zeros(CONTEXT_DIM)
        db.add(state)
    else:
        # Boyut değişimi: state'i sıfırla
        state.context_dim = CONTEXT_DIM
        state.alpha = DEFAULT_ALPHA
        state.reward_count = 0
        state.a_matrix = _identity(CONTEXT_DIM)
        state.b_vector = _zeros(CONTEXT_DIM)
        state.updated_at = now

    if commit:
        db.commit()
        db.refresh(state)
    return state


# ============================================================
# Update + score
# ============================================================


def update(
    db: Session,
    *,
    card_id: int,
    context: list[float],
    reward: float,
    commit: bool = True,
) -> FeatureBanditState | None:
    """LinUCB güncelleme: A = A + x·xᵀ, b = b + r·x. Reward = 0 ise no-op."""
    if reward == 0.0:
        return None
    if len(context) != CONTEXT_DIM:
        logger.warning("bandit.update: context boyutu uyuşmuyor (%d != %d)",
                       len(context), CONTEXT_DIM)
        return None

    state = ensure_state(db, card_id, commit=False)
    a = state.a_matrix
    b = state.b_vector
    _outer_add(a, context, coef=1.0)
    _vec_add(b, context, coef=reward)
    state.a_matrix = a
    state.b_vector = b
    state.reward_count = (state.reward_count or 0) + 1
    state.updated_at = datetime.now(timezone.utc)

    if commit:
        db.commit()
        db.refresh(state)
    return state


def update_from_event(
    db: Session,
    *,
    card_id: int,
    event_type: str,
    context: list[float],
    commit: bool = True,
) -> FeatureBanditState | None:
    """Event tipinden reward türetip update çağır."""
    reward = REWARD_BY_EVENT.get(event_type, 0.0)
    if reward == 0.0:
        return None
    return update(db, card_id=card_id, context=context, reward=reward, commit=commit)


def score(state: FeatureBanditState, context: list[float]) -> tuple[float, float]:
    """(mean, ucb) skoru döner — ranking veya seçim için.

    mean = θᵀx        — exploitation kestirimi
    ucb  = mean + α·√(xᵀA⁻¹x) — exploration ile birleştirilmiş
    """
    if len(context) != state.context_dim:
        return 0.0, 0.0
    a = state.a_matrix
    b = state.b_vector
    try:
        a_inv = _invert(a)
    except RuntimeError:
        return 0.0, 0.0
    theta = _matvec(a_inv, b)
    mean = _dot(theta, context)
    quad = _dot(context, _matvec(a_inv, context))
    if quad < 0:
        quad = 0.0  # sayısal güvenlik
    ucb = mean + (state.alpha or DEFAULT_ALPHA) * math.sqrt(quad)
    return mean, ucb


def avg_observations(db: Session, card_ids: list[int]) -> float:
    """Verilen kart kümesinin ortalama reward_count'u — hibrit ağırlık hesabı için."""
    if not card_ids:
        return 0.0
    rows = (
        db.query(FeatureBanditState.reward_count)
        .filter(FeatureBanditState.card_id.in_(card_ids))
        .all()
    )
    if not rows:
        return 0.0
    return sum(r[0] or 0 for r in rows) / len(rows)


# ============================================================
# Telemetri hook — feature_card_events üzerinden çağrılır
# ============================================================


def record_event_hook(
    db: Session,
    event: FeatureCardEvent,
    *,
    viewer: User | None = None,
    commit: bool = True,
) -> None:
    """telemetry.record_event() içinden çağrılır. Reward varsa state günceller."""
    try:
        reward = REWARD_BY_EVENT.get(event.event_type, 0.0)
        if reward == 0.0:
            return  # impression veya tanınmayan event — no-op
        ctx = extract_context(viewer, now=event.created_at)
        update(db, card_id=event.card_id, context=ctx, reward=reward, commit=commit)
    except Exception as e:  # noqa: BLE001
        logger.warning("bandit.record_event_hook hata: %s", e)
