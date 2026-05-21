# MIGRATION_INVENTORY — FastAPI+Jinja → FastAPI(JSON) + Next.js

**Tarih:** 2026-05-18
**Hedef:** Mevcut sistemin tüm rota ve şablon yüzeyini Next.js geçişi için tek doğru envanter olarak donaktırmak.
**Tek doğru kaynak:** Bu dosya. Çelişki olursa kod kazanır; bu dosya derhâl güncellenir.

---

## 1) Genel Sayılar

| Metrik | Sayı |
|---|---|
| Toplam route modülü (app/routes) | 40 |
| Toplam endpoint (api_v1 dahil değil) | **~241** |
| Mevcut JSON endpoint (`/api/v1/*`) | 14 (auth + student + teacher) |
| Toplam Jinja şablonu (app/templates) | **188** |
| → Tam sayfa (React'e taşınacak) | 116 |
| → HTMX fragment (component'e gömülecek) | 35 |
| → Hibrit kalıcı (email + print + KVKK) | 26 |
| → Macro / base | 3 |
| → Yardımcı/diğer | ~8 |

---

## 2) Endpoint Envanteri (özet)

> Tam tablo `MIGRATION_INVENTORY_FULL.csv` olarak ayrıca üretilecek (kodlama aşamasında); aşağıda **modül bazlı özet + öncelik atama** sunulur.

### 2.1 Sözlük
- `response_type` = `jinja` / `json` / `redirect` / `html-raw` (HTMX fragment) / `stream/file` / `plain`
- `htmx_partial` = `template/partials/` altında veya küçük HTML parçası
- **complexity:** salt okuma = low / mutasyon + tek service = med / çoklu service + OOB + sidebar update = high

### 2.2 Modül × Özet Tablosu

| Modül | Endpoint | Rol | Ortalama complexity | Side-effect | Göç dalgası |
|---|---|---|---|---|---|
| `auth.py` | 3 (login/logout) | public + get_current_user | high (lockout, captcha, security_monitor) | audit_log + active_session | Dalga 6 (Auth) |
| `signup.py` | 4 (teacher signup + invite accept) | public | med | audit, plans, quotas | Dalga 6 |
| `password.py` | 2 (change form + submit) | require_user | high (breach check, lockout) | audit, security_monitor | Dalga 6 |
| `me.py` | 4 (KVKK self-serve) | get_current_user | low–med | kvkk request log | Dalga 1 |
| `health.py` | 1 (/healthz) | public | low | — | DOKUNULMAZ |
| `kvkk_public.py` | 2 (info, privacy) | public | low | — | HİBRİT (Jinja kalır) |
| `offers_public.py` | 3 (token-bazlı teklif kabul/ret) | public | low | offers, audit | Dalga 7 |
| `whatsapp_webhook.py` | 2 (verify + callback) | public (HMAC imzalı) | med | notification_log UPDATE | DOKUNULMAZ |
| `partials.py` | 2 (pending count fragments) | get_current_user | low | request_service | Dalga 3 (React polling'e döner) |
| `student.py` | 10 | require_student | high (task complete OOB + sidebar) | task_service, event_triggers, gamification | **Dalga 2** |
| `student_requests.py` | 7 (change/replace/remove/add/question + withdraw) | require_student | low | request_service | Dalga 2 |
| `focus.py` | 7 (pomodoro start/end + badges + teacher view) | get_current_user / require_teacher | low–med | pomodoro, gamification | Dalga 2 |
| `dna.py` | 5 (chronotype + burnout heatmap) | mixed roller | low–med | study_dna, burnout, dna_parent_message | Dalga 2/3/5 |
| `goals.py` | 12 (hedef ağacı 4 rolde) | mixed | low–med | goals, goals_progress | Dalga 3 |
| `review.py` | 5 (FSRS spaced repetition) | mixed | low–med | review_scheduler, fsrs | Dalga 2/3 |
| `parent.py` | 13 (davet + dashboard + WhatsApp doğrulama) | mixed | med | parent_invitation, email, security (OTP), whatsapp | Dalga 5 |
| `teacher_dashboard.py` | 1 | require_teacher | **high** | analytics, risk_analysis, request_service, credits | **Dalga 4** |
| `teacher_students.py` | 12 (CRUD + CSV import + pause/resume) | require_teacher | med–high | quotas, plans, audit, csv_import, pause | Dalga 3 |
| `teacher_student_detail.py` | 3 (detay + kitap atama + veli notu) | require_teacher | high | event_triggers, audit, email_service | Dalga 3 |
| `teacher_program.py` | 13 (haftalık program + day-card OOB + week notes + book grid) | require_teacher | **high** (en yoğun HTMX) | suggestions, task_service, review_scheduler | **Dalga 3** |
| `teacher_tasks.py` | 9 (task CRUD + publish + reorder) | require_teacher | high (OOB swap her response) | task_service | Dalga 3 |
| `teacher_requests.py` | 4 (approve/reject/respond) | require_teacher | med | request_service, audit, **e-posta tetik** | Dalga 3 |
| `teacher_suggestions.py` | 4 (kabul/reddet/topluca) | require_teacher | high (OOB) | suggestions, task_service, audit | Dalga 3 |
| `teacher_diagnostics.py` | 1 | require_teacher | med | suggestions | Dalga 3 |
| `teacher_books.py` | 16 (kitap CRUD + bölüm + AI öneri + template) | require_teacher | med (HTMX yoğun) | ai_insights, event_triggers, audit | Dalga 3 |
| `teacher_book_sets.py` | 7 (set CRUD) | require_teacher | low | — | Dalga 3 |
| `teacher_years.py` | 5 (akademik yıl + phase) | require_teacher | low | — | Dalga 3 |
| `teacher_parents.py` | 3 (davet/iptal/unlink) | require_teacher | med | parent_invitation, email, audit | Dalga 5 |
| `teacher_settings.py` | 4 (ayarlar + cron + test mail) | require_teacher | low | email_service | Dalga 3 |
| `teacher_ai_insights.py` | 1 | require_teacher | med | ai_insights | Dalga 3 |
| `at_risk.py` | 4 (öğretmen + kurum panel + mute) | mixed | med | risk_analysis, institution_view | Dalga 4 |
| `plans.py` | 5 (pricing + my-plan + addons) | mixed | med | plans, addons (mock ödeme) | **Dalga 7** |
| `institution.py` | 22 (kurum dashboard + roster + invitation + cohorts + heatmap + quota + subscription) | require_institution_admin | med–high | institution_view, parent_invitation, email, plans, audit | **Dalga 4** |
| `admin.py` | **~110** (kurum/kullanıcı/feature catalog/revenue/security monitor/audit/CRM/kampanya/teklif) | get_current_super_admin | high | tenant_health, offers, audit, security_monitor, email | **Dalga 5** |

### 2.3 Şablon Sınıflandırma

| Sınıf | Sayı | Karar |
|---|---|---|
| **REACT'E** | 116 | Next.js sayfası |
| **PARTIAL (HTMX fragment)** | 35 | React component'e gömülür, JSON endpoint'e bağlı |
| **HİBRİT KALICI** | 26 (email 18 + print 5 + legal 3) | Jinja'da kalır, FastAPI render eder |
| **MACRO/BASE** | 3 (base.html, _macros.html, _macros/section_panel.html) | React'te `<Layout>` + `<SectionPanel>` component'i olur |

---

## 3) HTMX Deseni → React Karşılığı

| HTMX Deseni | Örnek (file:line) | React Karşılığı |
|---|---|---|
| `hx-swap-oob` (out-of-band, birden çok bölge) | `teacher/partials/week_draft_oob.html:14`, `student/partials/task_update_response.html:4,8` | TanStack Query `invalidateQueries(['xxx'])` + bağlı tüm component'ler otomatik yeniden çeker. Tek response'ta nested JSON dönmek yerine, mutation success'te 2-3 query invalidate edilir. |
| `hx-target` + `hx-swap` (sayfa içi parça) | `student/day.html:92-95`, `task_card.html:22-26` | React state + `useMutation` + optimistic update |
| `hx-trigger="every Ns"` (polling) | `base.html:576` (30s öğretmen), `base.html:591` (60s öğrenci), `admin/security_monitor_live.html:42` (5s) | TanStack Query `refetchInterval: N*1000` veya WebSocket (sonradan) |
| `hx-on::after-settle` (DOM hazır olunca JS) | `base.html:890-901` (book-grid modal aç) | useEffect with mutation callback / onSuccess |
| `<dialog>` + `showModal()` | `task_comm_modal.html`, `base.html:845-847` (book-grid-dialog) | Radix Dialog (shadcn) |
| Sticky sidebar (XL breakpoint) | `student/day.html:161` | CSS Grid + `position: sticky` (aynı sınıf) |
| Form HTMX submit + flash banner (`?err=`, `?ok=`) | `task_card.html`, çoğu redirect | sonner/react-hot-toast + url search params yerine state |
| Cascading select (ders→kitap→ünite) | `student/day.html`, `teacher_program.py` cascading routes | React Hook Form + watch + `enabled: !!subject` query |

### 3.1 OOB Swap Kullanan Yüksek Riskli Rotalar

Bu 11 rota mutasyon sonrası **birden fazla bölgeyi** atomik günceller. Next.js'te eşdeğer kalite için **mutation success → query invalidation listesi** her birinde belgelenmeli:

1. `POST /student/tasks/{task_id}/complete` → task card + sidebar (kaynak durumu) + day summary
2. `POST /student/tasks/{task_id}/uncomplete` → aynı 3 bölge
3. `POST /student/tasks/{task_id}/items/{item_id}/set-completed` → aynı 3 bölge
4. `POST /teacher/students/{sid}/tasks` → day card + week draft badge
5. `POST /teacher/students/{sid}/publish-day` → day card + week draft badge
6. `POST /teacher/tasks/{task_id}/delete` → day card + week draft badge
7. `POST /teacher/tasks/{task_id}/edit` → day card + week draft badge
8. `POST /teacher/students/{sid}/suggestions/accept` → day card + week draft badge + suggestions panel
9. `POST /teacher/students/{sid}/suggestions/accept-all` → day card + week draft badge + suggestions panel
10. `GET /teacher/students/{sid}/week/day-card` → day card + week draft badge OOB
11. `POST /teacher/students/{sid}/week-notes/add` → not satırı + hafta özeti

**Migration kuralı:** Bu 11 rotanın v2 karşılığı (mutation endpoint), response gövdesinde **etkilenen ekran bölgelerinin listesini** açıkça döndürür:
```json
{ "data": {...}, "invalidate": ["task:42", "sidebar:student:7", "day-summary:2026-05-18"] }
```
Next.js tarafı bunu okur ve TanStack Query'de eşleşen query key'leri invalidate eder. (Bu, App Router caching'in bayatlamasını önlemenin **birincil mekanizması** — bkz. MIGRATION_RISKS R-007.)

---

## 4) Service Bağımlılık Haritası

Her route'un dokunduğu service ve yan etki, geçişte **dokunulmaz** olarak işaretlenir.

### 4.1 Yan Etki Üreten Service'ler (KORUNACAK)

| Service | Ne yapar | Dış sistem | Tetiği olan endpoint sayısı | Risk |
|---|---|---|---|---|
| `email_service` | SMTP veya log-only mail | SMTP | ~15 | YÜKSEK — talep onayı/red, davet, dunning |
| `whatsapp.py` | Meta Graph API template mesajı | Meta API v21 | ~5 | YÜKSEK — onaylı şablon adı sabit |
| `notification_producer` / `notification_dispatcher` | `notification_log` queue producer/consumer | dolaylı (SMTP+WA) | 0 doğrudan, cron tetikli | YÜKSEK |
| `request_service` | task_request approve → auto-rebalance + reserve | DB only | ~10 | YÜKSEK — iş mantığı kalbi |
| `task_service` | Görev CRUD + Model C rezerv invariant | DB | ~15 | YÜKSEK — `reserved + completed ≤ test_count` invariant |
| `analytics` | snapshot, projection, DOW forward walk | DB | ~10 | ORTA |
| `suggestions` | öneri üretimi, accept/reject feedback | DB | ~6 | ORTA |
| `event_triggers` | parent notification olayı producer'a verir | DB→queue | ~10 | YÜKSEK |
| `credits` | kredi kontrol + tüketim + aylık refill | DB | her AI/WA/email çağrısında | YÜKSEK |
| `plans` / `subscription` | trial expire, pause, guarantee, akademik yıl geçişi | DB | ~10 + cron | YÜKSEK |
| `security_monitor` | lockout, IP block, brute-force | DB | ~5 (auth) | YÜKSEK |
| `audit` | audit_log INSERT | DB | ~140 (yarısından fazlası) | YÜKSEK |
| `parent_invitation` | token üret, doğrula, consume | DB | 4 | ORTA |
| `offers` | revenue offer flow (token kabul/ret) | DB | 6 | ORTA |
| `ai_insights` | AI panel + kitap bölüm önerisi | (AI kullanıyorsa dış) | 2 | ORTA |
| `feature_flags` | per-tenant flag kontrol | DB + cache 60s | tüm jinja context | ORTA |
| `announcements` | duyuru görüntüleme | DB + cache 60s | tüm jinja context | DÜŞÜK |
| `kvkk` | data export + silme talebi | DB | 4 | DÜŞÜK |

### 4.2 Cron Job Kaydı (DOKUNULMAZ — Next.js bunlardan habersiz)

`app/services/cron_jobs.py:JOB_REGISTRY` — 19 job. Önemliler:
- `daily_summary` 06:00 UTC, `weekly_backstop` 23:55, `drop_alert` Pzt 06:00, `exam_approaching` 04:00
- `credits_monthly_refill` ayın 1'i 00:30, `trial_expire` 00:15 günlük
- `dunning_send_reminders` 09:00 günlük (D-7, D-3, D-1, D+1, D+3, D+7)
- `subscription_resume` 01:00, `subscription_guarantee_eval` Pzt 06:00
- `auto_pause_inactive_users` 02:15, `audit_cleanup` 03:00
- `admin_weekly_digest` Pzt 09:00
- `security_alarm_evaluate`, `abuse_scan`, `error_event_retention`, `slow_request_retention`, `health_snapshot_daily`, `addons_monthly_renewal`, `kvkk_apply_expired_deletions`

> **Karar:** Cron + dispatcher tek bir FastAPI worker'ında kalır (mevcut). Next.js içinde **hiç cron yoktur**. Bu sözleşme MIGRATION_RISKS R-011'de izlenir.

### 4.3 Webhook Kaydı (DOKUNULMAZ — Meta tarafı sabit URL)

- `GET /webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=...` (Meta verify)
- `POST /webhooks/whatsapp` (status callback, HMAC-SHA256 imza: `X-Hub-Signature-256`)

Bu yol Meta Business Manager'da kayıtlı; **path değiştirilemez**. Reverse proxy bu path'i her zaman FastAPI'ye verir.

### 4.4 Ödeme Durumu

- **Şu an hiçbir ödeme sağlayıcı entegrasyonu yok** (Stripe/iyzico değil). `plans.py` "mock ödeme" — kullanıcı plan seçer, `PlanChangeHistory` yazılır, ücretsiz uygulanır.
- `invoice` tablosu hazır (status, due_at, attempt_count, last_reminder_kind).
- `dunning_send_reminders` cron'u faturayı **mail** ile hatırlatır (gerçek tahsilat yapmaz).
- **Geçişte yapılacak:** Hiç. Ödeme sağlayıcı eklendiğinde webhook endpoint'i (`/webhooks/stripe` veya `/webhooks/iyzico`) FastAPI'ye gelir, Next.js'in iş bilmediği bir akış olur.

---

## 5) Hibrit Kalıcı (Asla Next.js'e Taşımayacaklarımız)

### 5.1 Email Şablonları — 18 dosya (Jinja → SMTP)
`parent_invitation`, `parent_daily_summary`, `parent_weekly_report`, `parent_drop_alert`, `parent_empty_day_alert`, `parent_exam_approaching`, `parent_new_program`, `parent_teacher_note`, `teacher_new_request`, `student_request_approved`, `student_request_rejected`, `student_question_answered`, `admin_weekly_summary`, `credit_warning`, `dunning_reminder` (varsa), `offer_invitation` (varsa), `security_super_admin_login` (varsa), `security_alarm_triggered` (varsa).

> İlk satır `Subject: ...`, geri kalan HTML body. Plain text fallback regex ile. **FastAPI render eder, SMTP üzerinden gider. Bitti.**

### 5.2 Print Sayfaları — 5 dosya
- `student/week_print.html` (A4 portrait)
- `student/weekly_report_print.html` (veli için)
- `institution/cohorts_print.html`
- `institution/at_risk_print.html`
- `institution/activity_heatmap_print.html` (A4 landscape)

> `@media print` + `.no-print` + `@page { size: A4 ...; }` + `-webkit-print-color-adjust: exact`. Next.js'te yapmaya değmez.

### 5.3 Legal/KVKK — 3 dosya
- `kvkk/info.html`, `kvkk/privacy.html`, `legal/kvkk_parent.html`

> Statik metinler, SEO'ya açık. FastAPI render edip cache header'ı koyar.

### 5.4 Public Token Sayfaları (KARAR BEKLİYOR)
- `parent/invitation_accept.html` + `_invalid.html`
- `auth/signup_invite.html` + `_unusable.html` + `_logged_in.html`
- `offers_public/view.html`

> Bunlar oturumsuz erişilen token-bazlı landing sayfaları. **Önerim:** Next.js'e taşımak (form kullanıcı deneyimi için). Ama email içindeki linklerin değişmesi gerekir. Geçişin son dalgasında kararlaştırılır.

---

## 6) Göç Dalgaları (Sıra ve Bağımlılık)

Her dalga bağımsız PR. Önceki dalga olmadan sonraki başlayabilir mi diye not düşülmüştür.

| # | Dalga | Modüller | Bağımlılık | Tahmini efor | Risk |
|---|---|---|---|---|---|
| 1 | **`/me` profil + KVKK self-serve** | me.py | yok | 1-2 gün | DÜŞÜK |
| 2 | **Öğrenci paneli** | student.py + student_requests.py + focus.py + dna.py (öğrenci tarafı) + review.py (öğrenci tarafı) + goals.py (öğrenci tarafı) | yok (api_v1 zaten student için var) | 4-6 gün | ORTA (OOB swap) |
| 3 | **Öğretmen paneli** | teacher_dashboard.py + teacher_students.py + teacher_student_detail.py + teacher_program.py + teacher_tasks.py + teacher_requests.py + teacher_suggestions.py + teacher_diagnostics.py + teacher_books.py + teacher_book_sets.py + teacher_years.py + teacher_settings.py + teacher_ai_insights.py + at_risk.py (teacher tarafı) + goals.py (öğretmen) + review.py (öğretmen) + dna.py (öğretmen) | Dalga 2 yeşil olmalı (OOB pattern olgunlaşmış olur) | 8-10 gün | YÜKSEK (HTMX yoğun, OOB) |
| 4 | **Kurum yönetici paneli** | institution.py + at_risk.py (institution tarafı) | Dalga 3 (öğretmen view'lerine read-only erişim gerek) | 4-5 gün | ORTA (tenant isolation testleri) |
| 5 | **Süper admin paneli** | admin.py (~110 endpoint) | Dalga 4 | 6-8 gün | YÜKSEK (revenue + security monitor + impersonation) |
| 6 | **Parent paneli** | parent.py + teacher_parents.py + goals.py (veli) | yok | 3-4 gün | ORTA (WhatsApp OTP + KVKK akışı) |
| 7 | **Auth + signup + password** | auth.py + signup.py + password.py + offers_public.py | Dalga 1-6'nın hepsi (BFF cookie hazır olmalı) | 4-5 gün | **YÜKSEK** (kullanıcı onayına stop edilir) |
| 8 | **Plans + ödeme** | plans.py | Dalga 7 sonrası (auth olgunlaşınca) | 2-3 gün | YÜKSEK (ödeme sağlayıcı eklenirse ayrı planlanır) |
| 9 | **Eski Jinja temizlik** | tüm Jinja sayfalarının sökümü; sadece hibrit kalıcı (email/print/legal) kalır | Dalga 1-8 yeşil | 1-2 gün | DÜŞÜK |

**Toplam:** ~36-45 iş günü (tek developer, riskli sprint'lerde durma süreleri dahil değil).

### 6.1 Dalga 0 (paralel) — Altyapı, bu envanterden hemen başlar

- Monorepo `/web` klasör yapısı (Next.js 15 App Router + TypeScript + Tailwind + shadcn init)
- `/api/v2` namespace iskeleti + `dependencies.py` (BFF cookie + JWT dual auth)
- BFF cookie auth akışı (`__Host-access` + `__Host-refresh`, refresh proxy route)
- Reverse proxy konfigürasyonu (Nginx + Docker Compose, path-based)
- OpenAPI → TypeScript codegen pipeline (`openapi-typescript`)
- Shadcn tema sözleşmesi (renkler + tipografi + spacing + section_panel macro → React component) — **kullanıcının "yamalı görünmesin" kırmızı çizgisinin** somutlanması

---

## 7) Side-by-side: Eski → Yeni URL Sözleşmesi

Reverse proxy bu path'leri Next.js'e açar; eski Jinja yolları aynı path'te FastAPI'de **soft-deprecated** kalır (kapatılmaz, sadece proxy'den geçmez). Her dalga sonrası eski handler **silinmez**, sadece pasifleştirilir (`@router.get(..., include_in_schema=False)` veya feature flag).

```
/me/account          → Next.js
/student/*           → Next.js (Dalga 2)
/teacher/*           → Next.js (Dalga 3)
/institution/*       → Next.js (Dalga 4)
/admin/*             → Next.js (Dalga 5)
/parent/*            → Next.js (Dalga 6)
/login, /logout      → Next.js (Dalga 7)
/signup/*            → Next.js (Dalga 7)
/password/change     → Next.js (Dalga 7)
/pricing, /plans/*   → Next.js (Dalga 8)
/api/v1/*            → FastAPI (DOKUNULMAZ — native mobile)
/api/v2/*            → FastAPI (Next.js tüketir)
/healthz             → FastAPI (DOKUNULMAZ)
/webhooks/*          → FastAPI (DOKUNULMAZ)
/kvkk, /privacy      → FastAPI (HİBRİT)
/legal/kvkk-veli     → FastAPI (HİBRİT)
/static/*            → FastAPI veya CDN
/parent/invitation/{token}    → Dalga 6 sonu değerlendirilir
/signup/invite/{token}        → Dalga 7 sonu değerlendirilir
/offers/{token}               → Dalga 7 sonu değerlendirilir
/*_print, /emails/*           → FastAPI (HİBRİT)
```

---

## 8) Mevcut API v1 ile İlişki

`/api/v1/*` 14 endpoint native mobile için **kontrat dondurulmuş** (47/47 smoke PASS). Geçişte:

- v1 **kapatılmaz**, **genişletilmez**, **şekli değiştirilmez**.
- v2 v1'i çağırmaz; ortak servis katmanını paylaşır.
- v2 token modeli farklıdır (BFF cookie); v1 Bearer JWT.
- v1 endpoint'leri Next.js'in hiçbir yerinde **dolaylı bile** tüketilmez.

---

## 9) Açık Noktalar (Aşama 0 sonrasına bırakılan kararlar)

1. **OpenAPI codegen toolchain:** `openapi-typescript` vs `orval` vs `kubb`. Karar Dalga 0 başında.
2. **Tablo kütüphanesi:** TanStack Table v8 mı, AG Grid Community mi? Admin revenue tablolarında 1000+ satır olabilir.
3. **Çoklu satır seçim + bulk action** (admin audit, account history) deseni: shadcn DataTable mı, kendi component mi?
4. **Print sayfaları:** Hibrit kalır (karar) ama tetik nasıl olur? Next.js'ten `window.open('/student/week/print')` ile yeni sekme yeterli.
5. **App Router caching:** RSC fetch `{ cache: 'no-store' }` mu zorunlu, yoksa `revalidate: 0` ile mi? Karar API_CONTRACTS_DRAFT.md §7'de.
6. **WebSocket gereksinimi:** Polling'in Next.js karşılığı TanStack Query yeterli mi, yoksa admin live monitor için SSE açılmalı mı? Karar Dalga 5'te.

---

**Sonraki adım:** `API_CONTRACTS_DRAFT.md` — bu envanterdeki ilk 10-12 kritik endpoint için kontrat şekli.
