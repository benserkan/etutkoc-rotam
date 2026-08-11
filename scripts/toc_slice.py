"""Tam kitap PDF'inden İÇİNDEKİLER dilimi üret (panel yüklemesi için, ≤10MB).

Admin panelindeki "Fotoğraftan/PDF'ten oku" aracı içindekiler ister; tam kitap
10MB sınırına takılır. Bu araç ilk N sayfayı küçük bir PDF'e kırpar.

Kullanım: python scripts/toc_slice.py "<tam_kitap.pdf>" [sayfa_sayisi=12]
Çıktı:    <tam_kitap>_icindekiler.pdf (aynı klasöre)
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import fitz


def main() -> int:
    if len(sys.argv) < 2:
        print("Kullanım: toc_slice.py <kitap.pdf> [sayfa_sayisi=12]")
        return 2
    src = Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    doc = fitz.open(src)
    out = fitz.open()
    out.insert_pdf(doc, from_page=0, to_page=min(n, doc.page_count) - 1)
    dst = src.with_name(src.stem + "_icindekiler.pdf")
    # Taranmış sayfalar büyük olabilir → sığana kadar görüntüye indirger
    out.save(dst, garbage=4, deflate=True)
    if dst.stat().st_size > 9_500_000:
        small = fitz.open()
        for page in out:
            pm = page.get_pixmap(dpi=110)
            p = small.new_page(width=pm.width, height=pm.height)
            p.insert_image(p.rect, pixmap=pm)
        small.save(dst, garbage=4, deflate=True)
    print(f"{dst.name} — {min(n, doc.page_count)} sayfa · {dst.stat().st_size/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
