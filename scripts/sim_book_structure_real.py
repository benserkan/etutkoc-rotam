"""GERÇEK Gemini ile kitap yapısı okuma doğrulaması (A4 benchmark).

Kullanım:
    PYTHONPATH=. python scripts/sim_book_structure_real.py <dosya1> [dosya2 ...]

Verilen içindekiler kaynağını (PDF veya JPEG/PNG foto) gerçek Gemini ile
ÇİFT okur; bölüm listesi + test sayıları + şüpheli/uyarı dökümünü basar.
Sunucu gerektirmez (servis doğrudan çağrılır). Kredi düşmez (personal_data=False
→ ücretsiz anahtar). Değerlendirme İNSAN gözüyle: çıktı belgeyle karşılaştırılır.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from pathlib import Path

# --- DNS filtresi atlatma (YALNIZ bu geliştirme makinesi) ---------------------
# Bu ağın DNS'i generativelanguage.googleapis.com sorgusunu düşürüyor (aile
# filtresi). TLS/SNI engelli değil → hostname DoH ile çözülmüş sabit IP'ye
# yönlendirilir. Prod'u etkilemez (yalnız bu script).
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
            except OSError as e:  # pragma: no cover
                last_err = e
        raise last_err
    return _orig_gai(host, *args, **kwargs)


_socket.getaddrinfo = _patched_gai
# -----------------------------------------------------------------------------

from app.services import ai_book_structure as abs_svc

_MIME = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        print("Kullanım: sim_book_structure_real.py <pdf|foto> [foto2 ...]")
        return 2
    files: list[tuple[bytes, str]] = []
    for p in paths:
        mime = _MIME.get(p.suffix.lower())
        if not mime:
            print(f"Desteklenmeyen uzantı: {p}")
            return 2
        raw = p.read_bytes()
        print(f"  girdi: {p.name} ({len(raw)/1024:.0f} KB, {mime})")
        files.append((raw, mime))

    print("\nGERÇEK Gemini ÇİFT okuma başlıyor…\n")
    try:
        r = abs_svc.read_structure(files)
    except abs_svc.NotATocError as e:
        print(f"[NOT_A_TOC] {e}")
        return 1
    except (abs_svc.AIServiceUnavailable, abs_svc.AIInvalidResponse) as e:
        print(f"[AI HATA] {type(e).__name__}: {e}")
        return 1

    print(f"Kitap adı  : {r['book_title']}")
    print(f"Yayınevi   : {r['publisher']}")
    print(f"Ders ipucu : {r['subject_hint']} · Sınıf ipucu: {r['grade_hint']}")
    print(f"Okuma      : {r['read_count']} bağımsız okuma\n")
    total = 0
    missing = 0
    suspects = 0
    for i, s in enumerate(r["sections"], 1):
        tc = s["test_count"]
        flag = " [ŞÜPHELİ]" if s["suspect"] else ""
        if tc is None:
            missing += 1
            print(f"  {i:>2}. {s['label']:<55} test: ?{flag}")
        else:
            total += tc
            print(f"  {i:>2}. {s['label']:<55} test: {tc}{flag}")
        if s["suspect"]:
            suspects += 1
    print(f"\nTOPLAM: {len(r['sections'])} bölüm · {total} test · "
          f"{missing} sayısız · {suspects} şüpheli")
    for w in r["warnings"]:
        print(f"  UYARI: {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
