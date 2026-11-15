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
import logging
import os
import subprocess
import tempfile
import wave
from pathlib import Path

import httpx

from app.services.ai_book_template import AIServiceUnavailable
from app.services.system_secrets import get_gemini_paid_key

logger = logging.getLogger(__name__)

# Model sırası (2026-11-15): Google 2.5 "preview-tts" modellerini en erken
# 18 Aralık 2026'da kapatıyor; yerine 3.8 Flash TTS öneriliyor. İlk model yanıt
# vermezse (kapandı / erişim yok / geçici hata) sıradakine düşülür — tek bir
# modelin kapanması Rota'nın sesini susturmaz. `GEMINI_TTS_MODELS` (virgüllü)
# ile dağıtım yapmadan değiştirilebilir.
DEFAULT_TTS_MODELS = (
    "gemini-3.8-flash-tts",
    "gemini-3.8-flash-lite-tts",
    "gemini-2.5-flash-preview-tts",
)
TTS_MODEL = DEFAULT_TTS_MODELS[0]
ROTA_VOICE = "Kore"

# Tek yorum seslendirmesi için üst sınır — TTS modeli çok uzun metinde kesebilir.
MAX_SPEECH_CHARS = 4500


def tts_models() -> list[str]:
    raw = os.environ.get("GEMINI_TTS_MODELS", "")
    models = [m.strip() for m in raw.split(",") if m.strip()]
    return models or list(DEFAULT_TTS_MODELS)


def _tts_url(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def decode_audio_part(part: dict) -> tuple[bytes, int]:
    """generateContent `inlineData` parçası → (ham 16-bit mono PCM, örnekleme hızı).

    2.5 modelleri başlıksız PCM döndürür ("audio/L16;codec=pcm;rate=24000");
    3.8 modelleri RIFF başlıklı WAV döndürür ("audio/wav"). İkisi de buradan
    aynı biçimde çıkar — WAV başlığı PCM sanılıp sese karışmaz.
    """
    raw = base64.b64decode(part["data"])
    mime = part.get("mimeType", "") or ""
    if raw[:4] == b"RIFF":
        with wave.open(io.BytesIO(raw), "rb") as w:
            if w.getsampwidth() != 2 or w.getnchannels() != 1:
                raise ValueError(
                    f"beklenmeyen WAV biçimi: {w.getnchannels()} kanal, "
                    f"{w.getsampwidth() * 8} bit"
                )
            return w.readframes(w.getnframes()), w.getframerate()
    rate = int(mime.split("rate=")[1].split(";")[0]) if "rate=" in mime else 24000
    return raw, rate


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
    for model in tts_models():
        for _ in range(2):  # geçici 429/503 için tek kısa tekrar
            try:
                with httpx.Client(timeout=timeout) as c:
                    r = c.post(
                        _tts_url(model), json=body,
                        headers={"x-goog-api-key": key, "content-type": "application/json"},
                    )
            except httpx.HTTPError as e:  # ağ hatası
                last = f"{model}: {e}"
                continue
            if r.status_code == 200:
                try:
                    part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
                    return decode_audio_part(part)
                except (KeyError, IndexError, ValueError, wave.Error) as e:
                    last = f"{model}: yanıt çözülemedi ({e})"
                    break  # bu modelin yanıtı bozuk → sıradaki model
            last = f"{model}: {r.status_code}: {r.text[:200]}"
            if r.status_code in (400, 403, 404):
                break  # model kapalı / erişim yok → tekrar deneme, sıradakine geç
        if last:
            logger.warning("TTS modeli yanıt vermedi, sıradakine geçiliyor · %s", last)
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
