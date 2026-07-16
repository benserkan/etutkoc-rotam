# App Review yanıtı — iOS 1.0 (build 8) — 2026-07

Ret #2 (2026-07-14, gönderim 5b65a5d3): 3.1.1 + 2.1(a) + 5.1.1(v).
Bu dosya: App Store Connect'te "Uygulama Yorumuna Yanıt Ver" ile gönderilecek
İngilizce mesaj taslağı + ekran kaydı talimatı + App Review notları.

---

## 1) App Store Connect mesajı (İngilizce taslak — build 8 seçilip yeniden gönderilirken yanıt olarak yapıştır)

Hello,

Thank you for the detailed review. We have addressed all three issues in the
new build 1.0 (8):

**Guideline 3.1.1 — In-App Purchase**

We have removed every remaining reference to paid plans, subscriptions,
trials, credits and upgrades from the iOS app:

- The "My Plan" (Paketim) screen shown in your screenshots has been removed
  entirely, together with the institution "Account Settings", "Credit Usage"
  and "Limits/plan comparison" screens.
- All "free trial" marketing copy has been removed from the onboarding,
  sign-in and sign-up screens.
- All remaining texts that referenced credits or plan status have been
  replaced with neutral wording.

The app now contains no purchase flow, no pricing, no trial or subscription
status, and it does not direct users to any external payment mechanism.

For context: ETÜTKOÇ Rotam is the companion app of a coaching-management
platform used by professional education coaches and institutions with their
students and parents (a classroom-management-type service). Accounts created
in the app are free accounts, and the app is fully functional for free
accounts. Paid digital content or services are neither sold nor advertised
anywhere in the app.

**Guideline 2.1(a) — App Completeness**

The sign-up screen now contains active, functional links to our Terms of Use
(EULA) and Privacy Policy (KVKK disclosure), shown together with the
acceptance statement. The same functional links were also added to the
sign-in screen. Both pages are live:
- https://rotam.etutkoc.com/kullanim-sartlari
- https://rotam.etutkoc.com/kvkk

**Guideline 5.1.1(v) — Account Deletion**

In-app account deletion has been added. It is available to every role from
Profile → "Hesabı sil" (Delete account). The flow explains the consequences,
asks for confirmation, and permanently deletes the account and all personal
data. In accordance with the Turkish personal-data-protection law (KVKK),
deletion is executed permanently after a 30-day legal grace period; during
that period the user can cancel the request from the same in-app screen.
This is a permanent deletion, not a temporary deactivation.

A screen recording demonstrating the full deletion flow on a physical device
is attached to this message.

Please let us know if anything else is needed.

---

## 2) Ekran kaydı (KULLANICI AKSİYONU — Apple açıkça istedi)

Fiziksel iPhone'da (TestFlight'tan build 8'yi kur) ekran kaydı al:

1. Uygulamayı aç → "Hesap oluştur" ile YENİ hesap aç (veya App Review'daki
   demo hesapla giriş yap).
2. Alt sekmeden **Profil**'e git.
3. **"Hesabı sil"** satırına dokun → açılan ekranda bilgilendirmeyi göster.
4. **"Hesabımı kalıcı olarak sil"** → onay diyaloğunda **"Hesabımı sil"**.
5. "Silme talebin alındı — {tarih} tarihinde kalıcı olarak silinecek"
   ekranını göster (akışın tamamlandığının kanıtı).

Kaydı App Store Connect'teki yanıt mesajına ekle (ataş simgesi).

## 3) App Review Bilgileri → Notlar alanına eklenecek (İngilizce)

Account deletion: available in-app for all roles at Profile → "Hesabı sil"
(Delete account). Deletion is permanent; per Turkish KVKK law it is executed
after a 30-day legal grace period, cancellable in-app during that period.
The app contains no purchase flows; accounts created in the app are free and
the app is fully functional for free accounts.

## 4) Gönderim öncesi kontrol listesi (KULLANICI)

- [ ] App Store Connect → iOS Gönderimi → build **1.0 (8)** seç (build 6'yı çıkar).
- [ ] Demo hesabın (App Review Bilgileri'ndeki) şifresi geçerli ve hesabın
      **paywall'da olmadığından** emin ol (gerekirse süper adminden ücretli
      plana çek — deneme süresi bitmiş demo koç, görev eklemede nötr de olsa
      hata alır; incelemeciye temiz deneyim ver).
- [ ] Yanıt mesajını (bölüm 1) yapıştır + ekran kaydını (bölüm 2) ekle.
- [ ] App Review Notlarına bölüm 3'ü ekle.
- [ ] Gizlilik Politikası URL'si metadata'da dolu mu kontrol et
      (https://rotam.etutkoc.com/kvkk).
