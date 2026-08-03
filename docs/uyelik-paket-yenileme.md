# Üyelik Paket Sistemi Yenileme — Sorun Analizi + Öneri (2026-08-04)

> Durum: **ONAY BEKLİYOR** — kod değişikliği yapılmadı. Onay sonrası fazlı uygulama
> (DB yedekli + tam senaryo testli).

---

## 1. SORUN ANALİZİ (mevcut durum denetimi)

### 1.1 Kartlar bayat — en satılabilir özellikler görünmüyor
Kartlardaki 5 madde Mayıs sonundan kalma. Haziran–Ağustos'ta eklenen ve
**satışın asıl silahı olan** özelliklerin HİÇBİRİ kartlarda yok:

| Eklenen özellik (canlı) | Kartlarda? | Satış değeri |
|---|---|---|
| AI karne okuma (deneme PDF → soru soru konu analizi, %99 doğruluk) | ❌ | ÇOK YÜKSEK — rakip ayrıştırıcı #1 |
| Konu × deneme analizi (ısı haritası, "+X net fırsatı", unutulan konular) | ❌ | YÜKSEK |
| Yanlış Soru Arşivi (foto + aralıklı tekrar + AI ipucu + hata türü) | ❌ | YÜKSEK — SınavKoçu'nun en güçlü özelliğinin üstünü yaptık |
| Rota Veli Asistanı (sesli yorum + yazılı/sesli sohbet) | ❌ | ÇOK YÜKSEK — pazarda benzeri yok |
| Randevu sistemi + Google Meet + hatırlatma | ❌ | ORTA-YÜKSEK |
| Mobil uygulama (öğrenci/veli/koç) | ❌ | YÜKSEK — güven sinyali |
| Rota Rehberi (sesli onboarding turu) | ❌ | ORTA — "kurulum korkusunu" kırar |
| Müfredat ilerleme + sınava yetişme projeksiyonu | ❌ | ORTA |
| AI kullanım şeffaflığı + kişi bazında kontrol (dün eklendi) | ❌ | ORTA — kurum satışında güven |

### 1.2 Farklılaşma yok — "neden 7.500₺?" sorusu cevapsız
Üç ücretli kartta madde listesi **birebir aynı**; yalnız öğrenci sayısı ve kredi
rakamı değişiyor. Anthropic dahil tüm olgun SaaS'lar kademeli anlatım kullanır:
"**Öncekinin hepsi, artı:** …". Bizde üst paketin tek görünür farkı bir sayı.

### 1.3 İsimlendirme — iç jargon müşteriye sızmış
"Solo" bizim segment kodumuz (solo koç = bağımsız koç). Müşteri için anlamı yok.
"Solo Başlangıç / **Solo** / Solo Sınırsız" — ortadaki paketin adının düz "Solo"
olması ayrıca absürt. Kod adları (`solo_pro`, `solo_elite`) DB/iyzico/App Store
ürünlerine gömülü — **kod adlarına DOKUNULMAZ**, yalnız görünen ad değişir
(sıfır migration riski; aşağıda).

### 1.4 Tasarım — dar kutu + soyut kredi + tutarsızlık
- `/teacher/plan` konteyneri **max-w-3xl (768px)** — geniş ekranda 3 kart dar
  şeride sıkışıyor ("insanın içi daralıyor" tespiti birebir doğru).
- Kredi soyut: "1.500 kredi" tek başına hiçbir şey anlatmıyor. Kredinin neye
  yettiği (kaç karne okuma, kaç veli sohbeti) hiçbir yerde yok.
- **Tutarsızlık (ekran görüntüsünde görünür):** Ücretsiz pakette "Yapay zekâ
  kredisi 0/200" çubuğu görünüyor ama AI kapalı. (200 = e-posta/WA iç
  maliyet payı; kullanıcıya "AI kredim var ama kullanamıyorum" dedirtiyor.)
- Karşılaştırma tablosu, SSS, güven sinyalleri (iptal/deneme koşulları) yok.

### 1.5 Veli-AI kredisi pakete kademelenmemiş
[project-ai-credits-packaging] kararı: veli-AI tüketimi ölçülüp paketlere
kademelenecekti. Ölçüm altyapısı tamam (AI_PARENT_* kind'ları + dünkü kişi
kırılımı); paket sunumuna hiç yansımadı.

---

## 2. BENCHMARK BULGULARI (web araştırması)

**Anthropic (claude.com/pricing):** Free / Pro / Max ("5x · 20x kullanım").
Dersler: (a) kademeli anlatım "Everything in Pro, plus…"; (b) üst paket
farkı KULLANIM ÇARPANI ile anlatılıyor (bizim kredi modeline birebir uyar);
(c) özellik karşılaştırma tablosu kategorili; (d) kullanıcıyı pakete yönlendiren
mini sihirbaz.

**Good-Better-Best literatürü:** 3 kademe standart; insanlar ortadakini seçer
("center-stage effect" — 3 kademe, 2 kademeye göre ~1.4× dönüşüm). Orta paket
"orantısız iyi anlaşma" hissi vermeli; "En popüler" rozeti oraya. Bizim yapı
(3 ücretli + ücretsiz) zaten doğru — içerik ve sunum eksik.

**CoachAccountable (koçluk SaaS):** saf kapasite bazlı (danışan sayısı) +
**ROI çerçevesi**: "faturamız, danışanlarından kazandığının %3'ünden azı".
Bize uyarlaması güçlü: koç öğrenci başına ayda ~2.000-3.000₺ alıyor;
Patika (10 öğrenci) 2.500₺ = **öğrenci başına ~250₺/ay ≈ kazancının ~%10'u**,
kart altına "öğrenci başına günde ~8₺" mikro-satırı yazılabilir.

**TutorBird/Teachworks:** düz araç fiyatlaması ($17-50); bizim fiyat onların
10 katı — bu yüzden kartlar "araç listesi" değil **"değer hikâyesi"** anlatmalı
(AI asistan + veli deneyimi + erken uyarı = koçun hizmet kalitesi ve kapasitesi).

---

## 2b. MODEL — üyelik satan gelişmiş sitelerin UÇTAN UCA AKIŞI

Kullanıcı direktifi: yalnız koçluk yazılımı değil, paketle üyelik satan tüm
gelişmiş sitelerden akış modeli. Notion/Anthropic/Slack/Canva incelemesinden
çıkan 7 aşamalı model + Rotam'ın her aşamadaki durumu:

| Aşama | En iyiler ne yapıyor | Rotam'da durum | Boşluk → aksiyon |
|---|---|---|---|
| **1. Keşif** (landing) | Değer vaadi + sosyal kanıt + video; paket kartları landing'de özet | Landing + tanıtım videosu + dinamik kartlar VAR | Kartlar bayat → yenilenen kart bileşeni landing'e de yansır |
| **2. Paket sayfası** | Notion anatomisi: hero → aylık/yıllık toggle → kademeli kartlar ("Öncekinin hepsi, artı") → "Önerilen" rozeti → KATEGORİLİ karşılaştırma matrisi → müşteri referansı → SSS. Anthropic: pakete yönlendiren mini sihirbaz | Toggle VAR; kartlar kademesiz/bayat; matris-SSS-referans YOK. **Referans sistemi (testimonials) sistemde ZATEN VAR ama pricing'e hiç bağlanmamış!** `recommended_plan` hesabı da var | Kart yeniden yapımı + matris + SSS + referans bandı + public sayfaya "Kaç öğrencin var?" seçici (mevcut recommended_plan mantığının öne çıkarılması) |
| **3. Deneme + aha anı** | Kartsız 14 gün + onboarding turu + deneme boyunca DEĞER SAYACI ("bu hafta X ürettin") | Kartsız deneme + Rota Rehberi VAR | Deneme banner'ına değer sayacı: "Denemende 3 karne okudun, 5 veli yorumu ürettin — Patika'da böyle devam eder" (mevcut kullanım dökümünden beslenir) |
| **4. Uygulama-içi yükseltme anları** | Reforge: bağlamsal prompt jenerik banner'dan %28 fazla çevirir. Kural: ÖZELLİĞİN ADI + PLANIN FİYATI + TEK TIK; "değer anında" göster, "iş anında" değil. Slack mesaj-limitinde, Canva HD-export'ta gösterir | 402/403 toast + "Paketi al" butonu + TrialBanner VAR (temel bağlamsal yapı kurulu) | Kapasite dolunca (11. öğrenciyi eklerken) özellik-adlı tam ekran teklif; karne okuma SONUCU ekranında ("bu analiz Patika'da her denemede") — değer anı yerleşimi |
| **5. Ödeme** | Tek sayfalık güvenli checkout + güven işaretleri | iyzico 3DS canlıda uçtan uca KANITLI + iOS IAP hazır | Dokunma (Faz 1'de yalnız sunum; akış sadeleştirmesi ayrı iş) |
| **6. Satın alma sonrası** | "Hoş geldin — paketinle neler açıldı" ekranı/e-postası, kurulum daveti | Aktivasyon + pasif öğrenci reaktivasyonu + e-postalar VAR | Ödeme sonucu sayfasına "paketinle açılanlar" bloğu (küçük ekleme) |
| **7. Yenileme/iptal** | D-3 hatırlatma, dönem sonuna kadar erişim, iptalde neden anketi + kurtarma | D-3 + past_due paywall + iptal-dönem-sonu VAR (güçlü) | İptal anında tek soruluk neden anketi (Faz 3) |

**Modelin ana ilkesi:** üyelik kartı ≠ ödeme kartı. Satış anlatımı (değer,
kademeli özellik, referans) public `/pricing`'te yaşar; `/teacher/plan` ise
"hesabını yönet + yükselt" sayfasıdır — Notion'un pricing (pazarlama) / billing
(ayarlar) ayrımı. İki yüzey AYNI kart bileşenini kullanır, ton farklıdır.

---

## 3. ÖNERİ

### 3.1 Yeni adlandırma (görünen ad — kod adları sabit)

**Seçenek A — Rota metaforu (ÖNERİLEN):** markanın kendisi (Rotam, pusula/rota
kimliği) hikâyeyi veriyor; paketler koçun yolculuğunu anlatır:

| Kod (DB, DEĞİŞMEZ) | Yeni görünen ad | Kapasite | Fiyat | Hikâye |
|---|---|---|---|---|
| solo_free | **Keşif** | 3 öğrenci | Ücretsiz | sistemi keşfet |
| solo_pro | **Patika** | 10 öğrenci | 2.500₺ | yola çıktın |
| solo_elite | **Rota** ⭐ en popüler | 25 öğrenci | 5.000₺ | rotandasın — amiral paket, marka adıyla aynı |
| solo_unlimited | **Zirve** | sınırsız | 7.500₺ | tavan yok |
| solo_trial | (paket değil) "14 gün ücretsiz deneme — Rota deneyimi" | | | |

Kurum tarafı zaten segment-tanımlı ve iyi çalışıyor; hafif rötuş:
"Kurum Tanıma (Ücretsiz) · Etüt · Dershane · Kampüs (Özel Okul/Enterprise)".

**Seçenek B — düz/açıklayıcı:** Başlangıç · Profesyonel · Sınırsız.
Güvenli ama jenerik, marka değeri taşımaz.

**Seçenek C — Anthropic tarzı:** Pro · Pro 25 · Pro Sınırsız.
Kullanım-çarpanı anlatımına uyar ama Türkçe pazarda soğuk.

### 3.2 Kart içerik stratejisi — kademeli + insan-dili kredi

**Keşif (ücretsiz):** çekirdek döngünün tamamı, AI'sız:
3 öğrenci · kitap→program→günlük takip · veli daveti + haftalık e-posta raporu ·
elle deneme girişi + net grafiği · Yanlış Soru Arşivi (elle) · mobil uygulama ·
sesli rehber turu. *AI kredi çubuğu ücretsizde GİZLENİR (1.4'teki tutarsızlık).*

**Patika — "Keşif'tekilerin hepsi, artı:"**
10 öğrenci · **AI karne okuma** (deneme PDF'ini yükle, soru soru konu analizi) ·
**Rota Veli Asistanı** (veline sesli yorum + sohbet) · YSA'da AI ipucu ·
sesli dikte + fotoğraftan seans notu · seans öncesi AI hazırlık ("bugün şunu
konuş") · randevu + Google Meet · **aylık 1.500 kredi** — "*örnek: her öğrenci
için ayda 2 karne okuma + haftalık veli yorumu + soru etiketleme, rahat yeter*".

**Rota (en popüler) — "Patika'dakilerin hepsi, artı:"**
25 öğrenci · **aylık 4.000 kredi** (veli asistanı tam kapasite — her veliye
haftalık sesli yorum + sınırsıza yakın sohbet) · AI kariyer sentezi vurgusu ·
öncelikli destek.

**Zirve — "Rota'dakilerin hepsi, artı:"**
Sınırsız öğrenci · **aylık 8.000 kredi** · **birebir kurulum ve taşıma desteği**
(kitaplarını + öğrencilerini birlikte kurarız — büyüme stratejisindeki "kurulumu
BEN yaparım" argümanının pakete bağlanması) · yeni özelliklere erken erişim.

Fonksiyon kısıtlaması YOK (ücretli paketler işlevsel eşit kalır — mevcut ödeyen
müşterilerden hiçbir şey geri alınmaz, churn riski sıfır). Farklılaşma:
kapasite + kredi + hizmet katmanı (destek/kurulum/erken erişim).

### 3.3 Kredi modeli
- **Tahsisler DEĞİŞMEZ** (1.500/4.000/8.000 — risk yok). Değişen: sunum.
- Kartlarda kredi insan diline çevrilir + "Krediler ne yapar?" mini tablosu
  (karne okuma 6 · veli sesli yorum 6+2 · veli sohbet sorusu 3 · YSA etiket 2 ·
  seans içgörüsü 6 · dikte 3).
- Veli-AI kademelendirmesi bu yapıyla kartlara girer ("veli asistanı temel /
  tam kapasite") — teknik kota eklemeden anlatım düzeyinde (ölçüm sürüyor;
  gerçek kota ayrı karar).
- İleride (Faz 3, ayrı onay): kredi ek paketi satışı ("+1.000 kredi").

### 3.4 Tasarım yenileme (web canlı)
**/teacher/plan:** konteyner max-w-3xl → **max-w-6xl**; kart bileşeni yeniden:
kademeli maddeler, kredi insan-dili satırı, rozetler (Sana uygun/En popüler),
öğrenci-başına fiyat mikro-satırı; altına "Krediler ne yapar?" tablosu +
katlanır **paket karşılaştırma matrisi** (kategorili: Takip · Yapay Zekâ ·
Veli Deneyimi · Analiz · Destek) + **SSS** (iptal, kredi biterse, yükseltme,
deneme). Mevcut kullanım/onay kartları (dünkü) altta kalır.
**/pricing (public):** aynı kart bileşeni + karşılaştırma matrisi + SSS +
güven şeridi (14 gün · kart istemez · istediğin zaman iptal) + tanıtım
videosuna köprü. Kurum sekmesi korunur.
**Tek bileşen iki yüzeyde** (PricingCards zaten paylaşımlı — genişletilir).

### 3.5 "Gelişmiş paket yönetimi" (admin)
Bugün: fiyat/kapasite admin'den düzenlenebilir (app_settings override) ama
**madde listeleri kodda**. Öneri (Faz 2): kart maddeleri + rozetler + kredi
açıklamaları da pricing config'e taşınır → süper admin `/admin/pricing`'den
yeni özellik eklendiğinde kartı KODSUZ günceller. (Bu, "kartlar bayat kaldı"
sorununun kalıcı çözümü — içerik güncelleme kod deploy'una bağlı olmaktan çıkar.)

---

## 4. GÜVENLİK / RİSK PLANI (kullanıcı şartları)

1. **Plan kodları değişmez** → users.plan, abonelik kayıtları, iyzico akışı,
   RevenueCat ürün eşlemesi (`rotam_solo_pro_monthly` → solo_pro), kota/kredi
   anahtarları AYNEN çalışır. Migration YOK (yalnız görüntü katmanı + config).
2. **DB yedeği** her deploy öncesi (pg_dump, mevcut prosedür).
3. **Test kapsamı (deploy öncesi zorunlu):** pricing 8 · subscription_lifecycle 22 ·
   entitlement 13 · iyzico 29 · IAP 23 · membership 19 · signup p3 13 · kurum 18+18+19 ·
   admin_pricing 8 · tenant 29 + **Playwright canlı senaryolar**: yeni koç kayıt →
   deneme → kart görünümleri → yükseltme diyaloğu → (mock) ödeme; kurum yöneticisi
   plan talebi; admin fiyat düzenleme round-trip.
4. **Yayılım süpürmesi:** "Solo" geçen tüm yüzeyler (signup paneli, e-posta
   şablonları [katalogdan besleniyor → otomatik düzelir], membership teklif
   sayfası, admin ekranları, mobil Paketim [API'den besleniyor → OTA'sız düzelir;
   yalnız App Store ürün GÖRÜNEN adları ASC'den elle güncellenir — kullanıcı]).
5. Fazlı gidiş: **Faz 1** isim+içerik+2 sayfa tasarım (bu onayla) → **Faz 2**
   admin'den düzenlenebilir kart içeriği + karşılaştırma matrisi genişletmesi →
   **Faz 3** (ayrı karar) kredi ek paketi / gerçek veli-AI kotaları.

---

## 5. AÇIK KARARLAR (onay bekliyor)

1. İsim seti: A (Keşif/Patika/Rota/Zirve) — B (Başlangıç/Profesyonel/Sınırsız) — C (Pro ailesi)?
2. Üst paket ayrıcalıkları (birebir kurulum desteği Zirve'de, öncelikli destek
   Rota+Zirve, erken erişim Zirve) — onay?
3. Faz 1 kapsamı onayı (isim + kart içerikleri + /teacher/plan + /pricing tasarım).
4. Kredi tahsisleri: dokunulmasın (önerilen) / yeniden hesaplansın?
