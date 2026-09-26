"""Video Sepeti — oynatma listesini KONU gruplarına bölen algoritma.

Hocalar başlığı farklı yazar ("Üslü Sayılar 1 | TYT Kampı 3. Gün", "TYT
Matematik - Üslü Sayılar Konu Anlatımı", "Checkpoint 4"), ama sıra sabittir:
konu anlatımı → (bazen) soru çözümü/checkpoint → sıradaki konu. Algoritma bu
sıraya dayanır:

  1. ROL — başlıktaki anahtar sözcükten: soru çözümü / tekrar-özet / diğer
     (tanıtım, canlı yayın, program) / varsayılan konu anlatımı.
  2. KONU — başlık, öğrencinin o dersteki müfredat konularıyla deterministik
     eşleşir (curriculum_mapping anahtarları; konu adının TÜM sözcükleri başlıkta
     geçmeli; en uzun eşleşen kazanır, eşit iki aday = belirsiz → konu yok).
  3. İLERİ TAŞIMA — konu bulunamayan soru/tekrar videosu (checkpoint) ÖNCEKİ
     konunun grubuna katılır. Konusu bulunamayan anlatım videosu başlığından
     temizlenmiş etiketle kendi grubunu açar; aynı etiket ardışıksa birleşir.
  4. (Opsiyonel) AI — konusuz kalan grupların etiketleri TEK Gemini çağrısıyla
     kapalı listeden (yalnız aday konular) konuya bağlanır; kişisel veri yok
     (ücretsiz anahtar sırası). Başarısızsa sessizce atlanır.
  5. Aynı konuya düşen gruplar birleşir (ilk görüldüğü yerde durur).

Çıktı yalnız ÖNERİDİR: koç sepette grubu/konuyu/rolü düzeltir, video çıkarır.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import re
from dataclasses import dataclass, field

from app.models import Topic
from app.services import gemini
from app.services.curriculum_mapping import _canon_from_norm, _parse_json, normalize

logger = logging.getLogger(__name__)

# normalize() sonrası (küçük harf, Türkçe sade) aranır; sözcük sınırıyla.
_ROLE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("diger", re.compile(
        r"\b(tanitim|fragman|canli yayin|canli ders|yayin programi|kamp programi|ders programi|"
        r"calisma programi|nasil calisilir|motivasyon|duyuru|soru cevap|kitap tanitimi|trailer)\b")),
    ("soru", re.compile(
        r"\b(soru cozum\w*|soru cozumu|checkpoint|check point|test cozum\w*|cikmis sorular?|"
        r"osym sorular?\w*|yeni nesil sorular?|soru bankasi cozum\w*|pekistirme|"
        r"kazanim testi|alistirma\w*|ornek sorular?|soru analizi|cozumlu sorular?|"
        r"soru kampi|sorulari)\b")),
    ("tekrar", re.compile(
        r"\b(genel tekrar|tekrar\w*|ozet\w*|full tekrar|son tekrar|bir videoda|tek videoda|"
        r"kisa tekrar|hizli tekrar|harita)\b")),
]

# Etiket temizlerken atılan sözcükler (sınav/ders/program gürültüsü)
_NOISE = {
    "tyt", "ayt", "lgs", "yks", "kpss", "msu", "dgs", "matematik", "mat", "geometri",
    "fizik", "kimya", "biyoloji", "turkce", "edebiyat", "tarih", "cografya", "felsefe",
    "din", "kulturu", "fen", "bilimleri", "sosyal", "ingilizce", "kamp", "kampi",
    "gun", "gunu", "ders", "dersi", "bolum", "part", "konu", "anlatim", "anlatimi",
    "video", "sezon", "full", "hd", "pdf", "yeni", "mufredat", "sinif", "sinav",
    "hazirlik", "2023", "2024", "2025", "2026", "2027", "hoca", "hocasi",
}
_SPLIT_RE = re.compile(r"\s*(?:[|•·/\\]|\s[-–—:]\s|#)\s*")


@dataclass
class SegVideo:
    """Girdi: bir oynatma listesi videosu (sıra = liste sırası)."""
    key: str  # çağıranın kimliği (youtube_id)
    title: str


@dataclass
class SegItem:
    key: str
    role: str
    topic_id: int | None
    group_key: str
    group_label: str
    order: int


@dataclass
class _Group:
    label: str
    topic_id: int | None
    label_key: str
    members: list[int] = field(default_factory=list)  # girdi indeksleri


def detect_role(title: str) -> str:
    n = normalize(title)
    for role, pat in _ROLE_PATTERNS:
        if pat.search(n):
            return role
    return "anlatim"


def clean_label(title: str) -> str:
    """Başlıktan konu etiketi: ayraçlara böl, gürültü/sayı parçalarını at,
    ilk anlamlı parçayı döndür (koça görünen grup adı)."""
    parts = [p.strip() for p in _SPLIT_RE.split(title or "") if p and p.strip()]
    best = ""
    for p in parts:
        toks = [t for t in normalize(p).split() if t not in _NOISE and not t.isdigit()]
        if len(" ".join(toks)) >= 3:
            best = p
            break
    lab = best or (title or "").strip()
    # "Konu Anlatımı", "Soru Çözümü", sonda parça numarası ("... 2", "... -3") at
    lab = re.sub(r"(?i)\b(konu anlat[ıi]m[ıi]|soru [çc][öo]z[üu]m[üu]?|part)\b", "", lab)
    lab = re.sub(r"[\s\-–—:#(]*\d+\s*\)?\s*$", "", lab).strip(" -–—:|()")
    return (lab or (title or "Video")).strip()[:120]


def _label_key(label: str) -> str:
    toks = [t for t in normalize(label).split() if t not in _NOISE and not t.isdigit()]
    return _canon_from_norm(" ".join(toks))


_SUFFIXES = ("larin", "lerin", "lari", "leri", "nin", "nun", "lar", "ler",
             "si", "su", "in", "un", "i", "u")
_ALT_SPLIT_RE = re.compile(r"\s*(?:,|\bve\b|\bile\b)\s*")


def _stem(tok: str) -> str:
    """Türkçe ek atma (normalize sonrası, kaba): newtonun/newtonin → newton,
    enerjisi/enerjinin → enerj, atislar → atis. Kök en az 4 harf kalır."""
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIXES:
            if tok.endswith(suf) and len(tok) - len(suf) >= 4:
                tok = tok[: -len(suf)]
                changed = True
                break
    return tok


def _stems(text_norm: str) -> set[str]:
    return {_stem(t) for t in text_norm.split() if len(t) >= 3}


class TopicMatcher:
    """Başlık → konu.

    Her konu için birden çok anahtar-kümesi (varyant) tutulur: tam ad; parantez
    öncesi ana ad; parantez içindeki ve virgül/"ve" ile ayrılmış alternatifler
    ("Hareket (Doğrusal, Bağıl, Atışlar)" → hareket · dogrusal · bagil · atis;
    "Kuvvet, Tork ve Denge" → kuvvet · tork · denge). Bir varyantın TÜM sözcükleri
    (ek atılmış kökleriyle) başlıkta geçmeli; en çok sözcüklü varyant kazanır.
    Eşit en iyi adaylar belirsizdir — o an sürmekte olan grubun konusu aralarındaysa
    o seçilir (liste sırası bağlamı), değilse konu yok."""

    def __init__(self, topics: list[Topic]):
        self._items: list[tuple[frozenset[str], Topic]] = []
        seen: set[tuple[frozenset[str], int]] = set()
        for t in sorted(topics, key=lambda x: (x.order, x.id)):
            name = t.name or ""
            head = name.split("(")[0]
            inner = name[len(head):].strip("() ")
            variants = [name, head]
            for chunk in (head, inner):
                variants += [p for p in _ALT_SPLIT_RE.split(chunk) if p.strip()]
            for v in variants:
                key = _canon_from_norm(normalize(v))
                words = frozenset(_stems(key))
                if not words or (words, t.id) in seen:
                    continue
                seen.add((words, t.id))
                self._items.append((words, t))

    def match(self, title: str, prefer_topic_id: int | None = None) -> Topic | None:
        toks = _stems(_canon_from_norm(normalize(title)))
        # alias'lı biçimler de denensin (başlıkta "Üslü İfadeler" → "uslu sayilar")
        toks |= _stems(_canon_from_norm(_label_key(title)))
        best: dict[int, tuple[int, Topic]] = {}
        for words, t in self._items:
            if words <= toks:
                n = len(words)
                if t.id not in best or best[t.id][0] < n:
                    best[t.id] = (n, t)
        if not best:
            return None
        ranked = sorted(best.values(), key=lambda x: -x[0])
        top = [t for n, t in ranked if n == ranked[0][0]]
        if len(top) == 1:
            return top[0]
        for t in top:
            if t.id == prefer_topic_id:
                return t
        return None


_DAY_RE = re.compile(r"^\s*\d+\s*\.?\s*(gun|gunu|hafta|ders|bolum)\b")


def _chapter_tags(videos: list[SegVideo]) -> list[str | None]:
    """Başlığın 2.+ parçalarından bölüm etiketi ("... | Atışlar | 88 Günde AYT
    Fizik Kampı | 12. Gün"). Listenin çoğunda geçen parça (kamp adı) ve gün/yıl
    parçaları atılır; etiket en az iki videoda ortak olmalı."""
    parts_per = [[p.strip() for p in _SPLIT_RE.split(v.title or "") if p and p.strip()][1:]
                 for v in videos]
    freq: dict[str, int] = {}
    for parts in parts_per:
        for k in {_label_key(p) for p in parts}:
            if k:
                freq[k] = freq.get(k, 0) + 1
    limit = max(3, int(len(videos) * 0.4))
    out: list[str | None] = []
    for parts in parts_per:
        tag = None
        for p in parts:
            k = _label_key(p)
            if not k or len(k) < 3 or _DAY_RE.match(normalize(p)):
                continue
            if freq.get(k, 0) < 2 or freq.get(k, 0) > limit:
                continue
            tag = re.sub(r"[\s\-–—:#(]*\d+\s*\)?\s*$", "", p).strip(" -–—:|()") or p
            break
        out.append(tag)
    return out


def segment(
    videos: list[SegVideo],
    topics: list[Topic],
    *,
    batch_token: str,
    use_ai: bool = True,
) -> list[SegItem]:
    matcher = TopicMatcher(topics)
    roles = [detect_role(v.title) for v in videos]
    tags = _chapter_tags(videos)
    groups: list[_Group] = []
    assign: list[int] = [-1] * len(videos)
    cur: int | None = None  # son içerik (anlatım/soru) grubunun indeksi

    for i, v in enumerate(videos):
        role = roles[i]
        topic = matcher.match(v.title, groups[cur].topic_id if cur is not None else None)
        if role == "diger" and topic is None:
            # ardışık "diğer"ler tek grupta; içerik zincirini bozmaz
            prev = assign[i - 1] if i > 0 else -1
            if prev >= 0 and groups[prev].label_key == "__diger__":
                gi = prev
            else:
                groups.append(_Group("Diğer videolar", None, "__diger__"))
                gi = len(groups) - 1
            groups[gi].members.append(i)
            assign[i] = gi
            continue
        if topic is not None:
            if cur is not None and groups[cur].topic_id == topic.id:
                gi = cur
            else:
                groups.append(_Group(topic.name, topic.id, "t" + str(topic.id)))
                gi = len(groups) - 1
        elif role in ("soru", "tekrar") and cur is not None:
            gi = cur  # checkpoint / soru çözümü → önceki konuya
        else:
            # bölüm etiketi varsa ("| Basit Makineler |") alt başlıklar onda birleşir
            lab = tags[i] or clean_label(v.title)
            lk = _label_key(lab) or normalize(lab)
            if cur is not None and groups[cur].topic_id is None and groups[cur].label_key == lk:
                gi = cur
            else:
                groups.append(_Group(lab, None, lk))
                gi = len(groups) - 1
        groups[gi].members.append(i)
        assign[i] = gi
        cur = gi

    if use_ai:
        _ai_fill(groups, topics)

    # aynı konu → ilk grupta birleşir
    final_key: dict[int, str] = {}
    first_by_topic: dict[int, int] = {}
    for gi, g in enumerate(groups):
        if g.topic_id is not None:
            if g.topic_id in first_by_topic:
                final_key[gi] = _gkey(batch_token, groups[first_by_topic[g.topic_id]], first_by_topic[g.topic_id])
                continue
            first_by_topic[g.topic_id] = gi
        final_key[gi] = _gkey(batch_token, g, gi)

    # birleşen gruplarda etiket/konu ilk grubundan
    label_of: dict[str, str] = {}
    topic_of: dict[str, int | None] = {}
    for gi, g in enumerate(groups):
        label_of.setdefault(final_key[gi], g.label)
        topic_of.setdefault(final_key[gi], g.topic_id)
    out: list[SegItem] = []
    for i, v in enumerate(videos):
        gi = assign[i]
        k = final_key[gi]
        out.append(SegItem(key=v.key, role=roles[i], topic_id=topic_of[k],
                           group_key=k, group_label=label_of[k], order=i))
    return out


def _gkey(batch_token: str, g: _Group, gi: int) -> str:
    base = f"t{g.topic_id}" if g.topic_id is not None else f"g{gi}"
    return f"{batch_token}:{base}"[:64]


# AI konu bağlama süre sınırları (saniye).
AI_CALL_TIMEOUT = 20.0
AI_TOTAL_BUDGET = 25.0
_AI_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="video-seg-ai")


def _ai_fill(groups: list[_Group], topics: list[Topic]) -> None:
    """Konusuz içerik gruplarının etiketlerini kapalı listeden konuya bağla."""
    todo = [(gi, g) for gi, g in enumerate(groups) if g.topic_id is None and g.label_key != "__diger__"]
    if not todo or not topics:
        return
    valid = {t.id: t for t in topics}
    topic_lines = "\n".join(f"{t.id}: {t.name}" for t in topics[:400])
    grp_lines = "\n".join(f"{gi}: {g.label}" for gi, g in todo[:80])
    prompt = (
        "Bir YouTube ders oynatma listesinin video grup adlarını resmi müfredat "
        "konularına eşle. Emin değilsen topic_id=null. Yalnız listedeki topic_id'leri "
        "kullan.\n\n"
        f"RESMİ KONULAR (topic_id: ad):\n{topic_lines}\n\n"
        f"GRUPLAR (grup_no: ad):\n{grp_lines}\n\n"
        'Yalnız JSON: {"mappings":[{"group":N,"topic_id":N|null}]}'
    )
    # Toplam süre sınırı: gemini.generate anahtar/model zincirinde her denemede
    # ayrı zaman aşımı bekler (pro → flash → ücretsiz anahtarlar); içe aktarma
    # isteği bunun toplamını bekleyemez (vekil bağlantıyı koparır). AI adımı
    # yardımcıdır — sınırı aşarsa gruplar AI'sız kalır, içe aktarma sürer.
    fut = _AI_POOL.submit(
        gemini.generate, [gemini.text_part(prompt)], personal_data=False,
        json_mode=True, max_output_tokens=8192, timeout=AI_CALL_TIMEOUT, prefer_fast=True,
    )
    try:
        raw = fut.result(timeout=AI_TOTAL_BUDGET)
        data = _parse_json(raw)
        maps = data if isinstance(data, list) else (data.get("mappings") or [] if isinstance(data, dict) else [])
    except Exception as e:  # noqa: BLE001
        logger.info("video_segmentation AI atlandı: %s", e)
        return
    ok = {gi for gi, _ in todo}
    for m in maps:
        if not isinstance(m, dict):
            continue
        gi, tid = m.get("group"), m.get("topic_id")
        if isinstance(gi, int) and gi in ok and tid in valid:
            groups[gi].topic_id = int(tid)
            groups[gi].label = valid[tid].name


def batch_token_for(seed: str) -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
