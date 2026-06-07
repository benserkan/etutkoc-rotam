# ETÜTKOÇ Rotam — Mağaza Görselleri (Store Assets)

Premium, marka-tutarlı mağaza görsel seti. İki tasarım dili:

- **Hero kapaklar (koyu)** — Khan Academy tarzı: koyu petrol yıldız zemin +
  marka kilidi (amblem + "etütkoç · rotam") + büyük beyaz **Playfair** serif slogan +
  **logo sarısı** (#f1b422) alt-slogan + altın kıvılcım + cyan el-çizimi + eğik cihaz.
- **Özellik görselleri (açık)** — Udemy tarzı editöryel: düz açık-gri zemin +
  sola yaslı **Playfair** serif başlık (siyah + **marka cyan'ı** #0e7490 vurgu) +
  cyan alt-başlık + alttan taşan çerçeveli cihaz. Logo/şekil yok, sade.

## Renk & tipografi
- Marka cyan (petrol): `#0e7490` · logo sarısı (altın): `#f1b422` · mürekkep: `#1c1d1f`
- Hero zemin: koyu petrol-lacivert degrade `(13,49,60)→(6,23,30)` + yıldız alanı
- Başlık: **Playfair Display** (variable, wght 780–800) — Türkçe ş/ğ/ç/İ/ı tam
- Alt-başlık / wordmark: **Plus Jakarta Sans** (variable, wght 600–700)

## Dosyalar
- `play/` — tüm set (1080×1920, 16 görsel):
  - `01-hero-rota` · `02-hero-kimse-geride` (koyu kapaklar)
  - `03..16` — özellikler: öğrenci listesi, erken uyarı, program, konu perf.,
    AI içgörü, denemeler, öğrenci bugün/hafta/gelişim, veli detay/rapor,
    kurum koç/risk/tükenmişlik
- `play8/` — **Play Store için seçilmiş 8** (koç-öncelikli, yüklenme sırası 1–8):
  1 hero-rota · 2 hero-kimse-geride · 3 program · 4 konu-perf · 5 AI içgörü ·
  6 denemeler · 7 veli-rapor · 8 kurum-risk
- `feature-graphic.png` — 1024×500 Play feature graphic (koyu hero dili)
- `src/` — telefondan çekilen ham ekran görüntüleri (1080×2340)
- `fonts/` — Playfair + Plus Jakarta Sans (OFL) + şeffaf amblem `mark-transp.png`

## Mağaza spesifikasyonları
- **Play telefon görseli**: 1080×1920 (9:16, ≤2:1 oran şartına uygun) ✓
- **Play feature graphic**: 1024×500 ✓
- **App Store**: aynı set kullanılabilir (max 10 görsel; ilk 8'e 2 hero + 6 özellik)

## Yeniden üretim
Görseller PIL (Pillow) + cairosvg ile kod-üretimli. Slogan/renk/düzen değişince
`fonts/` içindeki variable font'larla composer yeniden çalıştırılır (amblem SVG'den
şeffaf rasterize edilir: `web/public/etutkoc-mark.svg`).
