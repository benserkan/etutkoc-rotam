"""özdebir-ayt-16-02 kararlılık + merge tanısı: çift okuma N kez tekrarlanır;
her okumanın ham ders kovaları (ad, adet, soru-no aralığı, part etiketi) ve
merge sonucu dökülür → 311-satır çift sayımının kök nedeni görülür."""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# DNS filtresi atlatma (yalnız bu makine — bkz. sim_exam_import_benchmark.py)
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
from collections import defaultdict
from pathlib import Path

from app.services import ai_exam_import
from app.services import exam_import_service as svc

PDF = Path(r"D:\ÖĞRENCİ KOÇLUĞU\ÖĞRENCİLER\BERRA\DENEME ANALİZLERİ\özdebir-ayt-16-02-Berra.pdf")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2


def _dump_read(tag: str, r: dict) -> None:
    qs = r.get("questions") or []
    buckets: dict = defaultdict(list)
    for q in qs:
        buckets[(q.get("part"), q.get("subject"))].append(q.get("no"))
    print(f"  {tag}: {len(qs)} soru · başlık='{r.get('exam_title')}' · "
          f"özet dersleri={[(s.get('part'), s.get('name'), s.get('net')) for s in r.get('subjects') or []]}",
          flush=True)
    for (part, subj), nos in sorted(buckets.items(), key=lambda x: str(x[0])):
        nn = [n for n in nos if n is not None]
        rng = f"{min(nn)}-{max(nn)}" if nn else "no'suz"
        print(f"    part={part!r:<8} {subj!r:<28} {len(nos):>3} soru · no {rng}",
              flush=True)


def main() -> int:
    b64 = base64.b64encode(PDF.read_bytes()).decode("ascii")
    for i in range(1, N + 1):
        print(f"\n===== KOŞU {i} =====", flush=True)
        r1, r2 = ai_exam_import.read_exam_pdf_double(b64)
        _dump_read("OKUMA-1 (ham)", r1)
        _dump_read("OKUMA-2 (ham)", r2)
        svc._sanitize_parts(r1)
        svc._sanitize_parts(r2)
        merged, _ = svc.merge_reads(r1, r2)
        qs = merged["questions"]
        n_sus = sum(1 for q in qs if q.get("_suspect"))
        print(f"  MERGE: {len(qs)} satır · şüpheli {n_sus}", flush=True)
        buckets: dict = defaultdict(int)
        for q in qs:
            buckets[q.get("subject")] += 1
        for subj, cnt in sorted(buckets.items(), key=lambda x: -x[1]):
            print(f"    {subj!r:<30} {cnt}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
