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
| **Anketler (listele + doldur + sonuç gör)** | ✅ | ✅ | Gelişim hub kartı (bekleyen rozet) + push deep-link |
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
| Anket gönder + sonuç + AI Kariyer Sentezi | ✅ | ⬜ | web (öğrenci detayı "Anketler" sekmesi); koça push "Anket tamamlandı" öğrenci detayına gider |
| **Öğrenci Gelişim izleme** (DNA/Odak/Tekrar/Hedef) | ✅ | ✅ | "Gelişim izleme" — zorlandığı konular |
| **Öğrenciye hedef ekle + tekrar kartı seed** | ✅ | ✅ | Gelişim izleme içinde |
| Program **gelişmiş düzenleme** (sürükle-bırak, rezerv, blok, periyot) | ✅ | ⬜ | web |
| Kütüphane / kitap CRUD / şablon | ✅ | ⬜ | web (kaynak girişi) |
| AI koçluk içgörüsü (Gemini) | ✅ | ✅ | "Gelişim izleme → İçgörü"; web+mobil AYNI backend ucu (`/coaching-insight`) |
| AI foto/ses not (yakalama) | ✅ | ⬜ | web (native kamera/mik sonra) |
| Kaynak kullanım oranları / akademik yıl / sınıf yükseltme | ✅ | ⬜ | web (seyrek/yönetsel) |
| WhatsApp tekli/toplu gönderim | ✅ | ⬜ | web |

## Kurum Yöneticisi

| Özellik | Web | Mobil | Not |
|---|:--:|:--:|---|
| Panel (KPI + koç performansı) | ✅ | ✅ | orana göre renk; koç satırı → detay |
| Koç detayı (öğrenci listesi + 7g planlanan/çözülen) | ✅ | ✅ | gizlilik banner |
| Müdahale Merkezi | ✅ | ✅ | severity kartları |
| Talepler (gelen + kendi) | ✅ | ✅ | öğretmen + süper admin |
| Öğretmen daveti (oluştur/link paylaş/iptal) | ✅ | ✅ | Analiz hub → Kişiler |
| Program uyumu / akademik / karne / hedef / veli güveni | ✅ | ✅ | Analiz hub |
| Risk / tükenmişlik / kohort / ısı haritası | ✅ | ✅ | Analiz hub; risk+tükenmişlik "Koça ilet" |
| Haftalık özet (arşiv + detay + şimdi gönder) | ✅ | ✅ | Analiz hub |
| Abonelik / kuota / kullanım | ✅ | ✅ | Analiz hub → Üyelik |
| Aktivite akışı (kim katıldı/yükseltti) | ✅ | ✅ | Analiz hub → Genel |
| Öğretmen CRUD (pasife al/sil/rol) | ✅ | ⬜ | web (yönetim derinliği) |

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

## Demo videoları (panel-içi "▶ Nasıl kullanılır?")

Web ile aynı registry (`src/lib/demos.ts`, 35 demo) + `components/demos/demo-hint.tsx`
(expo-web-browser ile uygulama-içi açar; uygulamadan çıkmaz). Bağlamsal yerleşim
(genel "Demolar" listesi YOK — web kararıyla aynı):
- **Öğrenci**: Bugün (day) · Odak · Hedefler · Tekrar · Hafta
- **Koç**: Program · Seanslar · Tahsilat
- **Veli**: Haftalık Rapor · Yapay Zekâ Durum Analizi
- Demo içeriği canlı web `/demos`'tan gelir (sahne + sesli anlatım); yeni demo =
  web+mobil registry birlikte güncellenir.

## Hızlı Erişim Kartları (QA-3, 2026-06-11)

Web ile AYNI backend (`/api/v2/me/quick-cards` + `panel-visits`); skor/yaşam
döngüsü sunucuda. Mobil katman:
- `lib/quick-access.ts` — ÇİFT YÖNLÜ eşleme: mobil ekran→katalog web path
  (ziyaret izleme) + route_key→mobil ekran (kart navigasyonu). Yeni mobil
  ekran eklenince (web karşılığı varsa) İKİ tabloya da satır eklenir.
- `components/panel-visit-tracker.tsx` — authed layout'ta; ≥3sn kalış +
  30sn batch + arka plana inerken flush; `source: "mobile"`.
- `components/quick-access-strip.tsx` — 4 rol ana ekranında (koç Öğrenciler /
  kurum Panel / veli Çocuklarım / öğrenci Bugün) yatay kart şeridi; dokun→git,
  **basılı tut→Sabitle/Kaldır** menüsü; mobilde karşılığı olmayan kart gizlenir.

## EAS Update (OTA) — 2026-06-11

`expo-updates` kuruldu; `app.json` updates.url + `runtimeVersion: appVersion`;
`eas.json` kanalları: preview / production. **İlk etkinleşme yeni build ister**
(expo-updates native modül) → sonraki salt-JS değişiklikler
`eas update --channel production -m "mesaj"` ile store'suz gider.
Native değişiklikte (yeni modül/izin) yine yeni AAB + store gerekir.

---

## Sıradaki (opsiyonel, kullanıcı önceliğine bağlı)

1. **EAS build + projectId** → push'un gerçek cihazda uçtan uca testi + store derlemesi.
2. Koç: program **görüntüleme** (salt-okuma hafta) → düzenleme web'de kalır.
3. Native AI yakalama (kamera/mikrofon) → koç foto/ses not.
4. Faz 7: `app/preview/*` rotalarının store build öncesi kaldırılması.
