"""Çalışma zamanı TTS — Gemini "Kore" sesi (Rota'nın sesi).

Rehber/demolardaki build-time TTS'in (scripts/generate_demo_audio.py) uygulama
içi karşılığı: kişiye özel metni ANINDA seslendirir (Rota Veli Asistanı).

KVKK: seslendirilen metin kişisel veri içerir (çocuğun adı/performansı) →
YALNIZ ÜCRETLİ anahtar kullanılır (no-training); ücretsiz anahtara düşüş YOK
(gemini.generate(personal_data=True) kuralının aynısı).

Çıktı: MP3 (ffmpeg varsa — prod imajına eklendi) yoksa WAV (saf Python,
bağımlılıksız). Çağıran, dönen content_type'ı saklar/servis eder.
"""
from __future__ import annotations

import base64
import io
import subprocess
import tempfile
import wave
from pathlib import Path

import httpx

from app.services.ai_book_template import AIServiceUnavailable
from app.services.system_secrets import get_gemini_paid_key

TTS_MODEL = "gemini-2.5-flash-preview-tts"
TTS_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{TTS_MODEL}:generateContent"
ROTA_VOICE = "Kore"

# Tek yorum seslendirmesi için üst sınır — TTS modeli çok uzun metinde kesebilir.
MAX_SPEECH_CHARS = 4500


def _tts_pcm(text: str, voice: str, timeout: float) -> tuple[bytes, int]:
    key = get_gemini_paid_key()
    if not key:
        raise AIServiceUnavailable(
            "Seslendirme için ücretli Gemini anahtarı tanımlı değil "
            "(süper admin → AI Ayarları)."
        )
    body = {
        "contents": [{"parts": [{"text": text[:MAX_SPEECH_CHARS]}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    last = ""
    for _ in range(2):  # geçici 429/503 için tek kısa tekrar
        try:
            with httpx.Client(timeout=timeout) as c:
                r = c.post(
                    TTS_URL, json=body,
                    headers={"x-goog-api-key": key, "content-type": "application/json"},
                )
        except httpx.HTTPError as e:  # ağ hatası
            last = str(e)
            continue
        if r.status_code == 200:
            try:
                part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
                mime = part.get("mimeType", "")
                rate = int(mime.split("rate=")[1].split(";")[0]) if "rate=" in mime else 24000
                return base64.b64decode(part["data"]), rate
            except (KeyError, IndexError, ValueError) as e:
                raise AIServiceUnavailable(f"TTS yanıtı çözülemedi: {e}") from e
        last = f"{r.status_code}: {r.text[:200]}"
    raise AIServiceUnavailable(f"TTS başarısız: {last}")


def _pcm_to_wav_bytes(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _pcm_to_mp3_bytes(pcm: bytes, rate: int) -> bytes | None:
    """ffmpeg varsa 64k MP3 (WAV'ın ~1/6'sı); yoksa None → WAV fallback."""
    wav_path = mp3_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = Path(tf.name)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
            mp3_path = Path(tf.name)
        wav_path.write_bytes(_pcm_to_wav_bytes(pcm, rate))
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
             "-codec:a", "libmp3lame", "-b:a", "64k", str(mp3_path)],
            check=True, timeout=60,
        )
        data = mp3_path.read_bytes()
        return data if data else None
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    finally:
        for p in (wav_path, mp3_path):
            if p is not None:
                p.unlink(missing_ok=True)


def synthesize_speech(
    text: str, *, voice: str = ROTA_VOICE, timeout: float = 120.0
) -> tuple[bytes, str]:
    """Metni seslendir → (ses baytları, content_type).

    MP3 tercih edilir (küçük); ffmpeg yoksa WAV. Hata → AIServiceUnavailable
    (çağıran 502 ai_unavailable'a çevirir; kredi düşmez).
    """
    pcm, rate = _tts_pcm(text, voice, timeout)
    mp3 = _pcm_to_mp3_bytes(pcm, rate)
    if mp3 is not None:
        return mp3, "audio/mpeg"
    return _pcm_to_wav_bytes(pcm, rate), "audio/wav"
