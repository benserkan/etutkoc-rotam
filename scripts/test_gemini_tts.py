"""Gemini 2.5 TTS feasibility testi — mevcut anahtarla tek cümle seslendir.

  python -m scripts.test_gemini_tts
Çıktı: scripts/_tts_test.wav (oynatıp kalite kontrol edilebilir).
"""
from __future__ import annotations
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import base64
import struct
import wave
from pathlib import Path

import httpx

from app.services.system_secrets import get_gemini_paid_key, get_gemini_free_keys

MODEL = "gemini-2.5-flash-preview-tts"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
VOICE = "Kore"  # net, ciddi ton; alternatif: Aoede, Puck, Charon, Zephyr
TEXT = ("Merhaba. Bu, Etütkoç Rotam demo seslendirme testidir. "
        "Sayılar net okunmalı: yirmi beş dakika, yüzde seksen dört. "
        "L, G, S sınavına hazırlık.")


def pcm_to_wav(pcm: bytes, path: Path, rate: int = 24000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(rate)
        w.writeframes(pcm)


def main():
    key = get_gemini_paid_key() or (get_gemini_free_keys() or [None])[0]
    if not key:
        print("HATA: Gemini anahtarı yok (.env GEMINI_API_KEY / system_secrets).")
        return 1
    print(f"Anahtar bulundu (…{key[-4:]}). Model={MODEL} Ses={VOICE}")
    body = {
        "contents": [{"parts": [{"text": TEXT}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}
            },
        },
    }
    try:
        with httpx.Client(timeout=120) as c:
            r = c.post(URL, json=body, headers={"x-goog-api-key": key, "content-type": "application/json"})
    except httpx.HTTPError as e:
        print(f"HTTP hatası: {e}")
        return 1
    if r.status_code != 200:
        print(f"HATA {r.status_code}: {r.text[:500]}")
        return 1
    data = r.json()
    try:
        part = data["candidates"][0]["content"]["parts"][0]
        inline = part["inlineData"]
        mime = inline.get("mimeType", "")
        pcm = base64.b64decode(inline["data"])
    except (KeyError, IndexError) as e:
        print(f"Beklenmeyen yanıt: {e} · {str(data)[:400]}")
        return 1
    # mime "audio/L16;codec=pcm;rate=24000" → rate çek
    rate = 24000
    if "rate=" in mime:
        try:
            rate = int(mime.split("rate=")[1].split(";")[0])
        except Exception:
            pass
    out = Path(__file__).resolve().parent / "_tts_test.wav"
    pcm_to_wav(pcm, out, rate=rate)
    secs = len(pcm) / 2 / rate
    print(f"✓ BAŞARILI · mime={mime} · {len(pcm)} bayt PCM · ~{secs:.1f} sn · {rate}Hz")
    print(f"  WAV: {out}")
    print("  → Dosyayı oynatıp ses kalitesini kontrol et.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
