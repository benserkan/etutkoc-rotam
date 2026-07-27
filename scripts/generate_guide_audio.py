"""Rehber (Rota) seslendirme üretici — Gemini 2.5 TTS ile adım başına MP3.

TEK KAYNAK: web/components/guide/coach-guide-content.json (oynatıcıyla aynı
metinler). Çıktı: app/static/guide/audio/{bolum}/{adim}.mp3. İdempotent
(var olanı atlar; --force ile yeniden üretir).

  python -m scripts.generate_guide_audio            # eksikleri üret (koç)
  python -m scripts.generate_guide_audio --guide student   # öğrenci rehberi
  python -m scripts.generate_guide_audio --force
  python -m scripts.generate_guide_audio --chapter kitap-ekle
  python -m scripts.generate_guide_audio --dry-run  # yalnız metinleri say

Ses: marka sesi "Kore" (demolarla aynı). PCM → WAV → ffmpeg MP3 ve key
rotasyonu scripts/generate_demo_audio.py'den aynen kullanılır.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# --- DEV MAKİNESİ DNS YAMASI --------------------------------------------------
# Bu ağın DNS'i generativelanguage.googleapis.com'u düşürüyor (aile filtresi).
# TLS/SNI engelli DEĞİL → hostname DoH ile çözülmüş sabit IP'lere yönlendirilir.
# Prod'u etkilemez (yalnız bu script çalışırken geçerli).
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
# ------------------------------------------------------------------------------

import argparse
import json
from pathlib import Path

from scripts.generate_demo_audio import pcm_to_mp3, tts
from app.services.system_secrets import get_gemini_free_keys, get_gemini_paid_key

ROOT = Path(__file__).resolve().parent.parent
CONTENT_BY_GUIDE = {
    "coach": ROOT / "web" / "components" / "guide" / "coach-guide-content.json",
    "student": ROOT / "web" / "components" / "guide" / "student-guide-content.json",
    "parent": ROOT / "web" / "components" / "guide" / "parent-guide-content.json",
}
OUT_ROOT = ROOT / "app" / "static" / "guide" / "audio"
VOICE = "Kore"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--guide", default="coach", choices=sorted(CONTENT_BY_GUIDE))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--chapter", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    content = json.loads(CONTENT_BY_GUIDE[args.guide].read_text(encoding="utf-8"))
    chapters = content["chapters"]
    if args.chapter:
        chapters = [c for c in chapters if c["key"] == args.chapter]
        if not chapters:
            print(f"HATA: bölüm yok: {args.chapter}")
            return 1

    keys: list[str] = []
    pk = get_gemini_paid_key()
    if pk:
        keys.append(pk)
    for fk in get_gemini_free_keys() or []:
        if fk and fk not in keys:
            keys.append(fk)
    if not keys and not args.dry_run:
        print("HATA: Gemini anahtarı yok.")
        return 1
    exhausted: set[str] = set()
    if not args.dry_run:
        print(f"Kullanılabilir TTS key sayısı: {len(keys)}")

    made = skip = fail = 0
    for ch in chapters:
        steps = ch["steps"]
        print(f"\n[{ch['key']}] {len(steps)} adım")
        for i, step in enumerate(steps):
            out = OUT_ROOT / ch["key"] / f"{i}.mp3"
            if args.dry_run:
                print(f"  {i}: {step['caption'][:70]}…")
                continue
            if out.exists() and not args.force:
                skip += 1
                continue
            try:
                pcm, rate = tts(step["caption"], VOICE, keys, exhausted)
                pcm_to_mp3(pcm, rate, out)
                made += 1
                print(f"  ✓ {out.relative_to(ROOT)}")
            except Exception as e:  # noqa: BLE001 — üretim scripti, devam et
                fail += 1
                print(f"  ✗ {ch['key']}/{i}: {e}")
    if not args.dry_run:
        print(f"\nÜretilen: {made} · Atlanan: {skip} · Hata: {fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
