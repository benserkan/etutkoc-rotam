# ETÜTKOÇ Rotam — Mağaza Görselleri (Store Assets)

Premium, marka-tutarlı mağaza seti — **Claude (Anthropic) editöryel dili** uyarlandı.

## Tasarım dili
- **2 fotoğraf kapağı** — sinematik genç/öğrenci fotoğrafı (teal film tonu) + büyük
  **Playfair** serif slogan (beyaz) + alt film scrim + marka kilidi (gold spark +
  "etütkoç · rotam"). Claude'un "The AI for problem solvers / Keep thinking" ikilisi gibi.
- **6 özellik slaytı** — düz marka-renkli zemin (petrol / terracotta / koyu) + sola
  yaslı serif başlık + altın el-çizimi kıvrım + **kürasyonlu (idealize) UI kartı**
  ("dolu dolu": özet şerit + çok satır + ikincil bloklar). Ham ekran değil, hikâye
  anlatan temiz mockup.

## Renk & tipografi
- Marka cyan (petrol) `#0e7490` · logo sarısı `#f1b422` · mürekkep `#1c1d1f`
- Başlık **Playfair Display** (variable) — Türkçe tam · alt metin **Plus Jakarta Sans**
- Slayt zeminleri: petrol `(18,98,118)` · terracotta `(199,104,72)` · koyu `(28,40,47)`

## Dosyalar (`play/` — 1080×1920, 8 görsel)
1. `01-hero-rota` — kapak: **Hedefe giden net rota** (foto)
2. `02-hero-kimse-geride` — kapak: **Kimse geride kalmasın** (foto)
3. `03-erken-uyari` — Geride kalmadan önce uyar (öğrenci listesi · terracotta)
4. `04-ai-seans` — Yapay zekâ seansa hazırlar (koçluk içgörüsü · petrol)
5. `05-program` — Programı dakikada kur (haftalık plan · koyu)
6. `06-deneme-netleri` — Deneme netleri otomatik trend (grafik + kırılım · terracotta)
7. `07-veli` — Veli her şeyi görür (haftalık rapor · petrol)
8. `08-kurum-risk` — Riski gör, müdahale et (kurum risk paneli · koyu)

`play8/` — Play yükleme sırası `1.png … 8.png` (yukarıdaki sırayla, koç-öncelikli).
`feature-graphic.png` — 1024×500 · `store-icon-512.png` — 512×512.

## Kapak fotoğrafları
AI ile üretildi (Gemini), Gemini watermark'ı kırpıldı, teal film tonuyla tutarlı.
Kompozit: `_gen_covers.py` mantığı (film scrim + serif slogan + marka).
Yeni foto gelince aynı akışla yenilenir.

## Yeniden üretim
- Özellik slaytları: `python mobile/store/_gen_concept.py` (kürasyonlu kartlar).
- Fontlar `fonts/` (Playfair + Plus Jakarta Sans, OFL) + şeffaf amblem `mark-transp.png`.

## Mağaza spesifikasyonları
- Play telefon görseli 1080×1920 (≤2:1) ✓ · feature graphic 1024×500 ✓
- App Store: aynı set (ilk 8 = 2 kapak + 6 özellik; 10'a tamamlanabilir).
