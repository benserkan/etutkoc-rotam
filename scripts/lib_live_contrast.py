"""Canlı testler için KONTRAST ÖLÇÜMÜ — tek merkez (2026-09-10).

NEDEN AYRI MODÜL: koyu tema kontrastı tekrarlayan bir hata sınıfı
(`bg-*-50` + tema-token metin, ton+dark: varyant çifti…). Canlı testlere
ölçüm koyunca "görsel olarak iyi sanıyorduk" hatası kapanıyor — ama ölçümün
KENDİSİ doğru olmalı.

İKİ TUZAK (ikisi de burada çözülü):
  1. Tailwind v4 renkleri **OKLCH** üretir. `getComputedStyle().color`
     `oklch(...)` dönebilir; bunu `match(/[\\d.]+/g)` ile RGB sanıp parse
     etmek saçma sayılar verir (ölçüm "okunmuyor" der, ekranda okunuyordur).
     Çözüm: rengi canvas `fillStyle`e verip normalize edilmiş değeri okumak —
     tarayıcı hangi formatta gelirse gelsin RGB'ye çevirir.
  2. Zeminler yarı saydam olabilir (`dark:bg-teal-500/10`). Üstteki katmanı
     atlayıp opak ataya bakmak yanlış — katmanlar sırayla KARIŞTIRILIR.
"""
from __future__ import annotations

# Sayfada çalışan ölçüm. Dönen: {"bad": int, "worst": [str]}
# `selector` → hangi kökler taransın (querySelectorAll ile).
# `minRatio`  → bunun altındaki her yaprak metin "okunmuyor" sayılır.
CONTRAST_JS = """
(args) => {
  const { selector, minRatio } = args;

  // --- renk normalizasyonu: rengi 1x1 canvas'a ÇİZ ve pikseli oku.
  //     `fillStyle` geri okuması yetmez — Chrome modern renkleri
  //     `lab(...)` / `oklch(...)` olarak AYNEN döndürür ve ilk üç sayıyı
  //     RGB sanmak saçma sonuç verir (bu ölçüm bir kez tam olarak böyle
  //     yanlış "okunmuyor" dedi). getImageData daima sRGB byte verir.
  const cv = document.createElement('canvas');
  cv.width = 1; cv.height = 1;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const toRgba = (c) => {
    if (!c) return null;
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = 'rgba(0, 0, 0, 0)';
    try { ctx.fillStyle = c; } catch { return null; }
    ctx.fillRect(0, 0, 1, 1);
    const d = ctx.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  };

  const lum = ([r, g, b]) => {
    const f = (v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };

  // Yarı saydam zeminler ÜST ÜSTE bindirilir (alpha compositing).
  const overlay = (fg, bg) => {
    const a = fg[3];
    return [
      fg[0] * a + bg[0] * (1 - a),
      fg[1] * a + bg[1] * (1 - a),
      fg[2] * a + bg[2] * (1 - a),
      1,
    ];
  };

  const bgOf = (el) => {
    const layers = [];
    let n = el;
    while (n && n !== document.documentElement.parentElement) {
      const c = toRgba(getComputedStyle(n).backgroundColor);
      if (c && c[3] > 0.001) {
        layers.push(c);
        if (c[3] >= 0.999) break;           // opak katman: altı görünmez
      }
      n = n.parentElement;
    }
    let base = [255, 255, 255, 1];          // hiç opak katman yoksa: beyaz kâğıt
    if (layers.length && layers[layers.length - 1][3] >= 0.999) {
      base = layers.pop();
    }
    for (let i = layers.length - 1; i >= 0; i--) base = overlay(layers[i], base);
    return base;
  };

  const roots = [...document.querySelectorAll(selector)];
  let bad = 0;
  const worst = [];
  roots.forEach((root) =>
    root.querySelectorAll('*').forEach((el) => {
      if (el.children.length || !el.textContent.trim()) return;
      const st = getComputedStyle(el);
      if (st.visibility === 'hidden' || st.display === 'none') return;
      if (parseFloat(st.opacity) < 0.15) return;
      const fg = toRgba(st.color);
      if (!fg) return;
      const l1 = lum(fg);
      const l2 = lum(bgOf(el));
      const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      if (ratio < minRatio) {
        bad++;
        worst.push(
          el.textContent.trim().slice(0, 30) +
          ' :: r=' + ratio.toFixed(2) + ' :: ' + (el.className || el.tagName)
        );
      }
    })
  );
  return { bad, worst: worst.slice(0, 8) };
}
"""


def measure(page, selector: str, min_ratio: float = 3.0) -> dict:
    """`selector` ile eşleşen kökler altındaki yaprak metinlerin kontrastı.

    min_ratio 3.0: WCAG AA büyük metin eşiği. Küçük gövde metni için 4.5
    idealdir ama mevcut tasarımdaki bilinçli 'soluk yardımcı metin'leri
    kırmızıya boğmamak için canlı testlerde 3.0 kullanıyoruz — asıl yakalamak
    istediğimiz "hiç okunmayan" (r < 2) vakalar.
    """
    return page.evaluate(
        CONTRAST_JS, {"selector": selector, "minRatio": min_ratio}
    )
