# Tenant Aktivite Kamerası 2.0 — Yol Haritası

**Durum:** Plan / Backlog (henüz başlanmadı)
**Hazırlanma tarihi:** 2026-05-16
**Bağlam:** Mevcut `/admin/security-monitor/activity` (Katman 11.H) çok dar bir kamera — sadece "kim açtı" sorusunun temelini sunuyor. Bir üyelik sistemini yönetmek için 7 farklı pencereye bakmak gerekir; şu an sadece 1 tanesinde yarım veri var.

---

## Üyelik Sistemini Yönetirken Bakılan 7 Pencere

| # | Pencere | Soru | Şu an durumu |
|---|---|---|---|
| 1 | **Sağlık** | "Bugün sistem ölü mü, ayakta mı?" | ⚠ Yarım |
| 2 | **Tutunma** | "Bugün gelenler yarın da gelir mi?" | ❌ Yok |
| 3 | **Derinlik** | "Ne kadar kullanıyorlar?" | ❌ Yok |
| 4 | **Genişlik** | "Hangi özellikleri kullanıyorlar?" | ❌ Yok |
| 5 | **Zaman örüntüsü** | "Ne zaman aktifler?" | ⚠ Yarım |
| 6 | **Erken uyarı** | "Kim gitmek üzere?" | ⚠ Yarım |
| 7 | **Karşılaştırma** | "Bu kurum normalin neresinde?" | ❌ Yok |

---

## Faz A — Dil/Jargon Temizliği *(S — Hemen yapılmalı, tüm sayfaları kapsar)*

**Mevcut sayfada düzeltilecek:**
- "DAU (24h)" → "Günlük Aktif Kullanıcı" + alt satır: "Son 24 saatte sisteme giriş yapan kişi sayısı"
- "WAU (7g)" → "Haftalık Aktif Kullanıcı"
- "MAU (30g)" → "Aylık Aktif Kullanıcı"
- "Tenant Aktivite (MAU descending)" → "Kurum Aktivitesi (Aylık aktif kullanıcı sayısına göre — yüksekten düşüğe)"
- "Heatmap" → "Saat × Gün Isı Haritası" + alt satır: "Hangi saatlerde yoğun, hangi saatler boş"
- Her sayfanın üst kısmında **"Bu sayfada ne yazıyor?"** açılır kutusu (3-5 satırlık sade Türkçe özet)
- Her metrik kartının yanında **ⓘ tooltip** — anlamı ve niye önemli olduğu

**Bağımsız iş:** Bu temizlik tüm kameralarda (1-8 ve gelecek olanlar) eşzamanlı yapılmalı.

---

## Faz B — Pencere 1 (Sağlık) Tamamlama *(M)*

Mevcut DAU/WAU/MAU yetmez. Ekle:

**Rol kırılımı kartları:**
- Bugün aktif öğretmen: X (dün: Y, fark: ±%Z)
- Bugün aktif öğrenci: X (dün: Y)
- Bugün aktif veli: X (dün: Y)
- Bugün aktif kurum yöneticisi: X (dün: Y)

**Her kurumun kalp atışı:**
- Kurum adı | yetkili yöneticisinin son giriş zamanı | uyarı bandı
- 14 gün+ giriş yoktu → kırmızı uyarı (kurum ölmek üzere)
- 7-14 gün arası → kehribar uyarı
- 7 gün altı → yeşil

**Karşılaştırma satırı (mini grafik):**
- "Bu haftaki DAU eğrisi geçen hafta ile karşılaştır" — yan yana iki çizgi

---

## Faz C — Pencere 2 (Tutunma) *(M-L)*

**Yapışkanlık metriği (Stickiness):**
- DAU/MAU oranı = "kullanıcılarımızın yüzde kaçı bugün geldi"
- %30+ = sağlıklı (yeşil), %20-30 = orta, <%20 = zayıf
- Trend göstergesi (son 30 gün)

**1. hafta tutunma oranı:**
- Bu hafta kayıt olan kullanıcının kaçı 7 gün sonra hâlâ aktif
- Plan başına ayrı (trial → ödemeli geçen kohort en kritik)

**30 gün hayatta kalma:**
- Bir kullanıcının kayıt olduktan 30 gün sonra hâlâ aktif olma oranı
- "Bu sayı %50'nin altındaysa onboarding bozuk" sinyali

**Yeniden aktiflenme (resurrected):**
- 14 gün+ sessiz olup tekrar dönen kullanıcılar
- "Hangi kampanya tetikledi" not edilirse altın değerinde veri

**Kohort tutunma heatmap:**
- Aylık kohort tablosu — 2026-01 kayıtlıların 1., 2., 3., ... ayda tutunma %'si
- Yeşil-kırmızı gradyan, düşüş örüntüsü görsel

---

## Faz D — Pencere 3 (Derinlik) *(L)*

**Oturum metrikleri:**
- Ortalama oturum süresi (dakika)
- Medyan oturum süresi
- Çok kısa oturum oranı (<1 dk — "açtı kapattı")
- Çok uzun oturum oranı (>30 dk — "çalışıyor")

**Oturum başına aksiyon sayısı:**
- Soru çözme, plan oluşturma, rapor görüntüleme, vb.
- Yüksek = ürün değer üretiyor, düşük = sadece login

**Aktif öğretmen başına aktif öğrenci oranı:**
- Bu metrik "kurum gerçekten kullanıyor mu" en iyi göstergesi
- Plan ortalaması ile karşılaştırma

**Power kullanıcı analizi:**
- En aktif %10 kullanıcı kim, neden aktif (referans olarak öne çıkar)
- En sessiz %10 kullanıcı kim, neden sessiz (intervention listesi)

---

## Faz E — Pencere 4 (Genişlik / Özellik Benimseme) *(L)*

**Özellik benimseme matrisi:**
- Y ekseni: kurumlar
- X ekseni: özellikler (plan oluşturma, soru çözüm takibi, raporlama, etüt çizelgesi, veli iletişimi, vb.)
- Hücreler: kullandı/kullanmadı + son kullanım zamanı

**Özellik popülerlik grafiği:**
- Hangi özellik en çok kullanılıyor, hangisi terk edilmiş
- "Kayıp özellikler" — hiç kimsenin kullanmadığı özellikler

**Onboarding ilerleme:**
- Yeni kurumların "kritik 5 özellik" ilerleme yüzdesi
- "Plan oluşturma" yapmadıysa kurum henüz onboarding'i bitirmemiş

**Sönmüş kullanıcılar (dormant features):**
- Eskiden bir özelliği kullanıp 30 günden uzun süredir kullanmayanlar
- Re-engagement kampanyası listesi

---

## Faz F — Pencere 5 (Zaman Örüntüsü — Kurum Bazlı) *(M)*

**Kurum bazlı ısı haritası:**
- Mevcut toplam heatmap yetmiyor
- Her kurumun kendi 7 gün × 24 saat haritası
- Drill-down: "ETUTKOC'a tıkla → bu kurumun heatmap'i çıksın"

**Örüntü tanıma:**
- Otomatik etiket: "Hafta sonu boş", "Sabah ağırlıklı", "Akşam ağırlıklı"
- "Cuma çöküşü" tespit (her cuma sonrası aktivite düşüyorsa)
- "Pazartesi sendromu" tespit (hafta başında düşüş)

**En iyi temas zamanı:**
- "Bu kuruma e-posta atmak için en iyi saat: Salı 14:00"
- Geçmiş kampanya başarıları + heatmap çakışması

**Tatil/bayram etkisi:**
- Resmî tatil sonrası geri dönüş oranı
- Yarıyıl tatili etkisi
- LGS sınav haftası etkisi (LGS özelinde önemli)

---

## Faz G — Pencere 6 (Erken Uyarı) Tamamlama *(M-L)*

Mevcut "7 gün sessiz" listesi var; tek satır. Genişlet:

**Risk bantları:**
- 3-7 gün sessiz: "İzle" (sarı)
- 7-14 gün sessiz: "Dikkat" (turuncu)
- 14-30 gün sessiz: "Risk" (kırmızı)
- 30+ gün sessiz: "Kayıp/ölü" (siyah/gri)

**Sönüş hızı (decay rate):**
- "Bu kurumun aktivitesi son 7 günde %X düştü"
- Yavaş düşüş = 2-3 hafta uyarı, sert düşüş = günler içinde kaybedebilirsin

**Risk sebepleri (otomatik etiket):**
- "Yetkili 14 gündür yok"
- "Öğretmen sayısı yarıya düştü"
- "Hiç soru çözülmüyor"
- "Bildirimler açılmıyor"

**Plan + aktivite çapraz tablosu:**
- Ödeyen ama kullanmayan = en kritik
- Bedava ama kullanan = upgrade adayı
- Bedava ve kullanmayan = ihmal et
- Ödeyen ve kullanan = referans iste

---

## Faz H — Pencere 7 (Karşılaştırma) *(M)*

**Plan ortalaması karşılaştırma:**
- Bu kurum: DAU 5 | Dershane Pro ortalama: 12 | Sıralaması: 8/15
- Yeşil/kırmızı renk göstergesi

**Kohort karşılaştırma:**
- "2026-01'de kayıt olanlar ortalama X aktiviteye sahip; sen Y"
- Yaşıt kurumlar ile kıyaslama

**Champion rozeti:**
- En üst %10 kurum otomatik "Champion" etiketi
- Bu kurumlar = referans/case study/testimonial adayı
- "Champion'ı 3 ay korursak yıllığa geçirme şansı %X"

**Plan başına benchmark tablosu:**
- Her plan için ortalama DAU, oturum süresi, soru çözüm vb.
- Yeni kayıt için "hedef belirleme" referansı

---

## Faz I — Drill-Down + Kurum 360 Bağlantısı *(M)*

Bütün üst kartlar, listeler, heatmap'ler **tıklanabilir** olmalı:
- "DAU 5" → 5 aktif kullanıcının listesi
- "8 sessiz kurum" → liste açılır + her kuruma "neden sessiz" etiketi
- Heatmap hücresi → o saatte aktif olan kullanıcılar

Her kurum adına tıklayınca **Kurum 360** dosyasına gider (Ticari Pano Roadmap'inde Faz B ile birleşik).

---

## Faz J — Aksiyon Önerileri (CRM Entegrasyonu) *(L)*

Her uyarı/risk satırı için **"Önerilen aksiyon"** kolonu:
- "Yetkili 14g yok" → [Yetkiliyi ara] [Onboarding tekrar gönder]
- "Aktif öğrenci %50 düştü" → [Memnuniyet anketi] [Sebebini öğren]
- "Champion seviyede" → [Memnuniyet referansı iste] [Yıllığa geçir teklif]

Bu kısım Ticari Pano Yol Haritası'nın Faz D'siyle ortak — aynı CRM aksiyon merkezi her iki kamerada da görünür.

---

## Önerilen Sprint Sıralaması

| Sprint | Fazlar | Süre | Çıktı |
|---|---|---|---|
| **Sprint 0** (acil) | Faz A — Tüm panellerin dil temizliği | 1 gün | Jargon yok, mini sözlük + tooltip |
| **Sprint 1** | Faz B (Sağlık) + Faz F (kurum bazlı heatmap) + Faz I (drill-down) | 3-4 gün | "Kim hayatta + ne zaman + tıklanabilir" |
| **Sprint 2** | Faz C (Tutunma) + Faz G (Erken uyarı tamamlama) | 3-4 gün | "Kim gidiyor + kohort tutunma" |
| **Sprint 3** | Faz D (Derinlik) + Faz E (Genişlik) | 4-5 gün | "Ne yapıyorlar, hangi özellik" |
| **Sprint 4** | Faz H (Karşılaştırma) + Faz J (Aksiyon CRM) | 3-4 gün | "Benchmark + ne yapayım önerisi" |

**Sprint 0 derhal yapılmalı** — dil temizliği tüm kameralarda eksik ve kullanıcı her açtığında jargonla karşılaşıyor.

---

## Bağımlılıklar

- **Faz B-C-D için:** kullanıcı aktivite tablosu detaylandırılmalı (oturum süresi, aksiyon sayısı log)
- **Faz E için:** her özellik için "kullanım eventi" log'lanmalı (örn. "plan_created", "report_viewed")
- **Faz H için:** plan ortalamaları için periyodik snapshot tablosu

---

## Başarı Kriterleri

- **Sprint 0 sonrası:** Hiçbir kullanıcı "DAU nedir?" diye sormuyor; her metriğin yanında ⓘ açıklama var
- **Sprint 1 sonrası:** Her sayı tıklanabilir; her kurumun kalp atışı görünüyor
- **Sprint 2 sonrası:** Bir kurumun "gidiyor" sinyalini 14-30 gün önceden yakalıyoruz
- **Sprint 3 sonrası:** Hangi kurumun hangi özelliği kullandığını biliyoruz; onboarding kayıp noktaları görünüyor
- **Sprint 4 sonrası:** Her risk satırında "ne yapayım" cevabı + kıyaslama referansı

---

## İlişki

- [Ticari Pano 2.0 Yol Haritası](roadmap_revenue_panel_v2.md) — bu iki kamera birbirini tamamlar. Faz B (Kurum 360) ortak hub.
- Sprint 0 (dil temizliği) **tüm kameralarda eşzamanlı** olmalı.
