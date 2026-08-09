# Apple IAP (Uygulama İçi Satın Alma) Kurulum Rehberi — App Store 3.1.1 Çözümü

> **Neden:** Apple 5 kez 3.1.1 ile reddetti — "deneme bitince abonelik uygulama
> içinde satın alınamıyor, dış ödemeye yönlendiriliyor". Türkiye vitrininde tek
> yasal çözüm: solo koç paketlerini App Store'un kendi aboneliği (IAP) olarak
> satmak. **Kod tarafı hazır** (backend RevenueCat webhook + sync, mobil Paketim
> IAP ekranı). Bu rehber SENİN yapacağın kurulum adımlarını sırayla anlatır.
>
> Web/iyzico satışı AYNEN devam eder — kural 3.1.3(b): web'den alınan abonelik
> uygulamada kullanılabilir, çünkü aynı abonelik uygulamada IAP ile de satılıyor.

---

## SIRA ÖZETİ

0. **Hesabı kurumsala çevir** (KULLANICI KARARI 2026-07-19: bireysel değil
   Ltd. Şti. kimliğiyle satış) — D-U-N-S + Apple Support dönüşümü (~1-3 hafta)
1. App Store Connect: Paid Apps sözleşmesi + banka + vergi (bir kez, ŞİRKET adına)
2. Small Business Program başvurusu (%30 → %15 komisyon)
3. App Store Connect: 3 abonelik ürünü oluştur
4. RevenueCat hesabı + proje kurulumu (**Adım 0'ı beklemez — paralel yapılabilir**)
5. Sunucu `.env` + deploy (ben hazırladım — sen değerleri girip deploy edersin)
6. Mobil anahtar (`app.json`) + **EAS build 9** + TestFlight sandbox testi
7. App Store'a gönderim (inceleme notu hazır — en altta)

---

## ADIM 0 — Bireysel hesabı KURUMSALA çevir (önce bu)

Mevcut Apple Developer üyeliği BİREYSEL ("Serkan Aydn" yasal varlık). Karar:
şirket (ETÜTKOÇ Akademi ... Ltd. Şti.) kimliğiyle satış → dönüşüm gerekli.

1. **D-U-N-S numarası** — ✅ ALINDI (2026-08-09): **448959103**
   (ETÜTKOÇ Akademi Ltd. Şti. · MERSIS 0381113961000001 · vergi 3811139610 ·
   İskenderpaşa Mah. adresi). Sorgu/doğrulama:
   https://developer.apple.com/enroll/duns-lookup/ (Türkiye).
   Dönüşüm talebinde resmi ünvan bu D-U-N-S kaydıyla BİREBİR aynı yazılmalı.
2. **Dönüşüm talebi**: developer.apple.com → Contact Us → Membership →
   "Convert my individual membership to an organization". İstenecekler:
   resmi ünvan (D-U-N-S kaydıyla birebir), D-U-N-S, web sitesi (etutkoc.com),
   kurumsal e-posta.
3. **İmza yetkisi**: Apple, hesap sahibinin şirketi hukuken bağlama yetkisini
   doğrulayabilir (şirketi telefonla arayabilir). Münferit imza yetkilisi
   Avni Bektaş → onu bilgilendir (Apple ararsa "Serkan Aydın yetkilidir"
   demesi yeterli) + garanti için şirketten yazılı yetkilendirme hazırlat.
4. Dönüşüm tamamlanınca Business sayfasındaki yasal varlık ŞİRKET olur →
   Adım 1'e şirket kimliğiyle devam.

NOT: App Store yayını dönüşüm bitene kadar bekler (bilinçli tercih —
satıcı adı App Store'da şirket görünür, gelir şirkete gider).

## ADIM 1 — Paid Apps sözleşmesi + banka + vergi (ZORUNLU ön koşul)

> Ekrandaki mavi bant "update your legal entity information prior to signing"
> diyorsa: önce **Edit Legal Entity** ile yasal bilgiler tamamlanır; Paid Apps
> Agreement satırı (Status: New) ancak ondan sonra imzalanabilir.

App Store Connect → **Business (İş)** (eski adı Agreements, Tax, and Banking):

1. **Paid Apps Agreement** → satırdaki "View" → sözleşmeyi kabul et (Adım 0
   sonrası şirket kimliğiyle: ETÜTKOÇ Akademi ... Ltd. Şti.).
2. **Bank Account**: şirketin TL hesabı (IBAN — hesap sahibi adı yasal
   varlıkla birebir aynı olmalı). Apple ödemeleri buraya yapar (aylık,
   eşik ~$150 üzeri).
3. **Tax Forms**: ABD vergi formu (W-8BEN-E — şirket için; "beneficial owner"
   şirket, Türkiye vergi mukimi işaretlenir). Ayrıca varsa Türkiye/diğer
   bölge formları.

⏱ Onay birkaç saat–birkaç gün sürebilir. **Sözleşme "Active" olmadan abonelik
ürünü OLUŞTURULAMAZ** — bu yüzden ilk adım bu.

## ADIM 2 — Small Business Program (%15 komisyon)

- https://developer.apple.com/app-store/small-business-program/ → Enroll.
- Şart: son 12 ay App Store geliri < 1 M$ (bizde 0 → uygun).
- Onaylanınca komisyon %30 yerine **%15** olur. Başvuru 15 dakika sürer,
  ürün satışa çıkmadan önce yapılması avantajlı (geriye dönük uygulanmaz).

## ADIM 3 — Abonelik ürünleri (App Store Connect)

App Store Connect → ETÜTKOÇ Rotam → **Monetization → Subscriptions**:

### 3a. Abonelik grubu

- "Create Subscription Group" → Reference Name: **ETUTKOC Rotam Solo**
- Localization (Türkçe): görünen ad **ETÜTKOÇ Rotam** (kullanıcı Ayarlar →
  Abonelikler'de bu adı görür).
- Üç paket AYNI grupta olmalı (kullanıcı gruplar arası yükseltme/düşürme yapabilir).

### 3b. 3 ürün (Product ID'ler birebir böyle — kod bunlara bağlı!)

| Product ID | Referans adı | Görünen ad (TR) | Süre | Fiyat |
|---|---|---|---|---|
| `rotam_solo_pro_monthly` | Solo Baslangic Aylik | Solo Başlangıç | 1 ay | ₺2.499,99 |
| `rotam_solo_elite_monthly` | Solo Aylik | Solo | 1 ay | ₺4.999,99 |
| `rotam_solo_unlimited_monthly` | Solo Sinirsiz Aylik | Solo Sınırsız | 1 ay | ₺7.499,99 |

Her ürün için:
- **Subscription Duration**: 1 Month
- **Price**: Türkiye fiyatını seç (Apple fiyat listesinden en yakın kademe;
  web fiyatıyla aynı politika — 2.500 → ₺2.499,99 gibi). Diğer ülkeler
  otomatik türetilir (sorun değil — hedef kitle TR).
- **Localization (Türkçe)**: Görünen ad + kısa açıklama. Örnekler:
  - Solo Başlangıç: "10 öğrenciye kadar koçluk takibi + yapay zekâ özellikleri"
  - Solo: "25 öğrenciye kadar koçluk takibi + tüm yapay zekâ özellikleri"
  - Solo Sınırsız: "Sınırsız öğrenci + tüm özellikler"
- **Review Information → Screenshot**: Paketim ekranının ekran görüntüsü
  (build 9'u TestFlight'a yükleyince çekip buraya koyarsın; ürünü "hazır"
  yapmak için gerekli).

> Yıllık paket ŞİMDİLİK YOK (web'deki "akademik yıl" 10 aylık; Apple yalnız
> 1 yıllık süre destekler). İleride istenirse `rotam_solo_pro_yearly` vb.
> ID'lerle eklenir — backend bunları tanımaya hazır.

### 3c. App bilgileri

- App Information → **Privacy Policy URL**: https://rotam.etutkoc.com/kvkk (zaten var)
- App Description'ın SONUNA şu satırları ekle (Apple abonelikli uygulamalarda ister):
  ```
  Kullanım Şartları (EULA): https://rotam.etutkoc.com/kullanim-sartlari
  Gizlilik Politikası: https://rotam.etutkoc.com/kvkk
  ```

## ADIM 4 — RevenueCat kurulumu (~30 dk)

RevenueCat = makbuz doğrulama + abonelik olay köprüsü. Aylık ~2.500$ gelire
kadar ücretsiz. https://app.revenuecat.com → hesap aç (şirket e-postasıyla).

### 4a. Proje + App Store bağlantısı

1. "Create Project" → **ETUTKOC Rotam**
2. Project → Apps → **+ New → App Store** → Bundle ID: `com.etutkoc.rotam`
3. **In-App Purchase Key** yükle (StoreKit 2 doğrulaması için):
   - App Store Connect → Users and Access → **Integrations → In-App Purchase**
     → anahtar oluştur (.p8 indir; Issuer ID + Key ID'yi not al)
   - RevenueCat'te App Store app ayarlarına bu .p8 + Issuer ID + Key ID'yi gir.
4. **App Store Server Notifications** (önerilir): App Store Connect → App
   Information → App Store Server Notifications → Production + Sandbox URL
   alanlarına RevenueCat'in verdiği URL'yi yapıştır (RevenueCat app ayarında
   "Apple Server Notifications" bölümünde gösterir).

### 4b. Ürünler + Entitlements + Offering

1. **Products** → + New → 3 ürün ID'sini aynen ekle
   (`rotam_solo_pro_monthly`, `rotam_solo_elite_monthly`, `rotam_solo_unlimited_monthly`).
2. **Entitlements** → 3 entitlement oluştur ve ürünleri bağla:
   - `solo_pro` → rotam_solo_pro_monthly
   - `solo_elite` → rotam_solo_elite_monthly
   - `solo_unlimited` → rotam_solo_unlimited_monthly
3. **Offerings** → "default" offering → 3 paket ekle (Custom package):
   - Identifier `solo_pro` → ürün rotam_solo_pro_monthly
   - Identifier `solo_elite` → ürün rotam_solo_elite_monthly
   - Identifier `solo_unlimited` → ürün rotam_solo_unlimited_monthly

### 4c. Anahtarlar + webhook

1. **API Keys**:
   - **Public app-specific key** (`appl_...` ile başlar) → mobil uygulamaya
     gömülür (aşağıda Adım 6).
   - **Secret key** (`sk_...` ile başlar) → sunucu `.env`'ine
     (`REVENUECAT_SECRET_KEY`).
2. **Webhook** (Project → Integrations → Webhooks):
   - URL: `https://rotam.etutkoc.com/webhooks/revenuecat`
   - **Authorization header value**: uzun rastgele bir değer üret
     (sunucuda `openssl rand -hex 24`) → hem buraya hem `.env`'e
     (`REVENUECAT_WEBHOOK_AUTH`) AYNI değeri gir.
   - Event seçimi: hepsi açık kalabilir (backend gerekenleri işler).

## ADIM 5 — Sunucu `.env` + deploy

Sunucuda `/opt/etutkoc/deploy/.env` dosyasına ekle:

```
REVENUECAT_WEBHOOK_AUTH=<openssl rand -hex 24 çıktısı — webhook'takiyle aynı>
REVENUECAT_SECRET_KEY=<RevenueCat sk_... secret key>
```

Sonra (kod deploy'uyla birlikte):

```
cd /opt/etutkoc && git pull
bash deploy/redeploy.sh        # veya: docker compose up -d --build web worker next
```

Doğrulama:
```
curl https://rotam.etutkoc.com/webhooks/revenuecat
# → {"ok":true,"service":"revenuecat-webhook","auth_configured":true}
```
RevenueCat webhook ekranındaki "Send test event" → sunucu 200 dönmeli.

## ADIM 6 — Mobil anahtar + EAS build 9

1. `mobile/app.json` → `extra.revenueCatIosKey` alanına RevenueCat **public**
   iOS anahtarını (`appl_...`) yaz. (Public anahtar — uygulamaya gömülmesi
   güvenli ve normaldir.)
2. Build (react-native-purchases NATİVE modül → OTA YETMEZ, yeni build şart):
   ```
   cd mobile
   npx eas-cli build --platform ios --profile production
   npx eas-cli submit --platform ios
   ```
3. TestFlight'tan kur → **Sandbox test**:
   - iPhone → Ayarlar → App Store → Sandbox Account: App Store Connect →
     Users and Access → **Sandbox Testers**'da oluşturduğun test Apple ID'sini gir.
   - Uygulamada koç hesabıyla gir → Profil → **Paketim** → bir paket satın al
     (sandbox'ta gerçek para çekilmez; yenileme hızlandırılmıştır — aylık ≈ 5 dk).
   - Beklenen: satın alma → "Aboneliğin aktif" → paket etiketi değişir;
     web /teacher/plan da aynı paketi "App Store'dan yönetiliyor" notuyla gösterir.
   - Paketim ekranının ekran görüntüsünü al → ADIM 3b'deki ürün Review
     Screenshot alanlarına yükle.

## ADIM 7 — App Store gönderimi

App Store Connect'te yeni sürüm (1.0 build 9) oluştururken:

1. **Sürümle birlikte abonelikleri gönder**: sürüm sayfasında "In-App
   Purchases and Subscriptions" bölümüne 3 aboneliği EKLE (ilk abonelik
   gönderimi uygulama sürümüyle birlikte incelenir).
2. **App Review Information → Notes** alanına aşağıdaki İngilizce notu yapıştır.
3. Demo hesabı: paywall'da OLMAYAN, içinde veri bulunan koç hesabı ver
   (mevcut demo hesap bilgilerini koru) + istersen deneme süresi bitmiş bir
   hesap da ekle ki IAP paywall'ını görebilsinler.

### App Review notu (İngilizce — kopyala/yapıştır)

```
Hello,

Thank you for your previous feedback. We have resolved the Guideline 3.1.1
issues in this build:

1. Auto-renewable subscriptions via In-App Purchase: The paid coach plans
   (Solo Baslangic, Solo, Solo Sinirsiz) are now available for purchase
   inside the app using StoreKit In-App Purchase. See: Coach account →
   Profile → "Paketim" (My Plan). The screen shows the three auto-renewable
   subscriptions with localized App Store pricing, a purchase flow using the
   standard StoreKit payment sheet, a "Restore Purchases" button, links to
   our Terms of Use (EULA) and Privacy Policy, and the auto-renewal
   disclosure.

2. Trial expiry now leads to In-App Purchase: when the free trial ends, the
   user can subscribe directly in the app via IAP. There are no links,
   buttons or instructions directing users to external payment anywhere in
   the app.

3. Multiplatform parity (3.1.3(b)): subscriptions purchased on our website
   remain accessible in the app, and the same subscriptions are now equally
   available as In-App Purchases in the app.

Student, parent and institution-staff accounts have no purchase relationship
with us and see no commercial content; their access is provisioned by their
coach or institution.

Demo account: [demo koç e-posta / şifre]. To see the subscription screen:
log in as the coach → Profile tab → "Paketim".

Thank you for your time.
```

---

## Nasıl çalışıyor (özet — teknik referans)

- Mobil: RevenueCat `appUserID = backend User.id` ile yapılandırılır
  (girişte otomatik). Satın alma → StoreKit → RevenueCat doğrular →
  (a) uygulama `POST /api/v2/payment/iap/sync` ile ANINDA aktive eder,
  (b) RevenueCat webhook'u (`/webhooks/revenuecat`) her olayda (yenileme,
  iptal, bitiş) planı günceller.
- Backend eşleme: `rotam_solo_pro_monthly → solo_pro` vb.
  (`app/services/iap_service.py PRODUCT_PLANS`).
- `users.subscription_platform` = `app_store` | `iyzico` | `manual` — kanal
  koruması: iyzico aboneliğini Apple olayı düşüremez; App Store abonesine
  web'de iyzico ödeme butonu kapalı (409); yenileme cron'u app_store
  kullanıcılarını past_due yapmaz, RevenueCat'ten doğrular.
- İptal: kullanıcı App Store → Abonelikler'den iptal eder → CANCELLATION
  (erişim dönem sonuna kadar) → EXPIRATION (solo_free'ye düşer). Sistemin
  iyzico iptal semantiğiyle birebir aynı.
- Android: Google Play aynı kuralı ister (Play Billing). RevenueCat aynı kodla
  Play'i de destekler — sıradaki AAB güncellemesinde Play ürünleri + `goog_`
  anahtarı eklenerek açılır (ayrı iş).

## Sık sorulanlar

- **Fiyatı kim tahsil ediyor?** Apple. KDV'yi Apple toplar/beyan eder; sana
  komisyon düşülmüş net tutar gelir (Small Business ile %15 komisyon).
- **Web'den alan koç uygulamada ne görür?** "Aboneliğin web hesabın üzerinden
  yönetiliyor" — satın alma butonları gizli (çifte tahsilat olmaz).
- **İkisini birden alabilir mi?** Hayır — App Store aboneliği aktifken web
  iyzico ödemesi 409 ile engellenir; tersi yönde de mobil satın alma
  butonları web-yönetimli abonelikte gizlenir.
