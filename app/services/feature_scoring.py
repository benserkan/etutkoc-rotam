"""Katman 5 — Mamdani Fuzzy skorlama servisi.

Her FeatureCard için **prominence** (0-100) skoru üretir. Bu skor anasayfada
hangi kartın hangi sırada görüneceğine karar verir.

5 girdi sinyali → 1 çıktı (prominence):
  1. freshness    — `introduced_at` üzerinden gün cinsinden tazelik
  2. priority     — admin'in elle verdiği stratejik öncelik (1..5)
  3. tier_strength— düzey gücü (core=1.0, enhancement=0.65, experimental=0.30)
  4. completeness — mockup_type + benefits + demo_slug bütünlük oranı (0..1)
  5. role_match   — ziyaretçinin rolü target_roles'da mı (0/1)

Mamdani sup-min kompozisyon + centroid defuzzification (fuzzy_core).

Kullanım:
    from app.services.feature_scoring import score_card
    breakdown = score_card(card, role="student")
    print(breakdown.prominence)        # 0..100
    print(breakdown.inputs)            # her sinyalin crisp değeri
    print(breakdown.firings_sorted)    # ateşlenen kurallar + güç

Sert kurallar (skoru ezer, scoring'in DIŞINDA uygulanır):
  - manual_pin=True       → her zaman tepe
  - manual_hide=True      → asla gösterme
  - status != PUBLISHED   → asla gösterme
  - mockup_type boş       → landing'e çıkmaz
Bu kontratlar `get_for_landing`'de uygulanır; scoring sadece sıralama içindir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from app.models import FeatureCard, FeatureTier, UserRole
from app.services.fuzzy_core import (
    FuzzyRule,
    FuzzyVariable,
    InferenceResult,
    MamdaniInference,
    triangle,
    trapezoid,
)


# ============================================================
# 1) Girdi tanımları (linguistic variables + üyelik fonksiyonları)
# ============================================================


def _build_engine() -> MamdaniInference:
    """Mamdani motorunu kuruluyor; module-level tek instance — thread-safe (saf okuma)."""

    # --- freshness (gün cinsinden) ------------------------------
    # yeni (0-30), yakın (15-90), yerleşik (60-240), eski (180+)
    freshness = FuzzyVariable("freshness", (0, 730))
    freshness.add_set("yeni",      trapezoid(0, 0, 14, 45))
    freshness.add_set("yakin",     triangle(20, 60, 120))
    freshness.add_set("yerlesik",  triangle(75, 150, 270))
    freshness.add_set("eski",      trapezoid(180, 365, 730, 730))

    # --- priority (1..5) ---------------------------------------
    priority = FuzzyVariable("priority", (1, 5))
    priority.add_set("dusuk",  trapezoid(1, 1, 1.5, 2.5))
    priority.add_set("orta",   triangle(2, 3, 4))
    priority.add_set("yuksek", trapezoid(3.5, 4.5, 5, 5))

    # --- tier_strength (0..1) ----------------------------------
    tier_strength = FuzzyVariable("tier_strength", (0, 1))
    tier_strength.add_set("zayif", trapezoid(0, 0, 0.35, 0.6))
    tier_strength.add_set("guclu", trapezoid(0.55, 0.8, 1, 1))

    # --- completeness (0..1) -----------------------------------
    completeness = FuzzyVariable("completeness", (0, 1))
    completeness.add_set("eksik", trapezoid(0, 0, 0.25, 0.55))
    completeness.add_set("zengin", trapezoid(0.45, 0.75, 1, 1))

    # --- role_match (0 veya 1, ama trapezoid soft) -------------
    role_match = FuzzyVariable("role_match", (0, 1))
    role_match.add_set("yok", trapezoid(0, 0, 0.1, 0.4))
    role_match.add_set("var", trapezoid(0.6, 0.9, 1, 1))

    # --- çıktı: prominence (0..100) ----------------------------
    prominence = FuzzyVariable("prominence", (0, 100))
    prominence.add_set("gizle", trapezoid(0, 0, 8, 22))
    prominence.add_set("dusuk", triangle(15, 32, 50))
    prominence.add_set("orta",  triangle(40, 55, 72))
    prominence.add_set("yuksek", triangle(60, 78, 92))
    prominence.add_set("tepe",  trapezoid(82, 92, 100, 100))

    # ============================================================
    # 2) Kural tabanı — 14 kural, pratik desenlere göre
    # ============================================================

    rules: list[FuzzyRule] = [
        # Tepe: yeni + yüksek öncelik + zengin içerik
        FuzzyRule(
            [("freshness", "yeni"), ("priority", "yuksek"), ("completeness", "zengin")],
            ("prominence", "tepe"),
        ),
        # Yüksek: yeni + yüksek öncelik (içerik ne olursa olsun)
        FuzzyRule(
            [("freshness", "yeni"), ("priority", "yuksek")],
            ("prominence", "yuksek"),
        ),
        # Yüksek: yeni + zengin (orta önceliği bile öne çıkar)
        FuzzyRule(
            [("freshness", "yeni"), ("completeness", "zengin")],
            ("prominence", "yuksek"),
        ),
        # Yüksek: yakın + yüksek öncelik
        FuzzyRule(
            [("freshness", "yakin"), ("priority", "yuksek")],
            ("prominence", "yuksek"),
        ),
        # Orta: yakın + orta öncelik
        FuzzyRule(
            [("freshness", "yakin"), ("priority", "orta")],
            ("prominence", "orta"),
        ),
        # Orta: yerleşik + zengin + güçlü düzey
        FuzzyRule(
            [
                ("freshness", "yerlesik"),
                ("completeness", "zengin"),
                ("tier_strength", "guclu"),
            ],
            ("prominence", "orta"),
        ),
        # Orta: rol uyumu var + orta öncelik (+ herhangi tazelik)
        FuzzyRule(
            [("role_match", "var"), ("priority", "orta")],
            ("prominence", "orta"),
        ),
        # Düşük: orta öncelik + eksik içerik
        FuzzyRule(
            [("priority", "orta"), ("completeness", "eksik")],
            ("prominence", "dusuk"),
        ),
        # Düşük: yerleşik + zayıf düzey
        FuzzyRule(
            [("freshness", "yerlesik"), ("tier_strength", "zayif")],
            ("prominence", "dusuk"),
        ),
        # Düşük: eski + orta öncelik
        FuzzyRule(
            [("freshness", "eski"), ("priority", "orta")],
            ("prominence", "dusuk"),
        ),
        # Düşük: rol uyumu yok + orta öncelik (rol mismatch yumuşak ceza)
        FuzzyRule(
            [("role_match", "yok"), ("priority", "orta")],
            ("prominence", "dusuk"),
            weight=0.6,
        ),
        # Gizle: eski + düşük öncelik
        FuzzyRule(
            [("freshness", "eski"), ("priority", "dusuk")],
            ("prominence", "gizle"),
        ),
        # Gizle: düşük öncelik + zayıf düzey + eksik içerik
        FuzzyRule(
            [
                ("priority", "dusuk"),
                ("tier_strength", "zayif"),
                ("completeness", "eksik"),
            ],
            ("prominence", "gizle"),
        ),
        # Gizle: rol uyumu yok + düşük öncelik
        FuzzyRule(
            [("role_match", "yok"), ("priority", "dusuk")],
            ("prominence", "gizle"),
        ),
    ]

    return MamdaniInference(
        input_vars={
            "freshness": freshness,
            "priority": priority,
            "tier_strength": tier_strength,
            "completeness": completeness,
            "role_match": role_match,
        },
        output_var=prominence,
        rules=rules,
        resolution=200,
    )


# Module-level singleton — kurallar değişmiyor, her çağrı için yeniden inşa etmeye gerek yok.
_ENGINE: MamdaniInference = _build_engine()


# ============================================================
# Crisp girdi çıkartma (Card → 5 sayı)
# ============================================================


_TIER_STRENGTH: dict[str, float] = {
    FeatureTier.CORE.value: 1.0,
    FeatureTier.ENHANCEMENT.value: 0.65,
    FeatureTier.EXPERIMENTAL.value: 0.30,
}


def _days_since(introduced_at: datetime, now: datetime) -> float:
    """introduced_at'tan now'a kaç gün geçmiş (negatif olamaz)."""
    if introduced_at.tzinfo is None:
        introduced_at = introduced_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = (now - introduced_at).total_seconds()
    return max(0.0, delta / 86400.0)


def _completeness(card: FeatureCard) -> float:
    """3 zenginleştirme alanının (mockup_type, benefits, demo_slug) varlık oranı."""
    present = 0
    if card.mockup_type:
        present += 1
    if card.benefits:  # property, JSON listesi
        present += 1
    if card.demo_slug:
        present += 1
    return present / 3.0


def _role_match(card: FeatureCard, role: str | None) -> float:
    """Ziyaretçinin rolü target_roles'da varsa 1, yoksa 0. Hiç hedef yok → 0.5 (nötr)."""
    targets = card.target_roles  # property, list[str]
    if not targets:
        return 0.5
    if role is None:
        # Anonim ziyaretçi: hedefte STUDENT veya TEACHER var mı → ana kitleye yakınsa 1
        public_roles = {UserRole.STUDENT.value, UserRole.TEACHER.value}
        return 1.0 if any(r in public_roles for r in targets) else 0.3
    return 1.0 if role in targets else 0.0


# ============================================================
# Public API
# ============================================================


@dataclass
class ScoreBreakdown:
    """Bir kartın skor detayı — admin panelinde gösterilir."""
    prominence: float                 # 0..100 (Mamdani crisp output)
    inputs: dict[str, float]          # her sinyalin crisp değeri
    fired_rules: list[tuple[str, float]] = field(default_factory=list)

    @property
    def prominence_int(self) -> int:
        return int(round(self.prominence))


def score_card(
    card: FeatureCard,
    *,
    role: str | None = None,
    now: datetime | None = None,
) -> ScoreBreakdown:
    """Verilen kart için Mamdani fuzzy skoru üret.

    role: viewer'ın UserRole.value değeri ya da None (anonim ziyaretçi)
    now : "şimdi" zamanı; test edilebilirlik için override edilebilir
    """
    if now is None:
        now = datetime.now(timezone.utc)
    inputs = {
        "freshness": _days_since(card.introduced_at, now),
        "priority": float(card.strategic_priority or 3),
        "tier_strength": _TIER_STRENGTH.get(card.tier, 0.5),
        "completeness": _completeness(card),
        "role_match": _role_match(card, role),
    }
    result: InferenceResult = _ENGINE.infer(inputs)
    fired = [
        (rule.label(), strength)
        for rule, strength in result.firings
        if strength > 0
    ]
    fired.sort(key=lambda x: x[1], reverse=True)
    return ScoreBreakdown(
        prominence=result.crisp,
        inputs=inputs,
        fired_rules=fired,
    )


def score_cards(
    cards: Iterable[FeatureCard],
    *,
    role: str | None = None,
    now: datetime | None = None,
) -> list[tuple[FeatureCard, ScoreBreakdown]]:
    """Birden çok kart için skor + breakdown listesi (sıralama yapılmaz)."""
    if now is None:
        now = datetime.now(timezone.utc)
    return [(c, score_card(c, role=role, now=now)) for c in cards]
