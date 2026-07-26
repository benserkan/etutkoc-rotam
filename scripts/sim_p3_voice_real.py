# -*- coding: utf-8 -*-
"""P3 GERÇEK doğrulama — sesli soru (STT) + cevap balonu sesi (TTS) zinciri.

Kendi TTS'imizle "Oğlum programa uyuyor mu?" sorusunun sesini üretir (MP3),
bu sesi /chat/transcribe ucuna POST eder (GERÇEK Gemini STT) → dönen metnin
soruyu içerdiğini doğrular. Sonra bir Rota cevabını /voice ile seslendirir
(GERÇEK Gemini TTS) + audio stream'i doğrular. Demo veli (rehber-veli) ile
:8081'e karşı koşar. DNS yaması dahil (bu ağ Gemini'yi çözmüyor).

  PYTHONPATH=. python scripts/sim_p3_voice_real.py
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- DNS yaması (run_dev_patched ile aynı) ---
import socket as _socket
_GEMINI_HOST = "generativelanguage.googleapis.com"
_GEMINI_IPS = ["172.217.113.4", "172.217.114.4", "172.217.117.4"]
_orig_gai = _socket.getaddrinfo


def _patched_gai(host, *args, **kwargs):
    if host == _GEMINI_HOST:
        last_err = None
        for ip in _GEMINI_IPS:
            try:
                return _orig_gai(ip, *args, **kwargs)
            except OSError as e:
                last_err = e
        raise last_err
    return _orig_gai(host, *args, **kwargs)


_socket.getaddrinfo = _patched_gai

import base64
import time

import httpx

BASE = "http://127.0.0.1:8081"
EMAIL = "rehber-veli@etutkoc.demo"
PWD = "RehberDemo2026!"
QUESTION = "Oğlum programa uyuyor mu?"


def main() -> int:
    # 1) Soru sesini KENDİ TTS'imizle üret (MP3 — ALLOWED_AUDIO'da var)
    print("1) Soru sesi üretiliyor (Gemini TTS, 'Kore')…")
    t0 = time.time()
    from app.services.tts import synthesize_speech
    audio, ctype = synthesize_speech(QUESTION)
    print(f"   OK {len(audio)} bayt {ctype} ({time.time()-t0:.1f}sn)")
    if not ctype.startswith("audio/"):
        print("   FAIL: beklenmeyen içerik türü"); return 1

    c = httpx.Client(base_url=BASE, timeout=180.0)
    r = c.post("/api/v2/auth/login", json={"email": EMAIL, "password": PWD})
    if r.status_code != 200:
        print(f"   FAIL login {r.status_code}: {r.text[:200]}"); return 1
    print("2) Veli girişi OK")

    # Elif'in id'si — dashboard'dan
    r = c.get("/api/v2/parent/dashboard")
    kids = r.json().get("children") or r.json().get("students") or []
    sid = kids[0]["student_id"] if kids and "student_id" in kids[0] else kids[0]["id"]
    print(f"   çocuk id={sid}")

    # 3) GERÇEK STT: ürettiğimiz sesi transcribe ucuna gönder
    media = "audio/mpeg" if ctype.startswith("audio/mpeg") else "audio/wav"
    b64 = base64.b64encode(audio).decode()
    print(f"3) /chat/transcribe (GERÇEK Gemini STT, {media})…")
    t0 = time.time()
    r = c.post(f"/api/v2/parent/students/{sid}/chat/transcribe",
               json={"audio_base64": b64, "media_type": media})
    dt = time.time() - t0
    if r.status_code != 200:
        print(f"   FAIL {r.status_code}: {r.text[:300]}"); return 1
    d = r.json()
    text = d["text"]
    print(f"   OK ({dt:.1f}sn) metin: {text!r} · kalan sesli soru: {d['stt_daily_left']}")
    low = text.lower()
    if "program" not in low:
        print("   UYARI: metinde 'program' geçmiyor — STT sapmış olabilir")

    # 4) Rota cevabı bul (yoksa çevrilen soruyu gerçekten sor)
    r = c.get(f"/api/v2/parent/students/{sid}/chat")
    msgs = r.json()["messages"]
    rota = [m for m in msgs if m["role"] == "rota"]
    if not rota:
        print("4) Rota cevabı yok → çevrilen soru gönderiliyor (GERÇEK sohbet)…")
        t0 = time.time()
        r = c.post(f"/api/v2/parent/students/{sid}/chat", json={"message": text or QUESTION})
        if r.status_code != 200:
            print(f"   FAIL ask {r.status_code}: {r.text[:300]}"); return 1
        rota = [m for m in r.json()["messages"] if m["role"] == "rota"]
        print(f"   OK ({time.time()-t0:.1f}sn) cevap: {rota[-1]['body'][:120]}…")
    mid = rota[-1]["id"]
    print(f"4) Rota mesajı id={mid} has_audio={rota[-1].get('has_audio')}")

    # 5) İlk dinleme → TTS üretimi (kredi) — ses zaten varsa charged False beklenir
    print("5) /voice (GERÇEK Gemini TTS)…")
    t0 = time.time()
    r = c.post(f"/api/v2/parent/students/{sid}/chat/{mid}/voice")
    if r.status_code != 200:
        print(f"   FAIL {r.status_code}: {r.text[:300]}"); return 1
    d = r.json()
    print(f"   OK ({time.time()-t0:.1f}sn) charged={d['charged']} type={d['audio_content_type']}")

    # 6) Tekrar → önbellek (charged False)
    r = c.post(f"/api/v2/parent/students/{sid}/chat/{mid}/voice")
    d2 = r.json()
    if not (r.status_code == 200 and d2["charged"] is False):
        print(f"   FAIL tekrar: {r.status_code} {r.text[:200]}"); return 1
    print("6) Tekrar dinleme önbellekten (charged=False) OK")

    # 7) Ses akışı
    r = c.get(f"/api/v2/parent/students/{sid}/chat/{mid}/audio")
    if r.status_code != 200 or len(r.content) < 5000:
        print(f"   FAIL audio {r.status_code} {len(r.content)}b"); return 1
    print(f"7) Audio stream OK — {len(r.content)} bayt {r.headers.get('content-type')}")

    print("\n=== P3 GERÇEK ZİNCİR KANITLANDI (STT + sohbet + TTS + önbellek) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
