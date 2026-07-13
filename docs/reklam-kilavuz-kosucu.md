# ETÜTKOÇ "Kılavuz Koşucu" Instagram Reklamı — Devam Dosyası

> Bu dosya, reklam çalışmasının TÜM kararlarını, hazır metinlerini ve kalınan yeri
> içerir. Yeni sohbette "Instagram reklam işine devam — docs/reklam-kilavuz-kosucu.md
> oku" demek yeterli. Son güncelleme: 2026-07-12.

---

## 1) Konsept ve konumlandırma

- **Metafor:** Kılavuz koşucu (paralimpik) asla atleti geçemez; finiş çizgisini önce
  atlet geçer. Kılavuzun görevi: tempoyu ayarlamak, virajı haber vermek, stresi
  yönetmek. → Koçluk: LGS/YKS maratonunda koç, öğrencinin bileğindeki iptir.
  Finişi öğrenci geçer, zafer onundur.
- **İki ayrı iş, iki ayrı kampanya (KARıŞTıRMA):**
  - **Kampanya A (ANA):** ETÜTKOÇ = Trabzon YERELİNDE birebir öğrenci koçluğu
    hizmeti. Kullanıcı (Serkan) TEK koç → kapasite sınırlı → hedef: WhatsApp'tan
    **ücretsiz tanışma görüşmesi** almak. Coğrafya: YALNIZ Trabzon ili.
  - **Kampanya B (2. hafta, opsiyonel):** rotam.etutkoc.com platformu = ULUSAL,
    koç/eğitimci kitlesine trafik kampanyası.
- Metinlerde "kesin başarı / net garantisi" gibi vaatler BİLİNÇLİ yok (Meta
  eğitim reklam politikası). Emoji yok (marka kuralı).

## 2) Video — ÜRETİLDİ ✅

- **Final:** `C:\Users\serkan\Desktop\etutkoc-kilavuz-kosucu-v2-seslendirmeli.mp4`
  — 46 sn · 1080×1920 (9:16) · 25 fps · H.264 + AAC · **-14,4 LUFS** · ~43 MB.
  Instagram'a doğrudan yüklenebilir.
- **Kaynak (kullanıcının DaVinci çıktısı, müzikli):** `Desktop\etutkoc-kilavuz-kosucu-v1.mp4` (41,3 sn).
- **İçerik:** gerçek paralimpik kılavuz koşucu görüntüleri + 7 segment Türkçe
  seslendirme (Gemini TTS "Kore" — demo videolarındaki marka sesi) + satır satır
  ortalanmış bant metinler (koyu lacivert %55 saydam bant + beyaz Segoe UI Bold;
  pivot cümle altın #F59E0B) + sol üstte küçük amblem + kapanış kartı (koyu
  #0F172A, logo, ETÜTKOÇ, "Öğrencinin yanındaki kılavuz.", etutkoc.com,
  **0505 673 85 61 · rotam@etutkoc.com**). IG güvenli alanlarına uyumlu
  (üst 250px / alt 420px boş).
- **Seslendirme akışı:** 0:01 "Bu koşucu… asla birinci olamaz." → 0:06 "Çünkü o,
  bir kılavuz. Kural gereği, finiş çizgisini önce atlet geçer." → 0:12 görev
  üçlemesi → 0:20 "LGS ve YKS de bir maratondur…" → 0:28 "Etütkoç'ta koç ve
  öğrenci aynı ritimde koşar…" → 0:37 "Finiş çizgisini öğrenci geçer. Zafer,
  onun olur." → 0:42 (müzik sustuktan sonra) "Ama o çizgiye… birlikte gelinir.
  Etütkoç."
- **Müzik:** kullanıcının müziği korundu; seslendirme sırasında otomatik kısılır
  (sidechain ducking), boşluklarda öne çıkar; 0:39'dan itibaren çözülür.
- **Yeniden üretim / varyant:** çalışma dosyaları `C:\Users\serkan\Desktop\etutkoc-reklam-kaynak\`
  (gen_vo.py = TTS üretimi [D:\LGS-Program venv'i + Gemini anahtarıyla çalışır],
  build_assets.py = metin/filter üretimi, filters.txt, vo\*.wav, bant metin
  txt'leri, logo512.png). Render komutu: ffmpeg (C:\ffmpeg\bin) +
  `-filter_complex_script filters.txt` — ayrıntı build_assets.py içinde.
  Kullanılan segmentler: s1, s2, s3, s4, s5, s6b, s7b (diğerleri yedek varyant).
- **Bekleyen varyant fikri:** ilk 3 sn farklı kanca ("Madalyayı hiç alamayacak
  bir koşucu tanıyın.") ile 2. video → kreatif A/B (sıklık 4'ü aşınca üret).

## 3) Kampanya A — Trabzon veli kampanyası (plan KESİN)

- **Amaç:** Etkileşim → Mesajlaşma uygulamaları → **WhatsApp** (0505 673 85 61)
- **Bütçe:** 200 TL/gün, 7 gün. Küçük kitle → sıklık takibi: haftalık **sıklık > 4**
  olursa yeni kreatif / dinlendirme.
- **Hedefleme:** Konum **Trabzon (il)** + **"bu konumda yaşayanlar"** (turist
  hariç — yaz sezonu kritik) · Yaş 32-52 · Demografi → Ebeveynler →
  **"Genç çocuğu olan ebeveynler (13-17)"** + ilgi: Eğitim, Özel ders, Sınav ·
  Advantage+ açık (konumu genişletmez, güvenli).
- **Yerleşim:** Manuel → yalnız Instagram → Reels + Hikâyeler + Akış.
- **Reklam:** kimlik = Serkan'ın IG hesabı → **"Mevcut gönderiyi kullan"** →
  organik Reel seçilecek. CTA: "WhatsApp'tan Mesaj Gönder".
- **Kapasite yönetimi:** görüşme takvimi dolunca reklamı DURDUR; kontenjan
  açılınca / Eylül kayıt döneminde yeniden aç ("musluk" modeli).
- **Ölçüm:** sohbet başına maliyet 40-90 TL normal; 150+ TL kalıcıysa metin/kitle
  değiştir. İlk 72 saat DOKUNMA (öğrenme evresi). WhatsApp'a 10 dk içinde yanıt.

### Hazır metinler (kopyala-yapıştır)

**Organik Reel açıklaması:**
> Kılavuz koşucu asla atleti geçemez. Kural gereği finiş çizgisini önce atlet geçer. Kılavuzun görevi; tempoyu ayarlamak, virajları önceden haber vermek, yarışın stresini yönetmektir.
>
> LGS ve YKS maratonunda Etütkoç, öğrencinin yanındaki o kılavuzdur. Finişi öğrenci geçer. Zafer onun.
>
> Bilgi: 0505 673 85 61 · etutkoc.com
>
> #lgs #yks #öğrencikoçluğu #eğitimkoçluğu #veli #sınavhazırlık #lgshazırlık #ykshazırlık #koçluk #etütkoç #trabzon #trabzoneğitim

(+ konum etiketi: Trabzon · kapak karesi: "Bu koşucu asla birinci olamaz." anı · paylaşım sonrası profile sabitle)

**Reklam ana metni — varyant 1 (yerel):**
> Trabzon'da, LGS ve YKS maratonunda çocuğunuzun yanında koşan bir kılavuz: Etütkoç. Haftalık program, günlük takip, deneme analizi ve her hafta veli bilgilendirmesi — birebir koçlukla. Çocuğunuz yalnızca koşmaya odaklanır; finişi o geçer.
>
> Yeni dönem kontenjanı sınırlıdır. Ücretsiz tanışma görüşmesi için WhatsApp'tan yazın.

**Reklam ana metni — varyant 2 (soru kancalı, A/B):**
> Çocuğunuz çalışıyor ama bir sistemi yok mu? Trabzon'da birebir öğrenci koçluğu: haftalık programı birlikte kurarız, her gün takip ederim, deneme sonuçlarını analiz eder, sizi her hafta bilgilendiririm. Eylül dönemi için ücretsiz tanışma görüşmesi planlayalım — WhatsApp'tan yazın.

**WhatsApp karşılama mesajı şablonu (reklamda):**
> Merhaba, Instagram'daki tanıtımınızı gördüm. Trabzon'da öğrenci koçluğu için tanışma görüşmesi planlamak istiyorum.

**WhatsApp Business hızlı yanıt (kısayol /tanisma):**
> Merhaba, hoş geldiniz. Ben Serkan Aydın, Etütkoç'ta öğrenci koçuyum. Size doğru yardımcı olabilmem için: öğrencimiz kaçıncı sınıfta ve hedefi LGS mi YKS mi? Uygun olduğunuz bir gün ve saati yazarsanız ücretsiz tanışma görüşmemizi planlayalım.

**IG bio:**
> Trabzon'da birebir LGS & YKS öğrenci koçluğu
> Haftalık program · Günlük takip · Deneme analizi
> Ücretsiz tanışma görüşmesi ↓
(link: etutkoc.com · ad alanı: "Serkan Aydın · Etütkoç" · kategori: Eğitim)

## 4) Kampanya B — Ulusal koç kampanyası (2. haftada)

- Hedef: **Trafik** · URL: `https://rotam.etutkoc.com/?utm_source=instagram&utm_medium=paid&utm_campaign=kilavuz-kosucu-koc` (Plausible'da utm_campaign ile izlenir)
- Kitle: TR, 24-55, ilgi: Öğretmenlik, Özel ders, Rehberlik, Eğitim · Bütçe 150-200 TL/gün
- Ana metin:
> Koçluk yapıyorsanız kılavuz sizsiniz. Etütkoç Rotam; haftalık program, kaynak takibi, deneme analizi ve veli bilgilendirmesini tek panelde toplar. Öğrenciniz koşar, siz yönetirsiniz. 14 gün ücretsiz deneyin.
- Başlık: "Koçluk paneliniz hazır — 14 gün ücretsiz" · CTA: "Kaydol"

## 5) DURUM — kalınan yer (2026-07-12)

| Adım | Durum |
|---|---|
| Video (seslendirme+metin+logo+kart) | ✅ Masaüstünde hazır |
| IG profesyonel hesaba çevirme | ✅ (kişisel eğitim-ağırlıklı hesap dönüştürüldü) |
| IG'ye WhatsApp bağlama (profil butonu) | ✅ yeşil tik doğrulandı |
| IG e-posta/telefon (serkan@etutkoc.com / 0505) | ✅ |
| IG kategori "Ürün/Hizmet" → **"Eğitim"** | ✅ 2026-07-12 |
| IG ad/bio/profil fotoğrafı markalama | ⏳ söylendi, teyit yok |
| **Facebook Sayfası "Etütkoç" oluşturma** | ✅ 2026-07-12 (facebook.com/profile.php?id=61591843981542 · kategori "Eğitim Danışmanı" · bio + tel 0505/rotam@/etutkoc.com/WhatsApp girildi · logo + kapak yüklendi) |
| IG ↔ FB Sayfası bağlama | ✅ 2026-07-12 (FB Sayfası → Ayarlar → Bağlantılı hesaplar → Instagram) |
| WhatsApp Business uygulamasına geçiş (0505) | ✅ 2026-07-12 (taşıma + işletme profili + /tanisma hızlı yanıt + karşılama mesajı) |
| IG profil WhatsApp butonu teyidi | ✅ 2026-07-12 (buton ziyaretçiye görünür; bağlantı sağlam) |
| Sayfa ↔ WhatsApp bağlama | ⏳ reklam kurulumunda Meta bağlatacak (reklam seti → WhatsApp seçiminde, kod Business uygulamasına gelir) |
| Reel organik paylaşım | ✅ 2026-07-12 (Reel yayında + profile sabitlendi — iPhone'da sabitleme = ızgarada küçük resme basılı tut → "Başa tut"; video kişisel FB profiline de paylaşılmış [düğme açık kalmış] — zararsız, istenirse FB'den silinir; Sayfaya ayrıca elle yükleme opsiyonel) |
| Ads Manager ödeme kartı | ✅ kart hesapta kayıtlıymış (yayın kart engeline takılmadı). NOT: reklam hesabı 573118503086463 (kişisel, TRY); geçmiş reklamlar Ağu 2025 (Mesajlar ₺795 → 3 sohbet ≈ 265 TL/sohbet = kıyas bazı, hedef 40-90 TL). Bireysel hesapta +%20 KDV (200 TL/gün ≈ 240 TL/gün fiili çekim). ERİŞİM DERSİ: adsmanager/billing linkleri IG kimliğine kilitlenip "ig_no_ad_account" veriyor → çözüm GİZLİ PENCEREDE facebook.com'a FB profiliyle girip adsmanager.facebook.com açmak |
| **Kampanya A** | ✅ **2026-07-12 YAYINDA / AKTİF** (onaylandı, harcama başladı). Kurulum: Etkileşim → Mesaj yönlendirme → MANUEL yalnız WhatsApp (0505) · perf=konuşma sayısı maks · 200 TL/gün · 12→19 Tem (bitişli) · Trabzon (il), yaş 32-53, detaylı hedefleme TEK kutu OR: "Ergenlik Çağında Çocuğu Olan Anne Babalar (13-17)" + "Öğrenci (eğitim)" · kitle 160-189 bin · MANUEL yerleşim: yalnız IG Akış+Hikâye+Reels (FB/Messenger/AN/WhatsApp Durum kapalı; "hariç tutulanlarda %5 harcama" KAPALI) · çok-reklamverenli + tüm Advantage+ kreatif iyileştirmeleri KAPALI · kreatif = organik Reel (17891359428579016) · WhatsApp şablonu form'suz + sade · reklam adı "Kilavuz Kosucu - Reel - v1" |
| **A/B testi** | ❌ BİLİNÇLİ OLARAK YOK — küçük kitle + 200 TL/gün bütçede iki reklam öğrenmeyi böler. Ads Manager'ın "A/B Testi"/"Kreatif testi" butonları KULLANILMAZ. Varyant 2 metni yalnız 3-4. günde CPA>150 TL kalırsa AYNI reklam setine 2. reklam olarak eklenir |
| **3-4. gün (15-16 Tem) maliyet kontrolü** | ⏳ CPA 40-90 TL normal → dokunma · 150+ TL kalıcı → varyant 2 ekle |
| **7. gün (19 Tem) değerlendirme** | ⏳ kampanya otomatik durur → Ads Manager ekran görüntüsüyle karar: uzat / yeni kreatif / dinlendir |

**NOT (Meta arayüz kısıtı):** Konum tipi "bu konumda YAŞAYAN kişiler" seçeneği
Advantage+ hedef kitle modunda ARAYÜZDEN KALDIRILMIŞ (klasik moda geçiş linki de
yok) → turist filtresi olarak **Diller = Türkçe** kullanıldı. Sonraki kampanyalarda
aynı kısıt beklenir.

**Meta hesap notları:** İşletme portfolyosu "Etutkoc Akademi" (business_id
1719661449046433). İçindeki **"Test WhatsApp Business Account"** + "Etütkoç
Akademi Koçluk Merkezi" app'i = platformun Cloud API (K2) çalışmasından; bu
reklamla İLGİSİZ, DOKUNMA. Reklam, telefondaki WhatsApp (Business) uygulamasındaki
0505 numarasıyla çalışır.

## 6) Yayın sonrası rutin

- WhatsApp'a 5-10 dk içinde dön (/tanisma şablonu) — dönüşümün yarısı hız.
- Günlük 5 dk: Ads Manager "sohbet başına maliyet" + "sıklık" sütunları; Reel
  yorumlarına aynı gün yanıt.
- Sıklık > 4 → yeni kanca varyantlı video üretilir (bölüm 2'deki kaynaklarla).
- Takvim dolunca reklamı durdur; Eylül kayıt döneminde yeniden aç.
