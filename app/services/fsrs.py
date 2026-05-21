"""Stage 12 — FSRS-light spaced repetition.

FSRS (Free Spaced Repetition Scheduler) Anki'nin yeni varsayılan algoritması;
17-parametreli versiyonun basitleştirilmiş bir varyantı.

Bu modül topic-bazlı tekrar kartları için aşağıdakileri hesaplar:
- **stability** (S): kartın hatırlanma kapasitesi, gün cinsinden
- **difficulty** (D): kartın 1-10 arası zorluk seviyesi
- **state**: NEW → LEARNING/REVIEW/RELEARNING
- **due_at**: bir sonraki tekrar zamanı (S * ln(1/retention) civarı)

Rating skalası (Anki + FSRS standardı):
- 1 = AGAIN   (hatırlamadı) → relearning
- 2 = HARD    (zar zor hatırladı)
- 3 = GOOD    (iyi hatırladı)
- 4 = EASY    (kolayca hatırladı)

İlk değerlendirmede (NEW state):
- AGAIN: S=0.4 D=7 (kısa öğrenme adımı)
- HARD:  S=1.2 D=6
- GOOD:  S=3.0 D=5
- EASY:  S=7.0 D=4

Tekrarda (REVIEW state):
- elapsed_days = (now - last_reviewed).days
- retrievability R = exp(-elapsed/S)
- AGAIN (lapse): S = max(0.5, S_old * 0.3), state=RELEARNING
- HARD/GOOD/EASY: S = S_old * (1 + e^(0.1*(4-D)) * (rating-1) * 1.4 * (1 + (1-R)*0.6))

Default request_retention = 0.9 (Anki'nin önerisi). Bu, ortalama %90 doğru
hatırlama oranını hedefler.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


# ============================================================================
# Algoritma parametreleri (sade)
# ============================================================================

REQUEST_RETENTION = 0.9
DEFAULT_LEARNING_STEPS_MIN = [10, 60]  # AGAIN sonrası 10dk, sonra 1 saat (in-session)
MIN_INTERVAL_DAYS = 1
MAX_INTERVAL_DAYS = 365 * 3  # 3 yıl üst sınır


# Rating → enum-friendly sabitler
RATING_AGAIN = 1
RATING_HARD = 2
RATING_GOOD = 3
RATING_EASY = 4
VALID_RATINGS = (RATING_AGAIN, RATING_HARD, RATING_GOOD, RATING_EASY)

RATING_LABELS_TR = {
    RATING_AGAIN: "Tekrar",
    RATING_HARD: "Zor",
    RATING_GOOD: "İyi",
    RATING_EASY: "Kolay",
}


# State sabitleri
STATE_NEW = "new"
STATE_LEARNING = "learning"
STATE_REVIEW = "review"
STATE_RELEARNING = "relearning"
VALID_STATES = (STATE_NEW, STATE_LEARNING, STATE_REVIEW, STATE_RELEARNING)


# ============================================================================
# Dataclass ile çıktı (modelden bağımsız test için)
# ============================================================================


@dataclass
class FsrsState:
    """Bir kartın FSRS durumu — model bağımsız temsil."""
    stability: float
    difficulty: float
    state: str
    last_reviewed_at: datetime | None = None
    review_count: int = 0
    lapse_count: int = 0

    def copy(self) -> "FsrsState":
        return FsrsState(
            stability=self.stability,
            difficulty=self.difficulty,
            state=self.state,
            last_reviewed_at=self.last_reviewed_at,
            review_count=self.review_count,
            lapse_count=self.lapse_count,
        )


@dataclass
class FsrsResult:
    """compute_next çıktısı: yeni durum + due_at + scheduled_days."""
    stability: float
    difficulty: float
    state: str
    scheduled_days: float
    due_at: datetime
    elapsed_days: float


# ============================================================================
# Algoritma çekirdeği
# ============================================================================


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _initial_stability(rating: int) -> float:
    """İlk değerlendirmede stability (gün)."""
    table = {
        RATING_AGAIN: 1.0,
        RATING_HARD: 4.0,
        RATING_GOOD: 10.0,
        RATING_EASY: 22.0,
    }
    return table[rating]


def _initial_difficulty(rating: int) -> float:
    """İlk değerlendirmede difficulty (1-10 arası)."""
    table = {
        RATING_AGAIN: 7.0,
        RATING_HARD: 6.0,
        RATING_GOOD: 5.0,
        RATING_EASY: 4.0,
    }
    return table[rating]


def _difficulty_update(old_d: float, rating: int) -> float:
    """Rating'e göre difficulty artar/azalır. Aralık [1, 10]."""
    delta = {
        RATING_AGAIN: 1.5,
        RATING_HARD: 0.5,
        RATING_GOOD: 0.0,
        RATING_EASY: -0.5,
    }[rating]
    return _clip(old_d + delta, 1.0, 10.0)


def _stability_update(old_s: float, new_d: float, rating: int, elapsed_days: float) -> float:
    """Rating + retrievability'ye göre yeni stability."""
    if rating == RATING_AGAIN:
        # Lapse: stability büyük oranda düşer, ama tamamen sıfırlanmaz
        return max(0.5, old_s * 0.3)
    # Retrievability — son tekrardan beri ne kadar "unutuldu"
    s_safe = max(old_s, 0.1)
    r = math.exp(-elapsed_days / s_safe)
    # Stability artış faktörü:
    #  - kolay zorluk (D küçük) → daha hızlı büyür
    #  - rating yüksek → daha hızlı büyür
    #  - retention düşük (zar zor hatırladı) → büyüme bonusu
    growth = math.exp(0.1 * (4.0 - new_d)) * (rating - 1) * 1.4 * (1.0 + (1.0 - r) * 0.6)
    return old_s * (1.0 + growth)


def _scheduled_days(stability: float, retention: float = REQUEST_RETENTION) -> float:
    """Stability + hedef retention'a göre kaç gün sonra hatırlama testi."""
    # R(t) = exp(-t/S) => t = -S * ln(R)
    days = -stability * math.log(retention)
    return _clip(days, MIN_INTERVAL_DAYS, MAX_INTERVAL_DAYS)


def compute_next(
    state: FsrsState,
    rating: int,
    now: datetime,
    retention: float = REQUEST_RETENTION,
) -> FsrsResult:
    """Mevcut state + rating → yeni state + due_at.

    `state.last_reviewed_at` None ise (NEW state) ilk değerlendirme kabul edilir.

    Raises:
        ValueError: rating geçersiz veya state geçersiz.
    """
    if rating not in VALID_RATINGS:
        raise ValueError(f"Geçersiz rating: {rating!r}. 1-4 arası bekleniyor.")
    if state.state not in VALID_STATES:
        raise ValueError(f"Geçersiz state: {state.state!r}")

    # now timezone-aware olmalı; naive ise UTC varsay
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # NEW kart → ilk değerlendirme (last_reviewed_at None)
    if state.state == STATE_NEW or state.last_reviewed_at is None:
        new_s = _initial_stability(rating)
        new_d = _initial_difficulty(rating)
        elapsed = 0.0
        new_state = STATE_REVIEW if rating != RATING_AGAIN else STATE_LEARNING
    else:
        last = state.last_reviewed_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = max(0.0, (now - last).total_seconds() / 86400.0)
        new_d = _difficulty_update(state.difficulty, rating)
        new_s = _stability_update(state.stability, new_d, rating, elapsed)
        if rating == RATING_AGAIN:
            new_state = STATE_RELEARNING
        else:
            new_state = STATE_REVIEW

    sched = _scheduled_days(new_s, retention)
    due = now + timedelta(days=sched)
    return FsrsResult(
        stability=new_s,
        difficulty=new_d,
        state=new_state,
        scheduled_days=sched,
        due_at=due,
        elapsed_days=elapsed,
    )


def apply_result_to_state(state: FsrsState, rating: int, result: FsrsResult) -> FsrsState:
    """compute_next sonucunu mevcut state'e işle (model güncellemesi öncesi)."""
    new = state.copy()
    new.stability = result.stability
    new.difficulty = result.difficulty
    new.state = result.state
    new.last_reviewed_at = result.due_at - timedelta(days=result.scheduled_days)
    new.review_count = state.review_count + 1
    if rating == RATING_AGAIN:
        new.lapse_count = state.lapse_count + 1
    return new


def is_due(state: FsrsState, due_at: datetime | None, now: datetime) -> bool:
    """Kart vadesi geçtiyse (due_at <= now) tekrar zamanı."""
    if state.state == STATE_NEW:
        return True
    if due_at is None:
        return True
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return due_at <= now
