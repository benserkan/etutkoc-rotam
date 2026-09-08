"""Müfredat eşleştirme — kitap ünitesi (BookSection) → resmi konu (Topic).

Hibrit müfredat omurgasının ÖN ŞARTI: BookSection.topic_id eşlemesi. Prod'da
section'ların yalnız ~%34'ü eşleşmiş; bu servis kalanı yükseltir:

  (a) Deterministik auto-map: section.label → Topic.name normalize/exact eşleşme
      (Türkçe karakter + noktalama normalize; ücretsiz, anlık, %100 güvenli).
  (b) Gemini semantik öneri: auto'nun çözemediği etiketler için (örn. "BS Doğrunun
      Analitiği" → "Doğrunun Analitiği") resmi konu listesiyle eşleştirme. KİŞİSEL
      VERİ DEĞİL (kitap/konu adı) → ÜCRETSİZ key, kredi yanmaz.

Koç önerileri onaylar → topic_id set edilir (apply). AI çağrısı best-effort;
anahtar yoksa/başarısızsa auto-map yine çalışır.
"""
from __future__ import annotations

import json
import logging
import re

from sqlalchemy.orm import Session

from collections import Counter
from dataclasses import dataclass

from sqlalchemy import or_

from app.models import Book, BookSection, Topic
from app.services import gemini

logger = logging.getLogger(__name__)

# Türkçe küçük harf + aksan sadeleştirme (eşleştirme için; gösterimde kullanılmaz).
_TR_MAP = str.maketrans("çğıöşüâîû", "cgiosuaiu")
# BÜYÜK Türkçe harfler .lower()'dan ÖNCE sadeleştirilir: Python'da "İ".lower()
# = "i" + U+0307 (combining dot) ürettiğinden "İşlem" ile "işlem" FARKLI anahtara
# düşüyordu (deneme içe aktarma sözlüğünde casing tutarsızlığı — 2026-07-16).
_TR_UPPER = str.maketrans("İIÇĞÖŞÜÂÎÛ", "iıçğöşüâîû")


def normalize(s: str | None) -> str:
    """Eşleştirme anahtarı: küçük harf + Türkçe sadeleştirme + yalnız harf/rakam."""
    if not s:
        return ""
    low = s.strip().translate(_TR_UPPER).lower().translate(_TR_MAP)
    # yaygın kitap önekleri/gürültü ("ünite", "konu", "test", "bölüm") sadeleştirme
    cleaned = re.sub(r"[^a-z0-9]+", " ", low).strip()
    return cleaned


# --- Eşleştirme anahtarı katmanı (auto-map kalitesi) -------------------------
# normalize() saf kalır; aşağıdaki katman SADECE eşleştirme anahtarı üretir.
#   - Önek temizleme: kitap etiketinden yayınevi/ünite öneki ("1. Ünite —", "BS",
#     "TYT", "Konu:") atılır → resmi konu adıyla eşleşme şansı artar (RESMİ KONU
#     ADINA DOKUNULMAZ, yalnız kitap etiketine).
#   - Bağlaç atma: "ve"/"ile" eşleştirme gürültüsüdür ("Oran ve Orantı" =
#     "Oran Orantı", "Veri ve İstatistik" = "Veri İstatistik").
#   - Alias: yaygın yazım/akronim varyantları ("OBEB OKEK" = "EBOB EKOK").
# Hepsi auto-map (ücretsiz, anlık) içindir; AI çağrısından önce daha çok ünite
# deterministik eşleşir → kredi yanmaz, koç daha az el ile düzeltir.

# normalize edilmiş (lower + tr-sade + yalnız harf/rakam) dize üstünde çalışır.
_PREFIX_RE = re.compile(
    r"^(?:\d+\s+)?(?:unite|bolum|konu|test|fasikul|deneme|bs|tyt|ayt|lgs|yks)\s+",
)
_STOPWORDS = {"ve", "ile"}
_ALIAS: dict[str, str] = {
    "obeb okek": "ebob ekok",
    "okek obeb": "ebob ekok",
    "ebob okek": "ebob ekok",
    "obeb ekok": "ebob ekok",
    # yaygın matematik eşanlam varyantları (yayınevleri "ifadeler"/"sayılar" karışık kullanır)
    "uslu ifadeler": "uslu sayilar",
    "koklu ifadeler": "koklu sayilar",
    "karekoklu ifadeler": "koklu sayilar",
    "karekoklu sayilar": "koklu sayilar",
    # sayı önekli ↔ yazıyla derece (kitaplar "1./2. Dereceden" yazabilir)
    "1 dereceden denklemler": "birinci dereceden denklemler",
    "2 dereceden denklemler": "ikinci dereceden denklemler",
    # TYT soru bankası yaygın bölüm adları ↔ resmi TYT taksonomisi
    # (2026-08-11, 345 TYT Matematik gerçek-kitap denemesinden; alias yalnız
    # hedef anahtar aday listesinde VARSA eşler — başka müfredatta zararsız).
    "gercel sayilar": "temel kavramlar",
    "gercel sayilar 1": "temel kavramlar",
    "gercel sayilar 2": "temel kavramlar",
    "faktoriyel kavrami": "faktoriyel",
    "basamak kavrami": "sayi basamaklari",
    "hiz problemleri": "hareket problemleri",
    "surat problemleri": "hareket problemleri",
    "emek problemleri": "isci problemleri",
    "isci emek problemleri": "isci problemleri",
    "asal carpanlar": "asal sayilar",
    "grafik yorumlama": "grafik problemleri",
    "sayi problemleri": "sayi kesir problemleri",
    "kesir problemleri": "sayi kesir problemleri",
    "sayma olasilik": "olasilik",
    "kumeler kartezyen carpim": "kumeler",
    "i ii bilinmeyenli denklemler": "birinci dereceden denklemler",
    "bir iki bilinmeyenli denklemler": "birinci dereceden denklemler",
    "i ii bilinmeyenli esitsizlikler": "basit esitsizlikler",
    # NOT: yalın "esitsizlikler" alias'ı BİLİNÇLİ YOK — Maarif/AYT'de birebir
    # "Eşitsizlikler" konusu var; alias exact eşleşmeyi bozardı (2026-08-11 taraması).
}


def _canon_from_norm(norm: str) -> str:
    """Normalize edilmiş dizeden eşleştirme anahtarı: bağlaç at + alias uygula."""
    if not norm:
        return ""
    key = " ".join(t for t in norm.split() if t not in _STOPWORDS)
    return _ALIAS.get(key, key)


def _topic_key(name: str | None) -> str:
    """Resmi konu adı → eşleştirme anahtarı (önek temizlenmez — resmi ad korunur)."""
    return _canon_from_norm(normalize(name))


def _label_key(label: str | None) -> str:
    """Kitap ünite etiketi → eşleştirme anahtarı (önek temizlenir + canon)."""
    norm = normalize(label)
    prev = None
    while norm != prev:  # zincirli önek ("12 unite ...", "tyt 1 unite ...")
        prev = norm
        norm = _PREFIX_RE.sub("", norm).strip()
    return _canon_from_norm(norm or normalize(label))


def _topics_by_norm(topics: list[Topic]) -> dict[str, Topic]:
    """Eşleştirme anahtarı → Topic (ilk geleni tutar, order'a göre)."""
    out: dict[str, Topic] = {}
    for t in sorted(topics, key=lambda x: (x.order, x.id)):
        key = _topic_key(t.name)
        if key and key not in out:
            out[key] = t
    return out


# --- Kaynak-konu NORMALİZASYON katmanı (2026-09-08) ---------------------------
# KOÇ: "TYT Matematik'te iki kaynak var; birinde 'Bölme Bölünebilme', diğerinde
# 'Bölme Bölünebilme Kuralları' yazıyor. Müfredat paneli yalnız adı birebir uyan
# yayının test sayısını topluyor — yayınevi adlandırmasıyla resmi konu arasındaki
# bağı nasıl kuracağız?"
#
# BAĞ = BookSection.topic_id. Bu katman o bağı deterministik adımlarla kurar
# (AI YOK, kredi YOK, belirsizde ASLA otomatik bağlamaz):
#   1. exact   — mevcut anahtar (önek/bağlaç/alias) birebir.
#   2. learned — ÖĞRENİLMİŞ SÖZLÜK: aynı derste doğrulanmış katalog kayıtları +
#                koçların uyguladığı eşleştirmeler (etiket-anahtarı → konu).
#                Çelişen anahtar (≥2 farklı konu) dışlanır.
#   3. tail    — etiketin sonundaki ANLAMSIZ kuyruk atılır ("Kuralları",
#                "Özellikleri", "Testleri", "I/II") ve 1-2 tekrar denenir.
#   4. contain — konu adının tüm sözcükleri etikette geçiyor ve artan sözcükler
#                yalnız anlamsız kuyruktan; tek aday olmalı. ("Asal Çarpanlara
#                Ayırma ve Bölen Sayısı" → artan {asal, bölen, sayısı} anlamlı
#                → BAĞLANMAZ; "Çarpanlara Ayırma"ya yanlış gitmesin.)
# Kalan → AI önerisi (modal) → koç onayı.

_GENERIC_TAIL = {
    "kurallari", "kurali", "kurallar", "kural",
    "ozellikleri", "ozellikler", "ozelligi",
    "uygulamalari", "uygulamalar", "uygulama", "uygulamasi",
    "konusu", "konulari", "konu",
    "testleri", "testi", "test",
    "calismalari", "calismasi", "alistirmalari", "alistirmalar",
    "sorulari", "soru", "bolumu", "bolum", "kismi",
    "i", "ii", "iii", "iv", "v", "1", "2", "3", "4", "5", "a", "b", "c",
}


def _strip_generic_tail(key: str) -> str:
    toks = key.split()
    while len(toks) > 1 and toks[-1] in _GENERIC_TAIL:
        toks.pop()
    return " ".join(toks)


@dataclass
class LabelMatch:
    topic: Topic
    source: str  # exact | learned | tail | contain


def learned_label_map(
    db: Session, subject_id: int, *, exclude_book_id: int | None = None,
) -> dict[str, int]:
    """Öğrenilmiş sözlük: etiket-anahtarı → topic_id (aynı ders).

    Kaynaklar: doğrulanmış katalog kayıtları (BookTemplateSection.topic_id) +
    koç kitaplarında uygulanmış eşleştirmeler (BookSection.topic_id). Aynı
    anahtar farklı konulara gitmişse (çelişki) anahtar DIŞLANIR — belirsiz asla
    otomatik bağlanmaz. Etiket/konu adı kişisel veri değildir; koçlar arası
    öğrenme deneme-içe-aktarma sözlüğüyle (exam_topic_aliases) aynı ilkedir.
    """
    from app.models.book import (
        CATALOG_STATUS_VERIFIED,
        BookTemplate,
        BookTemplateSection,
    )

    votes: dict[str, Counter] = {}
    cat_rows = (
        db.query(BookTemplateSection.label, BookTemplateSection.topic_id)
        .join(BookTemplate, BookTemplate.id == BookTemplateSection.template_id)
        .filter(
            BookTemplate.subject_id == subject_id,
            BookTemplate.catalog_status == CATALOG_STATUS_VERIFIED,
            BookTemplateSection.topic_id.isnot(None),
        )
        .all()
    )
    q = (
        db.query(BookSection.label, BookSection.topic_id)
        .join(Book, Book.id == BookSection.book_id)
        .filter(Book.subject_id == subject_id, BookSection.topic_id.isnot(None))
    )
    if exclude_book_id is not None:
        q = q.filter(Book.id != exclude_book_id)
    for label, tid in list(cat_rows) + list(q.all()):
        key = _label_key(label)
        if key and tid:
            votes.setdefault(key, Counter())[int(tid)] += 1
    return {k: next(iter(c)) for k, c in votes.items() if len(c) == 1}


def resolve_label(
    label: str | None,
    index: dict[str, Topic],
    learned: dict[str, int] | None = None,
) -> LabelMatch | None:
    """Etiket → konu (deterministik). `index` = _topics_by_norm(aday konular).
    Aday listesi dışındaki (başka ders) öğrenilmiş konu ASLA dönmez."""
    key = _label_key(label)
    if not key:
        return None
    by_id = {t.id: t for t in index.values()}
    learned = learned or {}

    def hit(k: str, src: str) -> LabelMatch | None:
        t = index.get(k)
        if t is not None:
            return LabelMatch(t, src)
        tid = learned.get(k)
        if tid is not None and tid in by_id:
            return LabelMatch(by_id[tid], "learned" if src == "exact" else src)
        return None

    m = hit(key, "exact")
    if m:
        return m
    tail = _strip_generic_tail(key)
    if tail != key:
        m = hit(tail, "tail")
        if m:
            return m
    ltoks = set(tail.split())
    cands: dict[int, Topic] = {}
    for k, t in index.items():
        ktoks = set(k.split())
        if ktoks and ktoks <= ltoks and (ltoks - ktoks) <= _GENERIC_TAIL:
            cands[t.id] = t
    if len(cands) == 1:
        return LabelMatch(next(iter(cands.values())), "contain")
    return None


def candidate_topics_for_book(db: Session, book: Book) -> list[Topic]:
    """Eşleştirme adayları: kitabın dersindeki LEAF konular (builtin + koçun kendi)."""
    if book.subject_id is None:
        return []
    all_topics = (
        db.query(Topic)
        .filter(
            Topic.subject_id == book.subject_id,
            or_(Topic.is_builtin.is_(True), Topic.teacher_id == book.teacher_id),
        )
        .order_by(Topic.order, Topic.name)
        .all()
    )
    parent_ids = {t.parent_id for t in all_topics if t.parent_id is not None}
    return [t for t in all_topics if t.id not in parent_ids]


def auto_apply_sections(
    db: Session,
    book: Book,
    sections: list[BookSection] | None = None,
    *,
    use_learned: bool = True,
) -> list[dict]:
    """topic_id'si BOŞ bölümleri deterministik katmanla bağlar (yazar, commit
    etmez). Dönen: [{section_id, label, topic_id, topic_name, source}].

    Bölüm oluşturma yollarına (tek/toplu/AI/şablon) ve geriye dönük dolduruma
    (scripts/backfill_section_topics.py) bağlıdır. Eşleşmeyen dokunulmaz.
    """
    topics = candidate_topics_for_book(db, book)
    if not topics:
        return []
    index = _topics_by_norm(topics)
    learned = (
        learned_label_map(db, book.subject_id, exclude_book_id=book.id)
        if use_learned else {}
    )
    applied: list[dict] = []
    for sec in (sections if sections is not None else (book.sections or [])):
        if sec.topic_id is not None:
            continue
        m = resolve_label(sec.label, index, learned)
        if m is None:
            continue
        sec.topic_id = m.topic.id
        applied.append({
            "section_id": sec.id, "label": sec.label,
            "topic_id": m.topic.id, "topic_name": m.topic.name,
            "source": m.source,
        })
    return applied


# Gemini 2.5 düşünme tokenı çıktıyı kesip JSON'u bozabiliyor → section'ları küçük
# parçalara böl (çok ünite = büyük yanıt = kesilme riski) + tokenı yükselt.
_AI_BATCH = 12


def _ai_suggest(
    sections: list[BookSection], candidate_topics: list[Topic],
) -> dict[int, tuple[int, str]]:
    """Gemini ile section.label → topic_id öner. {section_id: (topic_id, confidence)}.

    Best-effort: anahtar yok/başarısız → boş dict. Kişisel veri değil (ücretsiz key).
    Section'lar parçalara bölünür (kesilme önleme); bir parça hata verse de diğerleri
    devam eder.
    """
    if not sections or not candidate_topics:
        return {}
    out: dict[int, tuple[int, str]] = {}
    for i in range(0, len(sections), _AI_BATCH):
        out.update(_ai_suggest_batch(sections[i:i + _AI_BATCH], candidate_topics))
    return out


def _ai_suggest_batch(
    sections: list[BookSection], candidate_topics: list[Topic],
) -> dict[int, tuple[int, str]]:
    topic_lines = "\n".join(f"{t.id}: {t.name}" for t in candidate_topics)
    sec_lines = "\n".join(f"{s.id}: {s.label}" for s in sections)
    prompt = (
        "Bir kitabın ünite başlıklarını resmi müfredat konularına eşle. Her ünite "
        "için EN UYGUN resmi konuyu seç; emin değilsen topic_id=null bırak. Ünite "
        "başlığında '1. Ünite — ', yayın öneki (BS, AYT vb.), yazım farkı olabilir; "
        "bunları yok say, ANLAM olarak eşleştir (örn. '8. Ünite — Duyu Organları' = "
        "'Duyu Organları'). Yalnız listedeki topic_id'leri kullan, kısa tut.\n\n"
        f"RESMİ KONULAR (topic_id: ad):\n{topic_lines}\n\n"
        f"ÜNİTE BAŞLIKLARI (section_id: başlık):\n{sec_lines}\n\n"
        'Yalnız JSON dön: {"mappings":[{"section_id":N,"topic_id":N|null,'
        '"confidence":"high|medium|low"}]}'
    )
    try:
        raw = gemini.generate(
            [gemini.text_part(prompt)],
            personal_data=False, json_mode=True, max_output_tokens=16384,
        )
        data = _parse_json(raw)
        # Gemini bazen sarmalayıcı obje yerine doğrudan dizi döndürür
        # ([{...}]) → "mappings" anahtarı yok. İki şekli de kabul et.
        if isinstance(data, list):
            mappings = data
        elif isinstance(data, dict):
            mappings = data.get("mappings") or []
        else:
            mappings = []
        valid_ids = {t.id for t in candidate_topics}
        sec_ids = {s.id for s in sections}
        out: dict[int, tuple[int, str]] = {}
        for m in mappings:
            if not isinstance(m, dict):
                continue
            sid = m.get("section_id")
            tid = m.get("topic_id")
            conf = str(m.get("confidence") or "low")
            if sid in sec_ids and tid in valid_ids:
                out[int(sid)] = (int(tid), conf if conf in ("high", "medium", "low") else "low")
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning("curriculum_mapping AI suggest batch fail (%d sec): %s", len(sections), e)
        return {}


def _parse_json(raw: str) -> dict | list:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except Exception:
        # ilk { ... } veya [ ... ] bloğunu yakala (obje veya dizi)
        m = re.search(r"\{.*\}|\[.*\]", raw, flags=re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def suggest_for_book(
    db: Session,
    book: Book,
    candidate_topics: list[Topic],
    *,
    use_ai: bool = False,
) -> list[dict]:
    """Kitabın her section'ı için eşleştirme önerisi.

    Dönen her satır: section_id, label, order, current_topic_id, current_topic_name,
    suggested_topic_id, suggested_topic_name, source ("mapped"|"auto"|"ai"|"none"),
    confidence. Zaten eşleşmiş (current_topic_id) section'lara öneri üretilmez.
    """
    tmap = _topics_by_norm(candidate_topics)
    by_id = {t.id: t for t in candidate_topics}
    sections = sorted(book.sections or [], key=lambda s: (s.order, s.id))
    learned = (
        learned_label_map(db, book.subject_id, exclude_book_id=book.id)
        if book.subject_id is not None else {}
    )

    rows: list[dict] = []
    ai_needed: list[BookSection] = []
    for sec in sections:
        cur_id = sec.topic_id
        cur_name = by_id[cur_id].name if cur_id in by_id else (
            sec.topic.name if sec.topic else None
        )
        suggested = None
        source = "mapped" if cur_id is not None else "none"
        if cur_id is None:
            # exact + öğrenilmiş sözlük + kuyruk + kapsama (deterministik)
            m = resolve_label(sec.label, tmap, learned)
            if m is not None:
                suggested = m.topic
                source = "auto"
            else:
                ai_needed.append(sec)
        rows.append({
            "section_id": sec.id,
            "label": sec.label,
            "order": sec.order,
            "current_topic_id": cur_id,
            "current_topic_name": cur_name,
            "suggested_topic_id": suggested.id if suggested else None,
            "suggested_topic_name": suggested.name if suggested else None,
            "source": source,
            "confidence": "high" if source == "auto" else None,
        })

    if use_ai and ai_needed:
        ai_map = _ai_suggest(ai_needed, candidate_topics)
        if ai_map:
            for r in rows:
                if r["current_topic_id"] is None and r["suggested_topic_id"] is None:
                    hit = ai_map.get(r["section_id"])
                    if hit:
                        tid, conf = hit
                        t = by_id.get(tid)
                        if t is not None:
                            r["suggested_topic_id"] = tid
                            r["suggested_topic_name"] = t.name
                            r["source"] = "ai"
                            r["confidence"] = conf
    return rows


def apply_mappings(
    db: Session,
    book: Book,
    pairs: list[tuple[int, int | None]],
    candidate_topic_ids: set[int],
) -> int:
    """(section_id, topic_id|None) çiftlerini uygula. topic_id None → eşlemeyi kaldır.
    Yalnız bu kitabın section'ları + erişilebilir topic'ler. Dönen: değişen sayı."""
    sec_by_id = {s.id: s for s in (book.sections or [])}
    changed = 0
    for sid, tid in pairs:
        sec = sec_by_id.get(sid)
        if sec is None:
            continue
        if tid is not None and tid not in candidate_topic_ids:
            continue  # geçersiz/erişilemez topic — atla
        if sec.topic_id != tid:
            sec.topic_id = tid
            changed += 1
    return changed
