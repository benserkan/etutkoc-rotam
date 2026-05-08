# WhatsApp Cloud API — Production Setup Rehberi

ETÜTKOÇ Rotam'ın veli bildirim sistemi şu an **stub modda** çalışıyor: WA mesajları gerçekten gönderilmiyor, sadece logger'a yazılıyor ve `external_id="stub:{template_name}"` döndürülüyor. Bu rehber stub'tan production'a nasıl geçileceğini adım adım anlatır.

> **Maliyet uyarısı:** Meta WhatsApp Cloud API mesaj başına ücretlendirir (UTILITY ~$0.005, AUTHENTICATION ~$0.07). Türkiye için fiyatlar farklı olabilir; Meta panelinden güncel tariflere bak. Kanal başına aylık tavan koyman kritik (kod hatası → spam → fatura patlaması).

---

## Genel akış (özet)

1. Meta Business hesabı + WhatsApp Business hesabı oluştur
2. Telefon numarası ekle ve doğrula
3. Permanent System User Access Token üret
4. 6 mesaj şablonunu Meta paneline ekleyip onaylat
5. `.env`'e WhatsApp config'ini gir + `WHATSAPP_ENABLED=true`
6. Webhook'u Meta paneline tanıt
7. Tek bir test mesajıyla doğrula

Tahmini süre: **2-4 saat** (şablon onayı Meta tarafında 1-24 saat sürebilir).

---

## 1. Meta Business hesabı

Eğer henüz yoksa:

1. https://business.facebook.com adresine git, Facebook hesabınla gir
2. **Create Account** → Business Manager kur (firma adı: ETÜTKOÇ veya seçtiğin)
3. Sol menü → **Settings** → **Business Info** → vergi numarası, adres vs. doldur (Türkiye'de KEP adresi de istenebilir)

---

## 2. WhatsApp Business Account (WABA)

1. Business Manager'da: sol menü → **WhatsApp Accounts** → **Add** → **Create WhatsApp Account**
2. Bir telefon numarası ekle:
   - Yeni hat al ya da mevcut bir numarayı kullan (numarada aktif WhatsApp/WhatsApp Business **olmamalı**, taşıyabilirsin ama 2FA kapatman gerekir)
   - SMS/voice ile doğrula
3. Display name: "ETÜTKOÇ Rotam" (Meta onayı 1-3 iş günü)

---

## 3. Phone Number ID + Access Token

1. https://developers.facebook.com → **My Apps** → **Create App** → **Business** type
2. App'e WhatsApp ürününü ekle: **Add Product** → **WhatsApp** → **Set Up**
3. **API Setup** sekmesinde:
   - `Phone number ID`: 15 haneli sayısal — **bunu kopyala**, `.env`'e `WHATSAPP_PHONE_NUMBER_ID` olarak yaz
   - `WhatsApp Business Account ID`: ileride lazım olabilir
4. Access Token (kalıcı):
   - Üstteki **Temporary access token** 24 saatlik — production için işe yaramaz
   - Kalıcı için: Business Settings → **System Users** → **Add** → "etutkoc-server" sistem kullanıcısı
   - **Generate Token** → ilgili App'i seç → permissions: `whatsapp_business_messaging` + `whatsapp_business_management`
   - Süre: **Never expire** seç (yoksa 60 gün)
   - **Token'ı kopyala — Meta bir daha gösteremez!** Hemen `.env`'e `WHATSAPP_ACCESS_TOKEN` olarak yaz
5. App Secret (webhook imza doğrulama için):
   - App Settings → **Basic** → **App Secret** → Show → kopyala → `.env` `WHATSAPP_APP_SECRET`

---

## 4. 6 mesaj şablonu

Meta Business → WhatsApp Manager → **Message Templates** → **Create Template**.

> ⚠ Şablon adları kodda hardcoded — birebir aşağıdaki gibi yazmalısın. Türkçe karakter sorunu yaşamamak için isimde sadece ASCII kullan (`ş` yerine `s` vs.). Body metninde Türkçe karakter serbest.

Her şablonda:
- Category: aşağıda belirtilen
- Language: **Turkish (tr)**
- Allow category change: ✓ (Meta'nın kategorimi yeniden değerlendirmesine izin ver)

### 4.1 `veli_otp_kodu` (AUTHENTICATION)

Telefon doğrulama OTP'si. Kod tarafında: `app/services/whatsapp.py::send_otp`

- **Category:** Authentication
- **Type:** One-time password
- **Body:**
  ```
  ETÜTKOÇ Rotam doğrulama kodunuz: {{1}}
  Kodu kimseyle paylaşmayın. 5 dakika geçerli.
  ```
- **Button türü:** `One-tap autofill` (URL button, Android'de otomatik kod doldurma)
  - Kod tarafında `sub_type: "url"` ile gönderiliyor (`whatsapp.py::send_otp`)
  - Eğer "Copy code" türünü seçersen kod `sub_type: "copy_code"` olmalı — bu durumda whatsapp.py'ı da güncellemek lazım, **mevcut akışta One-tap autofill seç**
  - Meta paneli URL pattern'i isterse: `https://etutkoc.com/?otp={{1}}` (hayalî, sadece autofill için tetikleyici)
- **Variables:** `{{1}}` = 6-haneli kod

### 4.2 `veli_haftalik_rapor` (UTILITY)

- **Category:** Utility
- **Body:**
  ```
  Merhaba, {{1}} adlı öğrencinin haftalık çalışma raporu hazır.
  Bu hafta {{2}}/{{3}} görev tamamlandı (oran %{{4}}).
  Detaylı rapor: {{5}}
  ETÜTKOÇ Rotam
  ```
- **Variables:**
  - `{{1}}` öğrenci adı
  - `{{2}}` tamamlanan
  - `{{3}}` toplam plan
  - `{{4}}` yüzde (örn "75")
  - `{{5}}` rapor link (https://...)

### 4.3 `veli_yeni_program` (UTILITY)

- **Category:** Utility
- **Body:**
  ```
  Merhaba, {{1}} için yeni haftalık program hazırlandı.
  Önümüzdeki 7 gün toplam {{2}} görev planlandı.
  Programı görüntüleyin: {{3}}
  ETÜTKOÇ Rotam
  ```
- **Variables:** `{{1}}` öğrenci, `{{2}}` görev sayısı, `{{3}}` link

### 4.4 `veli_dusus_alarmi` (UTILITY)

- **Category:** Utility
- **Body:**
  ```
  Merhaba, {{1}} için bir dikkat noktası var.
  Bu hafta tamamlama oranı geçen haftaya göre %{{2}} düştü.
  Detaylar: {{3}}
  ETÜTKOÇ Rotam
  ```
- **Variables:** `{{1}}` öğrenci, `{{2}}` düşüş yüzdesi, `{{3}}` link

### 4.5 `veli_ogretmen_notu` (UTILITY)

- **Category:** Utility
- **Body:**
  ```
  Merhaba, {{1}}'in öğretmeni size bir not iletti.
  Notu okuyun: {{2}}
  ETÜTKOÇ Rotam
  ```
- **Variables:** `{{1}}` öğrenci, `{{2}}` link

### 4.6 `veli_sinav_yaklasiyor` (UTILITY)

- **Category:** Utility
- **Body:**
  ```
  Merhaba, {{1}} için {{2}} sınavına {{3}} gün kaldı.
  Sınav tarihi: {{4}}
  Detaylar: {{5}}
  ETÜTKOÇ Rotam
  ```
- **Variables:**
  - `{{1}}` öğrenci adı
  - `{{2}}` sınav etiketi (LGS / YKS / Yıl Sonu)
  - `{{3}}` kalan gün (30/7/1)
  - `{{4}}` tarih ("7 Haziran 2026")
  - `{{5}}` link

### Onay süresi

Meta her şablonu insan + AI ile inceleyip 1-24 saat içinde kararını verir. Reddedilirse kategori farklı olabilir (UTILITY → MARKETING) — düzelt + tekrar gönder. **Tüm şablonlar onaylanmadan WHATSAPP_ENABLED=true yapma**, çünkü onaylanmamış şablon `error 132` döner.

---

## 5. .env güncellemesi

```env
WHATSAPP_ENABLED=true
WHATSAPP_API_VERSION=v21.0
WHATSAPP_PHONE_NUMBER_ID=YYYYYYYYYYYYYY    # Adım 3'te kopyaladığın ID
WHATSAPP_ACCESS_TOKEN=EAAxxxx...           # Adım 3'te aldığın kalıcı token
WHATSAPP_APP_SECRET=abcdef...              # App Settings → Basic → App Secret
WHATSAPP_WEBHOOK_VERIFY_TOKEN=secret-string-you-pick
WHATSAPP_DEFAULT_LANGUAGE=tr
```

> `WHATSAPP_WEBHOOK_VERIFY_TOKEN`'u sen seç (uzun rastgele bir string). Aşağıda webhook setup adımında Meta paneline aynısını yazacaksın.

`.env` değişikliği sonrası uvicorn'u yeniden başlat (config bir kere okunuyor):

```powershell
# Eski sürecin PID'ini bul
netstat -ano | findstr :8081 | findstr LISTENING
# PID ile öldür
taskkill /F /PID <PID>
# Yeniden başlat
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8081
```

---

## 6. Webhook setup

WhatsApp delivery callback'leri (sent / delivered / read / failed) için Meta'nın senin sunucuna POST atması gerekir.

### 6a. Public URL gereksinimi

Local development'ta Meta sunucundan ulaşamaz. İki yol:

**A. Production'da deploy edilmişse:**
- Webhook URL: `https://senin-domain.com/webhooks/whatsapp`

**B. Local test için:**
- ngrok kullan: `ngrok http 8081` → public URL `https://abc-123.ngrok-free.app`
- Webhook URL: `https://abc-123.ngrok-free.app/webhooks/whatsapp`
- ngrok ücretsiz tier'da URL her başlatmada değişir; Meta paneline her seferinde tekrar gir

### 6b. Meta panelinde webhook tanıtma

1. App Dashboard → **WhatsApp** → **Configuration** → **Webhook**
2. **Edit Callback URL:**
   - Callback URL: yukarıdaki URL
   - Verify Token: `.env`'deki `WHATSAPP_WEBHOOK_VERIFY_TOKEN` ile aynı
   - **Verify and Save** → Meta `GET /webhooks/whatsapp?hub.verify_token=...` atar
3. Meta'nın doğrulama isteğinin başarılı olduğunu göreceksin (yeşil tik)
4. **Webhook fields** sekmesinde **subscribe**:
   - `messages` (gelen mesajlar — şu an kullanmıyoruz ama lazım)
   - `message_status` (delivery callback'leri — kritik)

### 6c. Doğrulama

Logger'da şunu görmelisin (uvicorn output'u):
```
INFO:app.routes.whatsapp_webhook: webhook GET verify OK
```

---

## 7. Test akışı

### 7.1 OTP test (en basit)

1. Veli olarak login ol (test velisi yoksa süper admin oluştur veya bir velinin şifresini reset et)
2. `/parent/settings` → WhatsApp bölümü → kendi telefon numaranı gir
3. **OTP gönder** butonuna bas
4. Telefonuna gerçek WA mesajı gelmeli (kod 6 hane). Eğer:
   - **Mesaj gelmediyse:** uvicorn log'una bak, muhtemelen `error_132 (template not approved)` veya `error_131_026 (number not registered)`
   - **Stub mesaj logger'a yazıldıysa:** `WHATSAPP_ENABLED` hâlâ false ya da config doğru okunmuyor

### 7.2 Kuyruk gönderimi test

1. Süper admin olarak `/teacher/settings` → cron bölümünde **Şimdi çalıştır: weekly_backstop**
2. Bir öğrencinin haftalık döngüsü tamamsa veliye WA mesajı gitmeli
3. `/admin/audit` veya direkt DB:
   ```sql
   SELECT * FROM notification_logs ORDER BY id DESC LIMIT 5;
   ```
   - `channel='whatsapp'` ve `status='sent'` görmek istiyoruz
   - `external_id` artık `stub:` prefix'i taşımıyor olmalı, gerçek Meta message ID

### 7.3 Webhook test

1. Test mesajının external_id'sini al
2. Telefondaki WA mesajını **read** et (mavi tik)
3. Birkaç saniye sonra `notification_logs` tablosunda o satırın `status='delivered'` veya `'read'` olmuş olmalı
4. Olmadıysa: webhook URL Meta'ya doğru tanıtılmamış veya app secret yanlış (imza doğrulama fail)

---

## 8. Production'a önce kontrol listesi

- [ ] 6 şablonun tümü Meta'da `Approved` durumunda
- [ ] Telefon numarasının `Display Name` onayı geldi
- [ ] `WHATSAPP_ENABLED=true` ve sunucu yeniden başlatıldı
- [ ] Webhook URL HTTPS (Meta HTTP kabul etmez)
- [ ] App Secret doğru (webhook imza doğrulama testi geçti)
- [ ] Tek bir gerçek mesaj gönderildi + delivered tik geldi + DB'de `sent`
- [ ] Tek bir webhook callback DB'ye düştü
- [ ] **Cost limit ayarlandı:** Meta Business → Billing → Spending Limit (örn 100 TL/ay) — bug → spam → fatura felaketini engeller
- [ ] Daily cap (`DAILY_CAP_PER_PARENT=4`) hâlâ kod içinde aktif (`app/services/notification_dispatcher.py`)

---

## Hata ipuçları

| Hata | Çözüm |
|---|---|
| `error_132` | Şablon onaylı değil veya isim yanlış. Meta panelinde durumu kontrol. |
| `error_131_026` | Hedef numara WA'da kayıtlı değil ya da business numarasıyla 24h pencerede konuşmamış. Şablon mesajları herkese gönderilebilir; sorun değilse format problemi |
| `error_133` | Phone number ID veya access token hatalı |
| `error_190` | Access token expired. Sistem User üzerinden yeni "Never expire" token üret |
| `error_131_009` | Telefon numarası geçersiz format. `normalize_phone()` E.164'e çevirir, manuel kontrol et |
| Webhook 403 | App Secret yanlış → imza fail. `.env` ile Meta App Settings → Basic karşılaştır |
| Webhook 200 ama callback gelmiyor | Webhook fields'da `message_status` subscribe değil |

---

## Kod referansları

| Dosya | Ne yapar |
|---|---|
| `app/services/whatsapp.py` | Cloud API client (send_template, send_otp, verify_webhook_signature) |
| `app/routes/whatsapp_webhook.py` | GET verify + POST callback handler |
| `app/services/notification_dispatcher.py` | WA mesajını kuyruktan alıp `send_template`'e geçirir |
| `app/services/notification_producers.py` | WA payload + template_name'i belirler |
| `app/config.py` | Settings sınıfında env mapping |

Şablon adı veya parametreleri değiştirirsen **producers'ı + Meta'daki şablonu birlikte güncelle**, yoksa template_name mismatch olur.
