# EAS Build — ETÜTKOÇ Rotam mobil (iOS + Android)

Bu rehber mobil uygulamanın bulutta derlenmesi (EAS Build) içindir. Mac
**gerekmez** — Apple derlemesi de Expo'nun bulutunda yapılır. Aşağıdaki komutları
**sen** çalıştırırsın (Expo hesabına interaktif giriş gerektiği için otomatik
yapılamaz).

> Çalışma dizini: `D:\LGS-Program\mobile`

## Hazır olanlar (bu repo'da kurulu)

- `app.json` — ad/slug (`etutkoc-rotam`), sürüm, `bundleIdentifier`
  (`com.etutkoc.rotam`), Android `package` (`com.etutkoc.rotam`), scheme
  (`etutkocrotam`), `expo-notifications` plugin (push için).
- `eas.json` — 3 build profili: **development** (dev-client) · **preview**
  (APK / internal — telefona doğrudan kurulur) · **production** (AAB / store +
  otomatik sürüm artışı).
- `package.json` build script'leri: `build:android:preview`, `build:ios:preview`,
  `build:android:prod`, `build:ios:prod`.
- API adresi prod'a sabit: `lib/api.ts` → `https://rotam.etutkoc.com`
  (override gerekirse `EXPO_PUBLIC_API_BASE`).
- `expo-doctor` 18/18 temiz · `tsc` temiz.

## Eksik tek adım: `projectId` (push token için ŞART)

`lib/push.ts` push token'ı `extra.eas.projectId`'den okur. Bu değer **`eas init`**
ile eklenir (Expo hesabına bağlar). O ana kadar push kaydı sessizce no-op olur
(uygulama bozulmaz, sadece push gelmez). Yani: **projectId set edilmeden push
çalışmaz; `eas init` zorunlu.**

---

## Adım adım

### 0) Ön koşullar (tek seferlik)
- Ücretsiz Expo hesabı: https://expo.dev/signup
- Android internal (preview APK) için **hiçbir mağaza hesabı gerekmez**.
- iOS gerçek-cihaz / TestFlight için **Apple Developer** ($99/yıl).
- Play Store yayını için **Google Play Console** ($25 tek seferlik).
  (Sadece test edeceksen Android APK yeter, mağaza hesabı gerekmez.)

### 1) Giriş
```powershell
cd D:\LGS-Program\mobile
npx eas-cli@latest login
```

### 2) Projeyi bağla (projectId yaz)
```powershell
npx eas-cli@latest init
```
- "Create a new project?" → Evet (veya mevcut `etutkoc-rotam` projeni seç).
- Bu komut `app.json`'a `expo.extra.eas.projectId` + `expo.owner` yazar.
- **Doğrula:** `app.json` içinde `"extra": { "eas": { "projectId": "..." } }`
  görünmeli. (Bu değişikliği commit'le — `git add app.json`.)

### 3) İlk derleme — PREVIEW (test için, en hızlı yol)
Android (telefona doğrudan kurulabilir APK):
```powershell
npm run build:android:preview
```
iOS (internal — cihaz UDID kaydı/Apple hesabı sorulabilir):
```powershell
npm run build:ios:preview
```
- İlk derlemede EAS **credentials** (Android keystore / iOS sertifika) üretmeyi
  teklif eder → "Generate" / "Yes" de (EAS otomatik yönetir).
- Build bulutta ~10–20 dk sürer; bitince **indirme linki** verir.
- Android APK'yı telefona kurup aç. iOS için linkten cihaza yükle.

### 4) Push'u uçtan uca test et (build sonrası)
1. Derlenen uygulamayı **gerçek cihaza** kur (Expo Go DEĞİL — push yalnız
   gerçek build'de çalışır) ve bir hesapla giriş yap.
2. Backend zaten canlı (`rotam.etutkoc.com`) ve push genişletmesi yayında.
3. Test senaryoları:
   - **Öğrenci → koç**: öğrenci hesabıyla bir görevi tamamla → koçun cihazında
     "Öğrenci ilerlemesi" push'u (3 saatte 1 throttle).
   - **Talep**: öğrenci talep açar → koça push; koç yanıtlar → öğrenciye push.
   - **Veli**: yeni program / haftalık rapor → veliye push (mevcut akış).
   - Push'a **dokun** → ilgili ekran açılmalı (deep-link).
4. Token kaydını doğrula (opsiyonel): giriş sonrası sunucuda
   `device_push_tokens` tablosunda kullanıcı için satır oluşur.

### 5) Production derleme (mağaza için, hazır olunca)
```powershell
npm run build:android:prod   # AAB → Play Console
npm run build:ios:prod       # IPA → App Store / TestFlight
```
Mağazaya gönderme (hesaplar hazırsa):
```powershell
npx eas-cli@latest submit --platform android --profile production
npx eas-cli@latest submit --platform ios --profile production
```

---

## Notlar / sık sorunlar
- **Push neden gelmiyor?** En sık sebep: `eas init` yapılmamış (projectId yok)
  veya uygulamaya bildirim izni verilmemiş. iOS'ta ilk açılışta izin sorulur.
- **Expo Go'da push çalışmaz** — gerçek EAS build şart.
- **Sürüm artışı**: production profilinde `autoIncrement: true` → her prod
  build'de build numarası otomatik artar (`appVersionSource: remote`).
- **Backend değişikliği gerekmez** — uçlar canlı; yalnız uygulama derlenir.
- **EAS_BUILD bu repoda**; build çıktıları (APK/AAB/IPA) EAS bulutunda saklanır,
  repo'ya girmez.
- Apple Icon Composer ikonu (`assets/expo.icon`) SDK 54 ile geçerli; ek işlem yok.
