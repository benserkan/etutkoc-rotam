"""Yanlış Soru Arşivi — AI etiketleme (Gemini vision).

Fotoğraftan: soru metni (OCR) + ADAY konu listesinden eşleme + zorluk tahmini +
**Sokratik ipucu**.

TASARIM KARARI (kullanıcı, 2026-07-13): AI **tam çözüm VERMEZ**. Yanlış bir AI
çözümü öğrenciyi yanlış öğretir ve markaya zarar verir. Bunun yerine "hangi
kavramı hatırla, hangi adımla başla" tarzı YAKLAŞIM ipucu üretir; çözümü öğrenci
kendi bulur (koç açıklaması + çözüm fotoğrafı katmanı zaten var).

KONU EŞLEME: model serbest metin üretmez — öğrencinin GERÇEK müfredat konuları
(aday listesi) verilir, model yalnız o listeden `topic_id` seçer (veya null).
Böylece uydurma konu adı sisteme giremez (curriculum_mapping._ai_suggest deseni).

GİZLİLİK: fotoğraf Gemini'ye gönderilir (öğrenci verisi → ÜCRETLİ key, no-training)
ve bu çağrı dışında AI tarafında saklanmaz. Rotam'daki kopya öğrenciye aittir.
"""
from __future__ import annotations

import base64
import binascii
import logging
from typing import Any

from app.services import gemini
from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable

logger = logging.getLogger(__name__)

ALLOWED_MEDIA = {"image/jpeg", "image/png", "image/webp"}
MAX_CANDIDATE_TOPICS = 60   # prompt şişmesin (öğrencinin açık konuları yeter)

_DIFFICULTY = {"kolay", "orta", "zor"}

_PROMPT = (
    "Aşağıdaki görsel, bir öğrencinin YANLIŞ yaptığı bir sınav sorusudur "
    "(LGS/YKS hazırlık). Görevin soruyu ÇÖZMEK DEĞİL; öğrencinin arşivini "
    "etiketlemek ve ona düşünme yolunu göstermektir.\n\n"
    "YALNIZ şu JSON nesnesini döndür:\n"
    "{\n"
    '  "question_text": "sorunun metni (kısa özet, en fazla 300 karakter; '
    'okunmuyorsa boş string)",\n'
    '  "topic_id": aday konulardan EN UYGUN olanın id\'si (tam sayı) veya null,\n'
    '  "difficulty": "kolay" | "orta" | "zor",\n'
    '  "hint": "SOKRATİK ipucu: çözümü VERME. Hangi kavram/kural hatırlanmalı ve '
    'ilk adım ne olmalı — 1-2 cümle, öğrenciye hitap et (sen dili), Türkçe."\n'
    "}\n\n"
    "KURALLAR:\n"
    "- Sonucu, işlemi veya doğru şıkkı ASLA yazma. 'Cevap ...' deme.\n"
    "- topic_id yalnız aşağıdaki ADAY KONULAR listesinden seçilir; listede uygun "
    "konu yoksa null yaz. Yeni konu adı UYDURMA.\n"
    "- Görsel okunmuyorsa question_text boş, topic_id null, hint boş bırak.\n"
)


def _b64_ok(data_b64: str) -> None:
    try:
        if not base64.b64decode(data_b64, validate=True):
            raise AIInvalidResponse("Görsel verisi boş")
    except (binascii.Error, ValueError) as e:
        raise AIInvalidResponse(f"Görsel verisi çözülemedi: {e}")


def _candidates_block(candidates: list[dict]) -> str:
    """Aday konular → prompt bloğu. candidates: [{id, name, subject_name}]."""
    if not candidates:
        return "ADAY KONULAR: (yok — topic_id null döndür)\n"
    lines = "\n".join(
        f"{c['id']}: {c.get('subject_name') or '—'} — {c['name']}"
        for c in candidates[:MAX_CANDIDATE_TOPICS]
    )
    return f"ADAY KONULAR (id: ders — konu):\n{lines}\n"


def _normalize(obj: dict[str, Any], valid_topic_ids: set[int]) -> dict[str, Any]:
    def _s(v: Any, limit: int) -> str:
        return (str(v).strip() if v is not None else "")[:limit]

    tid = obj.get("topic_id")
    try:
        tid = int(tid) if tid is not None else None
    except (ValueError, TypeError):
        tid = None
    # Model listede olmayan bir id uydurursa DÜŞÜR (uydurma konu sisteme girmez)
    if tid is not None and tid not in valid_topic_ids:
        logger.info("ai_wrong_question: geçersiz topic_id atıldı: %s", tid)
        tid = None

    diff = str(obj.get("difficulty") or "").strip().lower()
    if diff not in _DIFFICULTY:
        diff = ""

    return {
        "question_text": _s(obj.get("question_text"), 600),
        "topic_id": tid,
        "difficulty": diff or None,
        "hint": _s(obj.get("hint"), 600),
    }


def tag_wrong_question_photo(
    image_base64: str,
    media_type: str,
    *,
    candidates: list[dict],
    timeout: float = 45.0,
) -> dict[str, Any]:
    """Foto (base64) + aday konular → {question_text, topic_id, difficulty, hint}.

    Öğrenci verisi → `personal_data=True` (ücretli key, no-training). Görsel
    Rotam tarafında zaten saklanır; AI'a yalnız bu çağrı için gönderilir.

    Raises: AIInvalidResponse (okunamadı/format) · AIServiceUnavailable (anahtar
    yok / servis hatası — gemini katmanından yükselir).
    """
    if media_type not in ALLOWED_MEDIA:
        raise AIInvalidResponse("Desteklenmeyen görsel türü (jpeg/png/webp).")
    _b64_ok(image_base64)

    prompt = _PROMPT + "\n" + _candidates_block(candidates)
    text = gemini.generate(
        [gemini.inline_part(image_base64, media_type), gemini.text_part(prompt)],
        personal_data=True, timeout=timeout, json_mode=True,
    )
    obj = gemini.extract_json(text)
    if not isinstance(obj, dict):
        raise AIInvalidResponse("AI yanıtı beklenen biçimde değil.")
    valid = {int(c["id"]) for c in candidates if c.get("id") is not None}
    out = _normalize(obj, valid)
    if not out["question_text"] and out["topic_id"] is None and not out["hint"]:
        raise AIInvalidResponse(
            "Fotoğraf okunamadı — daha net/yakın bir kare deneyin.")
    return out


__all__ = [
    "ALLOWED_MEDIA",
    "AIInvalidResponse",
    "AIServiceUnavailable",
    "tag_wrong_question_photo",
]
