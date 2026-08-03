# -*- coding: utf-8 -*-
"""Tıkla-gör balonları için KIRPILMIŞ odak görselleri üret (2026-08-04).

DERS (tekrarlayan hata): 1440×900 tam ekran görüntüsü ~448px genişlikte
gösterilince HİÇBİR ŞEY okunmuyor (tanıtım videosunda da aynı ders çıkmıştı).
KURAL: küçük boyutta gösterilecek ekran kanıtı daima İLGİLİ BÖLGEYE kırpılır;
tam kare yalnız "Ekranın tamamını gör" büyütmesinde kullanılır.

Girdi: app/static/guide/shots/*.png (rehber çekimleri, 1440×900, demo veri)
Çıktı: app/static/pricing-shots/*.png (odak kırpımları — repo'ya girer)

İdempotent — her koşuda yeniden üretir. Kutu değişince tekrar koş.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from pathlib import Path

from PIL import Image  # yalnız crop/save — PIL text çizimi bu ortamda segfault, KULLANMA

SRC = Path("app/static/guide/shots")
DST = Path("app/static/pricing-shots")

# dosya → (sol, üst, sağ, alt) — 1440×900 koordinatları (odak bölgesi)
CROPS: dict[str, tuple[int, int, int, int]] = {
    # Soru kartı + mor YAKLAŞIM İPUCU kutusu ("çözümü vermez, yolu gösterir")
    "ogr-ai-ipucu.png": (385, 230, 1055, 650),
    # Rota kartı: avatar + başlık + Dinle/Yenile + "Bu hafta ne oldu?" girişi
    "veli-rota-dinle.png": (176, 397, 1012, 815),
    # Karne aktarımı: başlık + "18 otomatik eşleşti · 2 AI eşledi" + ilk satırlar
    "aktar-onizleme.png": (272, 40, 1168, 545),
    # YSA: başlık + "yeniden çözme zamanı" bandı + kart sırası (rozetli)
    "ogr-yanlislar.png": (224, 96, 1216, 570),
    # Rota yorumu (seslendir butonu + bölümlü metin girişi)
    "veli-rota-yorum.png": (176, 397, 1012, 815),
}


def main() -> int:
    DST.mkdir(parents=True, exist_ok=True)
    for name, box in CROPS.items():
        src = SRC / name
        if not src.exists():
            print(f"[ATLA] kaynak yok: {src}")
            continue
        im = Image.open(src)
        crop = im.crop(box)
        out = DST / name
        crop.save(out, optimize=True)
        w, h = crop.size
        print(f"[OK] {name}: {box} -> {w}x{h}  ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
