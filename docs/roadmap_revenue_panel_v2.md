# Ticari Pano 2.0 — Yol Haritası

**Durum:** Faz A tamam (2026-05-16) · diğer fazlar backlog
**Hazırlanma tarihi:** 2026-05-16
**Bağlam:** Mevcut `/admin/security-monitor/revenue` (Katman 11.G) "rapor" seviyesinde — kuru sayı listesi. Saha kullanımında "operasyon" seviyesi gerekiyor: sayıların arkasında isim, kuruma özel aksiyon, ödeme/kampanya akışları.

---

## Mevcut Eksiklikler (teşhis)

| Eksik | Sonuç |
|---|---|
| Sayı var, isim yok | "2 deneme dönüşmedi" diyor ama hangi kurumlar bilinmiyor |
| Tıklanabilir kırılım yok | Üst kartlar zoom-in yapmıyor (drill-down) |
| Sebep gerekçesi yok | "Kritik 2" diyor ama neden kritik söylemiyor |
| Aksiyon önerisi yok | Sorunu söyleyip çözümü kullanıcının kafasında kalıyor |
| Sistem kullanımı görünmüyor | Aktif öğretmen/öğrenci sayısı yok → "para verir mi" tahmini yok |
| Ödeme takvimi yok | "Ödemesi 5 gün sonra dolacak" listesi yok |
| Kampanya/teklif sistemi yok | "Bu kuruma indirim sun" akışı yok |
| Geçmiş aksiyon notu yok | "Geçen ay aradık ne dedi" hatırlanmıyor |
| Tahmin/öngörü yok | "Önümüzdeki 90 gün MRR ne olacak" yok |

---

## Faz A — Drill-Down & İsim Listesi *(S — Hızlı kazan)*  ✅ TAMAMLANDI (2026-05-16)

Her sayının arkasında tıklanabilir kurum listesi (modal veya HTMX ile genişleyen satır).

**Drill yapılacak yerler:**
- Kritik / Risk / Dikkat / Watch (churn proxy bantları)
- Trial bitiş yaklaşan (zaten kısmen var, derinleştir)
- Trial dönüşmedi (30g)
- Yeni kayıt / Pause / Upgrade / Downgrade
- Her plan satırı → o planda olan kurumlar

**Drill-down panel içeriği:** kurum adı + sebep + son aktivite + detay link.

---

## Faz B — Kurum 360 Dosyası *(M)*  🟡 KISMI TAMAMLANDI (2026-05-16)

**Sprint B'de yapılan:**
- ✅ `/admin/revenue/institutions/{id}` sayfası — kimlik üst banner + 4 KPI kartı (sağlık, aylık katkı, aktif kullanıcı, ödeme durumu)
- ✅ 5 sekme: ❤️ Sağlık ve Riskler · 📊 Kullanım · 💳 Plan & Ödeme · 📝 Notlar · 🎯 Aksiyonlar
- ✅ Yeni CRM modelleri: `CrmNote` (sabitlenebilir kronolojik notlar) + `CrmAction` (telefon/e-posta/WhatsApp/görüşme/teklif/onboarding türleri + takip tarihi + sonuç)
- ✅ 6 yeni route: not ekle/sabitle/sil + aksiyon ekle/tamamla/sil
- ✅ Sağlık skoru tersine çevrildi (yüksek = sağlıklı)
- ✅ Mevcut tenant_health indicators + ödeme gecikme + trial bitiş riski birleşik liste
- ✅ Drill-down'lardan "Kurum 360 →" linki
- ✅ Smoke test: `scripts/test_institution_360.py` 59/59 PASS

**Yapılmayan (Sprint sonrası):**
- Logo/iletişim metadata genişletmesi (LinkedIn, telefon vb.) — Institution modeli minimum kalıyor
- Aksiyon şablonları (Faz D — trial reminder vb.)
- Etiketler/tag sistemi (VIP, Pilot, vb.)
- Plan geçmişi timeline görseli (account_history'ye link var)

`/admin/revenue/institutions/{id}` — her kurum için tek sayfada her şey.

**Sol şerit — kimlik kartı:**
- Logo/isim · plan · plan başlangıcı · sonraki yenileme tarihi · ödeme yöntemi
- İletişim: yetkili kişi, telefon, e-posta, LinkedIn varsa
- Etiketler (tag): "VIP", "Pilot", "B2B referansı", vb.

**Üst şerit — sayısal sağlık:**
- Health skoru: 0-100 · ↑↓ son 7 günlük yön
- MRR katkısı · LTV tahmini · CAC (girdi varsa)
- Plan geçmişi timeline: trial → standart → pro → pause → resume

**Ana panel — sekmeli:**
1. Kullanım grafiği (7/30/90 gün): aktif öğretmen, aktif öğrenci, çözülen soru, gönderilen bildirim
2. Plan & Ödeme geçmişi (her satır: tarih, plan, neden, kim onayladı)
3. CRM notları — admin'in elle yazdığı notlar, kronolojik
4. Aksiyon geçmişi — atılan e-posta, yapılan arama, sunulan teklif, sonuç
5. Açık riskler — bu kuruma özel uyarılar (öğretmen düştü, ödeme gecikti, vb.)

---

## Faz C — Sağlık Skoru 2.0 + Erken Uyarı *(M-L)*  ✅ TAMAMLANDI (2026-05-16) — Sprint F.1

Mevcut churn_proxy basit (tenant_health'ten geliyor). Yenisi: **kullanım bazlı sağlık skoru**.

**Skor bileşenleri:**
| Bileşen | Ağırlık | Veri kaynağı |
|---|---|---|
| Aktif öğretmen oranı (haftalık) | 25% | login + task atama |
| Aktif öğrenci oranı (günlük) | 25% | login + soru çözüm |
| Soru çözüm hacmi trendi | 15% | study_session |
| Bildirim açma oranı | 10% | notification_log |
| Ödeme zamanlılığı | 10% | invoice geçmişi |
| Destek talebi sayısı | 5% | support tickets (varsa) |
| Plan yaşı | 10% | institution.created_at |

**Skor bantları:**
- 80-100 = Champion (referans aday)
- 60-79 = Healthy (sürdür)
- 40-59 = At Risk (izle + temas)
- 20-39 = Critical (haftalık ara)
- 0-19 = Lost-imminent (acil müdahale)

**Otomatik erken uyarı tetikleyiciler:**
- Aktif öğretmen sayısı %30 düştü 7 gün içinde → kart kırmızıya döner + alarm
- Hafta sonu sıfır soru çözüldü → uyarı
- Skor 7 gün üst üste düştü → uyarı

**Sprint F.1 çıktıları:**
- ✅ `health_score_v2.py` — 6 bileşenli ağırlıklı user-facing skor (yüksek=sağlıklı)
  - Aktif öğretmen %25 + Aktif öğrenci %25 + Görev tamamlama %15 + Bildirim başarısı %10 + Ödeme zamanlılığı %15 + Plan yaşı %10
- ✅ 5 band: champion (80+) / healthy (60-79) / at_risk (40-59) / critical (20-39) / lost_imminent (<20)
- ✅ `HealthScoreSnapshot` modeli + migration `b2d5g8f9e77z` — günlük snapshot (institution × date UNIQUE)
- ✅ 3 erken uyarı tetikleyicisi: T1 öğretmen %30+ düştü, T2 hafta sonu sıfır aktivite, T3 skor 7g monoton düşüş
- ✅ Cron job `health_snapshot_daily` (önerilen 03:00 UTC) — `cron_jobs.py`'a register edildi
- ✅ Kurum 360 → Sağlık & Riskler sekmesinde yeni bölüm: skor + band rozeti + bileşen breakdown + tetikleyici uyarıları + 14g sparkline
- ✅ Smoke test `scripts/test_health_score_v2.py` 23/23 PASS

---

## Sprint F.2 — Bağımsız Öğretmen Owner-Pattern Entegrasyonu  ✅ TAMAMLANDI (2026-05-16)

Sistemde iki "billing owner" tipi var: Institution (kurum) ve bağımsız öğretmen (User where role=TEACHER, institution_id=NULL). Önceki sprintler institution-only çalışıyordu; bu sprint owner-aware abstraction'ı ekledi.

**Sprint F.2 çıktıları:**
- ✅ Servis `app/services/revenue_owner.py` — `Owner` dataclass + `iter_owners`/`get_owner`/`plan_distribution_owner_aware`/`mrr_owner_aware`/`trial_ending_soon_owner_aware`
- ✅ `Owner.url` ve `Owner.display_label` property'leri — UI'da uniform link/etiket
- ✅ Yeni sayfa `/admin/revenue/users/{user_id}` — bağımsız öğretmen "user-360 lite" (plan KPI + öğrenci sayısı + trial + plan değişim geçmişi)
- ✅ Ticari Pano üst banner: "🏢 + 👤 Birleşik Görünüm" — toplam MRR (kurum+öğretmen), aktif sahip sayısı, ödeyen sayısı, trial bitenler
- ✅ Forecast `risk_at_mrr` genişletildi: ödeyen bağımsız öğretmenler heuristik ile dahil (last_login_at NULL veya 30g+ → critical; 14-30g → risk); `AtRiskInstitution.owner_type` field + `detail_url` property
- ✅ Forecast template'inde bağımsız öğretmenler 👤 ikonu ile ayırt edilir; teklif yolla butonu yerine "Profil →" linki
- ✅ Smoke test `scripts/test_revenue_owner.py` 30/30 PASS + regresyon: forecast 30/30, offers 58/58, campaigns 53/53, cohort 38/38, institution_360 59/59, action_center 42/42
- ⏭ Bekleyen: Campaign segment'lerine "bağımsız öğretmen" filtresi (free/trial_ending/champion gibi mevcut segmentleri owner-aware yap); CRM notes/actions extension to users; sağlık skoru v2'nin User varyantı

---

## Faz D — Aksiyon Merkezi (CRM-lite) *(M)*  ✅ TAMAMLANDI (2026-05-16)

**Sprint C'de yapılan:**
- ✅ `/admin/revenue/action-center` sayfası — "Bugün ne yapmalıyım?" akıllı önceliklendirilmiş liste
- ✅ 9 sinyal türü: health_critical/risk/watch, billing_overdue_severe/mild, trial_ending_imminent/week, champion
- ✅ Her satır: kurum + total_score + primary signal + ikincil sinyaller + önerilen aksiyonlar
- ✅ 7 öneri kategorisi × 2 aksiyon = otomatik öneri rasyonu
- ✅ Hızlı aksiyon: tek tık ile CrmAction oluşturma (3 gün takip default)
- ✅ Son temas bilgisi (kurum 7+ gün temas almamışsa uyarı)
- ✅ Smoke test: `scripts/test_action_center_dunning.py` 42/42 PASS

**"Bugünün arama listesi"** — sayfa açılışında ilk gördüğü şey:

Örnek:
1. Demo Dershane Antalya — Skor 7 gün üst üste düştü — [Ara] [E-posta] [Teklif sun]
2. ABC Etüt — Trial 2 gün kaldı, hareket yok — [Ara] [Uzatma sun]
3. XYZ Kolej — Ödeme 5 gün gecikti — [Hatırlat]
4. KLM Akademi — Aktif öğretmen %50 düştü — [Onboarding tekrar]
5. NMO Dershane — Champion seviyede — [Memnuniyet anketi / referans iste]

**Her aksiyon için:**
- Kuruma özel kısa script önerisi (template)
- Sonuç kaydı: "yapıldı / yapılamadı + not"
- Sonraki adım tarihi
- Birden fazla admin varsa atama (assignee)

**Aksiyon şablon kütüphanesi:**
- Trial bitiş hatırlatma (D-7, D-3, D-1)
- Win-back (pause sonrası 30 gün)
- Cross-sell (free → standart)
- Re-engagement (aktivite düşüşü)
- Memnuniyet anketi (Champion)

---

## Faz E — Kampanya & Teklif Sistemi *(L)*

İki seviye.

### Seviye 1: Bireysel teklif (per-kurum)  ✅ TAMAMLANDI (2026-05-16) — Sprint D.1

Form:
- Plan indirim (% / sabit ₺) — süre (ay)
- Trial uzatma (gün)
- Ücretsiz ek özellik
- Onboarding eğitimi (saat)
- "Teklifi yolla — e-posta / WhatsApp" veya "Linke dönüştür"

Akış: teklif link olarak gönderilir → kurum tıklar → tek tıkla kabul/ret → otomatik plan değişimi + audit.

**Sprint D.1 çıktıları:**
- ✅ `Offer` modeli + migration `f0c3e5d6e55x_offers_table.py` — 7 kind × 6 status + token bazlı public link
- ✅ Servis (`app/services/offers.py`) — create/send/cancel/accept/decline/expire + `describe_offer` UI özeti
- ✅ Public route `/offers/{token}` (login YOK) — view + accept + decline
- ✅ Standalone view template `templates/offers_public/view.html` — durum bazlı UI + ok/err query banner
- ✅ E-posta şablonu `emails/offer_invitation.html` — CTA "Teklifi gör" butonu
- ✅ Admin routes `/admin/revenue/institutions/{id}/offers/create|send|cancel` — full audit log
- ✅ Kurum 360 → "🎁 Teklifler" 6. sekme — sol panel form + sağ panel liste + inline aksiyon butonları
- ✅ Plan değişim entegrasyonu: PLAN_UPGRADE kabul → `inst.plan` değişir + PlanChangeHistory; TRIAL_EXTENSION → `inst.trial_ends_at` uzar; diğerleri sadece audit kaydı
- ✅ Smoke test `scripts/test_offers.py` 58/58 PASS + regresyon: institution_360 59/59, account_history 38/38, action_center_dunning 42/42, invoice_payment_calendar 35/35

### Seviye 2: Toplu kampanya  ✅ TAMAMLANDI (2026-05-16) — Sprint E.1

Form:
- Hedef segment (plan = free, trial bitiş 7g içinde, pause 30+ gün, Champion seviye, vb.)
- Mesaj kanalları (e-posta, WhatsApp, içeride banner)
- Süre (başlangıç-bitiş)
- A/B varyant desteği

Sonuç paneli: tıklama, kabul, kaybedilen, gelir etkisi.

**Sprint E.1 çıktıları:**
- ✅ `Campaign` + `CampaignRecipient` modelleri + migration `a1c4f7e8d66y_campaigns_table.py`
- ✅ 7 önceden tanımlı segment: free_plan, trial_ending_7d, paused_30d, champion, paying_at_risk, never_logged_in, custom_plan
- ✅ Servis `app/services/campaigns.py` — preview_segment/create/launch/pause/resume/complete/cancel/sync/stats
- ✅ A/B varyant desteği — institution_id paritesine göre deterministik split
- ✅ Launch akışı: her recipient için Offer üretilir + e-posta gönderilir + funnel takibi
- ✅ Funnel: targeted → sent → accepted/declined/expired/bounced
- ✅ Liste sayfası `/admin/revenue/campaigns` (kampanya listesi + funnel özet)
- ✅ Form sayfası `/admin/revenue/campaigns/new` — HTMX ile canlı segment önizleme (kaç kurum hedeflenecek)
- ✅ Detay sayfası `/admin/revenue/campaigns/{id}` — funnel KPI + A/B karşılaştırma + recipient liste
- ✅ E-posta kanalı (mevcut `offer_invitation.html` reuse); WhatsApp/banner kanalları ileride
- ✅ Smoke test `scripts/test_campaigns.py` 53/53 PASS
- ⚠️ Not: tenant_health.level kullanımı düzeltildi (raw score yüksek=kötü, level "critical"/"risk"/"watch"/"healthy")

---

## Faz F — Ödeme & Fatura Takvimi *(M)*  ✅ TAMAMLANDI (2026-05-16)

**Sprint A.2 tamamlandı:**
- ✅ `Invoice` modeli + migration (status: pending/paid/overdue/failed/refunded/cancelled)
- ✅ `payment_calendar_summary()` — 8 bucket (overdue_7plus..due_in_14d)
- ✅ Ana sayfa banner: vade yaklaşan + gecikmiş faturaların özeti, bucket'lar tıklanabilir
- ✅ `/admin/security-monitor/revenue/invoices` — tüm faturalar listesi + status filtresi
- ✅ Drill: `invoice_bucket:<key>` her bucket için kurum/fatura listesi
- ✅ `mark_overdue` cron job (günlük 02:30 UTC) — PENDING → OVERDUE
- ✅ Smoke test: `scripts/test_invoice_payment_calendar.py` 35/35 PASS

**Sprint C'de tamamlanan:**
- ✅ Dunning servisi (`app/services/dunning.py`) — 6 aşamalı zincir (D-7..D+7)
- ✅ Cron: `dunning_send_reminders` (günlük 09:00 UTC) — uygun aşamayı her fatura için bir kez tetikle
- ✅ E-posta şablonu: `emails/dunning_reminder.html` — aşamaya göre ton (nazik → uyarı → son şans)
- ✅ Manuel müdahale: postpone (vade ötele), mark-paid (manuel öden), cancel (iptal), send-reminder (manuel hatırlat)
- ✅ Kurum 360 Plan & Ödeme sekmesinde inline butonlar — her açık fatura için manuel aksiyonlar
- ✅ Audit log: tüm manuel aksiyonlar `invoice` target_type ile kayıt altında

**Geri kalan (ileride):**
- Stripe/Paykasa entegrasyonu (gerçek tahsilat — şu an stub)
- "Yeni ödeme yöntemi linki gönder" (kart yenileme akışı)
- WhatsApp Cloud kanalından dunning

**Üst banner — kritik ödemeler:**
- Yarın ödeme dolacak: kim, ne kadar, kart durumu
- 3 gün içinde: kim, ne kadar, kart süresi geçti mi
- Gecikti: kim, kaç gün, ne kadar

**Otomatik hatırlatıcı zinciri (dunning):**
- D-7: nazik hatırlatma e-postası
- D-3: ikinci hatırlatma + WhatsApp
- D-1: son uyarı
- D+1: ödeme gecikti uyarısı + grace period
- D+3: hesap kısıtlama uyarısı
- D+7: oto-downgrade (pause)

**Manuel müdahale aksiyonları:**
- Ödemeyi 7 gün ötele
- Tek seferlik ücret iste
- Yeni ödeme yöntemi linki gönder

---

## Faz G — Kohort & LTV Analizi *(M)*  ✅ TAMAMLANDI (2026-05-16) — Sprint D.2

**Aylık kohort tablosu:**
Aylık olarak kayıt olan kurumların 1.ay, 2.ay, ..., 12.ay tutunma oranı + LTV(₺).

Görselde **heatmap**: yeşil → kırmızı renk gradyanı, dik düşüş = problem.

**Plan başına churn oranı:**
- 14 günlük trial → ödemeye dönüşüm %
- 30 günlük pilot → dönüşüm %
- Aylık → yıllığa upgrade %

**LTV tahmini:** ortalama plan yaşı × MRR × marj. Plan başına ayrı hesaplanır.

**Sprint D.2 çıktıları:**
- ✅ Servis `app/services/revenue_cohort.py` — `signup_cohort_matrix` + `plan_churn_summary` + `ltv_estimate`
- ✅ Route `/admin/revenue/cohort` — filtre (months_back/horizon/churn_days) + KPI + heatmap + LTV tablosu
- ✅ Template `templates/admin/revenue_cohort.html` — 5 renk skalalı heatmap (emerald→rose), "future" hücreleri gri
- ✅ Plan tarihçesi entegrasyonu: `_plan_at(inst, dt)` PlanChangeHistory'den geriye gidip belirli tarihteki planı bulur
- ✅ Ticari Pano üst linkten "📊 Kohort & LTV" butonu
- ✅ Smoke test `scripts/test_revenue_cohort.py` 38/38 PASS + regresyon: institution_360 59/59, action_center_dunning 42/42, offers 58/58

---

## Faz H — Tahmin & Senaryo *(L — opsiyonel ileri seviye)*  ✅ TAMAMLANDI (2026-05-16) — Sprint E.2

**MRR projeksiyonu (90 gün):**
- Trend bazlı (basit lineer)
- + Trial dönüşüm tahmini (kohort oranı uygulanarak)
- − Beklenen churn (kritik/risk kurumların ortalama düşüş oranı)
- = Net MRR tahmini

**Senaryo karşılaştırma:**
- "Status quo" (hiçbir şey yapmazsan) vs "Müdahale et" (kritikleri kurtarırsan)
- 30/60/90 gün MRR farkı

**"Risk altında MRR":** o anki tüm "kritik" kurumların toplam aylık geliri → kaybedilebilecek tutar.

**Sprint E.2 çıktıları:**
- ✅ Servis `app/services/revenue_forecast.py` — `risk_at_mrr` + `mrr_projection` + `scenario_comparison`
- ✅ `_historical_trial_conversion_rate` (180g pencere) + `_historical_churn_rate_monthly` (90g pencere)
- ✅ Projeksiyon formülü: current_mrr + expected_trial_conversions − expected_churn − expected_at_risk_loss
- ✅ Risk altı kayıp katsayıları: critical %80, risk %30, horizon'a göre scale
- ✅ Sayfa `/admin/revenue/forecast` — 30/60/90 projeksiyon tablo + risk altı kurumlar listesi + status quo vs müdahale karşılaştırma
- ✅ Filtre: `save_rate` (%25/50/75/100 — risk altındakilerin ne kadarı kurtarılır)
- ✅ Risk altı kurumlardan doğrudan Kurum 360 teklif sekmesine derin link
- ✅ Ticari Pano üst köşesine "🔮 Tahmin" linki
- ✅ Smoke test `scripts/test_revenue_forecast.py` 30/30 PASS

---

## Önerilen Sprint Sıralaması

| Sprint | Fazlar | Süre |
|---|---|---|
| **Sprint A** (en hızlı değer) | Faz A (drill-down) + Faz F'in 1. yarısı (ödeme takvimi) | 1-2 gün |
| **Sprint B** (müşteri görünürlüğü) | Faz B (Kurum 360) + Faz C (Health 2.0) | 3-4 gün |
| **Sprint C** (operasyon) | Faz D (Aksiyon merkezi) + Faz F'in 2. yarısı (dunning) | 3-4 gün |
| **Sprint D** (büyüme) | Faz E (Kampanya) + Faz G (Kohort) | 5-6 gün |
| Faz H | İleride (tahmin) | opsiyonel |

**İlk hamle önerisi: Sprint A.** Mevcut sayfaya tıklanabilirlik + ödeme takvimi koyup hemen değer üretmek.

---

## Bağımlılıklar / Önkoşullar

- **Faz B-C için:** institution_health verisinin genişletilmesi (öğretmen/öğrenci aktivite metriklerinin günlük snapshot olarak tutulması)
- **Faz E için:** Coupon/teklif modeli (yeni tablo: `Offer`, `OfferRedemption`)
- **Faz F için:** Invoice tablosu (henüz yok) + ödeme yöntemi metadatası
- **Faz G için:** Plan history zaten var (`InstitutionPlanHistory`); kohort SQL'leri eklenmeli

---

## Başarı Kriterleri

- **Faz A çıktığında:** her sayı tıklanabilir, modal'da kurum listesi açılıyor
- **Faz B çıktığında:** her kurum için `/admin/revenue/institutions/{id}` sayfası işliyor
- **Faz C çıktığında:** her kurumun 0-100 skoru var, 7g trendi gösteriliyor
- **Faz D çıktığında:** "bugün ara" listesinde her kurum için aksiyon kaydı tutulabiliyor
- **Faz E çıktığında:** bir kuruma teklif sunup tek tıkla kabulü alabiliyoruz
- **Faz F çıktığında:** ödeme takvimi panele yerleşmiş, D-7'den D+7'ye dunning zinciri çalışıyor
- **Faz G çıktığında:** kohort heatmap'i + LTV tahmini görünüyor
- **Faz H çıktığında:** 90 günlük MRR senaryo karşılaştırması var
