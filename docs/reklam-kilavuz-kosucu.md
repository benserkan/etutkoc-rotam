# ETÜTKOÇ "Kılavuz Koşucu" Instagram Reklamı — Devam Dosyası

> Bu dosya, reklam çalışmasının TÜM kararlarını, hazır metinlerini ve kalınan yeri
> içerir. Yeni sohbette "Instagram reklam işine devam — docs/reklam-kilavuz-kosucu.md
> oku" demek yeterli. Son güncelleme: 2026-07-20 (Kampanya A sonuç analizi + v3
> kısa video + Kampanya A2 kurulum planı — bölüm 7).

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

## 6) Kampanya A SONUÇ ANALİZİ (12-19 Tem 2026) + v3 video + A2 planı — 2026-07-20

**Veri kaynakları:** Ads Manager "Creative Reporting" xlsx (toplam) + gün×yaş×
cinsiyet CSV + kullanıcı WhatsApp raporu. Yerleşim kırılımı ALINMADI (eksik).

**Sonuç:** 1.276,52 TL harcama · 7.069 erişim · 10.108 gösterim · sıklık 1,43 ·
CTR %2,9 (297 tıklama, CPC 4,30) · CPM 126 TL · **8 sohbet · CPA 159,57 TL**
(hedef 40-90'ın üstünde). **WhatsApp gerçeği: 8 sohbetin HEPSİ hayalet** — tek
dokunuşla hazır mesaj gönderip hiçbiri yanıt yazmadı → gerçek lead 0.

**Teşhisler (kanıtlı):**
1. **Mesaj ulaşmadı:** ort. video izlenme 5 sn; koçluk mesajı 0:20'deydi →
   izleyicilerin ~%90'ı reklamın ne sattığını duymadı (%50 işaretine ulaşan %7,5).
2. **Tıklama→sohbet %2,7** (normal %15-30): kaçak tıklama-sonrasında; düşük
   niyetli tıklayıcı + tek genel şablon.
3. **Kampanya ısınırken bitti:** ilk 4 gün CPA 195 → son 3 gün 138 (18 Tem:
   **85,8** — hedef bandın içi). Bitişli kampanya öğrenme evresini israf etti.
4. **Yaş/cinsiyet:** Erkek 45-54 = 3 sohbet @ **55,8 TL** (yıldız). Kadın
   35-54 = 2 sohbet @ 273 TL. **Advantage+ yaş 32-53 sınırını delmiş**: 18-24'e
   121 TL (0 sohbet), 55+'ya 171 TL → bütçenin ~%23'ü band dışı.

**KREATİF: v4 ÜRETİLDİ ✅ (reklamda BU kullanılır):**
`Desktop\etutkoc-kilavuz-kosucu-v4.mp4` (36,0 sn · 1080×1920 · 25fps ·
-14,6 LUFS · ~25,5 MB). Koçluk mesajı **0:04'te** (amber "LGS ve YKS
maratonunda / çocuğunuzun kılavuzu."), **0:11-0:18 "tıpkı" köprüsü** (kullanıcı
isteği: "Tıpkı, görme engelli koşucuya kılavuzluk eden bu koşucu gibi... koç da,
çocuğunuzun yanında koşar." — video↔koç ilişkisi açıkça kurulur; ekranda GUIDE
önlüklü koşucu), 0:18 Trabzon+hizmet bantları (4 kısa bant — taşma düzeltildi:
merkez 72/76px, alt 52px, "Deneme analizi·Veli bilgilendirmesi" İKİYE bölündü),
0:27 kapanış kartı (logo + "Ücretsiz tanışma görüşmesi" + WhatsApp). Kanca:
"Madalyayı hiç alamayacak bir koşucu tanıyın." Kurgu: v1'den 0-4,4 (çıkış) +
5,0-16,4 (kılavuz+atlet) + 29,8-40,8 (yarış→finiş→zafer). Ara sürüm v3-kisa
(28,4sn, tıpkı köprüsüz) masaüstünde yedek durur.
Üretim: `etutkoc-reklam-kaynak\gen_vo_v3.py` + `gen_vo_v4.py` (TTS segmentleri
n1/n2/n2b/n3/n4, Kore sesi; **D:\LGS-Program kökünden çalıştırılır** — DB yolu
göreli; DoH getaddrinfo yaması içinde) + `build_assets_v4.py` (filters_v4.txt) +
ffmpeg (**logo girişi `-loop 1` ŞART** — yoksa tek karelik PNG fade'de
saydamlaşıp kartta kaybolur; `-t 36.0`).

**Kampanya A2 kurulum çerçevesi (yeniden yayın):**
- v3'ü önce ORGANİK Reel olarak paylaş + profile sabitle → reklamda "mevcut
  gönderiyi kullan".
- Amaç/bütçe aynı: Etkileşim → mesaj → yalnız WhatsApp · 200 TL/gün ·
  **BİTİŞ TARİHİ YOK** (7. gün elle değerlendirme — musluk modeli).
- Hedefleme: Trabzon (il) · **yaş 35-55, minimum yaş 35 SERT kontrol**
  (Advantage+ minimumu sert sayar → 18-24 israfı kesilir) · detaylı hedefleme
  YALNIZ "Ergenlik Çağında Çocuğu Olan Anne Babalar (13-17)" — **"Öğrenci
  (eğitim)" ÇIKARILDI** · Diller=Türkçe · cinsiyet tümü (kadın dışlanmaz —
  mesaj artık ilk 10 sn'de net, yeni veriyle tekrar ölçülür).
- Yerleşim: Manuel yalnız IG Akış+Hikâye+Reels (aynı); **4-5. gün Dağılım→
  Yerleşim kontrolü** — çöp tıklama Reels'ten geliyorsa Reels kapatılır.
- Ana metin: varyant 2 (soru kancalı — niyet süzer). CTA "WhatsApp'tan Mesaj Gönder".
- **Hazır sorular (3 adet)** reklamın WhatsApp şablon ayarına: "Ücretsiz tanışma
  görüşmesi planlamak istiyorum." / "Koçluk sistemi nasıl işliyor?" / "Fiyat ve
  kontenjan bilgisi alabilir miyim?" (tek genel şablon 8 hayalet lead üretti).
- **WhatsApp takip protokolü:** ilk yanıt ≤10 dk ve TEK soru ("Öğrencimiz
  kaçıncı sınıfta?") — eski /tanisma 3 soruyu birden soruyordu, yanıt maliyeti
  yüksek · 24 saat sessize BİR nazik hatırlatma ("kontenjan sınırlı" vurgulu).
- Eşikler: ilk 72 saat dokunma · 5. gün CPA>150 → metin varyantı ekle · sıklık>4
  → yeni kreatif · 7. gün gün+yaş/cinsiyet+yerleşim kırılımıyla değerlendir.

**KAMPANYA A2 YAYINDA ✅ (2026-07-20):** v4 Reel organik paylaşıldı (linksiz,
sabitlendi; mavi tik alındı — reklamda güven rozeti) → "Kilavuz Kosucu A2 -
WhatsApp - Trabzon" kampanyası yayınlandı. Kurulum birebir: Etkileşim → manuel
yalnız WhatsApp (0505) · konuşma maks · 200 TL/gün · **bitişsiz** · Trabzon +
yaş 35-55 + YALNIZ "Ergenlik Çağında Çocuğu Olan Anne Babalar (13-17)" +
Türkçe · manuel yerleşim yalnız IG (Akış+Hikâye+Reels; WhatsApp Durum/platformu
kaldırıldı) · mevcut gönderi = v4 Reel · CTA WhatsApp · **mesaj şablonu
"Konuşmalar Başlatın" + 3 hazır soru** (tanışma görüşmesi / sistem / fiyat-
kontenjan; form bilinçli reddedildi) · çok-reklamverenli + Advantage+
iyileştirmeleri + **Meta Business Agent (AI yanıt) KAPALI** · kreatif testi yok.
Kurulum sırasında yakalanan Meta tuzakları: bütçe 300 önerisi→200'e çekildi ·
yaş önerisi 30-60→35-55 · "Öğrenci (eğitim)" ilgisi silindi · form şablonu→
konuşma şablonu. SIRADA: 23 Tem ilk gözlem (dokunma yok) → 24-25 Tem gün+
yerleşim+yaş/cinsiyet kırılımı ile ara analiz → 27 Tem 7-gün değerlendirmesi.
WhatsApp protokolü: ≤10 dk tek-soru yanıt + 24s tek hatırlatma.

## 7) Yayın sonrası rutin

- WhatsApp'a 5-10 dk içinde dön (/tanisma şablonu) — dönüşümün yarısı hız.
- Günlük 5 dk: Ads Manager "sohbet başına maliyet" + "sıklık" sütunları; Reel
  yorumlarına aynı gün yanıt.
- Sıklık > 4 → yeni kanca varyantlı video üretilir (bölüm 2'deki kaynaklarla).
- Takvim dolunca reklamı durdur; Eylül kayıt döneminde yeniden aç.
