# Faz 1 — Click-to-WhatsApp Manuel Test Rehberi

Bu rehber, Faz 1 (manuel Click-to-WA) sisteminin **tüm akışlarını** tarayıcıda doğrulamak için adım-adım senaryoları içerir. Her senaryoda hedeflenen davranış + bekleyiş ✅ ifadeleriyle açıklanmıştır.

---

## 0. Hazırlık

### Sunucular
- Backend: `uvicorn app.main:app --port 8081` (veya canlı 8081)
- Frontend: `cd web && pnpm dev` (3000)

### Tek-komut tam setup
```powershell
python scripts/faz1_full_setup.py
```

Bu komut:
- 5 rol kullanıcısı yaratır (süper admin, bağımsız koç A, kurum yön., kuruma bağlı öğretmen B, 2 öğrenci, 3 veli)
- Kurum X + veli-öğrenci bağlantıları kurar
- Tüm telefonları **önceden doğrulu** kaydeder (manuel SMS akışına gerek kalmaz; özel olarak P1 testinde yapacaksın)
- Bir veliyi (1B Baba) **telefonsuz** bırakır → toplu gönderim "atlandı" testi için

Şifre **hepsi için**: `TestFaz1!2026`

### Banner uyarısını görmek için (opsiyonel)
```powershell
python scripts/faz1_full_setup.py --inject-busy    # 70 dispatch log → amber
python scripts/faz1_full_setup.py --inject-heavy   # 120 dispatch log → rose
```

### Bitince temizlik
```powershell
python scripts/faz1_full_cleanup.py
```

---

## 1. P0 — Veli Aktivasyon + İletişim Tercihleri (KVKK)

> Bu senaryo `p0_manual_test_setup.py` ile ayrı çalışır (token üretir). Aşağıdaki adımlar bağımsız koç A'nın yeni veli daveti oluşturmasını varsayar — yoksa `python scripts/p0_manual_test_setup.py` çalıştırıp davet linkini al.

### A1 — Davet sayfası
- [ ] Davet URL'i tarayıcıda aç (incognito)
- [ ] Sayfa 3 bölümlü görünmeli:
  1. **Hesap bilgileri** (ad/şifre/telefon)
  2. **İletişim tercihleriniz** (7×2 matris e-posta+WhatsApp + sessiz saatler + 18 yaş altı çocuk WA onayı)
  3. **Aydınlatma metni onayı** (KVKK checkbox)

### A2 — Matris davranışı
- [ ] E-posta sütunu varsayılan ✓ (opt-out modeli)
- [ ] WhatsApp sütunu varsayılan ☐ (opt-in / KVKK)
- [ ] Birkaç toggle değiştir
- [ ] **Veli Aydınlatma Metni** linkine bas → `/legal/kvkk-veli` yeni sekmede açılır → **3 yeni alt-madde** (4.1 İletişim Kanalları / 4.2 18 Yaş Altı / 4.3 İletişim İptali)

### A3 — Hesap oluştur
- [ ] Tüm alanları doldur (telefon zorunlu)
- [ ] "Hesabımı Oluştur" → veli paneli açılır
- [ ] Üstte **amber banner** "Telefonunuzu doğrulayın" (kapatılamaz)

### A4 — Ayarlar sayfası
- [ ] `/parent/settings` → matris düzeni (7×2)
- [ ] Toplu işlem butonları (Tümünü WA aç / kapat / E-posta aç / kapat) çalışıyor
- [ ] Çocuk WA onayı kartı altta

---

## 2. P1 — Telefon Doğrulama (SMS)

### B1 — Üst banner + dialog
- [ ] Bağımsız koç A login → herhangi bir koç sayfasında **amber banner**
- [ ] "Şimdi Doğrula" butonu → **inline dialog açılır** (panelden çıkış YOK)
- [ ] Dialog'ta PhoneCard (3 durum: kapalı / kod bekleniyor / doğrulandı)
- [ ] "0532 100 00 01" gir → **DEV stub kutusunda kod görünmeli**
- [ ] Kodu input'a yaz → "Doğrula" → yeşil rozet
- [ ] Dialog kapan → **banner anında kaybolur** (router.refresh)

### B2 — /me/account doğrudan
- [ ] Veli 1A (Anne) login → telefonu zaten doğrulu (setup'tan) → banner GÖRÜNMEMELİ
- [ ] `/me/account` → "Cep Telefonu" kartı yeşil rozet + maskeli telefon
- [ ] **Veli için ekstra**: "İkinci Telefon (Veli)" kartı görünür (anne+baba senaryosu)
- [ ] Telefonu kaldır → "Kaldır" → banner geri görünür mü kontrol et

---

## 3. P2 — Süper Admin Şablon CRUD

### C1 — Şablon listesi
- [ ] Süper admin login → sidebar **"Sistem → WhatsApp Şablonları"**
- [ ] 35 seed şablon 7 kategoride gruplu görünmeli
- [ ] **Kategori filter chip-bar** + "Pasifleri göster" toggle
- [ ] KPI: Toplam / Aktif / Pasif

### C2 — Şablon detay + düzenle
- [ ] Bir şablona **kalem ikonuna** bas → form dialog
- [ ] Tüm alanlar dolu (kategori / hedef rol / metin / değişkenler / 4 bayrak)
- [ ] **"Önizle"** → gerçek render örnek değerlerle
- [ ] Metni değiştir + "Değişiklikleri Kaydet" → liste güncellendi

### C3 — Yeni şablon
- [ ] "Yeni Şablon" → form dialog
- [ ] Key: `manuel_test_sablonu` / kategori: veli / metin: "Test {{ad}}" / değişken ekle
- [ ] Önizle → metin doğru render
- [ ] Kaydet → kategoride göründü

### C4 — Pasif/Sil
- [ ] Aktif şablonu **çöp** → buton disabled (önce pasife al)
- [ ] **Kapalı daire** (toggle) → pasife alındı → çöp aktif → sil onayı

---

## 4. P3-P4 — Tekli Click-to-WhatsApp (öğrenci profili)

### D1 — Öğrenci sayfasında "WA Gönder"
- [ ] Bağımsız Koç A login → `/teacher/students/{Öğrenci 1 id}` (setup'ta gösterilen)
- [ ] Sağ üstte **"WA Gönder" emerald** butonu görünmeli
- [ ] Tıkla → dialog açılır
- [ ] Hedef header: öğrencinin adı + maskeli telefon (telefonu doğrulu olduğundan)

### D2 — Dialog akışı
- [ ] Kategori chip-bar → "Koç → Öğrenci" seç
- [ ] Şablon dropdown → "Bugün hala eksiksin" seç
- [ ] Değişken alanları **otomatik example pre-fill** (kalan_gorev vs.)
- [ ] **"Önizle"** → gerçek render metni yeşil kutuda
- [ ] **"WhatsApp'ı Aç"** → yeni sekme `wa.me/9053...?text=Merhaba%20...`
- [ ] WhatsApp Web/uygulaması açılıp metin hazır geliyor mu doğrula

### D3 — Veli kartlarına WA
- [ ] "Veliler" sekmesi → 2 veli görünmeli
- [ ] **Anne** (telefonu doğrulu) yanında yeşil MessageSquare ikon → tıkla → dialog çalışır
- [ ] **Baba** (telefonsuz) → ikon tıkla → **amber "Telefon doğrulanmamış" uyarı** + gönderim engeli

### D4 — Yetki sızıntı önleme
- [ ] Bağımsız Koç A ile çalışırken URL'i değiştirip kuruma bağlı bir öğrenci ID'sine gitmeyi dene (örn. `/teacher/students/{Öğrenci 2 id}`)
- [ ] **404 hatası** dönmeli (Koç A, B'nin öğrencisini göremez)

---

## 5. P5 — Toplu Gönderim Sihirbazı

### E1 — Sihirbaz açılışı
- [ ] Koç A → sidebar **"Toplu WhatsApp"** → `/teacher/bulk-wa`
- [ ] Üstte **SpamGuardBanner** durum:
  - Setup default → "Bu hafta 0 mesaj" gizli (banner yok)
  - `--inject-busy` setup → AMBER "Bugün 70 yoğun"
  - `--inject-heavy` setup → ROSE "Bugün 120 çok yoğun"
- [ ] 4 adımlı sihirbaz: 1. Şablon → 2. Değişken → 3. Hedef → 4. Mod

### E2 — Toplu akış (≤20 hedef → sıralı)
- [ ] **Adım 1**: "Bayram / özel gün" şablonu (allow_bulk)
- [ ] **Adım 2**: bayram_adi="Ramazan" → İleri
- [ ] **Adım 3**: "Tüm velilerim" chip → liste:
  - **eligible**: Veli 1A Anne (telefonu doğrulu) — seçilebilir
  - **no_phone**: Veli 1B Baba (telefonsuz) — alt accordion'da görünür ama seçilemez
- [ ] "Tümünü seç" → 1 eligible seçildi → "1 hedefe ilerle"
- [ ] **Adım 4**: < 20 → "Sıralı" otomatik seçili (Önerilen rozeti)
- [ ] "Gönderim Linklerini Üret"
- [ ] **Sonuç**: 1 dispatched + skipped (telefonsuz veli)
- [ ] **Sıralı görünüm**: 1/1 hedef + "WhatsApp'ı Aç" → yeni sekme

### E3 — Toplu broadcast modu simülasyonu
- [ ] Yeniden başla → Adım 4'te elle "Broadcast" seç
- [ ] Sonuç ekranında **2 kutu**:
  - **Mesaj metni** + "📋 Kopyala" → panoya kopyala (toast)
  - **Telefon listesi** + "📋 Kopyala"
- [ ] Amber **broadcast list talimat banner**

### E4 — Yetki testi
- [ ] Koç A → "Tüm öğrencilerim" → yalnız Öğrenci 1 görünür (kurum öğr. yok)
- [ ] Kurum Yöneticisi login → `/institution/bulk-wa`
- [ ] "Tüm kurum velileri" → Veli 2 (Anne) görünür
- [ ] "Tüm kurum öğretmenleri" → Öğretmen B görünür

---

## 6. P6 — Spam Guard Banner + Admin Audit

### F1 — Spam banner (koç)
- [ ] Koç A — toplu WA sayfasında üst banner durum:
  - Hiç log yok → SESSİZ
  - 1-49 log → küçük gri "Bu hafta N mesaj"
  - 50-99 → **AMBER** "yoğun" + AlertTriangle
  - 100+ → **ROSE** "çok yoğun" + Flame
- [ ] Banner simülasyonu için:
  ```powershell
  python scripts/p6_log_inject.py 70 faz1_kocA_bagimsiz@test.invalid
  ```
- [ ] Sayfayı yenile → AMBER

### F2 — Admin dispatch log paneli
- [ ] Süper admin login → sidebar **"Sistem → WhatsApp Audit"**
- [ ] **4 KPI kartı** (Bugün / Bu hafta / Son N gün / En aktif)
- [ ] **Top Senders** kart (en çok mesaj atan 5) — emerald kartlar, **aktif satır kontrast OK** (yazılar koyu emerald, zemin açık)
- [ ] **Süre filter chip-bar** (1g/7g/30g/90g) → tablo değişir
- [ ] Top senders'tan birine tıkla → **aktif filter chip** üstte (X ile temizlenir)
- [ ] **Tablodaki gönderen adına** tıkla → filter uygulanır
- [ ] Aktif satır: sol yeşil border (zemin müdahalesi yok)

### F3 — Kontrast testi (koyu/açık tema)
- [ ] OS koyu temada: top sender aktif buton **emerald-100 zemin + koyu emerald metin** → okunur
- [ ] Filter chip (emerald-100) → metin koyu emerald → okunur
- [ ] Tablo satır metin → default text-foreground → okunur

---

## 7. Sonuç ve Kapanış

### Tüm Smoke Çalıştır
```powershell
python scripts/run_faz1_smokes.py
```
Beklenen: **104 passed · 0 failed** 🎉

### Temizlik
```powershell
python scripts/faz1_full_cleanup.py
```

---

## Bilinen sınırlamalar (Faz 2'ye bırakıldı)

- **Otomatik bildirimler henüz Cloud API'ye değil** — Faz 2 (Meta Business onayı + sertifikalı şablonlar)
- **Mobil app push notification** — Faz 2 ile beraber, otomatik bildirim kanalı buraya kayacak (Click-to-WA manuel olarak kalır)
- **SMS sağlayıcı (Netgsm) prod entegrasyonu** — `SMS_ENABLED=true` + Netgsm kimlikleri prod `.env`'e eklendiğinde gerçek SMS gider; şu an dev stub
