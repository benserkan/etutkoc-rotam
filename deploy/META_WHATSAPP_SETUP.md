# WhatsApp Business Cloud API — Meta Doğrulama Rehberi (K2 ön koşulu)

Görsel-başlıklı (sigortam.net tarzı), mavi-tikli markalı üyelik teklifi mesajları
için gerekli. Şirket kaydı (ETÜTKOÇ Akademi Ltd. Şti.) tamamlandığından artık
yapılabilir. Süre: ~1-3 gün (Meta inceleme). Adımlar:

## 1. Meta Business Manager
- https://business.facebook.com → İşletme oluştur.
- İşletme adı: **ETÜTKOÇ Akademi Ltd. Şti.** · resmi e-posta · web: rotam.etutkoc.com
- Ayarlar → İşletme Bilgileri: vergi no/adres (ticaret sicilindeki bilgilerle birebir).

## 2. İşletme Doğrulaması (Business Verification)
- Ayarlar → Güvenlik Merkezi → **İşletmeyi Doğrula**.
- Gerekenler: ticaret sicil/vergi levhası (Ltd. tüzel kişi belgesi) + adres + telefon.
- Meta belgeleri inceler (1-3 gün). Onaylanınca "Doğrulanmış işletme" olur.

## 3. WhatsApp Business Account (WABA) + Telefon Numarası
- Business Manager → WhatsApp Accounts → Hesap oluştur.
- **Telefon numarası ekle**: kişisel WhatsApp'ta KAYITLI OLMAYAN bir numara olmalı
  (yeni hat veya WhatsApp'tan silinmiş hat). SMS/arama ile doğrula.
- Görünen ad (display name): "ETÜTKOÇ Rotam" — Meta onayından geçer.

## 4. API Erişim Bilgileri (sisteme girilecek)
- Meta for Developers (developers.facebook.com) → Uygulama oluştur (Business tipi) →
  WhatsApp ürününü ekle.
- Şunları al: **Phone Number ID** · **WhatsApp Business Account ID** ·
  **kalıcı (System User) Access Token** · App Secret (webhook imzası için).
- Bunlar `.env`'e girilecek:
  `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_APP_SECRET`,
  `WHATSAPP_WEBHOOK_VERIFY_TOKEN` (sen belirle), `WHATSAPP_ENABLED=true`.
- Webhook URL (Meta'ya gireceğin): `https://rotam.etutkoc.com/webhooks/whatsapp`
  (zaten sistemde hazır — verify + status callback'leri çalışıyor).

## 5. Mesaj Şablonu (Template) — görsel başlıklı üyelik teklifi
- WhatsApp Manager → Message Templates → Şablon oluştur.
- Kategori: **Marketing** · Dil: Türkçe.
- Yapı (sigortam.net gibi):
  - **Header: MEDIA → IMAGE** (kurumsal görsel/banner — ETÜTKOÇ markalı).
  - **Body**: değişkenli metin, örn:
    `Merhaba {{1}}, {{2}} için sana özel üyelik teklifimiz hazır. {{3}}`
  - **Footer** (ops.): "ETÜTKOÇ Rotam"
  - **Button: URL** → `https://rotam.etutkoc.com/membership/{{1}}` (dinamik token)
    ya da statik + body'de link. (URL button dinamik suffix destekler.)
- Meta onaya gönderir (genelde birkaç saat–1 gün). Onaylı şablon adı sisteme girilir.

## 6. Maliyet
- Marketing konuşması başına ücret (TR tarifesi). Faturalandırma: Business Manager →
  Ödeme yöntemi ekle. Hacme göre planla.

## ⚠️ Politika (numara güvenliği)
- Yalnız **opt-in / etkileşimli** kişilere marketing template at. Soğuk toplu gönderim
  → kalite puanı düşer → numara kısıtlanır. Sistemde prospect'lerde "opt-in" işareti
  var; düşük hacimle başla, kalite puanını WhatsApp Manager'dan izle.

## Hazır olunca
Yukarıdaki 4. adımdaki anahtarları ver (sohbete YAZMA — sunucu `.env`'ine kendin gir,
SMTP/ZeptoMail'de yaptığımız gibi) + onaylı şablon adını söyle → sistemdeki K2
(Cloud API branded gönderim) aktive edilir; `whatsapp.py send_template` zaten hazır.
