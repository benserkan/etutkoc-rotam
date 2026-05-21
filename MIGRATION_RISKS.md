# MIGRATION_RISKS — FastAPI+Jinja → Next.js Risk Haritası

**Tarih:** 2026-05-18
**Durum:** Aşama 0 çıktısı. Yaşayan bir doküman — her dalga sonrası güncellenir.
**Format:** Her risk için `ID — başlık — olasılık × etki = severity — sahip — azaltma — gözlem`.

**Skala:** Olasılık (1-5) × Etki (1-5) = Severity (1-25). 16+ = kritik (auto modda bile durur), 9-15 = yüksek (kullanıcı bildirimi zorunlu), 1-8 = düşük-orta (planda işaretlenir).

---

## ÖZET (severity'ye göre azalan)

| ID | Risk | S |
|---|---|---|
| **R-001** | Auth çift sistem (BFF cookie ↔ paralel session-cookie) köprü hatası | 20 |
| **R-002** | Stripe/iyzico webhook geleceği — sözleşme planı dondurmayalım | 16 |
| **R-003** | WhatsApp webhook path/imza değişimi | 20 |
| **R-004** | Notification queue dispatcher tek-instance (Postgres SKIP LOCKED yok) | 16 |
| **R-005** | bcrypt 4.0.1 pin'in Docker imajında bozulması | 16 |
| **R-006** | HTMX OOB → React reactivity kaybı (UI bayatlaması) | 20 |
| **R-007** | **Next.js App Router caching agresif** — kullanıcı kırmızı çizgi | 20 |
| **R-008** | Tenant isolation regresyonu (29/29 kırılırsa = security) | 25 |
| **R-009** | bcrypt + passlib + Python sürüm uyumsuzluğu (zaten yaşandı) | 15 |
| **R-010** | Cron + dispatcher → Docker Compose'da hangi container'da çalışacak | 12 |
| **R-011** | shadcn "yamalı görünüm" — kullanıcı kırmızı çizgi (tasarım sistemi) | 15 |
| **R-012** | Print/email Jinja kalır ama base.html'e gömülü context değişebilir | 9 |
| **R-013** | Parent invitation/signup token email link'leri bozulması | 12 |
| **R-014** | Impersonation cookie (super admin) — paralel session karmaşası | 16 |
| **R-015** | Activity tracking gap — Next.js sayfa view'leri kayboluyor | 12 |
| **R-016** | Rate limit in-memory + multi-worker (Render/Docker) tutarsızlık | 12 |
| **R-017** | Sticky sidebar + sinema-koltuk grid responsive bozulması | 8 |
| **R-018** | Chart.js → Recharts geçişinde tip/skala/locale farkı | 6 |
| **R-019** | CSV import (öğrenci toplu) — Next.js multipart UX | 6 |
| **R-020** | Reverse proxy path-based yönlendirme yanlış config | 16 |
| **R-021** | Audit log ve security_monitor — Next.js'in oluşturduğu olaylar | 10 |
| **R-022** | OpenAPI codegen + Pydantic v2 generic tip kayması | 8 |
| **R-023** | Türkçe locale + date-fns/Intl + ISO date karmaşası | 6 |
| **R-024** | Görev rezerv invariant'ı (`reserved + completed ≤ test_count`) frontend kaybedebilir | 12 |
| **R-025** | Test rejimi: 108 web smoke + 47 API + 29 tenant — Next.js E2E eklenmezse blind spot | 14 |

---

## DETAY

### R-001 — Auth çift sistem köprü hatası `Severity 20`

**Açıklama:** Geçiş süresince Jinja sayfaları session-cookie (`SessionMiddleware`) ile, Next.js BFF cookie (`__Host-access`) ile çalışır. İki dünya aynı `User`'a bakar ama `password_stamp` rotasyonu, `must_change_password`, impersonation gibi durumları farklı yorumlayabilir.

**Saha kanıtı:**
- `app/deps.py:29-112` — session["password_stamp"] rotasyon kontrolü
- `app/services/jwt_auth.py:148-161` — JWT pwd_stamp doğrulama
- İki sistem aynı `User.password_changed_at` alanından okuyor → senkron, ama `must_change_password=True` iken JWT akışı bunu zorlamıyor.

**Azaltma:**
1. `must_change_password` kontrolü v2 endpoint'lerinin **dependency'sine** eklenir (`get_current_user_v2` 403 + `code: "PASSWORD_CHANGE_REQUIRED"` döner).
2. Kullanıcı tek seferde sadece bir akıştan login olur (Jinja `/login` veya Next.js `/login`); login sonrası **diğer cookie temizlenir**.
3. Logout her iki cookie türünü de siler (Set-Cookie Max-Age=0).
4. Geçiş bitince Jinja session-cookie sistemi tamamen söker (Dalga 9).

**Test:** Login → password değiştir → her iki cookie'nin de invalidate olduğu doğrula (manuel + Playwright E2E).

**Sahip:** Dalga 0 sonu + Dalga 7'de revizyon. Kullanıcı **onay verir** (auto modda durulur).

---

### R-002 — Ödeme sağlayıcı geleceği `Severity 16`

**Açıklama:** Şu an Stripe/iyzico yok; `plans.py` mock. Geçiş bittikten sonra ödeme entegre edilirse webhook + checkout flow eklenecek. v2 sözleşmesini ödemesiz dondurursak, ödeme geldiğinde **kontrat değişikliği** gerekebilir.

**Saha kanıtı:**
- `app/services/plans.py:435` `start_solo_trial`, `app/services/subscription.py` — DB-only logic.
- `app/services/dunning.py` — mail ile hatırlatıyor, tahsilat etmiyor.
- `Invoice` tablo zaten hazır (status, due_at, attempt_count).

**Azaltma:**
1. v2 plan endpoint'leri **"checkout url" alanı opsiyonel** olarak şimdiden alana eklenir (`MutationResponse[MyPlanResponse]`).
2. Webhook için path **şimdiden reservasyon:** `/webhooks/payment/{provider}` (provider Stripe/iyzico).
3. Bu webhook Next.js'in **hiç bilmediği** bir endpoint — FastAPI'de.

**Sahip:** Dalga 8. Ödeme sağlayıcı seçimi kullanıcının ayrı kararı.

---

### R-003 — WhatsApp webhook sabit `Severity 20`

**Açıklama:** Meta Business Manager'da `https://app.etutkoc.com/webhooks/whatsapp` URL'i kayıtlı. Geçişte bu path **kazara** Next.js'e gönderilirse, Meta callback'leri kaybeder, `notification_log` status'leri sonsuza dek `QUEUED` kalır.

**Saha kanıtı:**
- `app/routes/whatsapp_webhook.py:34,51` — GET verify + POST callback.
- `app/services/whatsapp.py:172` — HMAC-SHA256 imza doğrulama.
- Şablon adları (`veli_otp_kodu`, `veli_daily_summary`, vb.) Meta'da onaylı.

**Azaltma:**
1. Reverse proxy config'inde `/webhooks/*` → FastAPI **explicit** kuralı, **en üst öncelikte**.
2. Smoke test: deploy sonrası `curl https://.../webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=...` → 200 verify token.
3. Health alert: `notification_log` 24 saatten uzun QUEUED kalırsa admin'e alarm (zaten `system_health` paneli var).

**Sahip:** Dalga 0. Reverse proxy yazılınca PR'da gözden geçirme.

---

### R-004 — Notification queue tek-instance `Severity 16`

**Açıklama:** `notification_dispatcher.dispatch_pending()` SQLite + tek FastAPI worker'ında çalışır. Multi-worker'a geçilirse aynı satır iki kez işlenebilir (mail çift gider).

**Saha kanıtı:**
- `app/services/notification_dispatcher.py:264` — `SELECT ... WHERE status='QUEUED'` (lock yok).
- Memo: `project_native_mobile_api.md` → "multi-worker durumunda Redis tabanlı'ya yükseltilmeli".

**Azaltma:**
1. Docker Compose yapılandırması: dispatcher **ayrı bir container** (`worker` service) — tek replica. Web container'larında dispatcher loop **çalışmaz** (env flag ile).
2. Postgres'e geçişte: `SELECT ... FOR UPDATE SKIP LOCKED` ile satır-bazlı kilit.
3. Kuyruk 5dk'dan uzun gecikirse Health'e bayrak ekle.

**Sahip:** Dalga 0 Docker Compose tasarımı.

---

### R-005 — bcrypt 4.0.1 pin Docker imajında `Severity 16`

**Açıklama:** Memo: bcrypt 5.x + passlib 1.7.4 → `detect_wrap_bug` ValueError. `requirements.txt`'te 4.0.1 pin var; Docker imajı yeniden build edilirken bu pin kaybolursa **tüm girişler kırılır**.

**Saha kanıtı:**
- `project_platform_evolution.md` — bcrypt 5.x + passlib uyumsuz.
- `project_native_mobile_api.md` — "bcrypt 4.0.1 pin'i korunmalı".

**Azaltma:**
1. Dockerfile içine açık `bcrypt==4.0.1` yorumu + smoke test (build sonrası `python -c "from passlib.hash import bcrypt; bcrypt.hash('x')"`).
2. CI'da `pip-compile --strip-extras` ile lockfile.
3. Hash subprocess fallback ([[project_platform_evolution.md]] — Stage 8'de bahsedilen sorun) korunur.

**Sahip:** Dalga 0 Dockerfile.

---

### R-006 — HTMX OOB → React reactivity kaybı `Severity 20`

**Açıklama:** Mevcut OOB swap'lerde tek POST → 3 ekran bölgesi güncellenir (task card + sidebar + day summary). Next.js'te yanlış uygulanırsa **kullanıcı görev tikler, sidebar güncellenmez, kafa karışıklığı**.

**Saha kanıtı:**
- 11 OOB swap kullanan endpoint (bkz. MIGRATION_INVENTORY §3.1).
- En kritik: `POST /student/tasks/{id}/complete` (öğrencinin günlük akışının kalbi).

**Azaltma:**
1. Mutation response'larda **`invalidate: list[str]`** alanı zorunlu (bkz. API_CONTRACTS_DRAFT §0.3).
2. Frontend `lib/api.ts` wrapper'ı `useMutation` `onSuccess`'te `invalidate` listesini okur ve `queryClient.invalidateQueries({ queryKey: [key] })` çağırır.
3. **Optimistic update:** task complete tıklandığı an UI hemen güncellenir (network'ten önce).
4. E2E test: Playwright ile "öğrenci görev tikle → sidebar 'kalan' sayısı eksildi" doğrula.

**Sahip:** Dalga 2 (öğrenci paneli) — bu kalıbın **referans implementasyonu** burada kurulur.

---

### R-007 — Next.js App Router caching agresif `Severity 20`

**Açıklama:** **Kullanıcının kırmızı çizgisi.** Next.js App Router default `fetch` cache'i `force-cache`. Yanlış konfigüre edilirse haftalık program güncellemesi 60 saniye veya daha uzun süre bayatlar.

**Azaltma:**
1. **Default kural:** `lib/api.ts` wrapper'ı tüm fetch çağrılarına `{ cache: 'no-store' }` ekler.
2. **İstisna allowlist:** Yarı-statik veri için açık opt-in (`fetchCached(url, { revalidate: 60 })`).
3. **RSC'de:** Sayfa-bazlı `export const dynamic = 'force-dynamic'` (auth gerektiren tüm sayfalarda).
4. **Client'ta:** TanStack Query default `staleTime: 0` + `refetchOnWindowFocus: true` + mutation'da invalidate.
5. Smoke test (her dalga): "Programı güncelle → 2 sn içinde tüm sekmelerde yansıdı mı" manuel doğrulama checklist.

**Sahip:** Dalga 0'da `lib/api.ts` ve cache policy yazılır; her PR'da `next.config.ts` cache override'ları gözden geçirilir.

---

### R-008 — Tenant isolation regresyonu `Severity 25 (KRİTİK)`

**Açıklama:** Süper admin / kurum admin / öğretmen / öğrenci / veli arasındaki yetki sızıntısı. Yanlış institution_id filter'ı = başka kurumun verisini görmek = ifşa.

**Saha kanıtı:**
- `project_multi_tenant_kurumlar.md` — 29/29 PASS.
- `scripts/test_tenant_isolation.py` mevcut, regresyon test.

**Azaltma:**
1. **Her v2 endpoint** v1'deki rol kapısının aynısını kullanır (require_teacher, require_institution_admin, ...).
2. `scripts/test_tenant_isolation.py` her PR'da CI'da koşar — **kırılırsa merge yok**.
3. Yeni v2 endpoint'leri için test script genişletilir (rol-bazlı erişim matrisinde her hücre).
4. Impersonation cookie'si v2 dependency'sinde de aynı şekilde tüketilir (R-014 ile birlikte).
5. **Test rejimi:** her dalga sonrası 29/29 + dalganın endpoint sayısı kadar yeni test eklenir.

**Sahip:** Sürekli. Her PR.

---

### R-009 — bcrypt + passlib + Python sürüm uyumsuzluğu `Severity 15`

R-005'in geniş hali. Python 3.13'e atlanırsa veya passlib 1.8 çıkarsa kırılma riski. **Geçiş süresince Python 3.12 + passlib 1.7.4 + bcrypt 4.0.1 sabit.**

---

### R-010 — Cron + dispatcher container yerleşimi `Severity 12`

**Açıklama:** Docker Compose'da FastAPI servisi başlatıldığında lifespan event'inde cron tick + dispatcher background task ayağa kalkar. Web service replika sayısı 2+ olduğunda her replikada cron çalışır → çift tetik.

**Azaltma:**
1. Yapı: `docker-compose.yml`'de 3 servis: `web` (uvicorn, N replika), `worker` (cron + dispatcher, 1 replika), `db` (Postgres).
2. `web` lifespan'inde cron tick + dispatcher **kapalı** (env: `LGS_RUN_BACKGROUND=false`).
3. `worker` lifespan'inde **açık** (env: `LGS_RUN_BACKGROUND=true`).
4. Kod tarafında: `app/main.py` veya benzeri lifespan'de env flag kontrolü.

**Sahip:** Dalga 0 Docker Compose.

---

### R-011 — shadcn yamalı görünüm `Severity 15` (kullanıcı kırmızı çizgisi)

**Açıklama:** Kullanıcı: "Yamalı bir görünüm istemiyorum." shadcn primitive'leri (Button, Dialog, DropdownMenu) düzgün konfigüre edilmezse her sayfa farklı bir tasarım dilinde görünür.

**Azaltma:**
1. **Tasarım sistemi anayasası** Dalga 0'da yazılır: `web/components/ui/_tokens.md` — renk paleti (ETÜTKOÇ markası), tipografi (font scale), spacing scale, border radius, gölge.
2. **Section panel macro karşılığı** (`app/templates/_macros/section_panel.html` → `<SectionPanel>` component) Dalga 0'da yazılır — tüm bölüm başlıkları **bu** component üzerinden render edilir. Çıplak `h2 + grid` pattern **yasak** ([[feedback_admin_section_panel.md]]).
3. shadcn theme: `globals.css` CSS variables ile **tek tema dosyası**. Inline `style="background:#..."` desenlerinden ([[project_lgs_tracker.md]] — Tailwind CDN dinamik class sorunu) component'lere geçilir.
4. Her dalga sonu **visual review** kullanıcıdan: ekran kayıtları gönderilir, yamalanma kontrolü.

**Sahip:** Dalga 0 tasarım sistemi + her dalga sonrası kullanıcı görsel onayı.

---

### R-012 — Print/email Jinja kalır, base.html context değişebilir `Severity 9`

**Açıklama:** Email/print şablonlar `base.html`'i extend edebilir veya ortak macro kullanabilir. Geçişte `base.html` değişirse email render'ları bozulur.

**Azaltma:**
1. Email/print şablonları **ayrı `base_email.html` / `base_print.html`** extend etsin (zaten öyleyse iyi; kontrol Dalga 0'da).
2. Email templates için ayrı smoke test: `scripts/test_email_render.py` her şablonu dummy context ile render eder, exception fırlamazsa PASS.

**Sahip:** Dalga 0.

---

### R-013 — Token email link'leri `Severity 12`

**Açıklama:** Veli daveti email'i içinde `https://app/parent/invitation/<token>` linki var. Geçişte path Next.js'e açılırsa Next.js sayfası yoksa 404.

**Saha kanıtı:**
- `app/routes/parent.py:95-237` — `/parent/invitation/{token}`.
- `app/templates/emails/parent_invitation.html` — link burada.
- `app/routes/signup.py:169-324` — `/signup/invite/{token}`.

**Azaltma:**
1. Email link path'leri **değiştirilmez**. Next.js bu path'leri implement eder, Jinja sürümü pasifleştirilir.
2. Geçiş sırasında Next.js sürümü henüz yokken Jinja sürümü çalışır kalır.
3. Geçiş anında reverse proxy bu path'leri Next.js'e açar, **aynı kullanıcı deneyimi**.

**Sahip:** Dalga 6 (parent) + Dalga 7 (signup).

---

### R-014 — Impersonation cookie karmaşası `Severity 16`

**Açıklama:** Super admin impersonate ettiğinde gerçek session ile impersonate session yan yana yaşar. Next.js BFF tarafında bunu nasıl temsil edeceğiz?

**Saha kanıtı:**
- `app/models/impersonation_session.py:27-80` — 30dk TTL.
- `app/deps.py:37-83` — session["impersonation_id"] / "impersonator_id".

**Azaltma:**
1. v2'de ayrı cookie `__Host-impersonate=<jwt>` set edilir. Bu cookie varken `get_current_user_v2` impersonate kullanıcıyı döner, `actor_id` ek alan olarak request state'e konur.
2. UI'da kalıcı uyarı şeridi: "Siz X'in yerine bakıyorsunuz — sona erdir." (mevcut Jinja base.html'de var; React'te SectionPanel veya banner component'i).
3. 30dk expire otomatik invalidate. UI deferred refresh ile uyarı banner'ı düşürür.
4. Audit: `IMPERSONATE_START/END/EXPIRED` olayları aynen yazılır.

**Sahip:** Dalga 5 (admin paneli).

---

### R-015 — Activity tracking gap `Severity 12`

**Açıklama:** Memo'ya göre `activity_tracking.py` tam impl değil. Next.js sayfa view'leri eski sistemde `audit_log`'a yazmıyorsa, admin'in "kim ne yapıyor" panelinde Next.js trafiği görünmez.

**Saha kanıtı:** Service modülü audit raporu — "activity_tracking.py YALNIZ TASARIMI VAR, FULL IMPL YOKSUN".

**Azaltma:**
1. Yeni endpoint `POST /api/v2/activity/heartbeat` (bkz. API_CONTRACTS_DRAFT §12 sonu).
2. Next.js `lib/activity.ts` her route change'de bunu çağırır (debounce + sample edilebilir).
3. Geriye dönük uyum için: aynı endpoint Jinja sayfalarından da çağrılabilir (geçiş süresince paralel).
4. Eğer `activity_tracking.py` hâlâ "tasarımı var" durumdaysa, Dalga 0'da minimum impl yazılır: `INSERT INTO activity_log (user_id, path, duration_ms, ts)`.

**Sahip:** Dalga 0 endpoint + her dalganın React sayfası entegre eder.

---

### R-016 — Rate limit in-memory + multi-worker `Severity 12`

**Açıklama:** `app/services/rate_limit.py` in-memory. Web container 2 replika olursa 10/dk login limit her replikada ayrı sayılır — toplam 20/dk olur.

**Azaltma:**
1. Web replika başlangıçta **tek** (Render free tier + tek VPS).
2. Redis eklenirse `rate_limit.py` Redis-backed olur (Dalga 0+ kararı — şimdilik gerek yok).
3. Test: `scripts/test_api_v1.py` rate limit testi yeşil kalmalı.

**Sahip:** Dalga 0 deployment.

---

### R-017 — Sticky sidebar + sinema-koltuk grid responsive `Severity 8`

**Açıklama:** XL breakpoint sticky sidebar (`xl:sticky xl:top-4 ...`) React'te yanlış yapılırsa scroll'da kaybolur veya mobile'da bozulur.

**Azaltma:**
1. Mevcut Tailwind class'ları **bire bir** korunur (CSS değişmez).
2. Sinema-koltuk grid (Sprint 6'da kurulan kalıp) `<BookGridCell state="DONE|RESERVED|FREE" number={n} />` component'i.
3. E2E: mobile (375px), tablet (768px), desktop (1280px) — 3 viewport smoke test.

**Sahip:** Dalga 2 + Dalga 3.

---

### R-018 — Chart.js → Recharts geçişi `Severity 6`

**Açıklama:** Mevcut 7 sayfada Chart.js init script. Recharts'a geçişte rakam formatları (Türkçe locale), Y ekseni skalası, renkler birebir korunmalı.

**Azaltma:**
1. Geçiş süresince Chart.js React wrapper (`react-chartjs-2`) kullanılabilir — minimum risk.
2. Recharts'a sonradan ekip rahat eder.
3. Renk paleti: tasarım sistemi token'ları kullanılır.

**Sahip:** Dalga 3 + Dalga 4.

---

### R-019 — CSV import UX `Severity 6`

**Açıklama:** Öğrenci toplu CSV import şu an `multipart/form-data` + Jinja preview sayfası. Next.js'te aynı UX (drag-drop + önizleme tablosu + onay) gerekir.

**Azaltma:**
1. `react-dropzone` + shadcn DataTable preview.
2. Backend zaten 3 aşamalı (form → preview → confirm) — JSON cevaplı versiyonu kolay.
3. Hata satırlarını sonradan indirme (results.csv) korunur.

**Sahip:** Dalga 3.

---

### R-020 — Reverse proxy yanlış config `Severity 16`

**Açıklama:** Nginx/Caddy/Traefik path-based routing'de yanlış sıra → `/webhooks/whatsapp` veya `/api/v1/*` Next.js'e gider → 404.

**Azaltma:**
1. Reverse proxy config dosyası kod review'da iki kişi tarafından okunur (kullanıcı + Claude).
2. Deploy sonrası smoke: `/healthz`, `/api/v1/auth/login` (401 dönmeli, 404 değil), `/webhooks/whatsapp?hub...` (200 verify).
3. Konfig örneği MIGRATION_INVENTORY §7'deki sıraya bire bir uyar.

**Sahip:** Dalga 0 deployment.

---

### R-021 — Audit log: Next.js olaylarını kim yazacak `Severity 10`

**Açıklama:** `audit.log_action()` her v1 route'da elle çağrılıyor. v2 endpoint'lerinde unutulursa olay log'da görünmez.

**Azaltma:**
1. v2 mutation endpoint'lerinde `audit.log_action(...)` çağırma **kontrat parçası**.
2. Code review checklist: yeni v2 endpoint mı? → audit_log yazıyor mu?
3. Karşı önlem: FastAPI middleware/dependency olarak v2 endpoint'lerine generic audit (action=ENDPOINT_CALLED) eklenebilir; ancak gürültü yaratır → manuel tercih.

**Sahip:** Her endpoint sahibi (Dalga 2-8).

---

### R-022 — OpenAPI codegen + Pydantic v2 generic `Severity 8`

**Açıklama:** `MutationResponse[T]` gibi generic Pydantic'in OpenAPI'ye tam yansımaması. `openapi-typescript` bunu `unknown` olarak üretebilir.

**Azaltma:**
1. Spike (Dalga 0'da 1 saatlik test): `MutationResponse[StudentTask]` → OpenAPI → TS — gerçek tip mi çıkıyor?
2. Çıkmıyorsa: Manuel non-generic wrapper yazılır (`StudentTaskMutationResponse`).
3. CI'da `tsc --noEmit` zorunlu.

**Sahip:** Dalga 0.

---

### R-023 — Türkçe locale `Severity 6`

**Açıklama:** Tarihler, sayı formatları (binlik ayracı), gün isimleri her yerde Türkçe görünmeli.

**Azaltma:**
1. `Intl.DateTimeFormat('tr-TR')` ve `Intl.NumberFormat('tr-TR')` `lib/locale.ts`'te tek noktada tanımlı.
2. date-fns kullanılırsa `tr` locale import edilir.
3. Smoke test: bir sayfa açıp Pazartesi/Salı/... görünmesini doğrula.

**Sahip:** Dalga 0.

---

### R-024 — Görev rezerv invariant'ı frontend kaybeder `Severity 12`

**Açıklama:** [[project_lgs_tracker.md]] Model C rezerv: `reserved + completed ≤ test_count`. Frontend görev oluştururken bu invariant'ı görmezse kullanıcıya yanlış limit gösterir.

**Saha kanıtı:**
- Mevcut HTMX `student/day.html` formunda `<input max="">` server-side hesaplanıyor.
- `app/services/task_service.py` invariant'ı koruyor (server son sözü söyler).

**Azaltma:**
1. v2 sözleşmesi `ResourceItem` içinde `max_completable: int` döndürür (bkz. API_CONTRACTS_DRAFT §3).
2. Frontend bu sayıyı kullanır; ama server **her zaman** son sözü söyler (422 over_capacity).
3. Test: invariant'ı kıracak request gönder, 422 dönmeli.

**Sahip:** Dalga 2 + Dalga 3.

---

### R-025 — Test rejimi blind spot `Severity 14`

**Açıklama:** Şu an 108 web smoke + 47 API + 29 tenant = 184 test. Next.js eklenince frontend E2E yoksa, geçiş sırasında bir mutation'ın UI'da gerçekten render edildiğini doğrulayamayız.

**Azaltma:**
1. Playwright konfigürasyonu Dalga 0'da (basit smoke: login → me → dashboard görüntüle).
2. Her dalga **en az 3 E2E senaryo** ekler (kabul kriteri).
3. CI matrisi: backend pytest + frontend vitest + e2e playwright + tenant isolation.
4. Geçici azaltma: dalga başlangıçlarında manuel kabul test rejimi (MIGRATION_INVENTORY §5'teki 6 senaryo).

**Sahip:** Dalga 0 + her dalga.

---

## Kabul Kriterleri (her dalga sonu için ortak)

Bir dalganın "tamamlandı" sayılması için aşağıdakilerin **HEPSİ** doğrulanmış olmalı:

- [ ] Tüm v2 endpoint'leri OpenAPI'de görünüyor + TypeScript tipleri üretildi
- [ ] 29/29 tenant isolation testi PASS
- [ ] 47/47 API v1 smoke testi PASS (v1 kontratı bozulmadı)
- [ ] 108/108 mevcut web smoke testi PASS (eski Jinja çalışıyor)
- [ ] Dalganın yeni endpoint sayısı kadar yeni v2 smoke testi yazıldı
- [ ] Dalganın yeni React sayfası için en az 3 Playwright E2E senaryosu eklendi
- [ ] **Manuel görsel onay:** kullanıcıya 1-2 ekran kaydı gönderildi, "yamalı görünüm yok" onayı alındı
- [ ] Audit log kontrolü: dalganın her mutation endpoint'i audit_log'a yazıyor
- [ ] Cache politikası gözden geçirildi (no-store default + istisnaların listesi)
- [ ] Reverse proxy konfigürasyonu güncel (dalganın path'leri Next.js'e açık)
- [ ] Geri dönüş planı: bu dalga için rollback adımları yazılı

---

## Risk Sahibi Atama Özeti

| Aşama | Önemli sahip riskleri |
|---|---|
| **Dalga 0** | R-001 (auth iskelet), R-007 (cache policy), R-008 (test pipeline), R-010 (compose), R-011 (tasarım sistemi), R-020 (proxy), R-015 (activity endpoint), R-005 (bcrypt) |
| **Dalga 1-2** | R-006 (OOB→invalidate kalıbı), R-024 (invariant) |
| **Dalga 3** | R-006 (OOB yoğun), R-019 (CSV) |
| **Dalga 4** | R-008 (tenant) |
| **Dalga 5** | R-014 (impersonation) |
| **Dalga 6** | R-013 (token link) |
| **Dalga 7** | R-001 (auth tamamı — kullanıcı onayı) |
| **Dalga 8** | R-002 (ödeme) |

---

## Açık Sorular (kullanıcıya)

1. Docker Compose tek VPS'te iki container yeterli mi (web + worker + db = 3), yoksa Next.js'i ayrı container'da mı? Önerim: `web` (FastAPI uvicorn), `next` (Next.js standalone), `worker` (cron + dispatcher), `db` (Postgres), `proxy` (Caddy/Nginx). 5 servis.
2. SSL sertifikası: Let's Encrypt mi (Caddy otomatik), yoksa Cloudflare proxy mi?
3. Yedekleme: Postgres dump cron'u zaten var mı, yoksa Dalga 0'da eklenecek mi?
4. Render'dan VPS'e geçiş (memo'da Render önerilmişti) — bu plan VPS varsayar. Render kalırsa Docker Compose yerine Render Blueprint güncellenir.
5. Geliştirme ortamında Next.js dev port (önerim 3000) ile FastAPI dev port (8081) arasında CORS — Next.js dev sunucusundan FastAPI'ye istek olur; `settings.cors_origins` listesine `http://localhost:3000` eklenir.

---

**Bu üç doküman (`MIGRATION_INVENTORY.md`, `API_CONTRACTS_DRAFT.md`, `MIGRATION_RISKS.md`) artık Aşama 0'ın çıktısıdır. Aşama 1 (kodlama: `/api/v2` iskelet + Next.js bootstrap) bu dokümanlar onaylandıktan sonra başlatılır.**
