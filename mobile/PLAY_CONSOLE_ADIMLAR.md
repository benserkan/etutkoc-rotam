# Google Play Console — Adım Adım Yayın Rehberi (ETÜTKOÇ Rotam)

> Tüm metinler kopyala-yapıştır hazır. Görseller `mobile/store/` içinde.
> Kişisel (Individual) geliştirici hesabıyla **kapalı test (12 tester / 14 gün)**
> üretim erişimi için zorunludur.

---

## 0) ÖN KOŞUL
- **Google Play Developer hesabı**: tek seferlik 25 USD + kimlik doğrulama (1–2 gün).
- Hesap **Kişisel** ise: üretime çıkmadan önce **en az 12 test kullanıcısı / 14 gün
  kesintisiz kapalı test** şart (Google 2023+ politikası).
- Hazır dosyalar:
  - İkon: `mobile/store/store-icon-512.png` (512×512)
  - Öne çıkan grafik: `mobile/store/feature-graphic.png` (1024×500)
  - Telefon görselleri: `mobile/store/play8/1.png … 8.png` (1080×1920)
  - **AAB**: bu oturumda EAS ile derlendi (production, versionCode 2) →
    https://expo.dev/accounts/etutkoc/projects/etutkoc-rotam/builds → indir.
    (Yeniden: `npx eas-cli@latest build --platform android --profile production`)

---

## 1) UYGULAMA OLUŞTUR
Play Console → **Uygulama oluştur**:
- **Uygulama adı**: `ETÜTKOÇ Rotam`
- **Varsayılan dil**: Türkçe (Türkiye) — `tr-TR`
- **Uygulama mı / oyun mu**: Uygulama
- **Ücretsiz / ücretli**: Ücretsiz
- Beyannameler: Program Politikaları + ABD ihracat yasaları → onayla.

---

## 2) "Uygulamanızı ayarlayın" GÖREVLERİ (sol menü → Pano)

**2.1 Uygulama erişimi (App access)** — KRİTİK
- "Tüm işlevler kısıtlı, giriş gerekir" seç.
- İncelemeci için **çalışan demo giriş bilgileri** ekle (her rol için ayrı satır).
  ⚠ Gerçek kullanıcı değil — geçici test hesabı aç (şifre kuralı). Örn:
  - Koç: `demo-koc@etutkoc.com` / şifre / "Koç paneli, öğrenci listesi"
  - Öğrenci: `demo-ogrenci@…` / şifre
  - Veli: `demo-veli@…` / şifre
  - Kurum: `demo-kurum@…` / şifre
- İncelemeci giriş yapamazsa uygulama **reddedilir**.

**2.2 Reklamlar (Ads)**: **Hayır**, reklam içermez.

**2.3 İçerik derecelendirmesi (Content rating)** — IARC anketi
- Kategori: **Eğitim / Referans**.
- Şiddet / cinsellik / küfür / uyuşturucu / kumar: **Hayır** (hepsi).
- Kullanıcılar birbiriyle iletişim kurabilir mi? → uygulama-içi talep/mesaj var →
  **Evet** (dürüst cevap). Konum paylaşımı: **Hayır**.
- Sonuç: muhtemelen **Herkes / 3+**.

**2.4 Hedef kitle ve içerik (Target audience)**
- Yaş grupları: **13–15, 16–17, 18+** (LGS/YKS öğrencisi 13+).
- "Uygulama çocuklara mı yönelik?" → **Hayır** (birincil hedef koç/veli/öğrenci 13+)
  → Families politikası karmaşasından kaçınır.

**2.5 Veri güvenliği (Data safety)**
- Veri topluyor/paylaşıyor mu? **Topluyor — Evet · Paylaşıyor (3. tarafla) — Hayır**
- Toplanan veri türleri:
  - **Kişisel**: Ad · E-posta · Telefon → amaç: Hesap yönetimi, Uygulama işlevi
  - **Uygulama içi içerik**: eğitim kayıtları (program/deneme/not) → Uygulama işlevi
  - **Uygulama etkinliği**: ürün etkileşimi → Analitik, Uygulama işlevi
  - **Cihaz/diğer ID**: kullanıcı/cihaz kimliği (push token) → Uygulama işlevi
  - (Opsiyonel) **Çökme/Tanı** → Kararlılık
- **Aktarımda şifreli mi?** Evet (HTTPS).
- **Kullanıcı veri silmeyi isteyebilir mi?** Evet (uygulama-içi hesap silme / KVKK).
- Reklam/izleme/veri satışı: **Yok**.

**2.6 Devlet uygulaması / COVID**: Hayır.

**2.7 Gizlilik Politikası URL**: `https://rotam.etutkoc.com/privacy`

---

## 3) MAĞAZA GİRİŞİ (Main store listing)

**Uygulama adı** (≤30)
```
ETÜTKOÇ Rotam
```

**Kısa açıklama** (≤80) — *hero slogan kullanıldı*
```
Hedefe giden net rota: program, deneme netleri, gelişim ve veli bilgisi
```
*(alternatif: `Öğrenci koçluğu: günlük program, deneme netleri, gelişim, veli bilgisi`)*

**Tam açıklama** (≤4000)
```
Sınav yolu bir labirenttir. ETÜTKOÇ Rotam, her öğrenciyi bu labirentte doğru
rotada tutar: koç planlar, öğrenci uygular, veli görür, sistem ölçer ve geride
kalmadan önce uyarır.

Tahmin değil, veri. Dağınık defterler ve WhatsApp grupları yerine; günlük
program, deneme netleri, gelişim analizi ve veli bilgilendirmesi tek bir akıllı
sistemde toplanır.

KOÇ İÇİN
- Günlük ve haftalık programı dakikalar içinde kur; kaynak takibini sisteme bırak
- "Kim geride kaldı, kim hedefte?" — her öğrencinin durumunu bir bakışta gör
- Deneme netleri, çalışma temposu ve tutarlılık otomatik ölçülür
- Yapay zekâ ile bir sonraki seansa hazırlan: bugün hangi öğrenciyle ne konuşmalı
- Sesle veya fotoğrafla not al; sistem senin yerine düzene koysun

ÖĞRENCİ İÇİN
- Bugünün programını gör, tamamladıkça işaretle
- Net gelişimini, çalışma serini ve hedeflerini takip et
- Koçundan gelen yönlendirmeleri ve bildirimleri kaçırma

VELİ İÇİN
- Çocuğunuzun gelişimini şeffaf ve gerçek zamanlı görün
- Haftalık rapor, deneme sonuçları ve önemli uyarılar bildirim olarak gelir
- "Çalışıyor mu, ilerliyor mu?" sorusunun cevabı her zaman elinizde

KURUM İÇİN
- Tüm koç ve öğrencileri tek panelden yönetin
- Program uyumu, akademik çıktı, risk ve veli güveni tek ekranda
- Müdahale merkezi: nerede sorun var, kime ne yapılmalı

GÜVENLİK VE GİZLİLİK
Verileriniz KVKK'ya uygun işlenir. Koça özel notlar yalnız koçta kalır. Hesap
güvenliği için güçlü şifre politikası ve iki adımlı doğrulama desteklenir.

ETÜTKOÇ Rotam — hedefe giden net rota. Plan, uygula, ölç, kazan.

İletişim: destek@etutkoc.com · rotam.etutkoc.com
```

**Grafikler**
- Uygulama ikonu: `mobile/store/store-icon-512.png`
- Öne çıkan grafik: `mobile/store/feature-graphic.png`
- Telefon ekran görüntüleri (2–8): `mobile/store/play8/1.png … 8.png`

**Kategori & iletişim**
- Uygulama kategorisi: **Eğitim**
- E-posta: `destek@etutkoc.com`
- Web sitesi: `https://rotam.etutkoc.com`

---

## 4) KAPALI TEST (Closed testing) — üretim için zorunlu
1. Sol menü → **Test → Kapalı test** → track aç (ör. "alpha").
2. **Test kullanıcıları**: e-posta listesi oluştur, **en az 12** Google hesabı ekle
   (gerçek koç/veli + güvendiğin kişiler).
3. **Sürüm oluştur** → **AAB** yükle (EAS production AAB).
4. Sürüm notları (aşağıda) + kaydet → **İncele ve kullanıma sun**.
5. **Opt-in linkini** test kullanıcılarına gönder; kurup kullansınlar.
6. **14 gün** kesintisiz, ≥12 aktif tester şartını koru.

---

## 5) ÜRETİME GEÇİŞ
1. 14 gün + 12 tester sonrası: **Üretim erişimi başvurusu** formunu doldur
   (uygulamayı tanıt, test sonuçları). Google inceler (birkaç gün).
2. Onaylanınca: **Üretim (Production)** → AAB → sürüm notu → **İncelemeye gönder**.
3. İlk inceleme genelde birkaç gün; onayla **yayında**.

---

## SÜRÜM NOTLARI (Release notes, ≤500) — `tr-TR`
```
ETÜTKOÇ Rotam mobil ile tanışın: günlük program takibi, deneme netleri, gelişim
analizi, veli bilgilendirmesi ve anlık bildirimler artık cebinizde.
```

---

## HERO & TÜM SLOGANLAR (mağaza metinlerinde / tanıtımda kullanıma hazır)

**Hero kapaklar**
- Hedefe giden net rota — *Plan, uygula, ölç, kazan*
- Kimse geride kalmasın — *Erken uyar, zamanında müdahale et*

**Özellik sloganları (başlık — alt-başlık)**
- Tüm öğrenciler tek panelde — Kim geride kaldı, bir bakışta gör
- Risk büyümeden fark et — Sistem geride kalanı önden işaretler
- Programı dakikada kur — Akıllı önerilerle haftayı planla
- Her konunun doğruluğu net — Eksik konu kör nokta kalmaz
- Yapay zekâ ile seansa hazır gel — Bir sonraki görüşmeye öneriyle gel
- Deneme netleri otomatik ölçülür — Net gelişim trendini izle
- Programın cebinde — Bugün ne yapacağını bil
- Haftanın tamamı bir bakışta — Tüm görevler tek ekranda
- Hedef, odak, tekrar gelişim sistemi — Gelişimini sen yönet
- Veli her şeyi görür — Çocuğun gelişimi tam şeffaf
- Haftalık rapor, gelişim şeffaf — Net gelişim her hafta elinde
- Tüm koç ve öğrenci tek panelde — Ekosistemi tek ekrandan yönet
- Riski gör, müdahale et — Sorumlu koça anında ilet
- Tükenmişliği erken yakala — Yorulan koçu zamanında fark et

---

## PLAY İÇİN SEÇİLEN 8 GÖRSEL (yükleme sırası)
1. `play8/1.png` — Hero: Hedefe giden net rota
2. `play8/2.png` — Hero: Kimse geride kalmasın
3. `play8/3.png` — Programı dakikada kur (koç)
4. `play8/4.png` — Her konunun doğruluğu net (koç)
5. `play8/5.png` — Yapay zekâ ile seansa hazır gel (koç)
6. `play8/6.png` — Deneme netleri otomatik ölçülür (koç)
7. `play8/7.png` — Haftalık rapor (veli)
8. `play8/8.png` — Riski gör, müdahale et (kurum)
