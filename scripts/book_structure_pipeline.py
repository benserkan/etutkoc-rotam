"""Kitap yapısı boru hattı — CLI sarmalayıcısı (algoritma: app/services/book_pipeline.py).

Süper admin panelinde aynı iş arka plan işi olarak da koşar (Katalog → Tam kitap tara).


345 TYT Matematik denemesinde (2026-08-11) elle kanıtlanan yöntemin tek-komutluk
hâli. Aşamalar:

  A) İÇİNDEKİLER ÇIKARIMI — ilk N sayfa görüntüsü, ÇİFT bağımsız Gemini okuma:
     konu listesi + (varsa) test sayısı + başlangıç sayfa numarası. Grup
     başlıkları (BÖLÜM N) ve çalışma-dışı satırlar (önsöz/cevap anahtarı) elenir.
  B) SAYFA HİZALAMA — basılı sayfa numarası okunarak PDF-indeks ↔ kitap-sayfası
     ofseti otomatik kalibre edilir (taranmış PDF'lerde kapak/boş sayfa kayması).
  C) GÖVDE TARAMASI (yalnız test sayısı içindekilerde OLMAYAN konular) — her
     sayfanın üst şeridi taranır, numaralı grup bantları (TEST N / ÖSYM TADINDA
     SORULAR N / ORİJİNAL SORULAR N ...) çıkarılır. KURAL: bant testin HER
     sayfasında tekrarlanabilir + numara KATEGORİ başına 1'den başlar → konu
     toplamı = kategori başına EN BÜYÜK numara toplamı; 1..N ZİNCİR DENETİMİ
     kopukları raporlar; ÇİFT bağımsız tarama karşılaştırılır.
  D) JSON çıktı + konsol raporu (bayraklı satırlar insan gözü ister).

Kullanım:
  PYTHONPATH=. python scripts/book_structure_pipeline.py "<pdf>" \
      --name "345 TYT Kimya Soru Bankası" --publisher "345 Yayınları" \
      --subject "TYT Kimya" [--type soru_bankasi] [--grade-min 11]
      [--grade-max 12] [--graduate] [--toc-pages 12] [--out cikti.json]

Çıktı JSON'u `scripts/seed_book_catalog_json.py` ile dev/prod kataloğuna basılır.
Kredi DÜŞMEZ (kitap yapısı kişisel veri değil → ücretsiz anahtar).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import argparse
import base64
import json
import re
import unicodedata
from pathlib import Path

# --- DNS oto-yaması: dev makinesinin DNS'i Gemini hostunda ARALIKLI şaşıyor
# --- (koşu ortasında bile). Sarmalayıcı DAİMA kurulur: önce normal çözüm,
# --- başarısızsa sabit IP'lere düşer — prod'da normal yol hep kazanır.
import socket as _socket

_GEMINI_HOST = "generativelanguage.googleapis.com"
_GEMINI_IPS = ["172.217.113.4", "172.217.114.4", "172.217.117.4"]
_orig_gai = _socket.getaddrinfo


def _patched_gai(host, *args, **kwargs):
    if host == _GEMINI_HOST:
        try:
            return _orig_gai(host, *args, **kwargs)
        except OSError:
            pass
        last = None
        for ip in _GEMINI_IPS:
            try:
                return _orig_gai(ip, *args, **kwargs)
            except OSError as e:
                last = e
        raise last
    return _orig_gai(host, *args, **kwargs)


_socket.getaddrinfo = _patched_gai

from app.services.book_pipeline import PipelineError, run_pipeline  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--name", required=True)
    ap.add_argument("--publisher", required=True)
    ap.add_argument("--subject", required=True, help="Builtin ders adı (örn. 'TYT Kimya')")
    ap.add_argument("--type", default="soru_bankasi")
    ap.add_argument("--grade-min", type=int, default=None)
    ap.add_argument("--grade-max", type=int, default=None)
    ap.add_argument("--graduate", action="store_true")
    ap.add_argument("--toc-pages", type=int, default=12)
    ap.add_argument("--offset", type=int, default=None,
                    help="Bilinen ofseti dayat (kalibrasyon atlanır); pdf_idx = kitap_sayfası - 1 + ofset")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    last = {"stage": ""}

    def progress(pct: int, stage: str) -> None:
        if stage != last["stage"]:
            last["stage"] = stage
            print(f"[{pct:3d}%] {stage}")

    try:
        res = run_pipeline(args.pdf, toc_pages=args.toc_pages, offset=args.offset, progress=progress)
    except PipelineError as e:
        print(e.message)
        return 1

    print(f"\n{'KONU':<44}{'test':>5}  kaynak")
    for it in res["sections"]:
        tc = it["test_count"]
        flag = f"  ⚠ {it['flag']}" if it.get("flag") else ""
        print(f"{it['label']:<44}{tc if tc else '?':>5}  {it.get('source') or '?'}{flag}")
    print(f"\nTOPLAM: {len(res['sections'])} konu · {res['total_tests']} test")
    for g in res["gates"]:
        print(f"  {'OK ' if g['ok'] else 'X  '} {g['label']}: {g['detail']}")
    for w in res["warnings"]:
        print(f"  UYARI: {w}")

    out = {
        "name": args.name,
        "publisher": args.publisher,
        "subject": args.subject,
        "type": args.type,
        "target_grade_min": args.grade_min,
        "target_grade_max": args.grade_max,
        "target_graduate": bool(args.graduate),
        "sections": [
            {"label": it["label"], "test_count": it["test_count"], "source": it.get("source"),
             **({"page": it["page"]} if it.get("page") else {}),
             **({"flag": it["flag"]} if it.get("flag") else {})}
            for it in res["sections"]
        ],
        "warnings": res["warnings"],
    }
    out_path = args.out or (Path(args.pdf).stem[:40].strip().replace(" ", "_") + "_yapi.json")
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    if res.get("scan_debug") is not None:
        Path(str(out_path) + ".raw.json").write_text(
            json.dumps(res["scan_debug"], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nJSON: {out_path}  →  seed: PYTHONPATH=. python scripts/seed_book_catalog_json.py {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
