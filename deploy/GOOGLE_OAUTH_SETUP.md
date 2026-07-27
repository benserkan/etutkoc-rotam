# Google OAuth Kurulumu — Randevu Sistemi (Meet linki otomatik üretimi)

Bu rehber, koçların "Google ile bağlan" diyerek görüşme (Meet) linklerini
KENDİ Google hesaplarından otomatik ürettirebilmesi için gereken tek seferlik
kurulumu anlatır. **Bu kurulum yapılmadan da randevu sistemi tam çalışır** —
koçlar Meet/Zoom linkini elle yapıştırır; kurulum tamamlanınca `.env`'e iki
değer girilir ve "Google ile bağlan" butonu kendiliğinden görünür.

Önemli gerçekler:
- Koçun **ücretsiz Gmail hesabı yeterli** (1:1 Meet görüşmesi 24 saate kadar).
  Google One / Workspace GEREKMEZ.
- Sistem koç adına Google Takvim'de etkinlik oluşturur → Meet linki oradan
  gelir; randevu koçun kişisel takvimine de düşer.
- Takvim izni Google'da "hassas kapsam" sayılır → uygulama **doğrulaması**
  tamamlanana kadar OAuth ekranı "doğrulanmamış uygulama" uyarısı gösterir ve
  en fazla 100 test kullanıcısıyla çalışır. Doğrulama başvurusu yapılır,
  onay birkaç gün–birkaç hafta sürebilir.

## 1) Google Cloud projesi

1. https://console.cloud.google.com → üstten proje seç → **New Project**.
   - Ad: `etutkoc-rotam` (herhangi bir ad olur).
2. Sol menü **APIs & Services → Library** → **Google Calendar API** → **Enable**.

## 2) OAuth consent screen (izin ekranı)

1. **APIs & Services → OAuth consent screen**.
2. User Type: **External** → Create.
3. Alanlar:
   - App name: `ETÜTKOÇ Rotam`
   - User support email: rotam@etutkoc.com
   - App logo: (isteğe bağlı — doğrulamada işe yarar)
   - App domain / Authorized domains: `etutkoc.com`
   - Developer contact: rotam@etutkoc.com
4. **Scopes** adımında **Add or Remove Scopes** →
   `https://www.googleapis.com/auth/calendar.events` işaretle (+ `openid`,
   `email` otomatik gelir). Kaydet.
5. **Test users** adımına kendi Gmail adresini + test edecek koçların
   adreslerini ekle (doğrulama onaylanana kadar yalnız bu adresler bağlanabilir).
6. Publish status: doğrulamaya hazır olunca **Publish App** → Google
   verification başvurusunu tamamla (domain doğrulaması Search Console
   üzerinden istenir; `etutkoc.com` zaten Cloudflare'de — TXT kaydı eklenir).

## 3) OAuth Client ID

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. Application type: **Web application**. Ad: `rotam-web`.
3. **Authorized redirect URIs** — TAM olarak şunu ekle:
   ```
   https://rotam.etutkoc.com/api/v2/google/oauth/callback
   ```
   (Yerel geliştirme için ikinci satır: `http://127.0.0.1:8081/api/v2/google/oauth/callback`)
4. **Create** → çıkan **Client ID** (`....apps.googleusercontent.com`) ve
   **Client secret** değerlerini kopyala. Secret'ı sohbete/koda YAZMA —
   yalnız sunucu `.env` dosyasına gir.

## 4) Sunucu yapılandırması

`/opt/etutkoc/deploy/.env` içine:

```
GOOGLE_OAUTH_CLIENT_ID=<client id>
GOOGLE_OAUTH_CLIENT_SECRET=<client secret>
```

Sonra: `docker compose up -d web` (recreate yeterli; migration gerekmez).

## 5) Doğrulama

1. Koç hesabıyla `https://rotam.etutkoc.com/teacher/appointments` → artık
   "Google Meet bağlantısı" kartında **Google ile bağlan** butonu görünür.
2. Bağlan → Google izin ekranı → onay → `?google=connected` ile geri döner.
3. Yeni randevu oluştur (link alanını boş bırak) → randevuda otomatik
   `meet.google.com/...` linki belirmeli + etkinlik koçun Google Takvim'inde
   görünmeli.

## Sorun giderme

- **"Google bağlantısı bu sunucuda henüz açık değil"** → `.env` değerleri boş
  ya da web container recreate edilmedi.
- **redirect_uri_mismatch** → Credentials'taki redirect URI birebir
  `https://rotam.etutkoc.com/api/v2/google/oauth/callback` olmalı (sondaki
  eğik çizgi bile fark yaratır).
- **"Bu uygulama doğrulanmadı" uyarısı** → normaldir (doğrulama sürecinde);
  test kullanıcıları "Advanced → Go to ..." ile ilerleyebilir. Kalıcı çözüm:
  consent screen doğrulamasını tamamlamak.
- **Refresh token gelmedi** → koç hesabı daha önce bağlanıp izin vermişse
  Google ikinci kez refresh token vermeyebilir; sistem `prompt=consent` ile
  her seferinde ister — yine de olursa koç https://myaccount.google.com/permissions
  adresinden uygulamayı kaldırıp yeniden bağlanır.
- Koç tarafında link üretimi başarısız olursa randevu YİNE kaydedilir; hata
  Görüşmeler sayfasındaki Google kartında görünür ve koç linki elle yapıştırabilir.
