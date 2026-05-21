"""AI seans yakalama — kâğıt görüşme formu fotoğrafı / sesli not → metin (KS3).

KS3a: Claude vision (Anthropic) ile el yazısı koçluk görüşme formunu okur.
KS3b: Whisper STT (OpenAI) ile koçun sesli dikte ettiği notu metne çevirir,
ardından Claude ile KS1 seans alanlarına (agenda/coach_note/next_change/mood/
tags) yapılandırır.

GİZLİLİK: Görsel/ses SAKLANMAZ — yalnız bu çağrıda işlenir, sonra atılır. Sonuç
TASLAKTIR; koç onaylayıp kaydeder. `ai_book_template.py` httpx desenini reuse.
Maliyet `consume_credits(UsageKind.AI_SESSION_CAPTURE | AI_SESSION_VOICE)` ile
metere edilir (endpoint'te).
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import re
from typing import Any

import httpx

from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_VERSION = "2023-06-01"

OPENAI_TRANSCRIBE_URL = "https://api.openai.com/v1/audio/transcriptions"
OPENAI_TRANSCRIBE_MODEL = "whisper-1"

ALLOWED_MEDIA = {"image/jpeg", "image/png", "image/webp"}

# Tarayıcı MediaRecorder çıktıları + yaygın ses formatları (Whisper destekli).
ALLOWED_AUDIO = {"audio/webm", "audio/mp4", "audio/ogg", "audio/mpeg", "audio/wav"}
_AUDIO_EXT = {
    "audio/webm": "webm", "audio/mp4": "mp4", "audio/ogg": "ogg",
    "audio/mpeg": "mp3", "audio/wav": "wav",
}

_PROMPT = (
    "Aşağıdaki görsel, bir öğrenci koçunun el yazısıyla doldurduğu haftalık "
    "koçluk görüşme formudur. İçeriği oku ve YALNIZ şu JSON nesnesini döndür "
    "(açıklama, markdown yok):\n"
    "{\n"
    '  "agenda": "bu/gelecek seansta konuşulacak ana konular (kısa)",\n'
    '  "coach_note": "görüşme notu: gözlem, başarı, zorluk (özet)",\n'
    '  "next_change": "gelecek hafta değiştirilecek 1 şey (yoksa boş)",\n'
    '  "mood": 1-5 arası tam sayı veya null,\n'
    '  "tags": ["kısa etiketler: kaygı, motivasyon, düzensizlik..."]\n'
    "}\n"
    "Okunamayan alanı boş/null bırak. Türkçe yaz."
)

_TEXT_PROMPT = (
    "Aşağıdaki metin, bir öğrenci koçunun bir seans hakkında SESLİ olarak dikte "
    "ettiği notların ham dökümüdür. İçeriği anla ve YALNIZ şu JSON nesnesini "
    "döndür (açıklama, markdown yok):\n"
    "{\n"
    '  "agenda": "bu/gelecek seansta konuşulacak ana konular (kısa)",\n'
    '  "coach_note": "görüşme notu: gözlem, başarı, zorluk (dökümün özeti)",\n'
    '  "next_change": "gelecek hafta değiştirilecek 1 şey (yoksa boş)",\n'
    '  "mood": 1-5 arası tam sayı veya null,\n'
    '  "tags": ["kısa etiketler: kaygı, motivasyon, düzensizlik..."]\n'
    "}\n"
    "Dökümde olmayan alanı boş/null bırak. Uydurma. Türkçe yaz.\n\n"
    "--- DÖKÜM ---\n"
)


def _extract_json_object(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except (ValueError, TypeError):
        pass
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except (ValueError, TypeError):
            pass
    raise AIInvalidResponse("Model çıktısı JSON nesnesi değil")


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


def _claude_messages(content: list[dict[str, Any]], *, timeout: float) -> str:
    """Anthropic messages çağrısı → düz metin yanıt. (ANTHROPIC_API_KEY env)."""
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise AIServiceUnavailable("ANTHROPIC_API_KEY tanımlı değil (.env)")

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": ANTHROPIC_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": ANTHROPIC_MODEL,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": content}],
                },
            )
    except httpx.HTTPError as e:
        logger.warning("Anthropic çağrısı başarısız: %s", e)
        raise AIServiceUnavailable(f"API çağrısı başarısız: {e}")

    if response.status_code != 200:
        logger.warning("Anthropic HTTP %s: %s", response.status_code, (response.text or "")[:200])
        raise AIServiceUnavailable(f"HTTP {response.status_code}")

    data = response.json()
    content_blocks = data.get("content", [])
    text = "\n".join(b.get("text", "") for b in content_blocks if b.get("type") == "text").strip()
    if not text:
        raise AIInvalidResponse("Metin yanıtı boş")
    return text


def parse_session_photo(
    image_base64: str, media_type: str, *, timeout: float = 40.0
) -> dict[str, Any]:
    """Foto (base64) → seans form taslağı (dict). Görsel saklanmaz.

    Raises:
        AIServiceUnavailable: API key yok / HTTP hatası
        AIInvalidResponse: desteklenmeyen tür / parse hatası
    """
    if media_type not in ALLOWED_MEDIA:
        raise AIInvalidResponse("Desteklenmeyen görsel türü (jpeg/png/webp).")
    text = _claude_messages([
        {"type": "image", "source": {
            "type": "base64", "media_type": media_type, "data": image_base64,
        }},
        {"type": "text", "text": _PROMPT},
    ], timeout=timeout)
    return _normalize(_extract_json_object(text))


def _structure_text_to_draft(transcript: str, *, timeout: float = 30.0) -> dict[str, Any]:
    """Ham dikte metnini → seans form taslağı (Claude). Boş yapılanırsa metin
    coach_note'a fallback."""
    out = _normalize(_extract_json_object(_claude_messages(
        [{"type": "text", "text": _TEXT_PROMPT + transcript}], timeout=timeout,
    )))
    # Yapılandırma boş çıktıysa ham dökümü en azından nota koy (veri kaybetme).
    if not out.get("coach_note") and not out.get("agenda"):
        out["coach_note"] = transcript.strip()
    return out


def transcribe_audio(
    audio_base64: str, media_type: str, *, timeout: float = 60.0
) -> str:
    """Ses (base64) → düz metin döküm (OpenAI Whisper). Ses saklanmaz.

    Raises:
        AIInvalidResponse: desteklenmeyen tür / bozuk base64 / boş döküm
        AIServiceUnavailable: API key yok / HTTP hatası
    """
    import os

    if media_type not in ALLOWED_AUDIO:
        raise AIInvalidResponse("Desteklenmeyen ses türü (webm/mp4/ogg/mp3/wav).")
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise AIServiceUnavailable("OPENAI_API_KEY tanımlı değil (.env)")

    try:
        audio_bytes = base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError) as e:
        raise AIInvalidResponse(f"Ses verisi çözülemedi: {e}")
    if not audio_bytes:
        raise AIInvalidResponse("Ses verisi boş")

    ext = _AUDIO_EXT.get(media_type, "webm")
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                OPENAI_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (f"session.{ext}", audio_bytes, media_type)},
                data={"model": OPENAI_TRANSCRIBE_MODEL, "language": "tr"},
            )
    except httpx.HTTPError as e:
        logger.warning("Whisper çağrısı başarısız: %s", e)
        raise AIServiceUnavailable(f"STT çağrısı başarısız: {e}")

    if response.status_code != 200:
        logger.warning("Whisper HTTP %s: %s", response.status_code, (response.text or "")[:200])
        raise AIServiceUnavailable(f"HTTP {response.status_code}")

    text = (response.json().get("text") or "").strip()
    if not text:
        raise AIInvalidResponse("Ses dökümü boş (konuşma algılanamadı)")
    return text


def parse_session_voice(
    audio_base64: str, media_type: str, *, timeout: float = 60.0
) -> dict[str, Any]:
    """Ses (base64) → seans form taslağı (dict). Whisper STT + Claude yapılandırma.

    Ses saklanmaz. Raises: AIInvalidResponse / AIServiceUnavailable.
    """
    transcript = transcribe_audio(audio_base64, media_type, timeout=timeout)
    return _structure_text_to_draft(transcript)
