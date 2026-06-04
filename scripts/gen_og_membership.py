"""WhatsApp üyelik teklifi OG banner'ı (1200×630 statik PNG) üretir.

Dinamik next/og route'u WhatsApp tarayıcısında küçük thumbnail'e düşüyordu
(Content-Length yok + must-revalidate). Statik PNG (temiz .png + Content-Length +
uzun cache) WhatsApp-dostu → büyük hero önizleme. Türkçe metin Pillow + Arial ile
piksel olarak basılır (serve anında font bağımlılığı yok).

Çalıştır:  python scripts/gen_og_membership.py
Çıktı:     web/public/og-membership.png
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUB = ROOT / "web" / "public"
OUT = PUB / "og-membership.png"

W, H = 1200, 630
TEAL = (17, 122, 134)        # #117A86  etütkoç
GOLD = (232, 172, 45)        # #E8AC2D  rotam
DOT = (148, 163, 184)        # slate-400
SLATE = (71, 85, 105)        # #475569 tagline
DOMAIN_C = (14, 116, 144)    # #0e7490
GRAD_TOP = (14, 116, 144)    # #0e7490
GRAD_BOT = (19, 78, 74)      # #134e4a

ARIAL = "C:/Windows/Fonts/arial.ttf"
ARIALBD = "C:/Windows/Fonts/arialbd.ttf"


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def main() -> None:
    img = Image.new("RGB", (W, H), GRAD_TOP)
    d = ImageDraw.Draw(img)
    # Dikey gradyan (cyan → koyu teal)
    for y in range(H):
        d.line([(0, y), (W, y)], fill=_lerp(GRAD_TOP, GRAD_BOT, y / H))

    # Beyaz kart + yumuşak gölge
    cx0, cy0, cx1, cy1 = 64, 70, W - 64, H - 70
    radius = 48
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([cx0, cy0 + 14, cx1, cy1 + 14], radius=radius,
                         fill=(0, 0, 0, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    img.paste(shadow, (0, 0), shadow)
    d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=radius, fill="white")

    cx = W // 2

    # Amblem (şeffaf)
    mark = Image.open(PUB / "etutkoc-mark.png").convert("RGBA")
    msize = 132
    mark = mark.resize((msize, msize), Image.LANCZOS)
    img.paste(mark, (cx - msize // 2, cy0 + 46), mark)

    # Wordmark: "etütkoç · rotam" (çok renkli, ortalı)
    wf = ImageFont.truetype(ARIALBD, 78)
    seg = [("etütkoç", TEAL), (" · ", DOT), ("rotam", GOLD)]
    widths = [d.textlength(s, font=wf) for s, _ in seg]
    total = sum(widths)
    wx = cx - total / 2
    wy = cy0 + 200
    for (s, c), w in zip(seg, widths):
        d.text((wx, wy), s, font=wf, fill=c)
        wx += w

    # Tagline (Türkçe — Arial piksel)
    tf = ImageFont.truetype(ARIAL, 30)
    tagline = "Öğrenci koçluğu takip platformu"
    tw = d.textlength(tagline, font=tf)
    d.text((cx - tw / 2, cy0 + 300), tagline, font=tf, fill=SLATE)

    # Domain
    df = ImageFont.truetype(ARIALBD, 26)
    dom = "rotam.etutkoc.com"
    dw = d.textlength(dom, font=df)
    d.text((cx - dw / 2, cy0 + 352), dom, font=df, fill=DOMAIN_C)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, "PNG", optimize=True)
    print(f"OK -> {OUT} ({OUT.stat().st_size} bytes, {img.size})")


if __name__ == "__main__":
    main()
