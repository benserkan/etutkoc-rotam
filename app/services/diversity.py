"""Katman 8 — Çeşitlilik Filtresi (MMR — Maximal Marginal Relevance).

Bandit + fuzzy hibrit sıralaması "en yüksek skoru tepeye" mantığıyla çalışır;
ancak benzer 3-4 kart üst üste yığılırsa kullanıcı sıkılır (aynı domain'den
3 art arda gibi). MMR algoritması, **alaka** ile **çeşitlilik** arasında
yumuşak bir denge kurar:

    MMR(d) = λ · alaka(d) − (1−λ) · max{ benzerlik(d, dj) | dj ∈ Seçilmiş }

Bizim sistemde:
  - alaka = hibrit fuzzy+bandit skoru (0..1 normalize)
  - benzerlik = Jaccard(card_a_features, card_b_features)
  - card_features kümesi: domain, tier, target_roles, category_label,
    ilk 3 benefit kelimesi
  - λ = 0.7 → alaka %70 ağırlık (çeşitlilik %30 ile düzeltir, %50 değil)

Sade Türkçe arayüzde:
  - "Çeşitlilik puanı" = anasayfanın 5 kartı arasındaki ortalama farklılık
    (1.0 = tamamen farklı temalar; 0.0 = hepsi aynı)
  - Kart-bazlı "tema benzerliği" = bir kartın üst kartla benzerlik skoru
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

from app.models import FeatureCard


# ============================================================
# Sabitler
# ============================================================

# MMR trade-off: 1.0 = sadece alaka, 0.0 = sadece çeşitlilik.
# 0.7 → alaka ağırlıklı ama çeşitlilik etkisi belirgin.
DEFAULT_LAMBDA = 0.7

# Tagline'dan kelime çıkarmak için (her benefit/category için)
_WORD_RE = re.compile(r"[a-zçğıöşü0-9]+", re.IGNORECASE | re.UNICODE)
_STOP_WORDS = {
    "ve", "ile", "için", "bir", "bu", "o", "ki", "de", "da", "mı", "mi",
    "mu", "mü", "ya", "ne", "nasıl", "her", "tek", "hep", "the", "and",
    "or", "of", "to", "a", "an",
}


# ============================================================
# Feature set + Jaccard
# ============================================================


def _tokens(text: str | None, *, max_n: int = 3) -> list[str]:
    """Metinden anlamlı kök kelimeleri çıkar (lower + stop-word filter)."""
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in _WORD_RE.findall(text.lower()):
        if m in _STOP_WORDS or len(m) < 3:
            continue
        if m in seen:
            continue
        seen.add(m)
        out.append(m)
        if len(out) >= max_n:
            break
    return out


def feature_set(card: FeatureCard) -> set[str]:
    """Kart için fonksiyonel özellik kümesi — Jaccard hesabı için.

    Namespace prefix'leri (domain:/tier:/role:/cat:/kw:) farklı tipte özelliklerin
    sahte eşleşmesini engeller (örn. "general" hem domain hem benefit olmaz).
    """
    feats: set[str] = set()

    # Sert sinyaller
    if card.domain:
        feats.add(f"domain:{card.domain}")
    if card.tier:
        feats.add(f"tier:{card.tier}")

    # target_roles — property, list[str]
    try:
        roles = card.target_roles or []
    except Exception:
        roles = []
    for r in roles:
        feats.add(f"role:{r}")

    # Kategori etiketinden 1-2 kelime
    if card.category_label:
        for tok in _tokens(card.category_label, max_n=2):
            feats.add(f"cat:{tok}")

    # Benefit kelimeleri (ilk 3 chip'in ilk anlamlı kelimesi)
    try:
        benefits = card.benefits or []
    except Exception:
        benefits = []
    for b in benefits[:3]:
        toks = _tokens(b, max_n=2)
        for t in toks:
            feats.add(f"kw:{t}")

    return feats


def jaccard(a: set[str], b: set[str]) -> float:
    """|A ∩ B| / |A ∪ B|. Her ikisi boşsa 0.0."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


def similarity(card_a: FeatureCard, card_b: FeatureCard) -> float:
    """İki kartın Jaccard benzerliği (0..1)."""
    return jaccard(feature_set(card_a), feature_set(card_b))


# ============================================================
# MMR rerank
# ============================================================


def mmr_rerank(
    cards: Sequence[FeatureCard],
    relevance: dict[int, float],
    *,
    k: int | None = None,
    lambda_param: float = DEFAULT_LAMBDA,
) -> list[FeatureCard]:
    """Karta listesini MMR ile yeniden sırala.

    cards: aday kart listesi (FeatureCard)
    relevance: card.id → alaka skoru (0..1)
    k: kaç kart döndür; None → hepsi
    lambda_param: 0..1 (alaka vs çeşitlilik trade-off)

    Sıralama:
      1. İlk kartı en yüksek relevance'a göre seç
      2. Sonrakileri: MMR(d) = λ·rel(d) − (1−λ)·max_sim(d, seçilmişlerden)

    Aynı relevance puanı varsa orijinal sıra (sıralı geldi varsayımı) korunur.
    """
    if not cards:
        return []
    if k is None:
        k = len(cards)

    # Feature set'leri tek seferde hesapla (ucuz değil, kart sayısı az)
    feats: dict[int, set[str]] = {c.id: feature_set(c) for c in cards}
    rel: dict[int, float] = {c.id: relevance.get(c.id, 0.0) for c in cards}

    remaining = list(cards)
    selected: list[FeatureCard] = []

    # İlk seçim: en yüksek alaka
    remaining.sort(key=lambda c: -rel[c.id])
    selected.append(remaining.pop(0))

    while remaining and len(selected) < k:
        best_score = -float("inf")
        best_idx = 0
        for i, c in enumerate(remaining):
            r = rel[c.id]
            # Seçilmiş kartlarla maks benzerlik
            max_sim = 0.0
            f_c = feats[c.id]
            for s in selected:
                f_s = feats[s.id]
                sim = jaccard(f_c, f_s)
                if sim > max_sim:
                    max_sim = sim
            mmr = lambda_param * r - (1.0 - lambda_param) * max_sim
            if mmr > best_score:
                best_score = mmr
                best_idx = i
        selected.append(remaining.pop(best_idx))

    return selected


# ============================================================
# Genel çeşitlilik metriği (admin paneli için "puan")
# ============================================================


def diversity_score(cards: Iterable[FeatureCard]) -> float:
    """Bir kart listesindeki ortalama PAIRWISE farklılık.

    Returns: 0..1 (1 = hiç ortak özellik yok, 0 = hepsi aynı)
    Tek kart veya boş → 1.0 (kıyas yok, çeşitlilik bozulmuyor)
    """
    cs = list(cards)
    if len(cs) < 2:
        return 1.0
    feats = [feature_set(c) for c in cs]
    n = len(cs)
    total_dissim = 0.0
    pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            total_dissim += 1.0 - jaccard(feats[i], feats[j])
            pairs += 1
    return total_dissim / pairs if pairs else 1.0


def neighbor_similarity(
    cards: Sequence[FeatureCard],
) -> dict[int, float]:
    """Sıralı listede her kartın bir-önceki kartla benzerliği.

    İlk karta None döner (öncesi yok). UI'da "üst kart" bağlamı gösterir.

    Returns: {card_id: similarity (0..1)} — ilk kart için 0.0
    """
    out: dict[int, float] = {}
    feats: list[tuple[int, set[str]]] = [(c.id, feature_set(c)) for c in cards]
    for i, (cid, f) in enumerate(feats):
        if i == 0:
            out[cid] = 0.0
        else:
            out[cid] = jaccard(feats[i - 1][1], f)
    return out
