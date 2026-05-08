# UX Denetim Raporu — LGS Takip

**Tarih:** 2026-04-25 · **Sprint:** 8

Bu rapor, Nielsen 10 Heuristics + Miller (7±2) + Hick + Progressive Disclosure ilkeleri çerçevesinde uygulamadaki bilişsel yükü değerlendirir ve aksiyon önerileri sunar.

---

## Özet Bulgular

| Sayfa | Sorun yoğunluğu | Birincil eksik |
|---|---|---|
| **Öğretmen Dashboard** (`/teacher`) | Yüksek | Görsel hiyerarşi yok, tüm paneller eşit ağırlıkta |
| **Öğrenci Detay (öğretmen)** (`/teacher/students/{id}`) | Yüksek | 6 panel dikey yığın → uzun scroll |
| **Öğrenci Günlük** (`/student/day`) | Orta | Öğrenci eylem-odaklı sayfada analitik yığını |
| Haftalık Görünüm (`/teacher/students/{id}/week`) | Düşük | Form alanları kademeli gizlenebilir |
| Diğer (kitap, hafta, talep listesi) | Düşük | Genel olarak temiz |

---

## 1. Öğretmen Dashboard

### Mevcut yapı
1. Bekleyen talep banner (koşullu)
2. Filo Durumu (4 sayaç)
3. Bugün toplamı + Hafta toplamı (2 büyük kart)
4. Öğrenci kartları listesi (her biri 4 mini metrik)
5. Uyarı akışı (sağda)

### İlke ihlali
- **Visibility of system status** ✓ var ama dağınık
- **Aesthetic & minimalist design** ✗ — 5 paralel panel; "şu an ne yapayım" cevabı belirsiz
- **Hick** ✗ — kullanıcı her seferinde 5+ paneli tarıyor
- **Miller (7±2)** ✗ — bilgi parçacıkları 15+ (filo sayaçları + bugün + hafta + her öğrenci kartı)

### Aksiyon
1. **Birincil eylem alanı (üst)**: Uyarılar + bekleyen talepler — *bu sayfaya geliş sebebi*
2. **İkincil özet (orta)**: Bugün/Hafta + Filo durumu yatay tek şerit, daha kompakt
3. **Detay (alt)**: Öğrenci listesi; her kart kompakt ve risk-sıralı; uyarı akışı katlanabilir

---

## 2. Öğrenci Detay (Öğretmen) — `/teacher/students/{id}`

### Mevcut yapı (üstten alta)
1. Header + isim + Haftalık linki
2. 5 KPI kartı (bugün, hafta, hız, tutarlılık, hedef tutturma)
3. Projeksiyon paneli + uyarı listesi yan yana
4. Trend grafiği + ders çubuğu yan yana
5. Kitap envanteri (ders bazında çok kart)

### İlke ihlali
- **Recognition over recall** kısmen — bilgi her yerde ama hangi sekmede ne var belirsiz
- **Aesthetic & minimalist** ✗ — sayfayı bir defada okumak imkansız (4-5 ekran scroll)
- **Progressive disclosure** ✗ — analitik + envanter aynı seviyede

### Aksiyon
**Sekmeli yapı:**
- **Genel** (varsayılan): KPI'lar + projeksiyon + uyarılar
- **Analitik**: Grafikler (trend + ders çubuğu)
- **Kitaplar**: Envanter
- **Plan**: Haftalık programa hızlı erişim (dış sayfaya link)

---

## 3. Öğrenci Günlük — `/student/day`

### Mevcut yapı
1. Header + tarih navigasyonu
2. Projeksiyon paneli (büyük)
3. Günlük özet barı
4. Görev kartları (asıl iş)
5. Ek görev öner formu
6. Trend grafiği
7. Ders çubuğu
8. Sticky Kaynak Durumu sidebar

### İlke ihlali
- Öğrenci için **eylem öncelikli** olmalı (görevleri tıkla); analitik ikincil
- **Hick** ✗ — analitik panelleri görsel olarak görevle yarışıyor
- **Match real world** ✓

### Aksiyon
1. **Görevler** sayfanın merkezinde → projeksiyon ve grafikler **katlanır** (bugün ortalama görmüyor)
2. Sticky sidebar şartlı: küçük ekranlarda altta, büyüklerde yan
3. Ek görev önerme formu zaten katlı; bu kalsın

---

## 4. Tutarlılık (Tüm Sayfalar)

### Sorunlar
- "Geri" linki bazı sayfalarda var, bazılarında yok
- Buton renkleri tutarsız (indigo vs slate vs amber bazen aynı seviyede)
- Panel başlıkları bazen `<h2>` bazen `<div>` ile
- Renkli ikonlar/emojiler bazen başlıkta bazen sadece banner'da

### Aksiyon
- Aynı tutarlılık standardı: panel = `bg-white border rounded-lg`, başlık `px-5 py-3 border-b font-semibold`
- "Geri" linki tüm detay sayfalarında üstte
- Birincil aksiyon = `bg-indigo-600`, yıkıcı = `bg-rose-600`, ikincil = `border-slate-300 bg-white`

---

## Öncelik Sırası (Bu Sprint)

1. **Dashboard refactor** (en görünür, en sık ziyaret edilen) — Hick + Miller
2. **Öğrenci detay sekmeli yapı** — progressive disclosure
3. **Öğrenci günlük analitik katlama** — eylem önceliği
4. **Tutarlılık pass'ı** — buton/panel standartları

Sonraki sprintlerde:
- Mobil-first layout (Sprint 9+ ile birlikte)
- Klavye gezinmesi & erişilebilirlik
- Tema/koyu mod
