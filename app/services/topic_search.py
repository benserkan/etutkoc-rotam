"""Konu arama — sezgisel, yazım hatasına dayanıklı (2026-10-16).

Saha: görev kutusunda "milli desten" hiçbir şey bulmuyordu. Eski arama sorguyu
TEK PARÇA ve harfi harfine konu adında arıyordu; "Millî Bir Destan" araya giren
"Bir" sözcüğü, î harfi ve "desten" yazım hatası yüzünden kaçıyordu.

Kurallar (deterministik, yapay zekâsız, anlık):
  · sorgu sözcüklere bölünür, SIRA ÖNEMSİZ ("destan milli" = "milli destan")
  · her sözcük konu adının, temasının (üst başlık), dersinin ya da kaynak
    (kitap/bölüm) adının bir sözcüğüne uymalı:
      tam eşleşme > baş harfler ("trig" → trigonometri) > yazım hatası
      (1 harf: 4-6 harfli, 2 harf: 7+ harfli sözcükte) > kısaltma (ebob → OBEB)
  · konu adındaki eşleşme, tema/ders/kitap adındaki eşleşmeden ağır basar
  · tüm sözcükler uyan sonuçlar önce; hiç tam uyan yoksa bir sözcüğü eksik
    olanlar düşük skorla gösterilir (koç yine bir şey görür)
  · tema adı yazılırsa ("sözün ezgisi") temanın alt konuları gelir
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.curriculum_mapping import normalize

_STOP = {"ve", "ile", "bir", "de", "da", "test", "testi", "soru", "konu", "konusu", "unite", "tema"}
# Kısaltma / akronim köprüsü (task_topic_link ile aynı mantık)
_ABBREV: dict[str, tuple[str, ...]] = {
    "ebob": ("obeb", "okek", "ebob", "ekok", "carpanlar"),
    "ebok": ("obeb", "okek", "ebob", "ekok", "carpanlar"),
    "ekok": ("obeb", "okek", "ebob", "ekok", "carpanlar"),
    "obeb": ("obeb", "okek", "carpanlar"),
    "okek": ("obeb", "okek", "carpanlar"),
    "trigo": ("trigonometri", "trigonometrik"),
    "inkilap": ("inkilap", "inkilaplari"),
}

W_NAME, W_SOURCE, W_THEME, W_SUBJECT = 1.0, 0.75, 0.7, 0.5


def tokens(text: str | None) -> list[str]:
    return [w for w in normalize(text).split() if w and w not in _STOP]


def _osa(a: str, b: str, cap: int) -> int:
    """Damerau (bitişik harf yer değiştirme dahil) mesafesi; `cap`ı aşınca erken çıkar."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev2: list[int] | None = None
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        best = cur[0]
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                v = min(v, prev2[j - 2] + 1)
            cur[j] = v
            best = min(best, v)
        if best > cap:
            return cap + 1
        prev2, prev = prev, cur
    return prev[-1]


def token_score(q: str, w: str) -> float:
    """Tek sorgu sözcüğü × tek aday sözcüğü → 0..1."""
    if q == w:
        return 1.0
    if w in _ABBREV.get(q, ()):
        return 0.9
    if len(q) >= 2 and w.startswith(q):
        return 0.92 if len(q) >= 3 else 0.6
    if len(w) >= 4 and q.startswith(w):
        return 0.5
    if len(q) >= 4:
        cap = 1 if len(q) <= 6 else 2
        if _osa(q, w, cap) <= cap:
            return 0.72
        # yazarken yarım kalmış + hatalı ("destn" → "destan"ın başı)
        if len(w) > len(q) and _osa(q, w[: len(q)], 1) <= 1:
            return 0.62
    return 0.0


@dataclass
class SearchDoc:
    key: int
    name: str
    theme: str | None = None
    subject: str | None = None
    extra: str = ""            # kitap/bölüm adları
    bonus: float = 0.0         # çağıranın sıralama ipucu (kendi sınıfı, kaynağı var…)


@dataclass
class SearchHit:
    key: int
    score: float
    full: bool                 # tüm sorgu sözcükleri uydu
    via_theme: bool            # en güçlü eşleşme tema adından


def search(query: str, docs: list[SearchDoc], limit: int = 25) -> list[SearchHit]:
    q = tokens(query)
    if not q:
        return []
    out: list[SearchHit] = []
    partial: list[SearchHit] = []
    for d in docs:
        fields = (
            (tokens(d.name), W_NAME),
            (tokens(d.extra), W_SOURCE),
            (tokens(d.theme), W_THEME),
            (tokens(d.subject), W_SUBJECT),
        )
        total = 0.0
        matched = 0
        name_hits = theme_hits = 0
        for qt in q:
            best = 0.0
            best_field = -1
            for idx, (ws, weight) in enumerate(fields):
                for w in ws:
                    s = token_score(qt, w) * weight
                    if s > best:
                        best, best_field = s, idx
            if best > 0:
                matched += 1
                total += best
                if best_field == 0:
                    name_hits += 1
                elif best_field == 2:
                    theme_hits += 1
        if matched == 0:
            continue
        full = matched == len(q)
        if not full and name_hits == 0:
            continue   # kısmi eşleşme yalnız konu ADINA değiyorsa anlamlı
        score = total / len(q)
        if not full:
            score *= 0.55
        name_toks = tokens(d.name)
        if name_toks and name_hits == len(q):
            # sözcükler konu adında baştan ve sırayla geçiyorsa (yazarken) ekstra
            joined = " ".join(name_toks)
            if joined.startswith(" ".join(q)[: max(3, len(" ".join(q)) - 2)]):
                score += 0.08
            score += 0.04 * (len(q) / len(name_toks))   # kısa/öz konu adı önde
        hit = SearchHit(key=d.key, score=score + d.bonus, full=full, via_theme=theme_hits > name_hits)
        (out if full else partial).append(hit)
    out.sort(key=lambda h: -h.score)
    # Tam uyan az ise kısmi uyanlar da (sonda) gösterilir: "hız ivme" iki ayrı konuya
    # ait sözcükler içerir — koç ikisini de görsün.
    if len(out) < 3:
        partial.sort(key=lambda h: -h.score)
        out += partial[: max(0, limit - len(out))]
    return out[:limit]
