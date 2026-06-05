# Web ↔ Mobil Uygulama — Özellik Karşılaştırması

Tarih: 2026-06-05 · Mobil sürüm: 1.0.0 (Expo SDK 54)

**Felsefe (kullanıcı kararı):** Mobil = **gözlem + günlük aksiyon + hızlı veri
girişi**; karmaşık kurulum/yönetim (kütüphane, program editörü, abonelik, analiz
derinliği) **web'de kalır**. Süper admin tamamen web. Tek ortak Postgres + FastAPI;
yalnız arayüz ayrı.

Erişim notu: her panelin **Profil** sekmesinde "Web paneli aç" + "Hesap & Şifre"
linkleri var → mobilde olmayan her şeye tek tıkla web'den ulaşılır.

---

## Öğrenci

| Özellik | Web | Mobil | Not |
|---|:--:|:--:|---|
| Günlük program (görev gör/tamamla) | ✅ | ✅ | kısmi tamamlama + doğru/yanlış |
| Haftalık program | ✅ | ✅ | |
| Görev talebi (soru/değiştir/kaldır/kaynak değiştir) | ✅ | ✅ | |
| Denemeler (gör) | ✅ | ✅ | net trend grafiği |
| **Günün düşünce notu (autosave)** | ✅ | ✅ | Bugün ekranında, 700ms debounce |
| **Kitaplarım + ilerleme** | ✅ | ✅ | ders bazlı + kitap progress barı |
| **Çalışma DNA (analiz)** | ✅ | ✅ | "Gelişim" sekmesi |
| **Odak (Pomodoro — başlat/çalıştır/bitir)** | ✅ | ✅ | canlı sayaç |
| **Tekrar (aralıklı — kart değerlendir)** | ✅ | ✅ | FSRS oturumu (1-4) |
| **Hedefler (oluştur/ilerlet/tamamla)** | ✅ | ✅ | tam yönetim |
| Bölüm baz "çözülmüş" girişi / projeksiyon detay | ✅ | ⬜ | web |

## Veli

| Özellik | Web | Mobil | Not |
|---|:--:|:--:|---|
| Pano (çocuk kartları + son deneme) | ✅ | ✅ | |
| Çocuk detayı (projeksiyon/ders/koç notu) | ✅ | ✅ | |
| Çocuğun haftası | ✅ | ✅ | |
| Bildirimler listesi | ✅ | ✅ | |
| Tercihler / sessiz saat / WhatsApp doğrulama | ✅ | ⬜ | web (/parent/settings) |

## Koç (Öğretmen)

| Özellik | Web | Mobil | Not |
|---|:--:|:--:|---|
| Öğrenci listesi (uyarı renkli) | ✅ | ✅ | arama + durum |
| Öğrenci detayı — durum özeti (Genel) | ✅ | ✅ | uyarı + bugün/hafta görev |
| **Denemeler — sonuç gir/sil** | ✅ | ✅ | net canlı hesap |
| **Seanslar — kaydet/gör** | ✅ | ✅ | durum/kanal/gündem/ruh hali |
| **Tahsilat — ücret + ödeme** | ✅ | ✅ | aylık pano |
| **Destek — talep/yanıt + gelen kutusu** | ✅ | ✅ | |
| **Haftalık programı gör** | ✅ | ✅ | "Program" sekmesi (gün kartları + %) |
| **Görev ekle (kaynaktan program yap)** | ✅ | ✅ | Test (kitap→bölüm→soru) + Etkinlik |
| **Öğrenci davet (oluştur + geçici şifre)** | ✅ | ✅ | listede "Davet" |
| **Paket yönetimi (bağımsız koç)** | ✅ | ✅ | durum + AI kredisi + tier yükselt |
| **Öğrenci Gelişim izleme** (DNA/Odak/Tekrar/Hedef) | ✅ | ✅ | "Gelişim izleme" — zorlandığı konular |
| **Öğrenciye hedef ekle + tekrar kartı seed** | ✅ | ✅ | Gelişim izleme içinde |
| Program **gelişmiş düzenleme** (sürükle-bırak, rezerv, blok, periyot) | ✅ | ⬜ | web |
| Kütüphane / kitap CRUD / şablon | ✅ | ⬜ | web (kaynak girişi) |
| AI foto/ses not + koçluk içgörüsü | ✅ | ⬜ | web (native kamera/mik sonra) |
| Kaynak kullanım oranları / akademik yıl / sınıf yükseltme | ✅ | ⬜ | web (seyrek/yönetsel) |
| WhatsApp tekli/toplu gönderim | ✅ | ⬜ | web |

## Kurum Yöneticisi

| Özellik | Web | Mobil | Not |
|---|:--:|:--:|---|
| Panel (KPI + koç performansı) | ✅ | ✅ | orana göre renk |
| Müdahale Merkezi | ✅ | ✅ | severity kartları |
| Talepler (gelen + kendi) | ✅ | ✅ | |
| Program uyumu / akademik / karne / veli güveni | ✅ | ⬜ | web (analiz derinliği) |
| Risk / tükenmişlik / kohort / ısı haritası | ✅ | ⬜ | web |
| Öğretmen CRUD / davet / koça-ilet | ✅ | ⬜ | web |
| Abonelik / kuota / kullanım | ✅ | ⬜ | web |

## Süper Admin

Tamamen **web** (mobil kapsam dışı — kullanıcı kararı).

---

## Bildirimler (e-posta → uygulama push) + deep-link

Backend: `device_push_tokens` + Expo Push API + dispatcher hook.
Mobil: bildirime **tıkla → doğru ekran** (`NotificationObserver`, soğuk+sıcak açılış).

| E-posta türü | Push | Tıkla → ekran |
|---|:--:|---|
| Veli: haftalık rapor | ✅ | → Haftalık rapor (geçen hafta performansı) |
| Veli: yeni program | ✅ | → Haftalık program |
| Veli: dikkat / koç notu / deneme yaklaşıyor / boş gün | ✅ | → Çocuk detayı |
| Destek yanıtı (koç/kurum/süper admin) | ✅ | → Destek thread |
| Trial/yenileme hatırlatma, signup admin, iletişim talebi | ⬜ | işlemsel; sonra eklenebilir |

Mobil: izinli cihazda otomatik token kaydı (authed olunca). **Tam çalışması için**
EAS projectId + EAS build gerekir; Expo Go'da projectId yoksa sessiz no-op
(özellik bozulmaz). Token DB'de saklanır, `DeviceNotRegistered`'da silinir.

---

## Sıradaki (opsiyonel, kullanıcı önceliğine bağlı)

1. **EAS build + projectId** → push'un gerçek cihazda uçtan uca testi + store derlemesi.
2. Koç: program **görüntüleme** (salt-okuma hafta) → düzenleme web'de kalır.
3. Native AI yakalama (kamera/mikrofon) → koç foto/ses not.
4. Faz 7: `app/preview/*` rotalarının store build öncesi kaldırılması.
