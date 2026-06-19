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

from app.models import Book, BookSection, Topic
from app.services import gemini

logger = logging.getLogger(__name__)

# Türkçe küçük harf + aksan sadeleştirme (eşleştirme için; gösterimde kullanılmaz).
_TR_MAP = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def normalize(s: str | None) -> str:
    """Eşleştirme anahtarı: küçük harf + Türkçe sadeleştirme + yalnız harf/rakam."""
    if not s:
        return ""
    low = s.strip().lower().translate(_TR_MAP)
    # yaygın kitap önekleri/gürültü ("ünite", "konu", "test", "bölüm") sadeleştirme
    cleaned = re.sub(r"[^a-z0-9]+", " ", low).strip()
    return cleaned


def _topics_by_norm(topics: list[Topic]) -> dict[str, Topic]:
    """Normalize ad → Topic (ilk geleni tutar, order'a göre)."""
    out: dict[str, Topic] = {}
    for t in sorted(topics, key=lambda x: (x.order, x.id)):
        key = normalize(t.name)
        if key and key not in out:
            out[key] = t
    return out


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
            auto = tmap.get(normalize(sec.label))
            if auto is not None:
                suggested = auto
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
