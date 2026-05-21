"""AI seans yakalama — kâğıt görüşme formu fotoğrafı / sesli not → metin (KS3).

Tek sağlayıcı **Gemini** (öğrenci verisi → ücretli key, no-training):
- KS3a: fotoğraf (vision) → seans form taslağı.
- KS3b: sesli dikte (audio) → tek Gemini çağrısıyla doğrudan yapılandırılmış taslak
  (ayrı transkripsiyon adımı YOK — Gemini sesi anlayıp JSON döndürür).

GİZLİLİK: görsel/ses SAKLANMAZ — yalnız bu çağrıda işlenir. Sonuç TASLAKTIR; koç
onaylayıp kaydeder. Maliyet `consume_credits(AI_SESSION_CAPTURE | AI_SESSION_VOICE)`
ile metere edilir (endpoint'te).
"""
from __future__ import annotations

import base64
import binascii
import logging
from typing import Any

from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
from app.services import gemini

logger = logging.getLogger(__name__)

# Gemini görsel destekli formatlar
ALLOWED_MEDIA = {"image/jpeg", "image/png", "image/webp"}
# Tarayıcı MediaRecorder + yaygın ses formatları
ALLOWED_AUDIO = {"audio/webm", "audio/mp4", "audio/ogg", "audio/mpeg", "audio/wav"}

_PROMPT = (
    "Aşağıdaki görsel, bir öğrenci koçunun el yazısıyla doldurduğu haftalık "
    "koçluk görüşme formudur. İçeriği oku ve YALNIZ şu JSON nesnesini döndür:\n"
    "{\n"
    '  "agenda": "bu/gelecek seansta konuşulacak ana konular (kısa)",\n'
    '  "coach_note": "görüşme notu: gözlem, başarı, zorluk (özet)",\n'
    '  "next_change": "gelecek hafta değiştirilecek 1 şey (yoksa boş)",\n'
    '  "mood": 1-5 arası tam sayı veya null,\n'
    '  "tags": ["kısa etiketler: kaygı, motivasyon, düzensizlik..."]\n'
    "}\n"
    "Okunamayan alanı boş/null bırak. Uydurma. Türkçe yaz."
)

_VOICE_PROMPT = (
    "Aşağıdaki ses kaydı, bir öğrenci koçunun bir seans hakkında SESLİ olarak "
    "dikte ettiği nottur. Sesi anla ve YALNIZ şu JSON nesnesini döndür:\n"
    "{\n"
    '  "agenda": "bu/gelecek seansta konuşulacak ana konular (kısa)",\n'
    '  "coach_note": "görüşme notu: gözlem, başarı, zorluk (anlatılanın özeti)",\n'
    '  "next_change": "gelecek hafta değiştirilecek 1 şey (yoksa boş)",\n'
    '  "mood": 1-5 arası tam sayı veya null,\n'
    '  "tags": ["kısa etiketler: kaygı, motivasyon, düzensizlik..."]\n'
    "}\n"
    "Söylenmeyeni uydurma; boş bırak. Türkçe yaz."
)


def _normalize(obj: dict[str, Any]) -> dict[str, Any]:
    def _s(v: Any) -> str:
        return str(v).strip() if v is not None else ""

    mood = obj.get("mood")
    try:
        mood = int(mood) if mood is not None else None
        if mood is not None and not (1 <= mood <= 5):
            mood = None
    except (ValueError, TypeError):
        mood = None

    raw_tags = obj.get("tags") or []
    tags = [str(t).strip() for t in raw_tags if t and str(t).strip()][:8] if isinstance(raw_tags, list) else []

    return {
        "agenda": _s(obj.get("agenda")),
        "coach_note": _s(obj.get("coach_note")),
        "next_change": _s(obj.get("next_change")),
        "mood": mood,
        "tags": tags,
    }


def parse_session_photo(
    image_base64: str, media_type: str, *, timeout: float = 45.0
) -> dict[str, Any]:
    """Foto (base64) → seans form taslağı (Gemini vision, ücretli key). Görsel saklanmaz."""
    if media_type not in ALLOWED_MEDIA:
        raise AIInvalidResponse("Desteklenmeyen görsel türü (jpeg/png/webp).")
    text = gemini.generate(
        [gemini.inline_part(image_base64, media_type), gemini.text_part(_PROMPT)],
        personal_data=True, timeout=timeout,
    )
    return _normalize(gemini.extract_json(text))


def parse_session_voice(
    audio_base64: str, media_type: str, *, timeout: float = 60.0
) -> dict[str, Any]:
    """Ses (base64) → seans form taslağı (Gemini audio, tek çağrı, ücretli key). Ses saklanmaz."""
    if media_type not in ALLOWED_AUDIO:
        raise AIInvalidResponse("Desteklenmeyen ses türü (webm/mp4/ogg/mp3/wav).")
    try:
        if not base64.b64decode(audio_base64, validate=True):
            raise AIInvalidResponse("Ses verisi boş")
    except (binascii.Error, ValueError) as e:
        raise AIInvalidResponse(f"Ses verisi çözülemedi: {e}")
    text = gemini.generate(
        [gemini.inline_part(audio_base64, media_type), gemini.text_part(_VOICE_PROMPT)],
        personal_data=True, timeout=timeout,
    )
    return _normalize(gemini.extract_json(text))
