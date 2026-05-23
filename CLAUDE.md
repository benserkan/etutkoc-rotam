# CLAUDE.md — Proje Notu

Bu dosya Claude Code'un her sohbette okuduğu kalıcı proje notudur. Memory'ye
yazmak yerine **yapılan paketler + kararlar + sırada ne var** burada tutulur.
Sohbet bitince son durumu buraya yaz; bir sonraki sohbet buradan devam eder.

---

## Proje

**ETÜTKOÇ** — LGS/YKS koçluk takip platformu. FastAPI + Jinja + HTMX'ten
Next.js 16 + React 19 + Tailwind v4 + TanStack Query v5'e taşınıyor (Strangler
Fig deseni; Caddy path-based routing).

- Deploy: AWS Lightsail VPS + 5-container Docker Compose (Caddy/FastAPI/Next.js/Postgres/Redis)
- BFF cookie auth, `/api/v2` JSON
- 5 rol izole: Öğrenci / Öğretmen / Kurum Yöneticisi / Veli / Süper Admin
- Backend Python 3.12, frontend pnpm + Next.js
- Dev: `uvicorn app.main:app --port 8081` + `pnpm dev` (port 3000)

## Yönetim kuralları (kullanıcının kırmızı çizgileri)

- **KURAL 1 — Jinja Read-Receipt Protokolü** (2026-05-19 yeniden tanımlandı):
  Her Jinja→Next.js paketinden önce **iki aşama** zorunlu:
  - **AŞAMA 1 — Link haritalama**: Hedef rolün ana sayfasından (örn.
    `/institution`) yayılan **TÜM** linkler haritalanır. Sadece o rolle ilgili
    kodlar incelenir.
  - **AŞAMA 2 — Eksiksiz okuma**: Haritadaki her route/template/service
    **SONUNA KADAR** okunur. İlk birkaç satıra bakıp tahmin yürütmek yasak;
    sayfa sonuna inilmeden sonraki dosyaya geçilmez. Mimari **tam ve
    eksiksiz** öğrenilir; "muhtemelen şöyledir" mantığı yok.
  - Çıktı: Files-Read Receipt + rolün **tüm eylemleri** (özellik listesi) +
    parite tablosu. Sonra eylem planı + **kullanıcı onayı**. Onaysız kod yasak.
  - Receipt çıkmadan kod yasak. Bu kuralın istisnası yok.
- **Eylem deşifreleme önceliği**: Sorun tasarım değil **fonksiyonellik**.
  Mimariyi anla, hangi eylemi nereden tetiklediğini öğren, eksik özellik
  bırakma. Öğretmen panelinde tek tek talimat verilmek zorunda kalındı —
  bunu kurum panelinde yaşatmamak için mimari önce eksiksiz çözülür.
- **Parite kuralı**: FEATURE parity zorunlu (yapı/akış aynı); VISUAL parity yasak
  (ikon/emoji/renk kopyası değil — fresh shadcn-flavored Next.js look). Parite
  tablosunda "Next.js görsel yaklaşımı" sütunu şart.
- **Rol izolasyonu**: 5 rolün her biri kendi dalgasında. 5a/5b/5c bölünmesi korunur.
- **Sade dil**: Yabancı kısaltma/jargon önce gelmez. Önce sade Türkçe + ne işe
  yaradığı + somut örnek; sonra parantez içinde teknik adı.
- **Admin panellerinde jargon yasak**: DAU/WAU/MRR/Tenant/Descending açıklamasız
  geçemez. Sayfa başına mini sözlük + metrik yanına ⓘ tooltip.
- **Section panel standardı**: Her bölüm `_macros/section_panel.html` (veya
  Next.js `<SectionPanel>`) içine sarılır — beyaz panel + renkli üst şerit +
  her zaman görünür açıklama. Çıplak h2+grid yasak.
- **Kullanıcı şifrelerine asla dokunma**: Gerçek hesapların password_hash/locked_until/
  failed_login_count alanları test için sıfırlanmaz; geçici test user oluştur.
- **Riskli sprint'ler**: auth/notification/external API/migration sprint'leri
  birleştirmeden göster, onay bekle.
- **Mobil hazır**: PWA terk edildi; Next.js + shadcn/ui + BFF cookie ile app-like UX.
- **Windows dev**: WatchFiles reload güvenilmez; port 8081 kullan; `taskkill //IM`
  yasak — PID ile kill.
- **Git/commit**: Kullanıcı açıkça istemeden commit oluşturma. Riskli ops
  (push --force, reset --hard, vs.) onaysız asla.

## Dalga sırası

| Dalga | Kapsam | Durum |
|---|---|---|
| **D0** | Aşama 0 envanter/contract/risk | ✅ Bitti |
| **D1** | `/me/account` auth foundation | ✅ Bitti |
| **D2** | Öğrenci paneli (`/student/*`) | ✅ Bitti |
| **D3** | Öğretmen paneli (`/teacher/*`) | ✅ **Tamamlandı 2026-05-19** |
| **D4** | Kurum Yöneticisi (institution admin) | ✅ **Tamamlandı 2026-05-19 (P1-P8)** |
| **D5** | Veli (`/parent/*`) | ✅ **Tamamlandı 2026-05-19 (P1-P6)** |
| **D6** | Süper Admin (`/admin/*`) | ✅ **TAMAMLANDI 2026-05-20** (P1-P6 + P7 Ticari Pano a-d + Güvenlik Kamarası G1-G4 + Caddy `/admin/*` → Next.js) |
| **D7** | Auth / güvenlik (`/login`, `/signup`, `/password`, 2FA) | ✅ **TAMAMLANDI 2026-05-20** (P1 parite+BFF güvenlik · P2 şifre sıfırlama · P3 signup+email doğrulama · P4 2FA/TOTP · P5 oturum yönetimi+public teklif) |

## Dalga 3 — son durumu (2026-05-19)

**Tamamlanan paketler:**

- **3.5a (1-8)** — Haftalık plan UX parite: 2-sütun, açılır günler, dnd-kit,
  inline edit dialog, sidebar invalidate, ders-bazlı sort, talep modalı SELECT
- **3.5b** — Header rozetleri/butonları (Yenile/Sınıf Yükselt/Hedefler/Tekrar/DNA/Odak),
  anchor, sinema-koltuk grid
- **3.5c** — Jinja read-receipt protokolü resmileşti; 5c gerçek içerik
  (promote/goals/review/dna/focus)
- **3.5d.2** — Students pasif row dim + library tonlu nav + /me redirect +
  password change kartı + settings güvenlik sekmesi
- **3.5d.3** — Book-set bulk apply endpoint + set→öğrenci agregasyon (student_count,
  grade_distribution, assigned_students) + Tabs (Set'ten uygula)
- **3.5d.4** — Öğrenci kitap envanteri: subject_id/name/publisher/sections eklendi;
  ders gruplama + 8-renk pastel ton (subject_id hash) + progress bar +
  3 KPI chip + `<details>` ünite breakdown + URL `?subject_id=` filter
- **3.5d.5** — `/teacher/library` redesign: overall KPI, chip-bar (Ders/Tip/Sınıf)
  her satır + sayım, ders bazlı bölümleme, tip-renkli kart şerit, klavye `/` + `Esc`
- **3.5d.6** — Müfredat farkındalığı: SubjectRef'e grade alanları,
  TargetGradePicker (3-radyo + ince ayar) book-create-form'da, optgroup ders
  dropdown, library'de müfredat chip-bar, book-set kitap-ekle dialog yeniden
  yapı (arama+tip+gruplama)
- **3.5d.7** — Curriculum hard-filter bug fix: kitap listesi de
  `subjectById[item].curriculum_model === effectiveCurriculum`'a göre frontend
  filtrelenir. "Tümü" müfredat chip'i kaldırıldı. Default = en dolu müfredat.
- **3.5d.8** — BookSet sınıf farkındalığı: migration `n5o7r0s1r99l` ile 3 alan
  (target_grade_min/max/graduate) + label_tr; create/patch validation;
  TargetGradePicker yeniden kullanım; set list kart badge; set detail edit
  formda picker; student-books-panel "Set'ten uygula" iki-grup (Önerilen / Diğer
  sınıflar) + uyumsuz seçimde AlertTriangle uyarı banner

**Asılı bırakılanlar (kullanıcının kararıyla):**
- **Jinja `/teacher/*` route emekliliği erteleme** — Caddy `/teacher/*` zaten
  Next.js'e yönlendiriyor; 14 Jinja teacher_*.py dosyası + 27 HTML şablonu dead
  code halinde **yayında bekliyor**. Silinmiyor (kullanıcı 2026-05-19 kararı:
  "Jinja'ya dokunma, kalsın").
- **Jinja `/institution/*` route emekliliği erteleme** — Caddy
  `/institution/*` Next.js'e yönlendiriyor (D4 P8, 2026-05-19);
  `app/routes/institution.py` (1153 satır, 28 route) + 17 HTML şablonu
  (`app/templates/institution/*.html`) dead-code halinde **yayında bekliyor**.
  Silinmiyor (aynı "Jinja'ya dokunma, kalsın" kararı).
- **Jinja `/parent/*` route emekliliği erteleme** — Caddy `/parent/*` +
  `/legal/kvkk-veli` Next.js'e yönlendiriyor (D5 P6, 2026-05-19);
  `app/routes/parent.py` (767 satır, 15 route) + 10 HTML şablonu (parent/*
  + legal/kvkk_parent.html) dead-code halinde **yayında bekliyor**. Bildirim
  altyapısı (producer/dispatcher/cron_jobs/whatsapp_webhook + 8 email
  template) DOKUNULMAMIŞ — server-side e-posta/WA gönderim için gerekli.
- **Jinja `/admin/*` route emekliliği erteleme** — Caddy `/admin` + `/admin/*`
  Next.js'e yönlendiriyor (D6 Caddy adımı, 2026-05-20); `app/routes/admin.py`
  (6154 satır, 133 endpoint) + 50 HTML şablonu (`app/templates/admin/*.html`)
  dead-code halinde **yayında bekliyor**. Silinmiyor (aynı "Jinja'ya dokunma,
  kalsın" kararı). `/api/v2/admin/*` zaten FastAPI'de (BFF backend). 27 admin
  servisi (tenant_health/revenue_panel/campaigns/offers/security_monitor/
  alarm_engine/abuse_detection/tenant_activity vb.) API v2 endpoint'leri
  tarafından AYNEN kullanılıyor — DOKUNULMADI.

## Sayım — backend smoke testleri

- `test_api_v2_teacher_read.py` — 12 senaryo
- `test_api_v2_teacher_students.py` — 14
- `test_api_v2_teacher_library.py` — 24 (18 senaryo, 24 alt-check)
- `test_api_v2_teacher_weekly_plan.py` — 14
- `test_api_v2_teacher_pages_5c.py` — 19
- `test_api_v2_teacher_pages_5d1.py` — 10
- `test_api_v2_teacher_pages_5d2.py` — 10
- `test_api_v2_teacher_book_set_apply.py` — 12
- `test_api_v2_teacher_book_set_grade.py` — 10
- `test_api_v2_teacher_program.py` — program endpoints
- `test_api_v2_teacher_insights_settings.py` — settings/cron/email
- `test_api_v2_teacher_requests.py` — talep yanıtlama
- `test_api_v2_teacher_academic_csv.py` — academic years + CSV
- `test_api_v2_institution.py` — D4 P1 (18 senaryo)
- `test_api_v2_institution_p2.py` — D4 P2 (19 senaryo)
- `test_api_v2_institution_p3.py` — D4 P3 (18 senaryo)
- `test_api_v2_parent.py` — D5 P1 (20 senaryo)
- `test_api_v2_parent_invitation.py` — D5 P2 (17 senaryo)
- `test_api_v2_admin.py` — D6 P1 (13 senaryo)
- `test_api_v2_admin_institutions.py` — D6 P2 (23 senaryo)
- `test_api_v2_admin_users.py` — D6 P3 (25 senaryo)
- `test_api_v2_admin_audit_kvkk.py` — D6 P4 (18 senaryo)
- `test_api_v2_admin_usage_quota_flags.py` — D6 P5 (21 senaryo)
- `test_api_v2_admin_feature_catalog.py` — D6 P6 (25 senaryo)
- `test_api_v2_admin_revenue_analytics.py` — D6 P7a (9 senaryo)
- `test_api_v2_admin_revenue_360.py` — D6 P7b (18 senaryo)
- `test_api_v2_admin_revenue_offers.py` — D6 P7c (19 senaryo)
- `test_api_v2_admin_revenue_campaigns.py` — D6 P7d (17 senaryo)
- `test_api_v2_admin_revenue_dashboard.py` — D6 G1 (11 senaryo)
- `test_api_v2_admin_security_overview.py` — D6 G2a (14 senaryo)
- `test_api_v2_admin_security_activity.py` — D6 G2b (15 senaryo)
- `test_api_v2_admin_security_sessions.py` — D6 G3 (17 senaryo)
- `test_api_v2_admin_security_alarms_abuse.py` — D6 G4 (21 senaryo)
- `test_api_v2_auth_p1.py` — D7 P1 (10 senaryo: ActiveSession/heartbeat/terminate/
  SuspiciousIp/turnstile/sid/must_change)
- `test_api_v2_auth_p2.py` — D7 P2 (11 senaryo: forgot/reset token akışı +
  enumeration + tek-kullanım + breach/policy + login doğrulama)
- `test_api_v2_auth_p3.py` — D7 P3 (13 senaryo: signup teacher/invite + email
  doğrulama + invite info + kuota + auto-login)
- `test_api_v2_auth_p4.py` — D7 P4 (14 senaryo: 2FA setup/enable/disable +
  login challenge + TOTP/yedek kod verify + rol kısıtı)
- `test_api_v2_auth_p5.py` — D7 P5 (12 senaryo: /me/sessions list+revoke +
  self-terminate + public offers view/accept/decline)
- `test_api_v2_institution_compliance.py` — Program Uyum Panosu (10 senaryo:
  kurum rate + doğruluk + öğretmen kırılımı + boş program + dikkat + trend)
- `test_api_v2_institution_action_center.py` — KP1 Müdahale Merkezi (8 senaryo)
- `test_api_v2_institution_scorecard.py` — KP2 Öğretmen Etkililik Karnesi (7 senaryo)
- `test_api_v2_institution_parent_trust.py` — KP3 Veli Güveni (9 senaryo)
- `test_api_v2_teacher_exams.py` — KP4a Deneme sonucu CRUD (16 senaryo: net
  hesap LGS/YKS + ders kırılımı + sahiplik 404 + summary/trend + sil)
- `test_api_v2_institution_academic.py` — KP4b Kurum Akademik Çıktı (13 senaryo:
  kapsama + net başarı % normalize + section/öğretmen kırılımı + gelişen/gerileyen)

**Toplam: ~205+ senaryo, hepsi yeşil** (2026-05-19 itibarıyla).

**D4 (Kurum Yöneticisi) frontend kapsamı (P7 sonu):** `/(institution)/*`
altında 19 route — Panel + 4 kişi (teachers list/detay/roster/davet) + 6
analiz (at-risk/cohorts/heatmap/burnout/goals/admin-digest list+detay) + 3
üyelik (subscription/quota/usage) + 3 print (at-risk/heatmap/cohorts).
Sidebar'da artık disabled item yok.

## Önemli mimari kararlar

- **MutationResponse.invalidate**: Backend her mutation'da etkilenen queryKey
  prefix'lerini liste olarak döner (`teacher:{id}:students:{sid}:books` gibi).
  Frontend `applyInvalidate(qc, keys)` ile TanStack Query'yi yeniden bayatlar.
  R-006 sözleşmesi.
- **Strangler Fig**: Caddy `/teacher/*` → Next.js (live); `/admin/*`, `/parent/*`,
  `/student/*` (kısmi) hâlâ Jinja'da. `/api/v2/*` Next.js BFF tarafından
  cookie-auth ile tüketilir.
- **Subject curriculum_model**: Subject tablosunda aynı ders adı (örn. "Matematik")
  farklı müfredat modellerinde (LGS / MAARIF_LISE / KLASIK_LISE) ayrı kayıt.
  UniqueConstraint (teacher_id, name, curriculum_model). UI'da optgroup ile
  gruplandırılır + müfredat chip-bar ile filtrelenir.
- **BookSet target_grade**: 3.5d.8'de eklenen alanlar (Book modeliyle aynı
  semantik). Set "Tüm seviyeler" sayılır = üç alan null/false. Bulk assign
  ENGEL DEĞİL — sadece uyarı.
- **Tonal sistem**: Subject_id hash → 8 pastel ton (indigo/emerald/amber/rose/
  violet/cyan/fuchsia/sky). Book tipi için 5 sabit ton. `border-l-4 +
  ring-1 ring-inset {tone}/10` deseni — açık background yok, dark mode uyumlu.

## Test komutları

```bash
# Backend smoke (tek dosya)
cd D:/LGS-Program && PYTHONPATH=. python scripts/test_api_v2_teacher_book_set_grade.py

# Frontend
cd D:/LGS-Program/web && pnpm tsc --noEmit
cd D:/LGS-Program/web && pnpm eslint . --max-warnings 0
cd D:/LGS-Program/web && pnpm build

# Tenant izolasyon regresyon
cd D:/LGS-Program && PYTHONPATH=. python scripts/test_tenant_isolation.py
```

## Dalga 4 — son durumu (2026-05-19)

**Tamamlanan paketler:**

- **D4 Aşama 1+2+3** — KURAL 1 protokolü: `/institution` link haritası (13 menü
  linki) + 30 endpoint + 17 template tam okundu; Files-Read Receipt + 50 ayrı
  eylem listesi + 17 satırlık parite tablosu üretildi; kullanıcı onayı alındı.
- **D4 Paket 1 — Backend foundation**:
  - `app/routes/api_v2/schemas/institution.py` (16 model)
  - `app/routes/api_v2/institution.py` (10 endpoint: dashboard / teachers list /
    POST teacher + auto-password / deactivate / activate / pause-alerts /
    resume-alerts / teacher card / roster + filters / goals summary)
  - `_require_institution_admin` dep (role + institution_id guard)
  - `scripts/test_api_v2_institution.py` — **18/18 yeşil**
- **D4 Paket 2 — Backend ileri özellikler**:
  - Şemalar: 17 yeni model (invitations + heatmap + risk + burnout + cohorts + WoW)
  - 7 yeni endpoint: `/invitations` GET/POST + revoke, `/activity-heatmap`,
    `/at-risk`, `/burnout`, `/cohorts` (4 sekme; sadece aktif sekme hesaplanır)
  - Privacy: `at-risk`/`burnout` öğretmen-öğrenci eşlemesi gösterir ama
    detay linki yok; mute durumu rozet olarak
  - Quota guard: invitation create'te `check_quota_for_create` ile öğretmen
    kuotası kontrol edilir (aşımda 403)
  - `scripts/test_api_v2_institution_p2.py` — **19/19 yeşil**
- **D4 Paket 3 — Backend abonelik & ticari**:
  - Şemalar: 16 yeni model (Subscription / Quota / Usage / AdminDigest)
  - 10 yeni endpoint: `/subscription` GET + 4 POST action
    (switch-academic-year / pause / resume / guarantee/enable),
    `/quota`, `/usage?days=N`, `/admin-digest` GET + send-now + detail
  - Yaz penceresi guard: `is_summer_window()` False → 409 summer_window_required
  - Idempotent: switch/resume/guarantee zaten aktifse 200 + no-op
  - Cross-tenant digest detail 404 — `institution_id` filtreli sorgu
  - `scripts/test_api_v2_institution_p3.py` — **18/18 yeşil**
- **D4 Paket 4 — Frontend foundation**:
  - `web/lib/types/institution.ts` (15 model) + `lib/api/institution.ts`
    (fetcher + queryKeys) + `lib/hooks/use-institution-mutations.ts`
    (create/deactivate/activate/pause/resume)
  - `app/(institution)/layout.tsx` — auth guard + redirect
  - `components/institution/institution-shell.tsx` — sticky sidebar (lg+) +
    mobil drawer; 13 menü linki 3 grup (Kişiler/Analiz/Üyelik); P5-P7
    item'lar "yakında" disabled görünür
  - 5 sayfa + client component'lar:
    - `/institution` Dashboard (KPI grid + risk/inactive callout + öğretmen tablosu)
    - `/institution/teachers` list + NewTeacherDialog (tek seferlik temp_password
      başarı kartı + "Kopyala") + TeacherRowActions (DropdownMenu + confirm dialog)
    - `/institution/teachers/[id]` kart (gizlilik banner, öğrenci listesi
      detay linki YOK)
    - `/institution/roster` filter form + URL state (geri/ileri navigasyon parite)
    - `/institution/goals` 3 KPI + hedefsiz uyarı + bilgi notu
  - `invalidate.ts` — `institution:{id}` → `institution:me` prefix mapping eklendi
  - **Birebir Jinja parite**: tüm form alanları, buton metinleri, onay
    diyaloğu cümleleri, gizlilik notları, rozet ayrımları (auto/manuel pause),
    renk eşikleri (≥70 emerald / ≥40 amber / <40 rose), pasif satır
    silikleştirmesi
  - **Verify**: tsc ✅ · eslint ✅ · build ✅ (5 yeni route)
- **D4 Paket 5 — Frontend risk & analytics**:
  - `recharts` bağımlılığı eklendi (Next.js standart bar chart)
  - Lib: `lib/types/institution.ts` 6 yeni şema (At-risk/Burnout/Heatmap/Cohort
    tüm tipler) + 4 fetcher + 4 queryKey
  - Paylaşılan: `heatmap-grid.tsx` (5-level emerald palette + 11px/8px),
    `level-badge.tsx` (RiskLevelBadge + BurnoutLevelBadge + PauseBadge +
    score color helper'ları), `cohort-bar-chart.tsx` (Recharts BarChart +
    custom Tooltip + Cell renkleri)
  - 4 görüntüleme sayfası:
    - `/institution/at-risk` — privacy banner + 3 count card (kritik/risk/dikkat)
      + tablo (öğrenci/öğretmen/seviye/risk puanı/indicator chip'leri); risk
      seviyesine göre satır arka planı + pause/mute rozetleri
    - `/institution/burnout` — risk skoru sıralı tablo + Seviye badge'leri +
      gizlilik notu
    - `/institution/activity-heatmap` — 4/12 hafta segmented buttons (URL state),
      bilgi banner (skor formülü + pasif tanımı), legend, GitHub-style grid
      + hover scale + native tooltip
    - `/institution/cohorts` — gizlilik notu + 3 WoW kartı (delta ↑↓ ok),
      4 sekme (border-bottom nav) + Recharts bar chart + tablo; tab-spesifik
      empty state
  - Backend ufak ekleme: `AtRiskRowItem.pause_reason` field (auto/manuel ayrımı için)
  - 3 print sayfası (`(print)` route group altında):
    - `/institution/at-risk/print` — A4 portrait, sayım kartları + risk tablosu
    - `/institution/activity-heatmap/print` — A4 landscape, heatmap grid table
    - `/institution/cohorts/print` — A4 landscape, 4 sekme 2x2 grid + WoW header
  - Sidebar: 4 disabled item aktif (Risk Paneli / Kohort / Aktivite / Tükenmişlik)
  - **Verify**: tsc ✅ · eslint ✅ · build ✅ (4 görüntüleme + 3 print = 7 yeni route)
- **D4 Paket 6 — Frontend davet & digest**:
  - `lib/types/institution.ts` — `AdminDigestPayload` detay tipi (totals,
    completion, at_risk, highlight, inactive_teachers, grade_cohorts)
  - `lib/api/institution.ts` — 3 yeni fetcher (invitations, admin-digest list,
    admin-digest detail) + 3 queryKey
  - `lib/hooks/use-institution-mutations.ts` — 3 yeni mutation hook:
    createInvitation (open/targeted) + revokeInvitation + sendAdminDigestNow
  - 3 yeni route:
    - `/institution/invitations` — güvenlik notu (violet) + tablo + 4 statü
      rozeti (pending/consumed/expired/revoked) + link copy + revoke confirm;
      "Yeni Davetiye" dialog (ad+email opsiyonel, "açık davetiye" varyantı)
    - `/institution/admin-digest` — otomatik gönderim notu (Pazartesi 12:00),
      "Şimdi Gönder" confirm dialog (force=True), 12 hafta arşiv tablo,
      4 send_status TR etiket (sent/log_only/failed/skipped_no_admin)
    - `/institution/admin-digest/[id]` — 4 KPI (öğretmen+pasif uyarı / öğrenci
      / tamamlama+delta+yön / risk+kritik) + Highlights (en iyi/en kötü sınıf)
      + pasif öğretmenler listesi (amber, +N daha) + sınıf kohort tablo +
      alıcı email listesi (collapsible)
  - Sidebar: 2 disabled item aktif (Davet, Haftalık Özet) — Üyelik grubu hâlâ
    P7 için disabled
  - **Verify**: tsc ✅ · eslint ✅ · build ✅ (3 yeni route)
- **D4 Paket 7 — Frontend abonelik & ticari**:
  - `lib/types/institution.ts` — 11 yeni tip (SubscriptionResponse / Status /
    GuaranteeEvaluation / QuotaResponse / QuotaInfoItem / PlanQuotaItem /
    UsageResponse / UsageAccount / Breakdown / DailyPoint / Event)
  - `lib/api/institution.ts` — 3 yeni fetcher + 3 queryKey
    (subscription / quota / usage(days))
  - `lib/hooks/use-institution-mutations.ts` — 4 abonelik aksiyon mutation
    (switchAcademicYear / pauseForSummer / resumeFromPause / enableGuarantee)
    + `summer_window_required` / `pause_not_allowed` errorTitle eşlemeleri
  - 3 yeni route:
    - `/institution/subscription` — kind badge'li durum kartı (period_end/
      pause_until/guarantee dahil 4 alanlı dl), akademik yıl promosyon kartı
      (`can_switch_to_academic_year`), yaz pause kartı (`can_pause` →
      PauseAction · `can_resume` → ResumeAction · değilse PauseHelpline ile
      "akademik yıl gerekli" veya "yaz penceresi gerekli" uyarısı), 60g garanti
      kartı (enable veya GuaranteeDetails: 60-gün ilerleme bar, eşik vs.
      mevcut tamamlama tabular, already_extended/triggered/note ayrımı);
      sidebar: Avantajlar (4-madde checklist) + Yardım (pricing / plans/me /
      destek email); 4 ayrı confirm dialog (Jinja onConfirm metinleri birebir)
    - `/institution/quota` — 3 quota kartı (is_at_limit=rose/is_warn=amber/
      normal=emerald progress bar) + has_override "size özel" badge
      (violet, override_note title) + is_unlimited "∞ sınırsız" durumu;
      plan karşılaştırma tablo (mevcut plan satır emerald + "sizin planınız"
      badge); 2 bilgi notu (sayım nasıl / limit dolarsa)
    - `/institution/usage` — 3 koşullu banner (hard_block / %80 warn /
      %100 overuse), ana bakiye kartı (used/allocated/+bonus/remaining +
      0-100 progress + scale 0%/N%/100%), tip kırılımı (her tip için
      kendi progress bar 0..100), 30 günlük Recharts bar chart
      (`usage-daily-bar-chart.tsx` indigo + custom tooltip), plan/birim
      maliyet stat'ları + 5 kind cost chip'i, son 50 event tablosu (ne zaman
      DD.MM HH:mm / etiketli kind / kredi mono / aktör)
  - Sidebar: 3 son disabled item aktif (Abonelik, Kredi Kullanımı, Limitler)
  - **Verify**: tsc ✅ · eslint ✅ · build ✅ (3 yeni route — toplam 19 route
    /(institution) grubu altında); backend smoke P3 18/18 + tenant 29/29
- Tenant izolasyon regresyon **29/29 yeşil** + tüm institution smoke (P1+P2+P3)
  **55/55 yeşil**

- **D4 Paket 8 — Caddy yönlendirme + tam regresyon**:
  - `deploy/Caddyfile`:
    - `@prints` istisna bloğu **kaldırıldı** (3 institution print path Next.js
      `(print)` route group altında P5'te yapılmıştı, hâlâ FastAPI'ye gidiyordu)
    - `/institution` + `/institution/*` reverse_proxy yorumları **açıldı**
      (öğretmen/öğrenci pattern'i ile aynı — `next:3000`)
    - Yorum metinleri P8 tarihiyle güncellendi
    - Stale "/student/week/print + weekly-report/print @prints'te" yorumu temizlendi
  - Caddy reload kullanıcının canlı ortamında: `docker compose exec proxy caddy
    reload --config /etc/caddy/Caddyfile`. <60 sn rollback (R-020).
  - Tam regresyon **otomatik** (84 senaryo geçti):
    - institution P1 18/18 · P2 19/19 · P3 18/18 · tenant_isolation 29/29 ✅
    - frontend tsc ✅ · eslint ✅ · build ✅ (18 institution route)
  - Manuel smoke (canlı ortam): admin login → 13 sidebar item tek tek
    açılıp doğrulanır — bu adım kullanıcının sorumluluğunda
  - Jinja `/institution/*` (28 route + 17 template) "asılı bırakılanlar"
    listesine eklendi (silinmez — kullanıcı kararı)

## Dalga 5 — son durumu (2026-05-19)

**Tamamlanan paketler:**

- **D5 Aşama 1+2** — KURAL 1: /parent envanteri (34 dosya, 10K+ satır)
  haritalandı; parent.py (767) + parent_view.py (334) + parent_invitation.py
  (159) + 10 template + parent.py model (358) tam okundu.
- **D5 Paket 1 — Backend API v2 foundation**:
  - `app/routes/api_v2/schemas/parent.py` (26 model)
  - `app/routes/api_v2/parent.py` (10 endpoint: dashboard / students[id] /
    students[id]/week / notifications / settings + 5 mutation:
    preferences / child-mute / WA start+verify+disable)
  - `_require_parent` dep (role kapısı + 403 role_required)
  - Privacy guard: assert_parent_can_view → 404 (sızıntı önleme)
  - OTP güvenliği: 60s cooldown / 10dk TTL / 5 max attempts /
    secrets.compare_digest
  - ParentSessionLog audit (preferences_updated / child_muted / whatsapp_*)
  - `scripts/test_api_v2_parent.py` — **20/20 yeşil**
- **D5 Paket 2 — Backend davet & unsubscribe (public)**:
  - 3 endpoint: GET invitation/{token}, POST invitation/{token}/accept,
    GET unsubscribe/{token}
  - Davet token: 4 hata durumu (not_found/expired/consumed/email_in_use)
  - Form validasyon: name>=3, password>=8, password_confirm match, kvkk_accept
  - can_register_parent_email: TEACHER/STUDENT email → 400 reddet
  - Mevcut PARENT → link ekle (şifre/ad değişmez, çoklu çocuk senaryosu)
  - Audit: invitation_accepted / invitation_added_link + login
  - JWT BFF cookie kuruldu (Jinja session yerine API v2 auth)
  - `scripts/test_api_v2_parent_invitation.py` — **17/17 yeşil**
- **D5 Paket 3 — Frontend foundation + dashboard + public sayfalar**:
  - `lib/types/parent.ts` (24 interface) + `lib/api/parent.ts` (7 fetcher) +
    `lib/hooks/use-parent-mutations.ts` (5 mutation + 15 error code label)
  - `(parent)/layout.tsx` auth guard
  - `parent-shell.tsx` — teal accent (#117A86) sticky header + mobile drawer
  - `(parent)/parent/page.tsx` — Dashboard çocuk kartları (warning_level
    border-l-4 + tonal bg + bugün/hafta/7g rate/istikrar)
  - `parent/invitation/[token]/page.tsx` — public form + 4 hata ekranı
  - `parent/unsubscribe/[token]/page.tsx` — public 3 durum
  - `legal/kvkk-veli/page.tsx` — KVKK aydınlatma 7 bölüm
- **D5 Paket 4 — Frontend: student detail & week**:
  - `parent/students/[id]/page.tsx` + client: 4 metrik + Projeksiyon (status
    pill) + Ders progress (hue rotation) + **Recharts 30g BarChart** +
    Öğretmen notları (teal left-border)
  - `parent/students/[id]/week/page.tsx` + client: gün accordion auto-expand
    dolu günler + subject tonal background + book_items detail
- **D5 Paket 5 — Frontend: notifications & settings**:
  - `parent/notifications/page.tsx` — 100 bildirim list, kind/channel/status
    badge'leri, empty state
  - `parent/settings/page.tsx` — 3 bölüm: Preferences (7 toggle + quiet hours)
    + Çocuk-başı mute (per-row badge + confirm dialog) + WhatsApp 3 durum
    (kapalı / kod bekleniyor / aktif) + DEV stub kod gösterimi
- **D5 Paket 6 — Caddy + tam regresyon + arşivleme**:
  - `deploy/Caddyfile`:
    - `/parent` + `/parent/*` reverse_proxy Next.js'e aç
    - `/legal/kvkk-veli` Next.js'e (generic /legal/* ÖNCE)
  - Tam regresyon (121/121 yeşil):
    - parent P1 20/20 · P2 17/17 · institution P1+P2+P3 55/55 · tenant 29/29
    - tsc ✅ · eslint ✅ · build ✅ (8 yeni parent route)
  - Jinja `/parent/*` (15 route + 10 template) "asılı bırakılanlar"a eklendi
- **Backend notification infra DOKUNULMAMIŞ**:
  - `app/services/notification_producer.py` + `notification_producers.py` +
    `notification_dispatcher.py` + `event_triggers.py` + `cron_jobs.py` +
    `whatsapp.py` + `whatsapp_webhook.py` + 8 email Jinja template — hepsi
    server-side e-posta/WA gönderim için gerekli, korundu.

## Dalga 6 — son durumu (2026-05-19)

**Envanter (Aşama 1+2 admin.py için):**
- Jinja `app/routes/admin.py` 6154 satır, **133 endpoint** tek monolit
- 50 template (`app/templates/admin/*.html` — 12.778 satır)
- 27 service (10.721 satır) — tenant_health, audit, revenue_panel,
  campaigns, offers, dunning, action_center, institution_360, feature_*,
  security_monitor, alarm_engine, abuse_detection, abuse_remediation,
  data_integrity, account_history, impersonation, error_capture, vb.
- 24 admin-spesifik model (3.086 satır) — Owner-pattern (institution|user)
  6 ana modelde (Invoice, Campaign, CRM, HealthScoreSnapshot,
  PlanChangeHistory, CreditAccount)
- **Owner-pattern KRİTİK**: Bağımsız öğretmen (TEACHER + institution_id=NULL)
  = ticari panoda birinci sınıf tenant
- `/api/v2/admin/*` SIFIR — tamamı sıfırdan inşa edilecek

**14 paket yol haritası onaylandı** (kullanıcı 2026-05-19):
- P1-P5: Çekirdek Yönetim
- P6-P10: Ticari Pano (Owner-pattern korunarak)
- P11-P12: Feature Catalog
- P13-P14: Güvenlik Kamarası + Caddy/regresyon

**Tamamlanan paketler:**

- **D6 Paket 1 — Backend foundation + Dashboard**:
  - `app/routes/api_v2/schemas/admin.py` (12 Pydantic model: counts,
    health summary/assessment/indicator, independent teacher activity,
    audit item, dashboard response)
  - `app/routes/api_v2/admin.py` — `_require_super_admin` dep +
    `GET /api/v2/admin/dashboard`:
    - 8 alanlı counts (Jinja birebir)
    - bulk_health_assessment + churn_summary + top-3 unhealthy
    - _independent_teacher_activity_payload (4 bant: healthy/watch/risk/
      critical login heuristiği — Jinja `_independent_teacher_activity()`
      ile birebir aynı algoritma)
    - recent_audits (son 10 + action_label + via_admin impersonation marker)
    - failed_logins_24h (LOGIN_FAILED+LOGIN_LOCKED son 24h sayım)
  - `web/lib/types/admin.ts` (11 interface) + `lib/api/admin.ts`
    (adminKeys + getAdminDashboard fetcher)
  - `web/app/(admin)/layout.tsx` — auth guard + redirect (5 rol mapping)
  - `web/components/admin/admin-shell.tsx` — sticky sidebar (lg+) + mobile
    drawer; 7 nav grup iskeleti (Panel + Kuruluşlar + Denetim + Limitler &
    Kullanım + Vitrin + Ticari Pano + Güvenlik Kamarası); P1 sonrası
    item'lar "yakında" disabled görünür; slate-900 brand header + amber
    "Süper" rozeti
  - `web/app/(admin)/admin/page.tsx` + `admin-dashboard-client.tsx` —
    6 bölüm: Hesap Özeti (4 OverviewCard, indigo/violet/sky/amber tonal),
    Failed Logins banner (>10), Commercial Shortcuts grid (7 kısayol — P6+),
    System Shortcuts grid (4 kısayol — P11+), Müşteri Sağlığı 2 sütun
    (kurum + bağımsız öğretmen 4-band stat + top-3 risk), Recent Audits
    table (action_class renkli + via_admin pill)
  - `scripts/test_api_v2_admin.py` — **13/13 yeşil** (happy + 4 shape check
    + 4 role guard + 1 anonim)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (1 yeni route `/admin`)

- **D6 Paket 2 — Backend institutions + account-history (Owner-pattern)**:
  - `app/routes/api_v2/schemas/admin.py` — 18 yeni Pydantic model (institutions
    list/detail/CRUD + account-history poly + backup summary)
  - `app/routes/api_v2/admin.py` — 11 yeni endpoint:
    - `GET /institutions` (sort=health/name/created + filter_level=unhealthy/critical)
    - `POST /institutions` (slug auto-gen + çakışma kontrolü 409)
    - `GET /institutions/{id}` (sağlık + admin/teacher listeleri)
    - `POST /institutions/{id}` (edit — before/after diff audit)
    - `POST /institutions/{id}/delete` (cascade: User.institution_id SET NULL)
    - `GET /institutions/{id}/backup` (counts + size_bytes summary)
    - `GET /institutions/{id}/backup.json` (raw JSON download, password REDACTED)
    - `GET /account-history/{owner_type}/{owner_id}` (poly institution|user;
      years 1-10, include_archived flag)
    - `POST /account-history/archive` (tek kayıt — plan|invoice)
    - `POST /account-history/unarchive` (geri al)
    - `POST /account-history/bulk-archive` (X yıldan eski tümü)
  - `_slugify` helper (Türkçe karakter destekli, Jinja birebir)
  - Tüm mutation'larda audit (INSTITUTION_CREATE/UPDATE/DELETE +
    USER_UPDATE for archive ops)
- **D6 Paket 2 — Frontend institutions UI + account-history**:
  - `lib/types/admin.ts` — 18 yeni interface
  - `lib/api/admin.ts` — 5 fetcher + adminKeys.institutions/institution/
    backup/accountHistory + adminInstitutionBackupDownloadUrl
  - `lib/hooks/use-admin-mutations.ts` (yeni) — 6 mutation (create/edit/
    delete + archive/unarchive/bulk-archive) + 5 error code label
  - `(admin)/admin/institutions/page.tsx` + `admin-institutions-client.tsx`:
    - 4 health KPI rozet (emerald/yellow/amber/rose)
    - Sort + Filter chip-bar (URL-based navigation)
    - Tablo: sağlık badge + ad/slug + plan + öğr/öğr sayım + 7g aktivite
      progress bars (indigo/emerald) + durum + detay link
    - "Yeni Kurum" Dialog (name+slug+contact+plan, slug auto-gen hint)
  - `(admin)/admin/institutions/[id]/page.tsx` + detail client:
    - Header (status + plan rozetleri)
    - Health card (5xl emoji + score + 4 stat + indicators)
    - 2 sütun: edit form (name/email/plan/is_active) / sayım+backup+danger
    - Backup card (violet, download .json)
    - Danger zone (rose, delete confirm dialog)
    - Admin + teacher list 2 sütun
  - `account-history-client.tsx` (paylaşımlı poly):
    - Help details collapsible
    - 4 KPI (gösterilen/arşivli/eski/pencere başı)
    - Filter form (years selector + include_archived toggle)
    - Bulk archive button + confirm dialog (older_count > 0 ise)
    - Event timeline (her event: tarih + badge + record_type#id + arşivli rozet
      + title + subtitle + archive_note + archive/unarchive button)
  - 2 sayfa: `/admin/institutions/[id]/account-history` (institution)
    ve `/admin/users/[id]/account-history` (user, Owner-pattern)
  - Sidebar: Kurumlar item aktive (Bağımsız Öğretmenler/Kullanıcılar hâlâ
    disabled — P3'te aktive)
  - `scripts/test_api_v2_admin_institutions.py` — **23/23 yeşil**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)

- **D6 Paket 3 — Backend users + impersonate (1445 satır okundu)**:
  - `app/routes/api_v2/schemas/admin.py` — 12 yeni Pydantic model (users CRUD
    + impersonate + independent teachers response)
  - `app/routes/api_v2/admin.py` — 10 yeni endpoint:
    - `GET /users` (role + institution_id + q filter, 500 cap + truncated flag)
    - `POST /users` (slug değil — email kontrolü 409; sistem rol-bazlı güçlü
      geçici şifre + must_change=True; INSTITUTION_ADMIN için kurum zorunlu)
    - `GET /users/{id}` (detail + institutions + recent_audits + is_self flag)
    - `POST /users/{id}` (edit — email çakışma 409 + before/after diff +
      USER_DEACTIVATE audit)
    - `POST /users/{id}/reset-password` (temp_password issued + must_change +
      kilit aç + audit)
    - `POST /users/{id}/change-role` (kendi rolü → 403 + INSTITUTION_ADMIN
      kurum zorunlu)
    - `POST /users/{id}/delete` (kendi hesabı → 403 + CASCADE)
    - `POST /users/{id}/impersonate` (reason 10-200 char + 3 kısıt: self/
      super_admin/inactive yasak + idempotent + SessionMiddleware target set)
    - `POST /impersonate/end` (auth zorunlu DEĞİL — impersonator_id session'dan)
    - `GET /independent-teachers` (login-bazlı 4-band heuristik P1 ile aynı)
  - `auth_security.generate_strong_password(role)` (14/12/10/8 rol-bazlı uzunluk)
  - `impersonation.validate_reason + start_session + end_session + 30dk TTL`
- **D6 Paket 3 — Frontend users UI**:
  - `lib/types/admin.ts` — 14 yeni interface (AdminUserListItem + Create/Edit/
    ChangeRole/Detail/Mutation + Impersonate + IndependentTeachers)
  - `lib/api/admin.ts` — 3 fetcher (getAdminUsers + getAdminUser +
    getAdminIndependentTeachers) + adminKeys.users/user/independentTeachers
  - `lib/hooks/use-admin-mutations.ts` — 7 mutation hook (Create + Edit +
    ResetPassword + ChangeRole + Delete + Impersonate + EndImpersonation) +
    14 yeni error code label
  - `(admin)/admin/users/page.tsx` + `admin-users-client.tsx`:
    - URL-based filter form (q + role + institution)
    - Tablo: ad/email/rol-badge (5 renk)/kurum/son giriş/kilit-pasif rozet
    - Yeni Kullanıcı Dialog (5 rol opt + kurum select + 🔐 güvenlik notu)
    - `TempPasswordDialog` (re-usable, "Kopyala" butonu + DOM clipboard API)
  - `(admin)/admin/users/[id]/page.tsx` + `admin-user-detail-client.tsx`:
    - Header (5 renk rol badge + kilit/pasif rozet + hesap hareketleri buton
      teacher/admin/super_admin için)
    - 2 sütun: EditUserForm + (SecurityCard + ChangeRoleCard + ImpersonateCard
      + DangerZone)
    - SecurityCard: 5 alan dl + Reset şifre confirm dialog → TempPasswordDialog
    - ChangeRoleCard: rol + kurum dropdown + audit onay dialog
    - ImpersonateCard: gerekçe textarea (min-10) + confirm dialog + redirect
      window.location.href (session set sonrası Jinja path'e)
    - DangerZone: kullanıcıyı sil confirm + audit
    - Self mode: yukarıdaki kartlar gizli + amber "/me/account kullan" notu
    - Recent activity tablosu (son 10 audit)
  - `(admin)/admin/independent-teachers/page.tsx` + client:
    - 4 BandKpi rozet (emerald/yellow/amber/rose, summary'den)
    - Tablo: band-pill + ad/email/son giriş label + detay link
  - Sidebar: Kullanıcılar + Bağımsız Öğretmenler item'ları aktive (P2-P3 kapandı)
  - `scripts/test_api_v2_admin_users.py` — **25/25 yeşil** (list/filter/search
    + 5 mutation × 3 path + 5 impersonate guard + 2 role/anon guard)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)
- **D6 P1+P2+P3 tam regresyon: 182/182 yeşil**:
  - admin P1 13 + P2 23 + P3 25 = 61
  - parent P1 20 + P2 17 = 37
  - institution P1 18 + P2 19 + P3 18 = 55
  - tenant isolation 29

- **D6 Paket 4 — Backend audit + KVKK + system-health + announcements (1895 satır okundu)**:
  - `app/routes/api_v2/schemas/admin.py` — 18 yeni Pydantic model
  - `app/routes/api_v2/admin.py` — 8 yeni endpoint:
    - `GET /audit` (50/sayfa pagination + 4 filter: action/actor_id/start_date/
      end_date inclusive + before/after diff parse + via_admin map)
    - `GET /system-health` (3 alt-bileşen: crons/dispatcher/database +
      overall_health en kötü; cron warn 25h/crit 48h günlük + 8d haftalık;
      dispatcher 100/6h warn + 500/24h crit; DB 500MB/1GB)
    - `GET /announcements` (son 50 + severities + audiences enum)
    - `POST /announcements` (severity + audience + starts_at/ends_at +
      dismissible + 60s cache invalidate)
    - `POST /announcements/{id}/delete` (audit + cache invalidate)
    - `GET /kvkk` (summary 5 status + pending_rows + recent_rows +
      DATA_INVENTORY 10+ kayıt)
    - `POST /kvkk/requests/{id}/apply` (apply_deletion: anonimize
      email=anonymized-{id}@kvkk.local, password_hash="", is_active=False +
      USER_DELETE audit; export tipi → 400 only_delete_can_be_applied)
    - `POST /kvkk/requests/{id}/reject` (status=REJECTED + admin_note 500 char)
- **D6 Paket 4 — Frontend**:
  - `lib/types/admin.ts` — 18 yeni interface (Audit + SystemHealth + Announcements
    + Kvkk)
  - `lib/api/admin.ts` — 4 fetcher (getAdminAudit/SystemHealth/Announcements/
    Kvkk) + 4 queryKey (audit/systemHealth/announcements/kvkk)
  - `lib/hooks/use-admin-mutations.ts` — 4 mutation hook (CreateAnnouncement +
    DeleteAnnouncement + KvkkApply + KvkkReject) + 6 yeni error code label
  - `(admin)/admin/audit/page.tsx` + `admin-audit-client.tsx`:
    - 4 filter form (action select + actor_id input + start/end date)
    - Hızlı kısayollar (24h / 7g / 30g)
    - Pagination 50/sayfa (← Önceki / N/M / Sonraki →)
    - Tablo: zaman + olay (renkli + label) + aktör (link + via_admin pill) +
      email_attempted + hedef (link to user/inst detail) + IP + detay
      (before/after diff yan yana JSON)
  - `(admin)/admin/system-health/page.tsx` + client:
    - Overall status banner (3 renk: ok/warn/crit + icon)
    - Cron table (job_key + schedule + son çalıştırma + status + health badge
      5 durum: ok/warn/crit/never/disabled)
    - Dispatcher kartı (queued + failed + oldest age + 3 health durumu)
    - Database kartı (file size + table counts + 500MB/1GB eşikleri)
  - `(admin)/admin/announcements/page.tsx` + client:
    - Create form (title + message + severity dropdown + audience dropdown +
      starts/ends datetime-local + dismissible checkbox)
    - Son 50 tablo (severity badge 3 renk + audience + yayın aralığı +
      yayında durumu + sil confirm dialog)
  - `(admin)/admin/kvkk/page.tsx` + client:
    - 5 durum sayım kartı (total + processing + pending + completed +
      cancelled/rejected)
    - Bekleyen talepler tablosu (kind label + hesap + tarihler + sebep +
      Hemen Uygula confirm + Reddet not'lu confirm)
    - Sistem veri envanteri tablosu (DATA_INVENTORY: tablo + PII + saklama +
      hukuki temel + amaç)
    - Son 20 talep özet tablosu (status badge 5 renk)
  - Sidebar: 4 Denetim item'ı aktive (Audit Log + KVKK + Sistem Sağlığı + Duyurular)
  - `scripts/test_api_v2_admin_audit_kvkk.py` — **18/18 yeşil**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)
- **D6 P1+P2+P3+P4 tam regresyon: 200/200 yeşil** (admin 79 + parent 37 +
  institution 55 + tenant 29)

- **D6 Paket 5 — Backend usage + quota + feature-flags (1469 satır okundu)**:
  - `app/routes/api_v2/schemas/admin.py` — 22 yeni Pydantic model
  - `app/routes/api_v2/admin.py` — 11 yeni endpoint:
    - `GET /usage` (owner-pattern 2 grup: kurumlar + bağımsız öğretmenler,
      CreditAccount usage_pct sıralı + totals + kind_costs)
    - `POST /usage/institution/{id}/hard-block` (sadece kurum, toggle)
    - `POST /usage/{owner_type}/{id}/bonus` (1-100000, kurum|user)
    - `GET /quota` (kurum × quota_key tablosu + plan defaults)
    - `POST /quota/{id}/override` (-1/0/N validation)
    - `POST /quota/overrides/{id}/delete`
    - `GET /feature-flags` (all_flags_for_admin + override sayım)
    - `GET /feature-flags/{id}` (override liste + available_institutions)
    - `POST /feature-flags/{id}/toggle` (global + 60s cache invalidate)
    - `POST /feature-flags/{id}/overrides` (set_override + cache invalidate)
    - `POST /feature-flags/overrides/{id}/delete`
- **D6 Paket 5 — Frontend**:
  - `lib/types/admin.ts` — 22 yeni interface (Usage + Quota + FeatureFlag)
  - `lib/api/admin.ts` — 4 fetcher + 4 queryKey
  - `lib/hooks/use-admin-mutations.ts` — 6 mutation hook (HardBlockToggle +
    AddBonus + SetQuotaOverride + RemoveQuotaOverride + ToggleFeatureFlag +
    AddFeatureFlagOverride + RemoveFeatureFlagOverride) + 6 error code label
  - `(admin)/admin/usage/page.tsx` + client:
    - 4 özet kart + 2 sekme (kurumlar/bağımsız) + UsageBar (3-renk) +
      hard-block confirm dialog (sadece kurum) + bonus dialog (her ikisi)
  - `(admin)/admin/quota/page.tsx` + client:
    - Kurum × quota_key tablosu (current/limit + progress + özel badge) +
      "Özel Limit" dialog (-1/0/N hint) + plan default tablosu
  - `(admin)/admin/feature-flags/page.tsx` + client:
    - Tablo (key + açıklama + global toggle confirm + override sayım)
  - `(admin)/admin/feature-flags/[id]/page.tsx` + client:
    - Global toggle kartı + override tablosu (kaldır confirm) + override
      ekleme formu (kurum + açık/kapalı + not)
  - Sidebar: 3 "Limitler & Kullanım" item'ı aktive
  - `scripts/test_api_v2_admin_usage_quota_flags.py` — **21/21 yeşil**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)
- **D6 P1-P5 tam regresyon: 221/221 yeşil** (admin 100 + parent 37 +
  institution 55 + tenant 29)
- **D6 Paket 6 — Feature Catalog (Vitrin Kartları)**:
  - KURAL 1: 17 endpoint (admin.py:1847-2800) + 4 model + 8 servis
    (feature_catalog/feature_discovery/feature_scoring/experiments/
    curator_dashboard/telemetry/bandit/diversity + landing_strategies/
    mockup_registry) + 7 template **sonuna kadar okundu**; Files-Read Receipt +
    veri yapısı/akış raporu + parite tablosu üretildi (~5000 satır).
  - **Mimari karar**: 8 destek servisi (Mamdani fuzzy / LinUCB / MMR / Wilson CI)
    HİÇ değişmedi — API v2 endpoint'leri AYNEN import edip çağırıyor, sadece
    dönen nesneler Pydantic'e serialize ediliyor. Veri yapısı/sorgu mutlak korundu.
  - Backend: `schemas/admin.py` +~30 model (list/form/dashboard/discovery/
    experiment + 6 mutation body); `api_v2/admin.py` +17 endpoint
    (`_fc_invalidate`/`_fc_parse_dt`/`_fc_discovery_pending`/enum-option helper'ları).
    REST düzeltmesi: create=POST /feature-catalog, update=POST /{id}.
  - `scripts/test_api_v2_admin_feature_catalog.py` — **25/25 yeşil**
  - Frontend: `lib/types/admin.ts` +~35 tip · `lib/api/admin.ts` +9 fetcher +
    queryKey · `use-admin-mutations.ts` +9 mutation hook · `feature-catalog-ui.tsx`
    (statik tone map — Tailwind purge güvenli badge/anomali/skor tonları)
  - 8 route + 7 client:
    - `/feature-catalog` list (masaüstü tablo + mobil kart-grid; skor/telemetri/
      🧠bandit/🎨çeşitlilik rozetleri; sağlık bandı; durum sayım filtresi)
    - `/feature-catalog/new` + `/[id]` ortak form (26 alan; accordion bölümler;
      hedef rol checkbox; öncelik slider; tehlikeli aksiyon sil dialog)
    - `/feature-catalog/dashboard` (6 KPI + anasayfa sağlığı + son 7g + aktif
      deney + anomali + son hareketler)
    - `/feature-catalog/discovery-queue` (checkbox toplu reddet/sil + tekil;
      kaynak filtre; reddedilenleri göster toggle)
    - `/feature-catalog/experiments` list + `/new` form (ctrl+test variant,
      ağırlık 100 doğrulama) + `/[id]` detay (Wilson CI bar + durum aksiyonları)
  - Sidebar: "Vitrin" grubu 3 item aktive (Kartlar/Vitrin Yönetimi/Deneyler)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (8 yeni route)
- **D6 P1-P6 tam regresyon: 246/246 yeşil** (admin 125 + parent 37 +
  institution 55 + tenant 29)

## Dalga 6 — Ticari Pano (Paket 7) son durumu (2026-05-20)

**Kapsam kararı (kullanıcı 2026-05-20):** `/admin/revenue/*` = 44 endpoint /
13 servis / 11 template / ~12K satır. **4 alt-pakete bölündü** (her biri kendi
KURAL 1 receipt + smoke + regresyon ile):
- **P7a — Analitik çekirdek**: Aksiyon Merkezi + Gelir Tahmini + Kohort/LTV
- **P7b — 360 + CRM**: Kurum 360 + Bağımsız Öğretmen 360 + CRM (not/aksiyon/
  iletişim/etiket) — en büyük, mutation-yoğun
- **P7c — Teklifler + Aksiyon Şablonları**: offers + action-templates + crm_templates
- **P7d — Kampanyalar**: campaigns (10 endpoint)

Güvenlik Kamarası (`/admin/security-monitor/*`) **ayrı oturuma** bırakıldı
(kullanıcı kararı). `_revenue_drill.html` + `/security-monitor/revenue` o tarafta.

- **D6 Paket 7a — Ticari Pano: Analitik çekirdek**:
  - KURAL 1: `/revenue/action-center` (3456) + `/forecast` (3901) + `/cohort`
    (3940) + `/action-center/quick-action` (3981) endpoint'leri + `action_center.py`
    (430) + `revenue_forecast.py` (395) + `revenue_cohort.py` (420) +
    `institution_360.create_action` + 3 template (action_center/revenue_forecast/
    revenue_cohort) **sonuna kadar okundu**; Files-Read Receipt + veri akışı raporu.
  - **Mimari karar**: 3 analitik servisi + create_action HİÇ değişmedi —
    API v2 endpoint'leri AYNEN import edip çağırıyor, dataclass/dict'ler
    Pydantic'e serialize. Owner-pattern korundu (risk_at_mrr bağımsız
    öğretmenleri `owner_type="user"` döndürür).
  - Backend: `schemas/admin.py` +~25 model (action-center/forecast/cohort) ·
    `api_v2/admin.py` +4 endpoint + `_revenue_invalidate` helper'ı
  - `scripts/test_api_v2_admin_revenue_analytics.py` — **9/9 yeşil**
  - Frontend (emoji yok — Lucide ikon): `lib/types/admin.ts` +~20 tip ·
    `lib/api/admin.ts` +3 fetcher + queryKey · `use-admin-mutations.ts` +1
    mutation (quick-action) · `revenue-ui.tsx` (kind→Lucide ikon map +
    severity/cohort statik ton map'leri)
  - 3 route + 3 client:
    - `/revenue/action-center` — 5 KPI + sinyal kartları (total_score rozeti +
      primary/other sinyaller + önerilen aksiyon butonları → quick-action 3g takip)
    - `/revenue/forecast` — save_rate seçici + 4 KPI + 30/60/90 projeksiyon tablo +
      risk altı kurum tablosu (owner ayrımı) + senaryo karşılaştırma 2 sütun
    - `/revenue/cohort` — 3 filtre + 6 plan-hareketi KPI + tutunma heatmap matrisi +
      yaşam değeri (LTV `JargonTooltip` ile) 3 KPI + plan tablosu
  - Sidebar: "Ticari Pano" grubu 3 item aktive (Aksiyon Merkezi/Tahmin/Kohort & LTV);
    Kampanyalar + Şablonlar P7c/P7d için disabled
  - Verify: tsc ✅ · eslint ✅ (lgs/no-bare-jargon LTV düzeltmesi) · build ✅ (3 route)
- **D6 P1-P7a tam regresyon: 255/255 yeşil** (admin 134 + parent 37 +
  institution 55 + tenant 29)
- **D6 Paket 7b — Ticari Pano: 360 + CRM (Owner-pattern)**:
  - KURAL 1: 20 endpoint (institutions/{id} + users/{id} GET + CRM notes/actions
    + contact + tags) + `institution_360` (581) + `revenue_owner` (306) +
    `owner_contact` (65) + `owner_tags` (133) + `health_score_v2` public API +
    `crm`/`owner_tag`/`owner_contact` modelleri + 2 template (979+956)
    **sonuna kadar okundu**; Files-Read Receipt + veri akışı raporu.
  - **Mimari karar**: institution_360 + revenue_owner + owner_contact +
    owner_tags + health_score_v2 servisleri HİÇ değişmedi — AYNEN çağrıldı,
    dataclass/dict/ORM nesneleri Pydantic'e serialize edildi.
  - **Owner-pattern**: CRM/tag/contact `owner_type` ("institution"|"user") ile
    tek API yüzeyi; not/aksiyon/tag pin/delete/complete owner-agnostic (id ile).
  - **P7b/P7c sınırı**: offers + fatura mutation'ları + invoices_for_owner +
    action-templates P7c'ye bırakıldı. Billing sekmesi P7b'de read (plan +
    özet + plan değişiklik geçmişi).
  - Backend: `schemas/admin.py` +~35 model · `api_v2/admin.py` +11 endpoint
    (`_rev360_invalidate`/`_crm_meta`/note·action·tag·contact·health dönüştürücü
    helper'ları)
  - `scripts/test_api_v2_admin_revenue_360.py` — **18/18 yeşil**
  - Frontend (emoji yok — Lucide): types +~35 · api +2 fetcher + queryKey ·
    mutations +9 hook · `revenue-360-shared.tsx` (HealthV2Card + CrmNotesPanel +
    CrmActionsPanel + ContactAndTagsPanel + PlanChangesTimeline + TabBar + statik
    ton map)
  - 2 route + 2 client (sekmeli, mobil-dostu):
    - `/revenue/institutions/[id]` — Sağlık&Riskler / Kullanım / Plan&Ödeme /
      Notlar / Aksiyonlar / İletişim&Etiketler + 4 KPI + sağlık v2 + risk listesi
    - `/revenue/users/[id]` — Sağlık / Öğrenciler / Kullanım / Plan&Ödeme /
      Notlar / Aksiyonlar / İletişim&Etiketler + öğrenci sağlık tablosu
  - Navigasyon: action-center kurum adları + "Kurum 360" linki, forecast risk
    tablosu isimleri → 360 detay (owner-aware detail_url)
  - Verify: tsc ✅ · eslint ✅ (set-state-in-effect düzeltmesi) · build ✅ (2 route)
- **D6 P1-P7b tam regresyon: 273/273 yeşil** (admin 152 + parent 37 +
  institution 55 + tenant 29)
- **D6 Paket 7c — Ticari Pano: Teklifler + Aksiyon Şablonları + Tahsilat**:
  - KURAL 1: 15 endpoint (offers create/send/cancel ×2 owner + invoice
    postpone/mark-paid/cancel/send-reminder + action-templates CRUD/render) +
    `offers.py` (446) + `crm_templates.py` (192) + `dunning.send_reminder` +
    `revenue_panel.invoices_for_owner`/`_invoice_row` + offer/crm_template/invoice
    modelleri + `action_templates.html` **sonuna kadar okundu**.
  - **Mimari karar**: offers / crm_templates / dunning servisleri HİÇ değişmedi —
    AYNEN çağrıldı. Invoice mark-paid/cancel/postpone (Jinja'da inline model
    mutation) aynı mantıkla API v2'de korundu. Owner-pattern: offer/invoice
    mutation'ları nesneden owner türetip 360 cache'ini bayatlar.
  - **360 entegrasyonu**: P7b'de boş bırakılan Teklifler sekmesi + billing fatura
    listesi şimdi dolu — 360 GET response'larına `offers` + `invoices` +
    `meta.offer_kinds` eklendi (tek query ile sekmeler dolar).
  - Backend: `schemas/admin.py` +~15 model · `api_v2/admin.py` +12 endpoint
    (`_offer_item`/`_invoice_item`/`_action_template_item`/owner-invalidate
    helper'ları). REST: create=POST /action-templates, update=POST /{id}.
  - `scripts/test_api_v2_admin_revenue_offers.py` — **19/19 yeşil**
  - Frontend (emoji yok — Lucide): types +~15 · api +1 fetcher + queryKey ·
    mutations +10 hook · `revenue-360-shared.tsx`'e `OffersPanel` +
    `InvoicesTable` (tahsilat: hatırlat/ötele/öden/iptal) eklendi
  - 360 sayfaları: Teklifler sekmesi (oluştur/gönder/iptal + public link) +
    billing'e fatura tablosu (mutation'lı) · yeni `/revenue/action-templates`
    sayfası (CRUD + accordion + inline düzenle) · sidebar "Şablonlar" aktive
  - Verify: tsc ✅ · eslint ✅ · build ✅ (1 yeni route — toplam 27 revenue endpoint)
- **D6 P1-P7c tam regresyon: 292/292 yeşil** (admin 171 + parent 37 +
  institution 55 + tenant 29)
- **Erişim iyileştirmesi**: Ticari 360 sayfalarına Kuruluşlar→Kurumlar ve
  →Bağımsız Öğretmenler listelerinden "Ticari 360" linki eklendi (eskiden sadece
  Aksiyon Merkezi/Tahmin'den koşullu erişiliyordu).
- **D6 Paket 7d — Ticari Pano: Toplu Kampanyalar**:
  - KURAL 1: 10 endpoint (list/new-meta/preview/create/detail + lifecycle
    launch/pause/resume/complete/cancel) + `campaigns.py` (695) + `campaign.py`
    modeli (Campaign + CampaignRecipient + Segment/Status/RecipientStatus enum) +
    4 template (campaigns_list/campaign_form/campaign_detail/_campaign_preview)
    **sonuna kadar okundu**.
  - **Mimari karar**: `campaigns.py` HİÇ değişmedi — AYNEN çağrıldı. Owner-pattern:
    segment hedeflemesi kurum + bağımsız öğretmeni birlikte kapsar (preview_segment
    Owner döndürür); PAUSED_30D yalnız kurum. A/B: deterministik hash split,
    funnel her varyant ayrı (accepted_pct dönüşüm). Launch P7c offers servisini
    reuse eder (her hedefe Offer + CampaignRecipient + e-posta).
  - Backend: `schemas/admin.py` +~14 model · `api_v2/admin.py` +10 endpoint
    (`_campaign_funnel`/`_campaign_variant`/`_campaign_lifecycle` helper'ları).
    REST: create=POST /campaigns, lifecycle=POST /{id}/<action>.
  - `scripts/test_api_v2_admin_revenue_campaigns.py` — **17/17 yeşil**
  - Frontend (emoji yok — Lucide): types +~14 · api +3 fetcher + queryKey ·
    mutations +7 hook (preview/create + 5 lifecycle)
  - 3 route + 3 client:
    - `/revenue/campaigns` liste (funnel sütunlu tablo)
    - `/revenue/campaigns/new` form (segment radyo + **canlı önizleme** +
      A/B variant accordion)
    - `/revenue/campaigns/[id]` detay (funnel KPI + A/B karşılaştırma + kazanan
      banner + recipient tablosu + lifecycle butonları)
  - Sidebar "Kampanyalar" aktive — **Ticari Pano grubu tamamen aktif**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (3 route — toplam 37 revenue endpoint)
- **D6 P1-P7d tam regresyon: 309/309 yeşil** (admin 188 + parent 37 +
  institution 55 + tenant 29)

## Dalga 6 — Güvenlik Kamarası (2026-05-20)

**Kapsam kararı (kullanıcı 2026-05-20):** `/admin/security-monitor/*` = 27
endpoint / 8 servis / 15 template / ~8K satır. **4 alt-pakete bölündü**
(her biri kendi KURAL 1 receipt + smoke + regresyon ile):
- **G1 — Ticari Ana Dashboard**: revenue + drill + invoices ✅
- **G2a — Genel Bakış + Sistem + Bildirim + Bütünlük** ✅ (2026-05-20)
- **G2b — Aktivite Kamerası** ✅ (2026-05-20)
- **G3 — Oturumlar + Canlı + IP + Impersonation** ✅ (2026-05-20)
- **G4 — Alarmlar + Suistimal** ✅ (2026-05-20)
Caddy `/admin/*` yönlendirmesi **en sonda** (tüm G paketleri bitince — yarım
taşınmış sayfalarda kırık link riski olmasın).

- **D6 Güvenlik Kamarası G1 — Ticari Ana Dashboard**:
  - KURAL 1: 3 endpoint (revenue + revenue/drill + revenue/invoices) +
    `revenue_panel.py` (969 — get_revenue_panel_data/mrr/plan_distribution/
    trial/plan_change/daily/churn/payment_calendar/drill_for_key) + revenue_owner
    (P7b) + 3 template (security_monitor_revenue 545, _revenue_drill 103,
    security_monitor_invoices 136) **sonuna kadar okundu**.
  - **Mimari karar**: revenue_panel + revenue_owner HİÇ değişmedi — AYNEN
    çağrıldı, hepsi salt-okunur. Owner-pattern segment toggle (Hepsi/Kurum/
    Bağımsız) korundu. Bu, P7 Ticari Pano'nun üst dashboard'u.
  - Backend: `schemas/admin.py` +~17 model · `api_v2/admin.py` +3 endpoint
    (drill için generic RevenueDrillRow — esnek opsiyonel alanlar)
  - `scripts/test_api_v2_admin_revenue_dashboard.py` — **11/11 yeşil**
  - Frontend (emoji yok — Lucide): types +~17 · api +3 fetcher + queryKey ·
    2 route + 2 client:
    - `/security-monitor/revenue` ana dashboard (segment toggle + KPI kartları +
      ödeme takvimi bucket + plan dağılımı + trial tablo + plan hareketi +
      tıklanabilir drill paneli)
    - `/security-monitor/revenue/invoices` (status sayım chip + fatura tablosu)
  - Sidebar: "Ticari Pano" grubuna "Genel Bakış" girişi eklendi
  - Verify: tsc ✅ · eslint ✅ · build ✅ (2 yeni route)
- **D6 Güvenlik Kamarası G1 tam regresyon: 320/320 yeşil** (admin 199 + parent
  37 + institution 55 + tenant 29)

- **D6 Güvenlik Kamarası G2a — Genel Bakış + Sistem + Bildirim + Bütünlük**:
  - KURAL 1: 5 endpoint (`/security-monitor` overview + `/integrity` + `/system`
    + `/system/{id}/resolve` + `/notifications`) + 6 servis (`security_monitor`
    580, `error_capture` 358, `notification_health` 370, `data_integrity` 362,
    `attention_engine` 671 public API, `impersonation.list_active`) + 4 template
    **sonuna kadar okundu**; Files-Read Receipt + veri yapısı raporu + parite
    tablosu üretildi.
  - **Mimari karar**: 6 servis HİÇ değişmedi — `get_security_dashboard_data` /
    `get_integrity_panel_data` / `get_system_health_data` / `get_health_data` /
    `get_attention_summary` / `list_active` AYNEN çağrıldı, dönen dict/dataclass
    Pydantic'e serialize edildi. resolve_error audit `AuditAction.USER_UPDATE`
    (Jinja birebir). G2b (Aktivite) `tenant_activity` 3159 satır + template 1616
    olduğu için ayrı oturuma bölündü (kullanıcı onayı 2026-05-20).
  - Backend: `schemas/admin.py` +~30 model (Security/Integrity/System/Notif) ·
    `api_v2/admin.py` +5 endpoint + `_attention_item_to_model` helper. Matris
    serialize: channel_matrix `channels`→`rows`, kind_matrix `kinds`→`rows`.
  - `scripts/test_api_v2_admin_security_overview.py` — **14/14 yeşil** (role guard
    + overview/integrity/system/notifications shape + resolve happy/idempotent/404)
  - Frontend (emoji yok — Lucide): `types/admin.ts` +~30 tip · `api/admin.ts`
    +4 fetcher + 4 queryKey (`admin:security:*`) · `use-admin-mutations.ts`
    +useResolveSystemError (invalidate `admin:security:system`+`overview`) ·
    `security-ui.tsx` (severity/level statik ton map + LevelBadge/SeverityBadge
    + humanizeAgo/fmtDateTime/successPctColor) · `notif-trend-bar-chart.tsx`
    (Recharts stacked bar 4 seri)
  - 4 route + 4 client:
    - `/security-monitor` (overview): Dikkat Odası kartları (attention, severity
      Lucide ikon — emoji map'lenmez) + 8 KPI + rol dağılımı + aktif
      impersonation tablo (kritik kırmızı) + aktif oturum + şüpheli IP + kritik
      audit akışı + süper admin giriş; 30s auto-refresh
    - `/security-monitor/integrity`: migration kartı (ok/pending/error tonu) +
      DB dosya boyut (500MB/1GB eşik) + orphan tarama + KVKK SLA (30g) tablo +
      cron drift tablo
    - `/security-monitor/system`: 3 özet + açık hata grupları (genişleyebilir
      stack trace + "Çözüldü" dialog note textarea) + endpoint hata oranı +
      yavaş istek tabloları
    - `/security-monitor/notifications`: 24h/7g özet kart (başarı% renk) + en
      eski kuyruk uyarısı + 7g stacked trend (Recharts) + kanal/tür matrisi
      (total>0 satır + failed kırmızı) + engellenme nedenleri + son hatalar
  - Sidebar: "Güvenlik Kamarası" grubuna 3 item aktive (Veri Bütünlüğü / Sistem
    Sağlığı / Bildirim Sağlığı) + Genel Bakış zaten aktifti; live/sessions/
    alarms/abuse/activity hâlâ disabled (G2b/G3/G4)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (4 yeni route)
- **D6 Güvenlik Kamarası G2a tam regresyon: 334/334 yeşil** (admin 213 + parent
  37 + institution 55 + tenant 29)

- **D6 Güvenlik Kamarası G2b — Aktivite Kamerası**:
  - KURAL 1: 3 endpoint (`/activity` panel + `/activity/active-users` drill +
    `/activity/heatmap` drill) + `tenant_activity` (3159 satır, ~50 fonksiyon)
    + 3 template (security_monitor_activity 1616, _activity_drill_users 58,
    _activity_drill_heatmap 92) **sonuna kadar okundu**; Files-Read Receipt +
    dev veri yapısı raporu + parite tablosu üretildi.
  - **Mimari karar**: `tenant_activity` HİÇ değişmedi — 3 endpoint
    `get_activity_panel_data_with_summary` / `active_users_window` /
    `institution_hour_day_heatmap` AYNEN çağırır, dönen dev dict'ler Pydantic'e
    serialize. Owner-pattern + segment (all/institution/solo) mutlak korundu.
    Heatmap int-key matrix → str-key (`_str_matrix`, JSON uyumu). D6'nın en
    büyük tek servisi.
  - Backend: `schemas/admin.py` +~45 model (ActivityPanelResponse + alt modeller
    + 2 drill response). `api_v2/admin.py` +3 endpoint + `_str_matrix` /
    `_retention_metric` helper.
  - `scripts/test_api_v2_admin_security_activity.py` — **15/15 yeşil** (3 segment
    + solo_special varlığı + heatmap 24×7 str-key + 2 drill + 6 role guard)
  - Frontend (emoji yok — Lucide): `types/admin.ts` +~45 tip · `api/admin.ts`
    +3 fetcher + 3 queryKey · `security-ui.tsx`'e band_color statik ton map
    (toneDot/toneBadge/toneText — purge-safe) · `activity-charts.tsx`
    (HeatmapGrid CSS + WowBarChart/DauTrendChart Recharts + StickinessSparkline +
    SessionBandsBar)
  - 1 route + client (6 sekme client-state, segment URL-state):
    - `/security-monitor/activity` — kritik özet 6 kart (sekmeye atlar) + segment
      toggle (Hepsi/Kurumlar/Bağımsız) + 6 sekme: **Bugün** (DAU/WAU/MAU
      tıklanabilir drill + yapışkanlık + rol kırılımı + solo özel panel + WoW
      grafik) · **Risk** (kalp atışı 6-bant + öneri popup + heatmap drill + plan×
      aktivite 4-quadrant + sönüş hızı + sessizleşenler) · **Tutunma** (yapışkanlık
      + sparkline + 1h/30g + geri dönenler + onboarding milestone tablosu) ·
      **Derinlik** (oturum süresi bantları + öğretmen/öğrenci oranı + power users
      + özellik popülerlik/matris — emoji→Lucide ikon) · **Zaman** (saat×gün ısı
      haritası + 14g DAU trend + en aktif kurumlar + kurum heatmap drill) ·
      **Karşılaştırma** (plan benchmark + champion kartları)
    - Drill'ler on-demand `useQuery` (açılır panel + kapat); owner-pattern
      detay linkleri 360 sayfalarına
  - Sidebar: "Güvenlik Kamarası → Aktivite" item aktive (live/sessions/alarms/
    abuse hâlâ disabled — G3/G4)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (1 yeni route)
- **D6 Güvenlik Kamarası G2b tam regresyon: 349/349 yeşil** (admin 228 + parent
  37 + institution 55 + tenant 29)

- **D6 Güvenlik Kamarası G3 — Oturumlar + Canlı + IP + Impersonation**:
  - KURAL 1: 7 endpoint (`/live` + `/live/feed` + `/sessions` + `/sessions/{token}/
    revoke` + `/ips/block` + `/ips/unblock` + `/impersonations/{id}/end`) +
    `alarm_engine.live_event_stream` (352-394) + `impersonation.end_session` +
    `security_monitor.terminate_session`/`revoke_session_by_token`/`block_ip_manual`/
    `unblock_ip` + 3 template (security_monitor_live 70, _live_feed 31,
    security_monitor_sessions 321) **sonuna kadar okundu**; Files-Read Receipt +
    veri akışı raporu + parite tablosu üretildi.
  - **Kritik bulgu**: `sessions` sayfası `get_security_dashboard_data` +
    `list_active` kullanır = **G2a `SecurityOverviewResponse`'un alt kümesi**.
    Yeni GET endpoint açılmadı; frontend sessions sayfası mevcut overview
    fetcher'ını yeniden kullanır.
  - **Mimari karar**: security_monitor + impersonation + alarm_engine servisleri
    HİÇ değişmedi — aynen çağrıldı. Mutasyonlar
    `invalidate=["admin:security:overview","admin:security:sessions"]` ile
    sessions görünümünü tazeler.
  - Backend: `schemas/admin.py` +5 model (LiveFeedItem/Response + IpBlock/Unblock
    Body + SecurityActionResult). `api_v2/admin.py` +5 endpoint (1 GET live/feed
    `ge=10/le=86400` clamp + 4 POST mutation; revoke/block/unblock USER_UPDATE,
    imp-end IMPERSONATE_REVOKED audit — Jinja birebir).
  - `scripts/test_api_v2_admin_security_sessions.py` — **17/17 yeşil** (live/feed
    + 4 mutation × happy/404/403 + clamp + ORM doğrulama)
  - Frontend (emoji yok — Lucide): types +3 · api +1 fetcher + 2 queryKey
    (`securitySessions`/`securityLiveFeed`) · `use-admin-mutations.ts` +generic
    `useSecurityAction` + 4 hook (useRevokeSession/useBlockIp/useUnblockIp/
    **useRevokeImpersonation** — mevcut P3 `useEndImpersonation` ile çakışmamak
    için yeni ad) + 4 error code label
  - 2 route + 2 client:
    - `/security-monitor/sessions` — overview verisini kullanır: aktif sahte
      oturumlar (sonlandır confirm) + 4 KPI + aktif oturum tablosu (rol badge +
      kapat confirm) + 24s fail bucket (bloka al) + şüpheli/blokli IP tablosu
      (serbest/bloka al + manuel blok formu hours 1-720) + süper admin giriş akışı;
      tek paylaşılan confirm Dialog
    - `/security-monitor/live` — poll feed (`refetchInterval` seçili aralık;
      pencere 5dk/10dk/30dk/1saat + yenileme 2/5/15sn/durdur seçici) + canlı
      nabız göstergesi + audit/alarm satırları (severity Lucide ikon + renk)
  - Sidebar: "Oturumlar" + "Canlı Akış" aktive (alarms/abuse hâlâ disabled — G4)
  - Verify: tsc ✅ · eslint ✅ · build ✅ (2 yeni route)
- **D6 Güvenlik Kamarası G3 tam regresyon: 366/366 yeşil** (admin 245 + parent
  37 + institution 55 + tenant 29)

- **D6 Güvenlik Kamarası G4 — Alarmlar + Suistimal**:
  - KURAL 1: 8 endpoint (alarms list/scan/ack/rule-update + abuse list/scan/
    resolve/remediate) + `alarm_engine` (406 — evaluate_all/list_rules/
    list_recent_events/acknowledge/update_rule) + `abuse_detection` (run_all/
    list_signals/resolve_signal/open_signal_count) + `abuse_remediation`
    (auto_remediate_signal + RemediationResult + ACTION_BUTTON_LABELS_TR) +
    2 template (security_monitor_alarms 186, security_monitor_abuse 199) +
    5 model label dict **sonuna kadar okundu**.
  - **Mimari karar**: alarm_engine + abuse_detection + abuse_remediation
    servisleri HİÇ değişmedi — aynen çağrıldı. Alarm kuralı eşik/cooldown/
    enabled/channels güncelleme + abuse remediate (kind'a göre toplu aksiyon:
    mass_invitation→davet iptal, mass_notification→bildirim bastır,
    multi_account→oturum kapat; başarıda otomatik resolve) mantığı korundu.
    Mutasyonlar `invalidate=["admin:security:alarms"|"abuse","overview"]`.
    Abuse label/severity/açıklama TR dict'leri response `meta` olarak gönderilir
    (jargon yasağı — sade Türkçe).
  - Backend: `schemas/admin.py` +12 model. `api_v2/admin.py` +8 endpoint
    (audit: scan/ack/update USER_UPDATE, remediate ABUSE_REMEDIATION — Jinja
    birebir; remediate başarısız → 400 remediation_failed).
  - `scripts/test_api_v2_admin_security_alarms_abuse.py` — **21/21 yeşil**
    (8 endpoint × happy/404/403 + rule update + remediate happy/already_resolved
    + meta 5 dict + ORM doğrulama)
  - Frontend (emoji yok — Lucide): types +12 · api +2 fetcher + 2 queryKey ·
    `use-admin-mutations.ts` generic `useSecurityAction<TBody,TResult>` + 6 hook
    (AlarmScan/AlarmAck/AlarmUpdateRule/AbuseScan/AbuseResolve/AbuseRemediate)
    + 4 error code label
  - 2 route + 2 client:
    - `/security-monitor/alarms` — unack sayısı + "Şimdi tara" + kural tablosu
      (satır-içi düzenleme: eşik/cooldown/kanal/aktif → dirty-aware Kaydet) +
      son 72s tetiklenen alarmlar (severity renk + "Gördüm" ack)
    - `/security-monitor/abuse` — açık sinyal sayısı + "Şimdi tara" + filtre
      (tür dropdown + sadece açıklar, URL state) + 4 tür açıklama kartı + sinyal
      tablosu (aktör/kurum 360 linki + ⚡toplu aksiyon confirm dialog + çöz
      not dialog)
  - Sidebar: "Alarmlar" + "Suistimal" aktive — **Güvenlik Kamarası grubu
    tamamen aktif (6/6 item)**
  - Verify: tsc ✅ · eslint ✅ · build ✅ (2 yeni route)
- **D6 Güvenlik Kamarası G4 tam regresyon: 387/387 yeşil** (admin 266 + parent
  37 + institution 55 + tenant 29)

## D6 Caddy yönlendirmesi (2026-05-20) — TAMAM

- `deploy/Caddyfile`: "Dalga 5: Süper admin — KAPALI" bloğu **açıldı** →
  `reverse_proxy /admin next:3000` + `reverse_proxy /admin/* next:3000`
  (yorum metni "Dalga 6 — AÇIK 2026-05-20" olarak güncellendi). `/api/v2/admin/*`
  zaten yukarıdaki `/api/v2/*` matcher'ından FastAPI'ye (BFF backend) gidiyor.
- **Kullanıcı onayı alındı (2026-05-20)**; Jinja `/admin/*` silinmedi, "asılı
  bırakılanlar"a eklendi.
- Otomatik regresyon: 21 suite **387/387 yeşil** (Caddy değişikliği kodu
  etkilemez — doğrulama amaçlı çalıştırıldı).
- **Kullanıcının yapması gerekenler (canlı ortam)**:
  1. `docker compose exec proxy caddy reload --config /etc/caddy/Caddyfile`
     (<60 sn rollback — R-020; geri almak için iki `reverse_proxy /admin*`
     satırını tekrar yorum yap + reload)
  2. Manuel smoke: super admin login → 7 sidebar grubu (Panel + Kuruluşlar +
     Denetim + Limitler & Kullanım + Vitrin + Ticari Pano + Güvenlik Kamarası)
     tek tek açılıp doğrulanır.

## Dalga 7 — Auth / Güvenlik (full paket, fazlı) — 2026-05-20

**Kapsam kararı (kullanıcı 2026-05-20):** full güvenlik paketi · 2FA yalnız
Süper Admin + Kurum Yöneticisi · fazlara bölünmüş, her faz kullanıcı onayıyla.
5 fazlı yol haritası:
- **P1 — Çekirdek parite + BFF güvenlik birleştirme** ✅ (2026-05-20)
- **P2 — Şifre sıfırlama (forgot password)** ✅ (2026-05-20, migration `o6p8s1t2s00m`)
- **P3 — Signup (teacher + invite) + email doğrulama** ✅ (2026-05-20, migration `p7q9t2u3t11n`)
- **P4 — 2FA/TOTP** (Süper Admin + Kurum Yöneticisi) ✅ (2026-05-20, migration `q8r0u3v4u22o`)
- **P5 — Oturum yönetimi + public teklif + Caddy/kapanış** ✅ (2026-05-20, migration YOK)

Migration'lı fazlar (P2/P3/P4) başlatılmadan önce migration kullanıcıya ayrıca
gösterilir (riskli-sprint kuralı).

**Mevcut güvenlik altyapısı envanteri** (zaten olgun, KURAL 1 ile okundu):
bcrypt · JWT access+refresh `pwd_stamp` rotation · HttpOnly+Secure+SameSite+
`__Host-` cookie · rol-bazlı lockout (3/30·5/15·5/10) · rol-bazlı şifre politikası
(14/12/10/8 + özel karakter) · ~150 yaygın şifre kara listesi · HaveIBeenPwned
breach check · Cloudflare Turnstile · IP brute-force blok (SuspiciousIp) ·
sliding-window rate limit · audit · ActiveSession heartbeat · süper admin login
alarmı · email enumeration koruması · auto-resume · self-signup + invite + trial.

- **D7 Paket 1 — Çekirdek parite + BFF güvenlik birleştirme**:
  - KURAL 1: tüm auth mimarisi okundu (api_v2/auth 330 + auth_security 223 +
    rate_limit/security/jwt_auth 264 + Jinja auth/signup/password/offers 891 +
    turnstile/password_breach/security_monitor_alerts 276 + 6 template).
  - **Kritik bulgu**: BFF login (api_v2), Jinja login'in 6 güvenlik katmanını
    kaçırıyordu (IP blok / CAPTCHA / SuspiciousIp besleme / **ActiveSession** /
    auto-resume / süper admin alarmı). ActiveSession eksikliği → G2a/G3 "Aktif
    Oturumlar + Canlı Akış" panelleri Next.js kullanıcılarını **göstermiyordu**.
  - **Mimari karar**: BFF stateless JWT olduğu için ActiveSession takibi JWT'ye
    opsiyonel `sid` claim eklenerek yapıldı — `jwt_auth.py` mobile (api_v1) ile
    PAYLAŞILDIĞINDAN `sid` None ise payload birebir aynı (geriye uyum; api_v1
    47/47 korundu). Her authenticated cookie isteğinde
    `dependencies._resolve_from_cookie` heartbeat atar; uzaktan revoke edilince
    401 `session_terminated`.
  - Backend:
    - `jwt_auth.py`: `_make_token`/`issue_*`/`issue_token_pair`'a `sid` (opsiyonel)
      + `TokenPayload.session_id` + decode `data.get("sid")`
    - `dependencies.py`: `_resolve_from_cookie` heartbeat + `_resolve_user_v2`
      helper + **`get_current_user_v2_allow_pwchange`** (must_change 403'ü atmaz)
    - `me.py`: `/me/password-change` artık `allow_pwchange` dep kullanır →
      **must_change kullanıcı kilitlenmesi giderildi** (kritik bug fix)
    - `api_v2/auth.py` login: IP blok (429 ip_blocked) + Turnstile CAPTCHA
      (LoginIn.turnstile_token; 401 captcha_failed) + record_failed_login_ip +
      record_session_start (sid) + maybe_auto_resume + süper admin alarmı;
      refresh sid taşır + heartbeat; logout terminate_session; yeni
      `GET /api/v2/auth/turnstile` (enabled + site_key, public)
  - `scripts/test_api_v2_auth_p1.py` — **10/10 yeşil**; mevcut
    `test_api_v2_auth.py` 14/14 + `test_api_v1.py` 47/47 korundu
  - **Test izolasyon notu**: `record_failed_login_ip` TestClient IP'sini
    ("testclient") brute-force eşiğiyle bloklayabilir → auth testlerinin
    cleanup'ına `SuspiciousIp.ip=="testclient"` temizliği eklendi (yoksa sonraki
    paketler 429 alır).
  - Frontend (emoji yok — Lucide): `app/login` güçlendirildi (role landing
    `_home_for` paritesi: admin/institution/teacher/parent/student + Turnstile
    widget `next/script` explicit render + `ip_blocked`/`captcha_failed` hata
    kodları + must_change → `/password/change`); yeni `app/password/change`
    (server auth-durum çözer: 403 password_change_required → zorunlu mod / 200 →
    normal / 401 → login) + form (breach/policy/lockout hata kodları)
  - Caddy: `/login` + `/password/change` → next:3000 AÇIK; `/logout` Jinja'da
    (Next.js çıkışı BFF ile); `/password/*`+`/signup/*`+`/offers/*` P2-P5'te
  - Verify: tsc ✅ · eslint ✅ · build ✅ (/login + /password/change)
- **D7 P1 tam regresyon: 25 suite GREEN** (api_v1 47 + auth 14 + auth_p1 10 +
  me + admin tüm + parent + institution + tenant)

- **D7 Paket 2 — Şifre sıfırlama (forgot password)**:
  - **Migration `o6p8s1t2s00m`** (down_revision n5o7r0s1r99l): `password_reset_tokens`
    tablosu. **Additive** — yalnız yeni tablo, mevcut veriyi ETKİLEMEZ, downgrade'li.
    `alembic upgrade head` uygulandı.
  - Model `app/models/password_reset.py` — `PasswordResetToken` (token unique 64 +
    user_id CASCADE + expires_at + consumed_at + requested_ip; `is_usable` property;
    TTL 60 dk). models/__init__ export.
  - Servis `app/services/password_reset.py` — `request_reset` (kullanıcı varsa
    token üret + eski kullanılmamışları iptal + e-posta gönder; yoksa sessizce None),
    `get_usable_token`, `consume_reset` (şifre değiştir + tüket + kilit/sayaç
    sıfırla → pwd_stamp değişir, eski tüm oturumlar revoke).
  - Endpoint'ler (`api_v2/auth.py`):
    - `POST /auth/forgot-password` — **enumeration koruması** (her zaman generic
      200) + rate limit + CAPTCHA (aktifse). E-posta `email_service` (disabled →
      log-only dev).
    - `POST /auth/reset-password` — token validate (400 invalid_token) + mismatch
      (422) + politika (422 password_weak) + eski-ile-aynı (422 password_same) +
      **HaveIBeenPwned breach** (422 password_breached) + tek-kullanım + audit.
  - Email template `emails/password_reset.html` (Subject + reset_url + 60 dk notu).
  - `scripts/test_api_v2_auth_p2.py` — **11/11 yeşil**.
  - Frontend (emoji yok — Lucide): `/password/forgot` (e-posta + Turnstile +
    generic başarı ekranı) + `/password/reset/[token]` (yeni şifre + confirm +
    hata kodları + ölü-token ekranı → yeni bağlantı iste). Login sayfasına
    "Şifremi unuttum" linki; "yöneticinizle iletişime geçin" metni kaldırıldı.
  - Caddy: `/password/change` spesifik → `/password/*` generic AÇIK (change +
    forgot + reset). Verify: tsc ✅ · eslint ✅ · build ✅.
- **D7 P2 tam regresyon: 16 suite GREEN** (api_v1 47 + auth 14 + auth_p1 10 +
  auth_p2 11 + me + admin çekirdek + parent + institution + tenant)

- **D7 Paket 3 — Signup (teacher + invite) + email doğrulama (soft)**:
  - **Migration `p7q9t2u3t11n`** (down_revision o6p8s1t2s00m): `users.email_verified_at`
    (nullable) + DATA (mevcut tüm kullanıcılar geriye dönük doğrulanmış) +
    `email_verification_tokens` tablosu. **Additive**, downgrade'li. Uygulandı.
  - **Soft doğrulama kararı (kullanıcı 2026-05-20)**: kayıt+giriş serbest, panelde
    banner ile teşvik; doğrulamadan da kullanılabilir. SMTP gecikse kimse
    kilitlenmez.
  - Model `email_verification.py` (EmailVerificationToken, 7g TTL, tek kullanım) +
    `User.email_verified_at` + `UserPublic.email_verified` (login/me yanıtında).
  - Servis `email_verification.py` — `issue_and_send` (token + mail, eski iptal),
    `verify` (email_verified_at doldur + tüket).
  - Endpoint'ler (`api_v2/auth.py`): `POST /auth/signup/teacher` (self-signup +
    14g trial + CAPTCHA + auto-login + doğrulama maili) · `GET /auth/signup/invite/{token}`
    (davet bilgisi public) · `POST /auth/signup/invite/{token}` (kuota + atomik
    consume + auto-login) · `POST /auth/verify-email/{token}` · `POST /auth/resend-verification`.
    Ortak `_establish_bff_session` helper (ActiveSession sid + cookie — login ile aynı).
    Email template `emails/email_verify.html`.
  - `scripts/test_api_v2_auth_p3.py` — **13/13 yeşil**.
  - Frontend (emoji yok — Lucide): `/signup/teacher` (full_name/email/şifre×2/
    şartlar + Turnstile) + `/signup/invite/[token]` (server invite-info + 4 durum
    ekranı + form pre-fill) + `/verify-email/[token]` (otomatik doğrulama:
    verifying/success/error). **NOT**: soft doğrulama banner'ı (resend butonu)
    P5'te `/me/account`'a eklenecek (resend endpoint hazır).
  - Caddy: `/signup/*` + `/verify-email/*` AÇIK. Verify: tsc ✅ · eslint ✅ · build ✅.
- **D7 P3 tam regresyon: 15 suite GREEN** (api_v1 47 + auth p1/p2/p3 + me + admin
  çekirdek + parent + institution + tenant)

- **D7 Paket 4 — İki faktörlü doğrulama (2FA/TOTP)**:
  - **Migration `q8r0u3v4u22o`** (down_revision p7q9t2u3t11n): `users.totp_secret` +
    `users.totp_enabled_at` (nullable) + `totp_backup_codes` tablosu. **Additive**,
    downgrade'li. Uygulandı.
  - **Kapsam (kullanıcı kararı)**: yalnız Süper Admin + Kurum Yöneticisi
    etkinleştirebilir (opsiyonel — kullanıcı kendi açar). `pyotp` kütüphanesi
    (requirements.txt) + frontend `qrcode.react`.
  - Model: `User.totp_secret`/`totp_enabled_at` + `two_factor_enabled` property +
    `TotpBackupCode` (bcrypt hash, tek kullanım).
  - Servis `totp.py`: setup (secret + provisioning_uri + 10 yedek kod) / enable
    (TOTP doğrula → aktif) / disable / verify_login (TOTP veya yedek kod ±1 pencere)
    / can_use_2fa (rol kısıtı) / remaining_backup_codes.
  - Endpoint'ler:
    - Login akışı: şifre doğru + 2FA aktif → cookie KURMA, `LoginOut(two_factor_required,
      challenge)` (5 dk imzalı `type=2fa` JWT). Ortak `_complete_login` helper
      (login 2FA'sız + 2fa/verify paylaşır).
    - `POST /auth/2fa/verify` (challenge + kod → register_failed_login brute force
      koruması + _complete_login + cookie)
    - `/me/2fa/status` · `/me/2fa/setup` (403 rol) · `/me/2fa/enable` · `/me/2fa/disable`
  - `scripts/test_api_v2_auth_p4.py` — **14/14 yeşil**. api_v1 47/47 + auth 14/14 +
    auth_p1 10/10 korundu (login akışı refactor regresyon-temiz).
  - Frontend (emoji yok — Lucide): login'e 2FA 2. adım (`TwoFactorStep` — kod/yedek
    kod + vazgeç) + `/me/account` `TwoFactorCard` (yalnız yönetici rolünde görünür:
    QR `qrcode.react` + secret + 10 yedek kod + enable/disable kod doğrulama).
  - Caddy: yeni path yok (`/login` + `/me` zaten açık). Verify: tsc ✅ · eslint ✅ · build ✅.
- **D7 P4 tam regresyon: 16 suite GREEN** (api_v1 47 + auth p1/p2/p3/p4 + me +
  admin çekirdek + parent + institution + tenant)

- **D7 Paket 5 — Oturum yönetimi + public teklif + kapanış** (migration YOK):
  - Backend: `me.py`'ye `GET /me/sessions` (kullanıcının son 24s aktif oturumları;
    access cookie sid → is_current işareti) + `POST /me/sessions/{token}/revoke`
    (sahiplik kontrolü — yalnız kendi oturumu; başkasının token'ı 404;
    terminate_session reason=self_revoke). Yeni `api_v2/offers_public.py` router
    (public, login'siz): `GET /offers/{token}` + `/accept` + `/decline` — P7c
    `offers` servisi AYNEN çağrıldı (get_offer_by_token/accept_offer/decline_offer/
    describe_offer). `api_v2/__init__` include. `me.py`'ye `Request` importu
    eklendi (sessions için).
  - `scripts/test_api_v2_auth_p5.py` — **12/12 yeşil**.
  - Frontend (emoji yok — Lucide): `/me/account`'a `SessionsCard` (cihaz/IP/son
    aktivite + "Bu cihaz" rozeti + uzaktan kapat) + `EmailVerifyBanner` (soft
    doğrulama uyarısı + resend, P3'ten ertelenen). Yeni `/offers/[token]` public
    sayfa (server view + `OfferActions` accept/decline + reason).
  - Caddy: `/offers/*` AÇIK. `/logout` Jinja'da kaldı (Next.js çıkışı BFF ile).
  - Verify: tsc ✅ · eslint ✅ · build ✅.
- **D7 P5 tam regresyon: 19 suite GREEN** (api_v1 47 + auth p1/p2/p3/p4/p5 + me +
  admin tüm + parent + institution + tenant)

## Kurum Yöneticisi — Program Uyum Panosu (2026-05-20)

**Bağlam:** Kullanıcı, kurum yöneticisi kimliğiyle paneli değerlendirdi. Tespit:
mevcut panel güçlü bir "gözlem kulesi" (aktivite/risk/tükenmişlik/kohort) ama
**çekirdek değeri (program → uyum → çıktı) yönetici görünürlüğü zayıf**. Öneri
kataloğundan **Program Uyum Panosu** seçildi (doğruluk % + boş-program dahil).

- **Kritik altyapı bulgusu (KURAL 1)**: Tamamlama verisi soru-adedi düzeyinde
  (`TaskBookItem.planned_count`/`completed_count`) **+ doğru/yanlış** (`correct_count`/
  `wrong_count`) zaten mevcut → "uydu mu" + "doğru mu yaptı" birlikte ölçülebilir.
  **Migration GEREKMEDİ.** Veri yapısı `tenant_health._compute_weekly_completion_rate`
  deseniyle birebir (Task + TaskBookItem + User.teacher_id); ek olarak `is_draft=False`
  (yayınlanmış program) filtresi.
- Servis `institution_compliance.py` — kurum özeti (rate + WoW delta + doğruluk +
  planlanan/yapılan soru) + haftalık trend (N hafta) + öğretmen kırılımı (rate +
  doğruluk + boş-öğrenci) + öğrenci dikkat listesi (en düşük 25) + boş-program
  (koç başına + örnek isim). Renk eşikleri D4 (≥70 emerald/≥40 amber/<40 rose).
  Gizlilik: öğrenci detay sayfası YOK (at-risk/burnout deseni).
- Endpoint `GET /api/v2/institution/compliance?weeks=8` (`_require_institution_admin`).
  `scripts/test_api_v2_institution_compliance.py` — **10/10 yeşil**.
- Frontend (emoji yok — Lucide): `/institution/compliance` route + `ComplianceClient`
  (4 KPI kartı + Recharts haftalık trend + öğretmen kırılım tablosu + öğrenci
  dikkat listesi + boş-program bölümü). Sidebar "Analiz → Program Uyumu" item
  (ClipboardCheck) en üste.
- Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon 10 suite GREEN.

**Kurum Yöneticisi Vizyon Paketleri (sırayla, kullanıcı 2026-05-20):**
KP1 Müdahale Merkezi ✅ · KP2 Öğretmen Etkililik Karnesi ✅ · KP3 Veli Güveni
Görünürlüğü ✅ · KP4 Akademik Çıktı/Deneme Takibi ✅ (KP4a öğretmen giriş ✅ ·
KP4b kurum panosu ✅) — **tüm KP vizyon paketleri tamamlandı**.

- **KP1 — Müdahale Merkezi** ✅ (2026-05-20, migration YOK):
  - `institution_action_center.py` — mevcut sinyalleri (compliance boş-program +
    düşük-uyum + `risk_analysis.bulk_risk_assessment`) tek önceliklendirilmiş
    aksiyon kartı listesinde toplar (attention_engine'in kurum-içi versiyonu).
    Eşik: boş 3+ kritik, uyum <40 uyarı / <25 kritik, risk high+critical.
  - `GET /api/v2/institution/action-center` · `test_api_v2_institution_action_center.py` 8/8 yeşil.
  - Frontend: `/institution/action-center` (3 özet + severity-renkli aksiyon
    kartları + kategori ikonu + öneri) · sidebar "Müdahale Merkezi" (Siren) en üste.
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon 8 suite GREEN.

- **KP2 — Öğretmen Etkililik Karnesi** ✅ (2026-05-20, migration YOK):
  - `institution_teacher_scorecard.py` — son N hafta birleşik etkililik skoru
    (0-100): %40 tamamlama + %25 doğruluk + %20 program disiplini (öğrenci başına
    haftalık planlanan soru / 50 hedef) + %15 düşük-risk. `institution_compliance`
    helper'larını (`_student_totals_for_week`/`_week_bounds`/`_rate`/`_accuracy`)
    + `risk_analysis.bulk_risk_assessment` reuse. burnout'un (kim yoruldu)
    çıktı-odaklı tamamlayıcısı (kim sonuç alıyor). Rozet: ≥75 Örnek/≥50 İyi/
    ≥30 Gelişmeli/<30 Dikkat.
  - `GET /api/v2/institution/teacher-scorecard?weeks=4` · `test_api_v2_institution_scorecard.py` 7/7 yeşil.
  - Frontend: `/institution/teacher-scorecard` (ortalama skor + en etkili koç +
    karne tablosu: skor bar/rozet + tamamlama/doğruluk/disiplin/risk) · sidebar
    "Analiz → Öğretmen Karnesi" (GraduationCap, Tükenmişlik'ten sonra).
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon 7 suite GREEN.

- **KP3 — Veli Güveni Görünürlüğü** ✅ (2026-05-20, migration YOK):
  - `institution_parent_trust.py` — kurum aktif öğrencileri üzerinden: veli
    kapsaması (ParentStudentLink), aktif veli (parent last_login son N gün),
    bekleyen davet (ParentInvitation consumed=null + süre>now), bildirim
    teslimatı (NotificationLog student_id kurum filtreli → sent/failed/suppressed
    + kanal kırılımı). notification_health'in kurum-filtreli versiyonu.
  - `GET /api/v2/institution/parent-trust?days=30` · `test_api_v2_institution_parent_trust.py` 9/9 yeşil.
  - Frontend: `/institution/parent-trust` (4 KPI: kapsama/aktif veli/bekleyen
    davet/bildirim başarısı + kanal teslim tablosu + düşük-kapsama uyarısı) ·
    sidebar "Analiz → Veli Güveni" (HeartHandshake, Haftalık Özet'ten sonra).
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon 8 suite GREEN.

- **KP4a — Akademik Çıktı / Deneme Takibi: ÖĞRETMEN GİRİŞ** ✅ (2026-05-20,
  **migration `r9s1v4w5v33p`**):
  - **Yeni özellik** (Jinja'da deneme sonucu modeli YOKTU — KURAL 1 parite için
    değil, mevcut öğretmen mimarisini anlamak için keşif yapıldı). Kullanıcı
    kararı: deneme sonucunu **öğretmen (koç)** girer · KP4'ü **KP4a (giriş) →
    KP4b (kurum panosu)** sırasına böl.
  - **Migration `r9s1v4w5v33p`** (down_revision q8r0u3v4u22o): `exam_results`
    tablosu. **Additive** — yalnız yeni tablo, mevcut veriyi ETKİLEMEZ,
    downgrade'li. `alembic upgrade head` uygulandı.
  - Model `app/models/exam_result.py` — `ExamResult` (student_id CASCADE +
    created_by_id SET NULL + title + exam_date + section[ExamSection enum] +
    total_correct/wrong/blank + net + subject_nets JSON-Text + note). Net hesabı
    `compute_net(correct, wrong, section)` = D − Y/ceza (LGS ceza=3, YKS=4, taban
    0). `section_penalty` helper. models/__init__ export.
  - Backend: `schemas/teacher.py` +8 model (ExamCreate/Result/Subject/Summary/
    SectionOption + StudentExamListResponse). `api_v2/teacher.py` +3 endpoint
    (`GET /students/{id}/exams` özet+liste · `POST /students/{id}/exams` net
    auto-hesap, ders kırılımı verilirse toplam türetilir · `DELETE /exams/{id}`)
    + `_get_owned_exam`/`_build_exam_row`/`_exam_section_options` helper'ları.
    Sahiplik 404 (cross-tenant/başka öğretmen sızdırmaz). invalidate
    `teacher:{id}:students:{sid}:exams`.
  - `scripts/test_api_v2_teacher_exams.py` — **16/16 yeşil**.
  - Frontend (emoji yok — Lucide): `lib/types/teacher.ts` +8 tip · `lib/api/teacher.ts`
    `studentExams` queryKey + `getTeacherStudentExams` fetcher · `use-teacher-mutations.ts`
    +useCreateExam/useDeleteExam · `student-exams-panel.tsx` (özet 4 KPI + net trend
    Recharts LineChart + deneme kartları: net/D-Y-B/section ton rozeti + açılır ders
    kırılımı tablosu + sil · ekleme dialog: Toplam/Ders-kırılımı mod seçici + canlı
    net önizleme + section sabit ton map purge-safe). Öğrenci detay sekmelerine
    "Denemeler" eklendi (Genel/Analitik/**Denemeler**/Kitaplar/Veliler).
  - Verify: tsc ✅ · eslint ✅ · build ✅ (`/teacher/students/[id]` derlendi).
  - **Regresyon notu**: 23-suite batch'te 3 suite (teacher_students/weekly_plan/
    parent_trust) Dalga 7 auth sertleştirmesinin `testclient` IP brute-force
    kontaminasyonu nedeniyle düştü; **üçü de tek başına yeşil** (14/14·14/14·9/9).
    KP4a regresyonu DEĞİL — büyük sıralı test koşusunda suite arası `SuspiciousIp`
    temizliği gerekir (exam smoke kendi cleanup'ında yapıyor).

- **KP4b — Akademik Çıktı / Deneme Takibi: KURUM PANOSU** ✅ (2026-05-20,
  migration YOK — veri KP4a `ExamResult`'tan gelir):
  - `institution_academic.py` — kurum aktif öğrencileri × ExamResult agregasyonu.
    **Net karşılaştırılabilirliği**: ham net sınava göre değişir (LGS ~90 soru,
    TYT 120) → kurum geneli/trend/koç karşılaştırması için **net başarı oranı**
    (`_net_pct` = net ÷ soru sayısı, %) kullanılır; section kırılımında ham ort
    net de gösterilir. Üretilen bloklar: özet (kapsama + ort net başarı + toplam/
    son30g deneme + trend deltası), sınav türü kırılımı (ham net + net başarı %),
    haftalık trend (net başarı %), öğretmen kırılımı (en yüksek üstte + son deneme
    tarihi), en çok gelişen/gerileyen öğrenci (≥2 deneme, ilk→son delta), deneme
    girmeyen (koç kırılımlı kapsama eksiği). Renk eşikleri D4 (≥70 emerald/≥40
    amber/<40 rose). Gizlilik: öğrenci adı görünür, detay sayfası YOK.
  - `GET /api/v2/institution/academic?weeks=8` · `_require_institution_admin` +
    `_get_institution_or_403` + `_institution_brief`. `schemas/institution.py`
    +7 model (AcademicSummary/Section/Trend/Teacher/Mover/NoExam + Response).
  - `scripts/test_api_v2_institution_academic.py` — **13/13 yeşil**.
  - Frontend (emoji yok — Lucide): `lib/types/institution.ts` +7 tip · `lib/api/institution.ts`
    `academic` queryKey + `getInstitutionAcademic` fetcher · `/institution/academic`
    route + `academic-client.tsx` (sade-dil "net başarı oranı" bilgi notu + 4 KPI
    + Recharts haftalık trend LineChart [connectNulls, 0-100 domain] + sınav türü
    tablosu + koç tablosu + gelişen/gerileyen 2 sütun + deneme girmeyen amber
    uyarı bölümü; PCT_TEXT sabit ton map purge-safe). Sidebar "Analiz → Akademik
    Çıktı" (LineChart ikon, Program Uyumu'ndan sonra).
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon (suite arası SuspiciousIp
    temizlikli) GREEN.

## Güvenlik düzeltmesi — kimlik formları `method="post"` (2026-05-20)

- **Sorun (kullanıcı bildirdi)**: Login formu JS hydrate olmadan submit edilince
  (dev'de ilk derleme yavaş / hydration yarışı) tarayıcı **native GET** yapıp
  `?email=...&password=...` ile şifreyi URL'ye koyuyordu (tarayıcı geçmişi /
  sunucu logu / referrer sızıntısı).
- **Kök neden**: react-hook-form `onSubmit` handler'ı hydration tamamlanmadan
  bağlanmıyor; form'da `method` yoktu → default GET.
- **Düzeltme**: TÜM kimlik/şifre formlarına `method="post"` eklendi (login +
  2FA + signup teacher/invite + password change/forgot/reset). Hydrate olunca
  `handleSubmit` preventDefault yapar (fetch ile çalışır); olmazsa native POST
  gövdede taşır — şifre **asla URL'ye düşmez**. **KURAL**: yeni kimlik formları
  daima `method="post"` ile yazılır.

## Anasayfa (vitrin) Next.js'e taşındı (2026-05-20)

- **Bağlam**: Kök `/` son Jinja içerikli sayfaydı (giriş yapmamışa pazarlama
  vitrini + feature_catalog A/B kartları). Kullanıcı "Next.js'te yeni tanıtım
  sayfası" + "UI'da son derece yaratıcı ol, sayfa mimarisini koru, görseli
  Next.js tasarım araçlarına bırak" dedi. KURAL 1: landing/index.html (1378) +
  _feature_card + 5 mockup + feature_catalog A/B servisi + telemetri sonuna
  kadar okundu, receipt + parite tablosu + plan onaylandı.
- **Mimari karar**: feature_catalog (A/B + strateji) + telemetry servisleri
  DOKUNULMADI — yeni public router AYNEN çağırır. Kartlar + variant + telemetri
  client tarafında (`/api/v2/landing`) yüklenir; anon session cookie (fc_sid)
  same-origin taşınır (Caddy prod / dev rewrite). FEATURE parity tam, VISUAL
  parity yok (emoji→Lucide, indigo/violet/fuchsia fresh palet).
- Backend: `api_v2/landing_public.py` (offers_public deseni, auth'suz) —
  `GET /api/v2/landing` (kartlar + variant_slug + ensure_session_id cookie) +
  `POST /api/v2/landing/telemetry` (record_event, KVKK hash, 204). __init__'e
  kayıt. `scripts/test_api_v2_landing_public.py` — **8/8 yeşil**.
- Frontend: `lib/types/landing.ts` + `lib/api/landing.ts` (fetcher + sendBeacon
  telemetri) + `components/landing/reveal.tsx` (Reveal + CountUp, IO-based) +
  `mockups.tsx` (5 mockup_type → React component map) + `landing-client.tsx`
  (10 bölüm: header/hero+DNA mock/trust marquee/dinamik feature kartları/stats
  CountUp/kurumlar B2B heatmap/nasıl çalışır 5 adım/paketler billing toggle/
  final CTA/footer; telemetri impression+view+demo_click). `app/page.tsx`
  Dalga 0 önizlemeyi DEĞİŞTİRDİ — server'da rol redirect (Jinja index() paritesi)
  + anonimde LandingClient.
- Caddy: `@root path /` → next:3000 (yalnız tam kök; /demos /kvkk /privacy Jinja
  fallback'te). next.config'e `/demos` rewrite (dev'de demo linki çalışsın).
  Jinja landing/index.html + /api/telemetry/event dead-code olarak kalır.
- **Kapsam dışı**: `/demos` video sayfası Jinja'da (kartların "Demo İzle" linki
  oraya gider, çalışır). İstenirse ayrı pakette taşınır.
- Verify: tsc ✅ · eslint ✅ · build ✅ (`/` dinamik) · regresyon 7 suite GREEN
  (landing 8/8 + feature_catalog + auth + institution + admin + parent + tenant).
- **Tasarım iterasyonları (2026-05-21, kullanıcı geri bildirimi)**:
  - **Marka paleti**: logodan (petrol labirent + altın figür) çıkarıldı →
    Tailwind `cyan` (petrol, #0e7490≈marka) + `amber` (altın) + sıcak nötrler.
    Eski indigo/violet markadan kopuktu. Gerçek logo `web/public/etutkoc-logo.png`
    (next/Image) header/footer/final-CTA + login'de kullanıldı; hepsi `/`'a tıklanır.
  - **Login logosu**: tıklanabilir (logout → /login → logo → anasayfa). KURAL:
    kimlik/landing sayfalarında logo daima `/`'a Link.
  - **Kaldırıldı**: "önde gelen koçlar" logo şeridi + sahte istatistik bandı
    (placeholder veriler).
  - **Özellikler = Bento grid** (kullanıcı seçimi): hero 2×2 (gradient+büyük
    mockup) + 3 dar + 1 geniş; fayda-odaklı başlık. İçerik DİNAMİK kalır
    (feature_catalog + A/B), telemetri korunur — sadece sunum düzeni.
  - **FOIC fix (kritik)**: `Reveal` IntersectionObserver+opacity-0 yerine saf
    CSS animasyonu (`.lp-reveal` globals.css) — içerik dinlenmede DAİMA görünür;
    hydrate gecikince hero kaybolmaz. KURAL: landing'de içerik gizleyen
    JS-bağımlı reveal yasak.
  - **force-light**: landing + login `.force-light` ile her zaman açık tema
    (koyu sistemde sabit cyan/beyaz + koyu token karışımı bozuluyordu).
  - **Zemin/kart ayrışması**: `--background` belirgin serin-gri (L91→L88) + `.lp-card`
    gerçek elevation gölgesi + `border-slate-200`. Soluk cyan-50 zeminler kaldırıldı.
  - **Logo → şeffaf SVG**: `etutkoc-logo.png` (krem kutulu) → vtracer ile **2 renk
    şeffaf SVG**. Amblem (`etutkoc-mark.svg`) metinden ayrıldı (tam kilit küçük
    boyutta okunmuyordu); paylaşılan **`components/brand-logo.tsx`** = amblem +
    "etütkoç·rotam" metni. Tüm shell'ler (site-header/teacher/institution/admin/
    parent) + auth sayfaları + landing bunu kullanır.
  - **KRİTİK proxy düzeltmesi**: `proxy.ts` (Next 16 middleware) statik dosyaları
    da auth'a sokup `/login`'e 307 redirect ediyordu → logo/görseller kırık. Artık
    statik uzantılar (svg/png/woff…) auth'suz geçer. **KURAL**: proxy statik
    varlıkları redirect etmemeli.

## Bağımsız Koç — Koçluk İşletme Modülü (2026-05-21)

**Bağlam:** Bağımsız koç = `TEACHER` + `institution_id` NULL = sistemin stratejik
bileşeni. Akademik araçları zengin ama **kendi işletmesi** için operasyonel/ticari
katman yoktu. Kullanıcıyla sorun fırtınası + ihtiyaç analizi → 4 paketlik yol
haritası (her biri ayrı migration + smoke + onay):
- **KS1 — Seans kaydı çekirdeği** ✅ (aşağıda)
- **KS2 — Tahsilat**: öğrenci başına ücret (genelde seans başı 2000-3000, aylık
  elden) + yapılan seans otomatik sayım + ödeme kaydı + "ayı kapat" + gelir panosu.
- **KS3 — Zahmetsiz yakalama** (2 alt-paket): **KS3a fotoğraf→metin** ✅ ·
  **KS3b ses→metin** ✅ (aşağıda). Kâğıt form fotoğrafı / sesli dikte → AI taslak
  doldur (3-tık ilkesi). Çok-modlu AI + KVKK rıza + medya saklanmaz.
- **KS4 — AI koçluk içgörüsü** ✅ (aşağıda): birikmiş seanslardan bir sonraki
  seans için özet + gündem + psikolog-vari ipuçları (sistem içinde, Claude).
- **İlke (kullanıcı):** teknoloji koçun zamanını çalmasın; veri girmek + sonuca
  ulaşmak en fazla 3 tık. Notlar yalnız koça özel (KVKK).

- **KS1 — Seans kaydı çekirdeği** ✅ (2026-05-21, **migration `s0t2w5x6w44q`**):
  - **Migration `s0t2w5x6w44q`** (down_revision r9s1v4w5v33p): `coaching_sessions`
    tablosu. **Additive**, downgrade'li, uygulandı.
  - Model `coaching_session.py` — `CoachingSession` (coach SET NULL + student CASCADE
    + session_date + **status** [done/postponed/cancelled/no_show] + duration/channel
    + agenda [zorunlu] + next_change + coach_note + mood 1-5 + tags JSON + **auto_snapshot
    JSON** [Kova 1, seans anında saklanır] + capture_source). 3 enum + label dict'leri.
  - **Senin "Haftalık Program Değerlendirme Formu" → 3 kova**: Kova 1 otomatik
    (study_dna/analytics/exam_result'tan: tamamlama %, hız, geride kalan ders, son
    net) → `auto_snapshot`; Kova 2 anlatı → coach_note (KS3'te ses/foto); Kova 3
    koç kararı → agenda (zorunlu) + next_change. Koç ~3 tık.
  - Backend: `schemas/teacher.py` +9 model · `api_v2/teacher.py` +6 endpoint
    (GET sessions [özet+timeline] · GET sessions/prefill [otomatik panel] · POST
    create [snapshot saklar] · GET/POST/DELETE detay) + helper'lar. Sahiplik 404.
  - `scripts/test_api_v2_teacher_sessions.py` — **14/14 yeşil**.
  - Frontend (emoji yok — Lucide): types +12 · api `studentSessions`/`sessionPrefill`
    + 2 fetcher · `use-teacher-mutations.ts` +useCreateSession/Update/Delete ·
    `student-sessions-panel.tsx` (özet 4 KPI + zaman çizelgesi + otomatik-panelli
    form: durum/kanal/süre/gündem[zorunlu]/not/değiştirilecek/ruh hali 1-5/etiketler)
    + öğrenci detayına **"Seanslar" sekmesi** (Genel/Analitik/Denemeler/**Seanslar**/
    Kitaplar/Veliler) + yazdırılabilir boş form (`(print)/teacher/students/[id]/
    sessions/print`, A4, senin form başlıkların).
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon (suite arası SuspiciousIp
    temizlikli) GREEN.

- **KS2 — Tahsilat (koç ↔ öğrenci)** ✅ (2026-05-21, **migration `t1u3x6y7x55r`**):
  - **Migration `t1u3x6y7x55r`** (down_revision s0t2w5x6w44q): `coach_student_rates`
    + `coach_payments`. **Additive**, downgrade'li, uygulandı.
  - Modeller `coach_billing.py` — `CoachStudentRate` (öğrenci başı seans ücreti,
    unique student_id, upsert) + `CoachPayment` (tutar/tarih/yöntem [cash/transfer/
    other]/period_month "YYYY-MM"/not). **Koç↔öğrenci** ilişkisi — platform↔koç
    `Invoice` (Owner-pattern admin) ile KARIŞTIRMA.
  - **Aylık hesap modelde DEĞİL — hesaplanır**: o ay status=DONE seans × ücret −
    o aya işlenen ödemeler = kalan. Ertelenen/iptal sayılmaz. "Ayı kapat" = kalan
    tutarı period_month'la ödeme girmek.
  - Backend: `schemas/teacher.py` +9 model · `api_v2/teacher.py` +6 endpoint
    (GET billing?month [aylık pano: öğrenci satırları + totals] · POST students/{id}/
    rate [upsert] · GET/POST students/{id}/payments · DELETE payments/{id}) +
    `_month_bounds`/`_payment_row`/`_get_owned_payment` helper. Sahiplik 404.
  - `scripts/test_api_v2_teacher_billing.py` — **15/15 yeşil**.
  - Frontend (emoji yok — Lucide): types +9 · api `billing`/`studentPayments`
    queryKey + 2 fetcher · `use-teacher-mutations.ts` +useSetRate/CreatePayment/
    DeletePayment · `/teacher/billing` sayfa + `billing-client.tsx` (ay seçici
    prev/next + 3 KPI [tahakkuk/tahsil/kalan] + tablo [öğrenci·seans·ücret·tahakkuk·
    ödenen·kalan·durum·işlem] + Ücret belirle dialog + Ödeme gir / **Ayı kapat**
    dialog [kalan ön-dolu]) + teacher-shell "Tahsilat" nav (Wallet).
  - Verify: tsc ✅ · eslint ✅ · build ✅ (`/teacher/billing`) · regresyon **12/12
    suite GREEN** (billing 15/15 + sessions + teacher + institution + admin +
    parent + auth + tenant).

- **KS3a — Fotoğraftan yakalama (foto→metin, AI taslak)** ✅ (2026-05-21,
  **migration `u2v4y7z8y66s`**):
  - **Migration `u2v4y7z8y66s`** (down_revision t1u3x6y7x55r): `users.ai_capture_consent_at`
    (nullable). **Additive**, downgrade'li, uygulandı. **Maliyet/KVKK planı kullanıcıya
    sunuldu + onaylandı** (foto-önce, ses KS3b'ye; rıza akışı uygun).
  - **KVKK kararı (kullanıcı 2026-05-21)**: el yazısı/not fotoğrafı yurt dışı alt-işleyene
    (Anthropic Claude) gönderildiğinden **açık rıza zorunlu** (`ai_capture_consent_at`).
    **Medya SAKLANMAZ** — bellekte işlenir, metne çevrilir, atılır. Yalnız koç görür.
  - **Kredi**: yeni `UsageKind.AI_SESSION_CAPTURE` (5 kredi). `usage_events.kind` plain
    VARCHAR (CHECK yok) → **migration gerekmedi**. `KIND_CREDITS` map'e eklendi.
    Bağımsız koç Owner-pattern: `consume_credits(owner=CreditOwner.for_user(coach))`.
  - Servis `ai_session_capture.py` — `parse_session_photo(image_base64, media_type)`
    → Claude **vision** (httpx, `ai_book_template` deseni: ANTHROPIC_API_URL +
    claude-haiku-4-5 + x-api-key) çok-modlu mesaj (image block + prompt) →
    `{agenda, coach_note, next_change, mood, tags}`. `AIInvalidResponse`/
    `AIServiceUnavailable` reuse. ALLOWED_MEDIA = jpeg/png/webp. Görsel kaydedilmez.
  - Backend: `schemas/teacher.py` +AiConsentResponse/ParsePhotoBody/SessionDraftResponse ·
    `api_v2/teacher.py` +GET/POST `/ai-consent` + POST `students/{id}/sessions/parse-photo`
    (consent yok→403 consent_required · boş→422 image_required · tür→422
    invalid_media_type · >7MB→422 image_too_large · CreditBlocked→402
    ai_credit_exhausted · AIInvalidResponse→422 photo_unreadable · AIServiceUnavailable→
    502 ai_unavailable). `_apply_session_body` capture_source set eder.
  - `scripts/test_api_v2_teacher_ai_capture.py` — **10/10 yeşil** (parse_session_photo
    monkeypatch — gerçek Claude çağrısı yok).
  - Frontend (emoji yok — Lucide): types +AiConsentResponse/SessionDraftResponse +
    CoachingSessionCreateBody.capture_source · api `aiConsent` key + getTeacherAiConsent ·
    `use-teacher-mutations.ts` +useSetAiConsent/useParseSessionPhoto (kod-bazlı toast;
    parse yan etkisiz → invalidate susturuldu) · `student-sessions-panel.tsx`'e
    **"Fotoğraftan doldur"** butonu (gizli file input, `capture=environment` mobil
    kamera) + **rıza modalı** (ShieldCheck: AI işleme + yurt dışı + saklanmaz +
    yalnız-koç açıklaması; onay→useSetAiConsent→parse) + parse sonucu **taslak →
    SessionForm prefill** (violet "AI okudu, kontrol edin" banner; kaydette
    capture_source=photo). İlk denemede rıza yoksa modal, sonra otomatik parse.
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon GREEN (ai_capture 10/10 +
    exams 16 + sessions 14 + billing 15 + teacher_read 12 + teacher_students 14 +
    tenant 29).

- **KS3b — Sesten yakalama (ses→metin, AI taslak)** ✅ (2026-05-21,
  **migration GEREKMEDİ**):
  - **Migration YOK**: rıza (`ai_capture_consent_at`, KS3a) + `capture_source`
    ("voice" değeri) + `usage_events.kind` plain VARCHAR (CHECK yok) zaten mevcut.
  - **KVKK**: ses kaydı da yurt dışı alt-işleyene gönderildiğinden KS3a rızası
    AYNEN kapsar (rıza metni "Anthropic, OpenAI" olarak genişletildi). **Ses
    SAKLANMAZ** — bellekte işlenir, metne çevrilir, atılır. Yalnız koç görür.
  - **Kredi**: yeni `UsageKind.AI_SESSION_VOICE` (**8 kredi** — Whisper STT +
    Claude yapılandırma = 2 çağrı, foto'nun 5 kredisinden pahalı; maliyet
    şeffaflığı). `KIND_CREDITS` + `USAGE_KIND_LABELS_TR` ("AI Seans Yakalama
    (Ses)") güncellendi; foto label'ı "(Foto)" oldu. AI_SESSION_CAPTURE yorumu
    "vision — foto (KS3a)" olarak netleştirildi.
  - Servis `ai_session_capture.py` (KS3a dosyasına eklendi):
    - `_claude_messages(content)` — Anthropic messages çağrısı tek helper'a
      refactor (foto vision + metin yapılandırma paylaşır).
    - `transcribe_audio(audio_base64, media_type)` → **OpenAI Whisper**
      (`whisper-1`, httpx multipart `files=` + `language=tr`, `OPENAI_API_KEY`
      env). ALLOWED_AUDIO = webm/mp4/ogg/mpeg/wav. Ses kaydedilmez.
    - `_structure_text_to_draft(transcript)` → Claude metin (`_TEXT_PROMPT`) →
      `{agenda, coach_note, next_change, mood, tags}`; boş yapılanırsa ham döküm
      coach_note'a fallback (veri kaybetme).
    - `parse_session_voice(audio, mt)` = transcribe → structure.
  - Backend: `schemas/teacher.py` +ParseVoiceBody · `api_v2/teacher.py`
    +POST `students/{id}/sessions/parse-voice` (consent yok→403 consent_required ·
    boş→422 audio_required · tür→422 invalid_media_type · >18MB→422 audio_too_large ·
    CreditBlocked→402 ai_credit_exhausted · AIInvalidResponse→422 voice_unreadable ·
    AIServiceUnavailable→502 ai_unavailable). consume_credits AI_SESSION_VOICE.
  - `scripts/test_api_v2_teacher_voice_capture.py` — **10/10 yeşil**
    (parse_session_voice monkeypatch — gerçek Whisper/Claude çağrısı yok).
  - Frontend (emoji yok — Lucide): `use-teacher-mutations.ts` +useParseSessionVoice
    (kod-bazlı toast; invalidate susturuldu) · `student-sessions-panel.tsx`'e
    **"Sesle doldur"** butonu (**MediaRecorder**: getUserMedia → kayıt → Durdur
    butonu + canlı süre sayacı m:ss → blob→base64; `pickAudioMime` webm/mp4/ogg
    desteklilik kontrolü) + paylaşılan rıza modalı (metin genişletildi) + parse
    sonucu **taslak → SessionForm prefill** (kaynak-bilinçli banner "AI sesinizi/
    fotoğrafı okudu"; kaydette `capture_source` foto/ses ayrı). `dispatch` ortak
    akış (foto+ses): rıza yoksa modal → onay → parse.
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon GREEN (voice 10/10 +
    ai_capture 10 + sessions 14 + billing 15 + exams 16 + admin_usage 21 + tenant 29).
  - **Yeni env (prod)**: `OPENAI_API_KEY` (Whisper). Tanımsızsa parse-voice 502
    ai_unavailable döner (özellik bozulmaz, diğer akışlar etkilenmez).

- **KS4 — AI koçluk içgörüsü** ✅ (2026-05-21, **migration `v3w5z8a9z77t`** —
  cache'li; KREDİ GÜVENLİĞİ revizyonu):
  - **Amaç (kullanıcı)**: "bugün şu öğrenciyle şunu konuş" — birikmiş seans
    notları + akademik durumdan koça bir sonraki seans için hazırlık. Öneri/
    taslak; yalnız koç görür; klinik teşhis değil (koçluk dili).
  - **KREDİ GÜVENLİĞİ (kullanıcı 2026-05-21 — kritik)**: içgörü **DB'ye cache'lenir**.
    İlk sürüm her görüntülemede Claude'a gidiyordu (her seferinde kredi) → düzeltildi.
    **Migration `v3w5z8a9z77t`** (down_revision u2v4y7z8y66s): `coaching_insights`
    tablosu (öğrenci başına TEK kayıt, unique). Additive, downgrade'li, uygulandı.
    - **GET** `students/{id}/coaching-insight` → cache'den okur, **KREDİ DÜŞMEZ**
      (insight null = henüz üretilmemiş).
    - **POST** `students/{id}/coaching-insight` → üret/**yenile**, **kredi düşer**,
      cache'i upsert eder (is_stale=False).
    - Seans create/update/delete → `_mark_insight_stale` cache'i `is_stale=True`
      yapar (AI çağrısı YOK; koça "yenile" önerilir).
  - **Kredi**: `UsageKind.AI_COACHING_INSIGHT` (**6 kredi** — tek Claude çağrısı,
    geniş bağlam). `KIND_CREDITS` + label ("AI Koçluk İçgörüsü").
  - Model `coaching_session.py`'a `CoachingInsight` (student_id unique + summary +
    3 JSON liste + based_on_sessions + is_stale + generated_at/by). models/__init__
    export.
  - Servis `ai_coaching_insight.py` — `generate_coaching_insight(student_name,
    sessions, academic)` → son ≤8 seans + akademik anlık görüntü
    (`_compute_session_prefill`) → Claude → `{summary, agenda_suggestions[],
    psychological_tips[], watch_outs[]}`. `_claude_messages` + `_extract_json_object`
    `ai_session_capture`'dan reuse. "Uydurma, yalnız notlara dayan, teşhis koyma".
  - Backend: `schemas/teacher.py` +CoachingInsightResponse (+generated_at) +
    CoachingInsightCacheResponse {insight, is_stale} · `api_v2/teacher.py` GET+POST
    + `_insight_to_response`/`_mark_insight_stale` helper'ları.
  - `scripts/test_api_v2_teacher_coaching_insight.py` — **11/11 yeşil**
    (GET ücretsiz · POST kredi=1 · GET tekrar kredi=1 · yeni seans→stale · POST
    yenile kredi=2; monkeypatch).
  - Frontend (emoji yok — Lucide): types +CoachingInsightCacheResponse · api
    `coachingInsight` queryKey + getTeacherCoachingInsight · `use-teacher-mutations.ts`
    `useGenerateCoachingInsight` (POST → setQueryData ile cache güncelle) ·
    `student-sessions-panel.tsx` "İçgörü" butonu dialog açar (ücretsiz GET);
    dialog: yoksa "İçgörü oluştur (kredi)" · varsa göster + stale ise amber uyarı +
    "Yenile (kredi)" + "Bu gündemle seans aç" (`draftSource="insight"`; capture_source
    YOK — manual). Rıza akışı tüm AI özelliklerine genelleştirildi
    (`gateConsent(action)` callback; modal metni foto/ses/seans notları +
    Anthropic+OpenAI). DraftSource = photo|voice|insight.
  - Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon GREEN (insight 11/11 +
    voice 10 + ai_capture 10 + sessions 14 + tenant 29).
  - **Koçluk İşletme Modülü (KS1-KS4) tamamlandı.** Bağımsız koç artık seans
    kaydı + tahsilat + zahmetsiz yakalama (foto/ses) + AI içgörü ile tam
    operasyonel/ticari katmana sahip.

- **AI özellikleri — kredi/paket notu (kullanıcı 2026-05-21, [[project-ai-credits-packaging]])**:
  AI özellikleri (foto/ses yakalama + içgörü) ileride **yalnız ücretli pakette**
  açık olacak; **trial/free → kapalı**; paket yükseltince açılır. Tüm AI çağrıları
  kullanıcının kendi kredisinden düşer. Bu kapı (entitlement) + paket yükseltme UI'ı
  **ücretlendirme/üyelik çalışmasında** yapılacak. API anahtarları (Anthropic/OpenAI)
  **süper adminde merkezi** yönetilecek (DB, env fallback) — Süper Admin Ayarlar paketi.

## AI Altyapısı — Süper Admin Anahtar + Ücretli Kapı + Simülasyon (2026-05-21, DEVAM EDİYOR)

**Bağlam (kullanıcı 2026-05-21):** KS3/KS4 AI özellikleri pahalı (gerçek Anthropic/
OpenAI çağrısı). 3 karar: (1) API anahtarları **süper adminde merkezi** yönetilsin
(DB şifreli, env fallback); (2) AI özellikleri **yalnız ücretli pakette**, trial/free
KAPALI, paket yükseltince açılsın; (3) gerçek anahtarla **uçtan uca ölçümlü simülasyon**.
Detaylı ücretlendirme/üyelik ileride ([[project-ai-credits-packaging]] memory'si).

**Paket A — KS4 kredi cache** ✅ (yukarıda KS4 bloğu — `coaching_insights` tablosu,
GET ücretsiz / POST kredi, migration `v3w5z8a9z77t`).

**Paket B — Süper Admin Merkezi AI Ayarları** ✅ (2026-05-21, **migration `w4x6a9b0a88u`**):
- Model `system_secrets` (name unique, value_encrypted, updated_by) — additive,
  downgrade'li, uygulandı. models/__init__ export `SystemSecret`.
- Servis `system_secrets.py`: **Fernet** şifreleme (anahtar `settings.session_secret`
  SHA256 türevi); `set_secret`/`delete_secret`/`get_db_value`/`mask`/`ai_settings_status`.
- **TEK SAĞLAYICI = GEMINI'YE GEÇİLDİ (kullanıcı 2026-05-21).** Anthropic/OpenAI
  kodu kaldırıldı; tüm AI işleri `app/services/gemini.py` üzerinden (generateContent,
  `responseMimeType=application/json`). Erişimciler: `get_gemini_paid_key()` /
  `get_gemini_free_keys()` (liste) / `get_gemini_model(paid)`.
- **KVKK key yönlendirmesi (kullanıcı kararı)**: öğrenci verili işler (foto/ses/içgörü)
  → `gemini.generate(personal_data=True)` = **ÜCRETLİ key** (no-training), fallback YOK.
  Kişisel-veri-içermeyen kitap şablonu → `personal_data=False` = ücretsiz key(ler)
  sırayla, kota (429) dolunca sıradakine, en son ücretliye.
- config.py: `gemini_paid_api_key` / `gemini_free_api_keys` (virgülle çoklu) /
  `gemini_paid_model` (vars. `gemini-2.5-pro`) / `gemini_free_model` (vars. `gemini-2.5-flash`).
- **AI servisleri Gemini'ye taşındı**: `ai_session_capture` (foto vision + **ses tek
  Gemini çağrısıyla** — Whisper ELENDİ) · `ai_coaching_insight` · `ai_book_template`
  (free→paid). Anahtar yoksa AIServiceUnavailable ("süper admin → AI Ayarları").
- `AuditAction.SYSTEM_SETTING_UPDATE` (değer ASLA loglanmaz).
- Endpoint'ler: GET `/admin/settings/ai` (anahtarlar maskeli + modeller düz + source) ·
  POST `/admin/settings/ai` (set, 400 invalid_setting/empty_value) · POST
  `/admin/settings/ai/{name}/delete`. schemas: AiSettingItem/AiSettingsResponse/SetAiSettingBody.
- `scripts/test_api_v2_admin_ai_settings.py` — **11/11 yeşil** (401/403 + şifreli
  roundtrip + get_gemini_* resolve + model config + delete).
- Frontend: types AiSetting* · api `aiSettings` key + getAdminAiSettings · use-admin-mutations
  +useSetAiSetting/useDeleteAiSetting · `/admin/settings` + `admin-ai-settings-client.tsx`
  (ücretli/ücretsiz key kartı maskeli + 2 model kartı düz + KVKK uyarısı) · admin-shell
  "Sistem → AI Ayarları".
- **.env değişken adları (kullanıcı bunları girecek)**: `GEMINI_PAID_API_KEY` (ilk/ücretli),
  `GEMINI_FREE_API_KEYS` (diğerleri/ücretsiz, virgülle), opsiyonel `GEMINI_PAID_MODEL` /
  `GEMINI_FREE_MODEL`. (Veya süper admin panelden.) Pillow + cryptography mevcut.
- Verify: tsc ✅ · eslint ✅ · build ✅.

**Paket C — AI ücretli paket kapısı (entitlement) + yükseltme** ✅ (2026-05-21, migration YOK):
- `plans.py`: `effective_plan_for_user(db, user)` (institution_id varsa Institution.plan,
  yoksa user.plan) + `ai_premium_allowed(db, user)` = `is_paid_plan(effective_plan)`.
  Ücretli = solo_pro/solo_elite/etut_standart/dershane_pro/enterprise; **trial/free →
  KAPALI** (is_paid_plan price!=0).
- `api_v2/teacher.py`: `_require_ai_premium(db, user)` → parse-photo + parse-voice +
  coaching-insight **POST**'una (sahiplik'ten sonra, consent/kredi'den önce) → 403
  `plan_upgrade_required`. GET cached insight ücretsiz okuma — gate YOK.
- `AiConsentResponse`'a `ai_premium` + `plan_code` eklendi (panel kilit göstergesi).
- **Self-serve yükseltme**: GET `/teacher/plan` (mevcut plan + solo seçenekleri +
  ai_premium) + POST `/teacher/plan/upgrade` (solo_pro|solo_elite, kurumlu → 403
  managed_by_institution, change_plan UPGRADE). **NOT: ödeme entegrasyonu (Stripe) ayrı
  iş — şimdilik doğrudan plan değişimi.**
- `scripts/test_api_v2_teacher_ai_entitlement.py` — **12/12 yeşil** (free/trial→403,
  paid→geçer, upgrade→açılır, kurumlu→403, geçersiz plan→400).
- Frontend: types +TeacherPlan* · api `plan` key + getTeacherPlan · use-teacher-mutations
  +useUpgradePlan + 3 AI hook'a `plan_upgrade_required` toast'ı · `student-sessions-panel`
  AI butonları kilitli (Lock ikon + "ücretli pakette" + amber banner → /teacher/plan) ·
  yeni `/teacher/plan` sayfa + `teacher-plan-client.tsx` (mevcut plan + 3 solo kart +
  yükselt confirm) · teacher-shell "Paket" nav (Gem).
- Verify: tsc ✅ · eslint ✅ · build ✅ · regresyon (entitlement 12 + ai_capture 10 +
  voice 10 + insight 11 + sessions 14 + api_keys 10 + admin 13 + tenant 29) GREEN.

**Paket D — Gerçek Gemini anahtarıyla simülasyon** ✅ (2026-05-21, GERÇEK çağrı doğrulandı):
- **`.env` kolaylığı**: tek `GEMINI_API_KEY`'e **virgülle** birden çok anahtar girilebilir
  → ilk = ücretli (öğrenci verisi), kalan = ücretsiz (kitap şablonu). Tek anahtar =
  hepsi ücretli. (Veya açık `GEMINI_PAID_API_KEY`/`GEMINI_FREE_API_KEYS` / süper admin.)
- **Gemini 503** (model yoğunluk) geçici → `gemini.py` kısa backoff retry (1.5s/3s).
- `scripts/simulate_ai_real.py` ile **gerçek** uçtan uca çalıştırıldı:
  - free koç (solo_free) → AI 403 (kapı), **maliyetsiz**.
  - paid koç → GERÇEK Gemini içgörü (6 kredi, kaliteli psikolog-vari çıktı) + cache GET
    ücretsiz (6→6) + sentetik formdan GERÇEK foto okuma (5 kredi). Toplam 11/50 kredi.
  - Ses: gerçek mikrofon kaydı gerektiğinden UI'dan test (Gemini tek çağrı).

**DURUM (2026-05-21):** A + B + C + D BİTTİ + **tek sağlayıcı Gemini geçişi BİTTİ**,
GERÇEK anahtarla doğrulandı. Smoke: ai_settings 11 + ai_capture 10 + voice 10 + insight 11
+ entitlement 12 + sessions 14 + admin 13 + tenant 29 + api_v1 47. tsc/eslint/build temiz.
Commit'ler: `94d9c92` (AI altyapı+Gemini+kapı) · `b2aaa43` (virgül-ayırma+503 retry) — pushed.
Migration'lar: `v3w5z8a9z77t` (coaching_insights), `w4x6a9b0a88u` (system_secrets) —
uygulandı, alembic head = `w4x6a9b0a88u`.

**UX iterasyonları (2026-05-22, kullanıcı geri bildirimi — pushed):**
- **`.env` GEMINI_API_KEY virgülle çoklu**: ilk=ücretli, kalan=ücretsiz (`_gemini_api_key_list`).
- **`.venv`'de cryptography eksikti** → AI 500; kuruldu + requirements'a eklendi.
- **Gemini 2.5 maxOutputTokens 2048→8192**: düşünme tokenı çıktıyı kesip JSON
  parse hatası veriyordu (AI ünite önerisi).
- **feature_flags cache ORM yerine düz veri**: commit sonrası detached ORM →
  DetachedInstanceError (is_enabled). Tüm is_enabled'ı etkiliyordu.
- **KS4 içgörü**: "Bu gündemle seans aç" butonu KALDIRILDI (erken "Yapıldı" seans
  yaratıyordu); içgörü yalnız okuma/hazırlık. Bayat uyarısı "N seansa dayanıyor,
  şu an M seans var" gösterir.
- **KS3b yeniden tasarım**: "Sesle doldur" üst butonu kaldırıldı → Yeni Seans
  formunda Gündem+Görüşme notu yanında **alan-bazlı 🎤 dikte** (SAF ses→metin,
  `POST /sessions/transcribe`, `UsageKind.AI_TRANSCRIBE`=3 kredi). "Fotoğraftan
  doldur" da form içine taşındı (tüm formu doldurur). Eski parse-voice (yapılandıran)
  kaldırıldı. Kredi: foto=5, dikte=3, içgörü=6.
- Commit'ler: `d954af4`/`94d9c92`/`b2aaa43`/`d373369`/`deb7345` (cryptography)/
  `3cecdd3` (feature_flags)/`3849985` (insight buton)/`0529903` (bayat banner)/
  `da91723` (token)/`dc79947` (dikte+foto form içine).

## Üyelik & Fiyatlandırma (2026-05-22, DEVAM EDİYOR)

**Onaylanan model (kullanıcı 2026-05-22):** Değer-bazlı. Solo öğrenci bandı:
ücretsiz 3 öğr · 1-5=2.000 · 6-15=4.000 · 16-30=6.000 · 30+ öğr başı +200 ₺/ay.
Kurum koç-başı (≤30 öğr/koç): Etüt 4.000/koç · Dershane 3.000/koç · Özel Okul/
Enterprise 2.500/koç + white-label; ücretsiz 2 öğretmen/20 öğrenci. Yıllık=10 ay
peşin. AI yalnız ücretli. Ödeme: **manuel aktivasyon** (Stripe/iyzico ertelendi).
Rakip kıyas: TR koçluk hizmeti 2.5-7.5K/ay; uluslararası tutor-SaaS ~$15-40/ay.

- **M1 ✅ tek kaynak** `app/services/pricing.py` (kod default + DB override) +
  public `GET /api/v2/pricing`. Hesaplayıcılar: compute_solo_monthly / 
  compute_institution_monthly / institution_tier_for_coaches. is_paid_plan_code.
  solo_pro sert öğrenci sınırı kaldırıldı (band-fiyatlı). Smoke 7/7.
- **M2 ✅ süper admin override** — `app_settings` tablosu (migration `x5y7b0c1b99v`,
  additive) + `app_settings.py` (generic JSON, kod default+DB). Süper admin
  GET/POST/reset `/admin/settings/pricing` → düzenleme her yere yansır (tek kaynak).
  UI `/admin/pricing` (Sistem nav). Koç Paket sayfası eski 299/599 kaldırıldı →
  /pricing linki (tutarlılık) + manuel aktivasyon notu. Smoke 8/8.
- **M3 ✅ public `/pricing` Next.js** — anasayfa kırık linki giderildi (proxy public
  allowlist + Caddy). Sekmeli (Koç/Kurum) + aylık/yıllık toggle, /api/v2/pricing'den.
- **M5 ✅ tek-kaynak pazarlama kopyası + anasayfa/`/pricing` birleşimi + kurumsal
  iletişim** (2026-05-22, **migration `y6z8c1d2c00w`** — contact_requests, additive):
  - **Tek kaynak kart kopyası**: `pricing.py` `_marketing_cards` → fayda-odaklı
    sade-dil 3 kart (free/solo/institution). Anasayfa + `/pricing` AYNI paylaşılan
    `PricingCards` bileşenini + `/api/v2/pricing`'i kullanır (tutarlılık). Anasayfa
    eski sabit-kodlu kartlar silindi.
  - **Solo kopyası sadeleşti** (eğitimci şıp diye anlasın): sınırsız öğrenci /
    "bugün şunu konuş" AI hazırlığı / sesle-fotoğrafla not / kopan öğrenci uyarısı /
    veli otomatik bildirim + net grafiği.
  - **Kurum kartı**: fiyat **kaldırıldı** ("Kurumunuza özel teklif") + ayrı **koyu
    slate** zemin (dikkat çeker) + CTA `/pricing?type=kurum#kurumsal`'a gider.
  - **Kurumsal iletişim akışı**: `/pricing?type=kurum` → kurum bölümüne kayar,
    fiyat yok, detaylı anlatım + **iletişim formu** + WhatsApp/telefon/e-posta
    alternatifi. Talep → `contact_requests` + satışa e-posta (`contact_request_admin.html`)
    + süper admin **İletişim Talepleri** sayfası (sayım/filtre/Yönet diyaloğu).
    Backend: model + public `POST /api/v2/contact` + admin GET/POST. Smoke
    `test_api_v2_contact.py` 11/11. İletişim ayarları `pricing.contact` (sales/
    support email + whatsapp/phone, boş→gizli) süper adminden doldurulabilir.
  - **14-gün uygulaması doğrulandı (kullanıcı sorusu)**: AI = `is_paid_plan`
    (trial/free dahil KAPALI, istek anında); öğrenci limiti `trial_expire` cron'u
    (`c1x7a0z1a00u`, günlük 00:15 UTC) ile solo_trial→solo_free düşünce sertleşir.
    Kısıt gerçek.
  - Verify: pricing 8/8 · contact 11/11 · tsc/eslint/build ✅ · admin 13/13 ·
    tenant 29/29.
- **M6 (P6) ✅ pakete duyarlı signup** (2026-05-22, frontend-only, migration YOK):
  - `/signup/teacher?plan=X` artık `/api/v2/pricing` kataloğundan okur (anasayfa
    kartıyla TUTARLI). Panel: seçilen Solo paketinin ad+tagline'ı + **"denemende
    hemen açık"** listesi (sınırsız öğrenci + tüm takip/veli/deneme — yapay zekâ
    HARİÇ) + ayrı **amber "Yapay zekâ — Solo aboneliğinde"** notu (dürüst: AI
    trial/free'de KAPALI) + "14 gün sonra Solo Ücretsiz'e (N öğrenci) düşer".
  - Eski yanıltıcı liste ("Yapay zeka plan şablonu / Veli WhatsApp" = 14 günde
    açık) kaldırıldı — AI ücretli gerçeğiyle çelişiyordu.
  - Panel hep Solo (pro) kartını gösterir (free/no-plan dahil; deneme Pro
    deneyimi verir). Kurum planıyla gelinirse `/pricing?type=kurum`'a yönlendiren
    bilgi bandı. Signup backend'i DEĞİŞMEDİ (solo trial açar; plan görüntüleme-
    amaçlı, aktivasyon manuel). Verify: tsc/eslint/build ✅.
- **P7 (firma bilgisi tamamlama) İPTAL** (kullanıcı 2026-05-22): bağımsız koça
  firma bilgisi gerekmez; kurumlar self-signup yapmaz (iletişim formundan gelir,
  süper admin panelden girilir). Yerine **Koç Trial Yaşam Döngüsü** işine geçildi.

### Koç Trial Yaşam Döngüsü (2026-05-22, DEVAM EDİYOR)

**Bağlam:** Üyelik sistemi yalnız bağımsız koçlar için. Simülasyonla
(`scripts/simulate_trial_lifecycle.py`) doğrulanan mevcut durum: signup→`solo_trial`
(14g sınırsız öğrenci, AI yok; `?plan` backend'de yok sayılıyor) → `expire_trials`
(günlük cron) `solo_free`'ye düşürür (3 sert sınır). **Öğrenciler PASİF OLMAZ** —
aktif kalır, sadece yeni eklenemez. **Trial bitiş uyarısı YOKTU** (ne banner ne
e-posta — `compute_trial_banner` yalnız ölü Jinja base.html'de).

**Onaylanan model (kullanıcı 2026-05-22):** tek "14 gün Pro deneme" (herkes alır,
AI kredi-tavanlı — *ayrı onay bekliyor*); 14 gün sonunda yükseltmezse **yumuşak
ödeme duvarı**: veri silinmez, öğrenciler görünür kalır ama limit aşıldıysa aktif
koçluk salt-okunur → koç ya yükseltir ya **kendisi 3 öğrenci tutup gerisini
arşivler** (sistem otomatik pasifleştirmez, "hangi 3" sorununu koç çözer).
**Zamanlama:** son 3 gün → banner + e-posta + offer + admin bildirimi; 14. gün →
pasiflik + ödeme duvarı.

- **Faz 1 ✅ Trial durum servisi + Next.js banner** (migration YOK):
  - `plans.solo_trial_status(db, user)` → is_solo/plan/trial_active/days_left/
    trial_critical(≤3g)/student_count/student_limit/over_limit/**paywall**/upgrade_target.
  - `GET /api/v2/teacher/trial-status` (`TrialStatusResponse`). Smoke
    `test_api_v2_teacher_trial_status.py` **6/6**.
  - `teacher-shell` üstünde `TrialBanner`: paywall (kırmızı, kapatılamaz →
    yükselt/arşivle) · son-3-gün (amber, kapatılabilir geri-sayım). Verify ✅.
- **Faz 2 ✅ proaktif uyarı** (migration YOK, yeni cron YOK):
  - `trial_notifications.py`: `send_trial_reminders` (≤3 gün koçlara "3 gün kaldı"
    e-postası + otomatik **DRAFT PLAN_UPGRADE teklifi** = süper admin CRM/360
    bildirimi; dedup = açık teklif varlığı) + `notify_trial_expired` ("deneme
    bitti" e-postası).
  - Mevcut **`trial_expire` günlük cron'una bağlandı** (cron_jobs): önce
    reminders → expire → expired e-postaları. `expire_trials` artık
    `expired_user_ids` döndürür.
  - E-posta şablonları: `trial_reminder.html` + `trial_expired.html`.
  - Smoke `test_trial_notifications.py` **4/4**; offers 19/19 + trial-status 6/6
    regresyon temiz.
- **Faz 3 ✅ yumuşak ödeme duvarı backend** (migration YOK):
  - `dependencies.assert_active_coaching(db, user)` → paywall aktifse (solo_free +
    limit aşıldı) 403 `paywall_active`. Çekirdek koçluk write'larına eklendi:
    teacher `POST /students/{id}/tasks` + `/bulk-tasks`, weekly_plan
    `publish-day` + `publish-week`. Salt-okuma + öğrenci pasifleştirme (limite
    inme) SERBEST → "arşivle akışı" mevcut `deactivate` ile çözülür.
  - Frontend: teacher mutations `paywall_active` → "Deneme bitti — paketi
    yükseltin" toast (banner Faz 1'de zaten var).
  - Smoke `test_api_v2_teacher_paywall.py` **5/5**; teacher_read 12 + weekly_plan
    14 + teacher_students 14 regresyon temiz.
- **Faz 4 ✅ AI-in-trial** (kullanıcı 2026-05-22: "50 kredi; tükenince ücretliye
  yönlendir; bitince AI iptal"; migration YOK):
  - `ai_premium_allowed` = ücretli plan **VEYA aktif solo_trial**. Deneme bitince
    (solo_free) AI gate kapanır (otomatik). `PLAN_ALLOCATIONS` solo planları
    explicit: solo_trial=50 (kredi tavanı), solo_free=50, solo_pro=500, solo_elite
    =2000 (pro/elite "yükselince daha fazla" — ücretlendirmede ayarlanabilir).
  - Akış: trial koç AI kullanır → consume_credits 50 havuzdan düşer → tükenince
    402 `ai_credit_exhausted` (frontend "yükselt" toast) → 14 gün bitince gate
    403 `plan_upgrade_required`.
  - `test_api_v2_teacher_ai_entitlement.py` **13/13** (trial→200 + tükenince→402 +
    free/expired→403 + paid→200 + upgrade); ai_capture 10 + insight 11 +
    trial-status 6 regresyon temiz.

### Abonelik Sistemi — uygulama-içi billing (2026-05-23, DEVAM EDİYOR)

**Bağlam (kullanıcı 2026-05-23):** Üye olmuş koç `/teacher/plan`'dan "Planları gör"
ile **public /pricing**'e (edinme/pazarlama sayfası, "14 gün ücretsiz dene")
gidiyordu — yanlış. Olgun SaaS ilkesi: **edinme (public /pricing) ≠ hesap yönetimi
(uygulama-içi abonelik)**. Onaylanan model: durum-bilinçli uygulama-içi abonelik +
ödeme/devam akışı + yenileme; public /pricing edinme-only kalır. Ödeme döngüsü
aylık + akademik yıl (/pricing ile tutarlı). Ödeme şimdilik MANUEL (Stripe sonra).

- **Faz 1 ✅ durum-bilinçli uygulama-içi abonelik ekranı** (migration YOK):
  - `/teacher/plan` artık **public /pricing'e yönlendirmiyor**; kendi içinde
    durum-bilinçli. `TeacherPlanResponse` +`status`(trialing/active/free/managed)
    +`student_count` +`solo_monthly_price`(öğrenci-bandı, pricing.py tek kaynak)
    +`annual_paid_months` +`sales_email`.
  - **Hata düzeltildi**: trial koça "Ücretli paketin aktif" diyordu (Faz4'te trial
    AI=açık olunca ai_premium ile karıştı) → artık trialing/active/free ayrı; AI
    rozeti "denemede açık (N gün)" / "açık" / "kapalı".
  - Frontend: Solo yükseltme kartı (aylık/akademik-yıl toggle, bant fiyatı, mevcut
    durum) + manuel-aktivasyon dialog (sales_email mailto). Verify tsc/eslint/build
    + entitlement 13/13 + trial-status 6/6.
- **Faz 2 ✅ ödeme/devam akışı** (manuel aktivasyon, migration YOK):
  - Koç: `/teacher/plan` "Öde ve devam et" → `POST /teacher/subscription-request`
    {plan, cycle} → `contact_requests`'e (source=`subscription_request`, mesajda
    plan/döngü/fiyat/koç_id) düşer; idempotent (bekleyen talep varsa tekrar
    yaratmaz). Dialog "Talebin alındı" durumu gösterir.
  - Süper admin: talep **İletişim Talepleri**'nde "Abonelik talebi (koç)" olarak
    görünür → ödeme alınınca admin user-detail'deki **Abonelik aktivasyonu**
    kartından `POST /admin/users/{id}/activate-plan` {plan} (yalnız solo koç;
    change_plan UPGRADE + audit). `AdminUserListItem`'a `plan` eklendi.
  - Smoke `test_api_v2_subscription_request.py` **11/11**; admin_users 25 +
    contact 11 + entitlement 13 regresyon temiz; tsc/eslint/build temiz.
- **Faz 3 ✅ solo abonelik durumu + yenileme** (**migration `z7a9d2e3d11x`** —
  users +subscription_status/period_end/cycle, additive nullable):
  - `activate-plan` artık `cycle` alır → ücretli planı active + period_end
    (aylık 30g / akademik yıl 365g) + cycle set eder; free → temizler. Admin
    kartına döngü seçici eklendi.
  - `/teacher/plan` aktif durumda **yenileme tarihi** gösterir.
  - `trial_notifications.process_renewals`: gün-3 yenileme hatırlatma e-postası +
    dönem sonu geçince `past_due` işaretle + "ödeme gerekli" e-postası. Mevcut
    `trial_expire` cron'una bağlandı. Şablonlar `renewal_reminder/overdue.html`.
  - **past_due → paywall**: `solo_trial_status` + `assert_active_coaching`
    past_due'yu da kapsar (koçluk write 403 paywall_active, mesaj "yenileme
    gerekli"); teacher-shell banner + /teacher/plan past_due durumu ("Aboneliğini
    yenile").
  - **İletişim Talepleri "koç sayfasına git" linki**: subscription_request'in
    mesajından `koç_id` parse edilip `linked_user_id` döner → admin tek tıkla
    koç user-detail'e gidip aktive eder.
  - Smoke `test_api_v2_subscription_renewal.py` **6/6**; subscription_request 11 +
    trial-status 6 + paywall 5 + entitlement 13 + admin_users 25 + trial_notif 4
    regresyon temiz; tsc/eslint/build temiz.
- **Bütüncül düzeltme** (2026-05-23, kullanıcı bildirdi — [[feedback-holistic-change-propagation]]):
  aktivasyonda `change_plan` `trial_ends_at`'i temizlemiyordu → koç solo_pro olsa
  bile is_trial_active True kalıp /teacher/plan + banner + AI rozeti "deneme"
  gösteriyordu. Düzeltildi: `change_plan` (USER+ücretli→trial temizle) + activate-plan
  (defensive). Admin SubscriptionCard artık durum rozeti (Aktif·yenileme/past_due/
  deneme) + "Güncelle/Yenile" butonu gösterir (`AdminUserListItem` +subscription_status/
  period_end/trial_active). renewal smoke 7/7 (trial-temizleme regresyonu dahil).
  **KURAL: bundan sonra bir alan/durum değişince etkilenen tüm yüzeyler aynı
  commit'te güncellenir.**
- **Abonelik iptal/geri-al** ✅ (2026-05-23, migration YOK): aktif abonede
  `/teacher/plan` "Aboneliği iptal et" (onaylı) → `subscription_status=canceled`
  (plan + erişim dönem sonuna kadar sürer) + "İptali geri al" (resume).
  `process_renewals` dönem sonunda canceled → **solo_free**'ye düşürür (past_due
  DEĞİL) + sub alanlarını temizler. Endpoint'ler `POST /teacher/subscription/
  cancel|resume`. Bütüncül: /teacher/plan (ActiveSubscriptionCard + StatusLine)
  + admin user-detail kartı "İptal edildi" rozeti + cron. renewal smoke **12/12**.
- **Admin dashboard kısayolları** ✅: `/admin`'de "Ticari & Ödemeler" (7) +
  "Sistem & Güvenlik" (4) kartları "YAKINDA"/disabled idi ama sayfalar mevcut →
  `disabled` kaldırıldı, tıklanır oldu. "Ödeme Takvimi" hedefi düzeltildi
  (`/admin/security-monitor/revenue/invoices`).
- **Ticari Pano (`/admin/security-monitor/revenue`) düzeltmeleri** ✅:
  - **Crash giderildi**: drill tablosu `key={institution_id}` mükerrer (owner-pattern/
    çoklu fatura) → `${institution_id}-${idx}`; 360 linki owner-aware `detail_url`.
  - **Okunabilirlik**: ödeme-takvimi bucket'larına açık metin rengi (rose/amber/
    emerald-900) — koyu temada beyaz-metin-açık-zemin görünmezliği giderildi.
  - **"7 gün içinde denemesi bitenler"** dar listeden belirgin kart-ızgarasına
    (gün-kaldı rozeti + owner-aware link) yükseltildi.
- **Teklif izleme + CRM şablon entegrasyonu** ✅ (2026-05-23, **migration `a8b1e3f4e22y`**):
  - **Teklif "açıldı" izleme**: `offers.viewed_at` (additive). Public `GET /offers/{token}`
    ilk açılışta doldurur → 360 Teklifler panelinde **"Açıldı: tarih" / "Henüz açılmadı"**
    + yanıt tarihi gösterilir (`OfferItem.viewed_at`). Admin artık "iletildi ama
    açtı mı?" sorusunu görebiliyor.
  - **Şablon → Aksiyon**: 360 "Yeni Aksiyon" formuna **"Şablondan doldur"** seçici
    (render endpoint owner placeholder'larını doldurur → kind/özet/detay otomatik aksar).
  - **Aksiyon Şablonları sayfası**: canlı **önizleme** (örnek koç verisiyle) +
    **tek-süslü `{...}` uyarısı** (yalnız `{{...}}` render edilir — kullanıcının
    `{trial_ends_at}` hatası önlenir).
  - **FIRE düzeltmesi**: past_due / limit-aşımı koçu öğrenci eklemeyi de artık
    paywall engelliyor (`_check_student_creation_quota`'ya `assert_active_coaching`).
    Önce sadece program/görev gate'liydi; öğrenci ekleme plan-kotasından geçiyordu.
  - **Kapsamlı simülasyon** `scripts/simulate_offer_action_flow.py`: teklif yaşam
    döngüsü (DRAFT kuyruk→gönder→açıldı→kabul) + 4 senaryo öğrenci-sayısı karar
    mekanizması + aksiyon merkezi sinyal yakalama. **Bulgular**: (a) öğrenciler
    asla otomatik pasifleşmez/silinmez — plan düşer, fazla öğrencide aktif koçluk
    kilitlenir, "hangi öğrenci"yi koç seçer; (b) **Aksiyon Merkezi KURUM-merkezli**
    (bağımsız koç orada görünmez; solo koç trial_reminder cron + Ticari Pano
    "denemesi bitenler"de yakalanır); (c) aksiyon = manuel görev/log, sistem
    otomatik aramaz/mesaj atmaz.
  - **Teklif kuyruk→onay→gönder sistemi VAR**: trial_reminder cron DRAFT teklif
    yaratır (kuyruk) → admin 360 Teklifler'de görür → "Gönder" → e-posta + public
    link → kullanıcı açar (viewed_at) → kabul/ret. (Eksik: admin DRAFT'ı
    göndermeden DÜZENLEYEMİYOR — iptal+yeniden oluştur gerekir.)
  - Verify: paywall 5/5 + offers 19/19 + renewal 12/12 + admin 13 + 360 18 +
    dashboard 11 + tenant 29; tsc/eslint/build temiz.
- **Faz 4 ⏳ Stripe/iyzico** otomatik yenileme (kart + auto-charge) — kalan tek faz.

Migration head: `a8b1e3f4e22y`. Commit'ler: `97b8075` (M1) · `8ca4871` (M3) ·
`df60ec0` (M2 backend) · `b0926a8` (M2 UI) · `854b0ec` (M1-M3 docs) ·
`8530ecb` (M5 tek-kaynak kopya + kurumsal iletişim) · `9c013b9` (M6 pakete duyarlı signup) ·
`62c1d7f`/`3a6738e`/`4cb7363`/`4eb9c80` (trial yaşam döngüsü Faz 1-4).

## Dalga 7 — KAPANIŞ (2026-05-20)

**5 rolün tamamı + auth/güvenlik Next.js'e taşındı. Strangler Fig tamamlandı.**
Caddy'de Next.js'e yönlenen path'ler: `/me` `/student` `/teacher` `/institution`
`/parent` `/admin` `/login` `/password/*` `/signup/*` `/verify-email/*` `/offers/*`
+ `/legal/kvkk-veli`. Jinja'da kalan: `/logout` (BFF logout kullanılıyor), `/kvkk`
`/privacy` `/legal/*` (hibrit), webhooks, /static, /healthz.

**D7 migration kayıtları:** `o6p8s1t2s00m` (P2 password_reset_tokens) ·
`p7q9t2u3t11n` (P3 email_verification + users.email_verified_at) ·
`q8r0u3v4u22o` (P4 totp + backup codes). Hepsi additive + downgrade'li, uygulandı.

**Yeni bağımlılıklar:** `pyotp` (backend, requirements.txt) · `qrcode.react`
(frontend, package.json).

## Sırada

**Açık iş kalmadı — tüm dalgalar (D0-D7) tamamlandı.** Olası sonraki adımlar
(kullanıcı onayına bağlı):
- **Canlı deploy doğrulama**: Caddy reload + manuel smoke (login/2FA/signup/
  forgot/oturum/teklif akışları canlı ortamda) — kullanıcının sorumluluğunda.
- **2FA zorunlu kılma** (şu an opsiyonel): istenirse admin rolleri için login
  duvarı eklenebilir.
- **Turnstile + SMTP prod yapılandırması**: `.env`'e `TURNSTILE_*` + `SMTP_*` +
  `EMAIL_ENABLED=true` (şu an log-only / CAPTCHA kapalı).
- **Jinja dead-code temizliği** — "Jinja'ya dokunma, kalsın" gereği yapılmıyor.

**Jinja dead-code** (teacher/institution/parent/admin route + template) — "Jinja'ya
dokunma, kalsın" gereği yapılmıyor.

## Notlar

- "feedback_lgs_workflow_decisions" + "feedback_lgs_ux_preferences" memory'lerini
  oku — UI tercihleri orada
- "project_jinja_features_to_preserve" memory'sinde Jinja'da olup taşınması
  gereken kritik özelliklerin envanteri var
- Önceki sohbetlerde alınan kararlar bu dosyaya not edilir; her paketin sonunda
  güncellenir.
