# API_CONTRACTS_DRAFT — `/api/v2` Sözleşmeler

**Tarih:** 2026-05-18
**Durum:** TASLAK — kod yazılmadan önce mutabakat dokümanı.
**İlke:** Pydantic `BaseModel` adı + alan listesi. JSON dönen response gövdesi (sadece yapı, henüz validation kodu değil). Schema değiştiğinde **bu dosya önce güncellenir, sonra kod**.

---

## 0) Genel Kurallar

### 0.1 Auth
- Tüm v2 endpoint'leri `Depends(get_current_user_v2)` ile çalışır.
- `get_current_user_v2` **iki kanaldan** kullanıcı çözebilir:
  1. `__Host-access` HttpOnly cookie (BFF tarafı için — Next.js)
  2. `Authorization: Bearer <jwt>` (geriye dönük geliştirici kolaylığı — Postman/cURL test için)
- Cookie eksikse 401 + `{"error": "unauthenticated"}`
- Yetki yetersizse 403 + `{"error": "forbidden", "code": "ROLE_REQUIRED"}`

### 0.2 Hata zarfı
Tüm 4xx ve 5xx yanıtları aynı şekilde:
```python
class ErrorResponse(BaseModel):
    error: str            # makine kodu (snake_case)  — örn. "task_not_found"
    message: str          # kullanıcıya gösterilebilir TR cümle — örn. "Görev bulunamadı."
    code: str | None      # iş kuralı kodu (varsa) — örn. "RESERVE_OVER_CAPACITY"
    details: dict | None  # opsiyonel ek alan (örn. validation hataları)
```

### 0.3 Başarılı mutasyon zarfı (OOB karşılığı)
OOB swap kullanan endpoint'lerin (bkz. MIGRATION_INVENTORY §3.1) yanıtı **`invalidate`** anahtarını içerir:
```python
class MutationResponse(BaseModel, Generic[T]):
    data: T
    invalidate: list[str]  # query key prefix listesi — Next.js TanStack Query bunları geçersiz kılar
```
Örnek `invalidate` değerleri:
- `"student:7:day:2026-05-18"` (belirli öğrencinin belirli günü)
- `"student:7:sidebar"` (kaynak durumu sidebar'ı)
- `"teacher:program:7"` (öğretmenin program ekranı)
- `"badges:teacher:pending"` (öğretmen pending count rozeti)
- `"queue:notification:7"` (öğrencinin notification log özet)

### 0.4 Sayfalama
List endpoint'leri ortak sayfalama:
```python
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int          # 1-indexed
    page_size: int     # default 25
    has_next: bool
```
Query: `?page=1&page_size=25&sort=created_at:desc&filter[status]=pending`

### 0.5 Tarihler
- Tüm tarih alanları **ISO 8601 UTC string** (`"2026-05-18T14:30:00Z"`).
- Sadece-gün alanları (örn. task.date) **`"YYYY-MM-DD"`** (timezone'suz). Backend zaten lokal gün olarak tutuyor.
- Frontend kullanıcı saat dilimine **Intl.DateTimeFormat('tr-TR')** ile çevirir.

### 0.6 Versiyonlama
- `/api/v2/*` — bu plan kapsamı. Her response model dondurulur; alan **silinmez**, sadece **eklenir** (additive change).
- Breaking change → `/api/v3`. Önce 30 gün önceden duyurulur.
- Mevcut `/api/v1/*` (mobile) **bu plandan etkilenmez**.

### 0.7 Caching politikası (App Router için)
Kullanıcının "App Router caching agresif olmasın" kırmızı çizgisi gereği:

| Endpoint kategorisi | Cache | Revalidate |
|---|---|---|
| Mutasyon (POST/PUT/DELETE) | — | mutation success'te ilgili query'ler `invalidate` listesi üzerinden geçersiz kılınır |
| Anlık veri (pending count, dashboard, day view) | `cache: 'no-store'` (RSC) veya `staleTime: 0` (client) | Polling 30s veya 60s (mevcut HTMX süreleriyle aynı) |
| Yarı-statik (kitap kataloğu, akademik yıl listesi, plan kataloğu) | `revalidate: 60` (RSC) veya `staleTime: 60_000` (client) | 60 sn |
| Statik (KVKK metni, feature catalog metadata) | `revalidate: 3600` | 1 saat |

**Default:** Tüm v2 endpoint'leri Next.js tarafında `cache: 'no-store'`. İstisna yarı-statik liste çağrılarıdır. Bayatlama yasak — kullanıcı kuralı.

---

## 1) Auth (Dalga 7)

### `POST /api/v2/auth/login`

**Request:**
```python
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    turnstile_token: str | None  # opsiyonel (admin IP'sinden gelirse boş)
```

**Response (200) — Set-Cookie ile cookie set edilir, gövde sade:**
```python
class LoginResponse(BaseModel):
    user: UserPublic
    must_change_password: bool
```

```python
class UserPublic(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: Literal["SUPER_ADMIN", "INSTITUTION_ADMIN", "TEACHER", "STUDENT", "PARENT"]
    institution_id: int | None
    is_active: bool
    created_at: datetime
    avatar_url: str | None
```

**Headers (response):**
```
Set-Cookie: __Host-access=<jwt>; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=900
Set-Cookie: __Host-refresh=<jwt>; HttpOnly; Secure; SameSite=Strict; Path=/api/v2/auth/refresh; Max-Age=604800
```

**Hatalar:**
- 401 `invalid_credentials` — generic mesaj (email enumeration koruması)
- 423 `account_locked` — `code: "LOCKED_UNTIL"`, `details.locked_until: <iso>`
- 429 `rate_limited` — `Retry-After` header

### `POST /api/v2/auth/refresh`
Cookie tabanlı. Body yok. Sadece `__Host-refresh` okur, yeni `__Host-access` set eder.

### `POST /api/v2/auth/logout`
Body yok. İki cookie de `Max-Age=0` ile invalidate. `ActiveSession.terminated_at` set edilir.

### `GET /api/v2/auth/me`
Cookie ile geçerli kullanıcıyı döner (Next.js middleware bunu kullanır).
**Response:** `UserPublic` (yukarıdaki ile aynı şekil).

---

## 2) /me — Profil + KVKK self-serve (Dalga 1)

### `GET /api/v2/me`
**Response:**
```python
class MyAccount(BaseModel):
    user: UserPublic
    plan: PlanSummary | None       # öğretmenin/kurumun planı
    parent_links: list[ParentLink]  # öğrenci ise velileri, veli ise çocukları
    kvkk_status: KvkkStatus
```

```python
class KvkkStatus(BaseModel):
    has_pending_delete_request: bool
    delete_request_id: int | None
    delete_scheduled_at: datetime | None
    can_export: bool
```

### `GET /api/v2/me/data-export`
**Response:** `application/zip` veya `application/json` — KVKK madde 11 hakkı.

### `POST /api/v2/me/data-delete`
**Request:** `{ reason: str | None }`
**Response:**
```python
class DeleteRequestResponse(BaseModel):
    request_id: int
    scheduled_at: datetime    # 30 gün sonra cron uygular
    can_cancel_until: datetime
```

### `POST /api/v2/me/data-delete/{request_id}/cancel`
**Response:** `{ "ok": true }`

---

## 3) Öğrenci Gün Görünümü (Dalga 2 — projenin kalbi)

### `GET /api/v2/student/day?date=2026-05-18`

**Response:**
```python
class StudentDayResponse(BaseModel):
    date: date_iso              # "2026-05-18"
    is_today: bool
    is_future: bool             # tıklama bloklanmış mı
    tasks: list[StudentTask]
    summary: DaySummary
    sidebar: ResourceSidebar    # kaynak durumu (kitap kalan testleri)
    projection: ProjectionPanel | None
    can_request: dict[str, bool]  # add/change/remove/replace/question için izin matrisi
```

```python
class StudentTask(BaseModel):
    id: int
    title: str                   # üretilmiş başlık
    subject_name: str | None
    book_name: str | None
    section_name: str | None
    is_exam: bool                # deneme mi
    state: Literal["PENDING", "PARTIAL", "COMPLETED"]
    planned_count: int
    completed_count: int
    items: list[StudentTaskItem]   # kalemler (tek tek)
    requested_change_id: int | None  # bekleyen talep varsa
    created_at: datetime
    completed_at: datetime | None
```

```python
class StudentTaskItem(BaseModel):
    id: int
    book_id: int
    section_id: int | None
    planned: int                 # planlanan test/deneme sayısı
    completed: int               # tamamlanan
    is_full: bool                # planned == completed
    max_completable: int         # sidebar'dan hesaplanır (rezerv + kalan)
```

```python
class DaySummary(BaseModel):
    total_planned: int
    total_completed: int
    pct: float                   # 0..1
    subjects: list[SubjectBreakdown]
```

```python
class ResourceSidebar(BaseModel):
    items: list[ResourceItem]    # kitap başına test/deneme durumu
    total_reserved: int
    total_remaining: int
```

```python
class ResourceItem(BaseModel):
    book_id: int
    book_name: str
    test_count: int
    reserved: int                # bugün + gelecekte planlanmış
    completed: int
    remaining: int               # test_count - reserved - completed
    sections: list[ResourceSection]
```

```python
class ProjectionPanel(BaseModel):
    target_date: date_iso
    effective_days: int          # tampon dahil
    dow_hit_measured: dict[Literal["Mon","Tue","Wed","Thu","Fri","Sat","Sun"], bool]
    expected_total: int
    current_pace: int
    advice_text: str             # "Çarşamba günlerinde tutturma %50, bunu yükseltmen yeterli"
```

### `POST /api/v2/student/tasks/{task_id}/complete`
**Request:** body yok.
**Response (MutationResponse[StudentTask]):**
```json
{
  "data": { /* StudentTask güncel */ },
  "invalidate": ["student:7:day:2026-05-18", "student:7:sidebar", "student:7:summary"]
}
```
**Hatalar:**
- 400 `future_task_blocked` (gelecek tarihli görev)
- 409 `already_completed`
- 422 `over_capacity` `code: "RESERVE_OVER_CAPACITY"`

### `POST /api/v2/student/tasks/{task_id}/uncomplete`
Aynı şekil. Yan etkisi rezerv iadesi + gamification negatif olabilir.

### `POST /api/v2/student/tasks/{task_id}/items/{item_id}/set-completed`
**Request:** `{ completed: int }`
**Response:** `MutationResponse[StudentTask]` (aynı invalidate seti).

### `GET /api/v2/student/week?anchor=2026-05-18`
**Response:** `{ days: StudentDayResponse[] }` — 7 günlük pencere.

### `GET /api/v2/student/book-grid?book_id=42&assignment_id=15`
**Response:** sinema-koltuk grid verisi.
```python
class BookGridResponse(BaseModel):
    book_id: int
    book_name: str
    test_count: int
    cells: list[BookCell]
```

```python
class BookCell(BaseModel):
    number: int                   # 1..test_count
    state: Literal["DONE", "RESERVED", "FREE"]
    task_id: int | None
    task_date: date_iso | None
```

### `GET /api/v2/student/books`
List of `StudentBook` (kitap envanteri sayfası).

---

## 4) Öğrenci Talep (request) (Dalga 2)

### `POST /api/v2/student/tasks/{task_id}/requests`
**Request:**
```python
class CreateTaskRequest(BaseModel):
    type: Literal["CHANGE", "REPLACE", "REMOVE", "QUESTION"]
    note: str | None              # öğrenci açıklaması
    proposed_count: int | None    # CHANGE için
    proposed_book_id: int | None  # REPLACE için
    proposed_section_id: int | None
```

**Response:** `MutationResponse[TaskRequest]` + `invalidate: ["badges:teacher:7:pending"]`.

### `POST /api/v2/student/day/{day_iso}/requests/add`
ADD type için ayrı endpoint (görev henüz yok, gün üzerinden).

### `POST /api/v2/student/requests/{req_id}/withdraw`
Bekleyen talebi geri çek.

### `GET /api/v2/student/requests?status=pending`
List.

---

## 5) Öğretmen Dashboard (Dalga 3)

### `GET /api/v2/teacher/dashboard`
**Response:**
```python
class TeacherDashboard(BaseModel):
    fleet_status: FleetStatus     # araba kadran metaforu
    warnings: list[StudentWarning]  # ⚡ Şimdi ilgilenmen gerekenler
    metrics_strip: MetricsStrip
    students: list[StudentCard]
    credit_banner: CreditBanner | None
    announcements: list[Announcement]
    pending_requests_count: int
```

```python
class FleetStatus(BaseModel):
    total: int
    at_risk: int
    needs_attention: int
    healthy: int
    completion_avg: float          # filo geneli tutturma
```

```python
class StudentCard(BaseModel):
    id: int
    full_name: str
    grade_label: str               # "8. Sınıf — MEB"
    completion_pct: float
    streak_days: int
    last_active_at: datetime | None
    status: Literal["RISK", "ATTENTION", "OK"]
    badges: list[str]              # "drop_alert", "stale_2d", vb.
```

```python
class CreditBanner(BaseModel):
    pct_used: float
    status: Literal["OK", "WARNING", "BLOCKED", "COOLDOWN"]
    blocked_until: datetime | None
    message: str
```

---

## 6) Öğretmen Program Görünümü (Dalga 3 — en yüksek HTMX yoğunluğu)

### `GET /api/v2/teacher/students/{student_id}/week?anchor=2026-05-18`
**Response:**
```python
class TeacherWeekResponse(BaseModel):
    student: StudentSummary
    anchor_date: date_iso
    days: list[TeacherDayCard]
    week_draft_state: WeekDraftState   # yayınlanmamış görev sayısı
    sidebar: ResourceSidebar           # öğrenci sidebar'ı ile aynı şekil
    week_notes: list[WeekNote]
    suggestions_panel: SuggestionsPanel | None
```

```python
class TeacherDayCard(BaseModel):
    date: date_iso
    dow_label: str                     # "Pazartesi"
    is_today: bool
    is_past: bool
    tasks: list[TeacherTask]
    suggestions: list[Suggestion]      # bu güne öneriler (✨ panel)
    is_draft: bool                     # yayınlanmamış görevler var mı
```

```python
class TeacherTask(BaseModel):
    id: int
    title: str
    state: Literal["DRAFT", "PUBLISHED", "PARTIAL", "COMPLETED"]
    is_exam: bool
    items: list[TaskItem]
    student_completed_count: int
    requested_changes_count: int       # bu görevde bekleyen talep
```

```python
class Suggestion(BaseModel):
    id: str                            # client_key, deterministic
    confidence: float                  # 0..1
    maturity_factor: float
    weakness_signal: bool
    label: Literal["WEAK", "OK", "STRONG", "VERY_STRONG"]
    subject_name: str
    book_name: str
    section_name: str | None
    typical_count: int
```

```python
class WeekDraftState(BaseModel):
    has_drafts: bool
    draft_count: int
    last_published_at: datetime | None
```

### Mutasyon endpoint'leri (hepsi `MutationResponse[TeacherDayCard]` döner)
- `POST /api/v2/teacher/students/{sid}/tasks` — yeni görev (req: tarih, ders, kitap, ünite, adet, tip)
- `POST /api/v2/teacher/tasks/{task_id}` — düzenle (birleşik form)
- `DELETE /api/v2/teacher/tasks/{task_id}`
- `POST /api/v2/teacher/students/{sid}/publish-day?date=...`
- `POST /api/v2/teacher/students/{sid}/publish-week`
- `POST /api/v2/teacher/students/{sid}/suggestions/{sug_id}/accept`
- `POST /api/v2/teacher/students/{sid}/suggestions/accept-all?date=...`
- `POST /api/v2/teacher/students/{sid}/suggestions/{sug_id}/reject`

**Tipik invalidate seti (mutation success):**
```json
["teacher:program:7", "teacher:program:7:day:2026-05-18", "teacher:program:7:sidebar", "teacher:dashboard"]
```

### `GET /api/v2/teacher/students/{sid}/book-grid?book_id=42`
Sinema-koltuk grid, öğrenci tarafıyla aynı şekil.

---

## 7) Öğretmen Talep Yönetimi (Dalga 3)

### `GET /api/v2/teacher/requests?status=pending&student_id=`
**Response:** `Page[TeacherRequestSummary]`.

```python
class TeacherRequestSummary(BaseModel):
    id: int
    student_id: int
    student_name: str
    type: Literal["CHANGE", "REPLACE", "REMOVE", "ADD", "QUESTION"]
    status: Literal["PENDING", "APPROVED", "REJECTED", "WITHDRAWN", "RESOLVED"]
    note: str | None
    task_id: int | None
    task_title: str | None
    day_iso: date_iso | None
    proposed: dict | None              # type'a göre yapı
    created_at: datetime
    teacher_response: str | None
    decided_at: datetime | None
```

### `POST /api/v2/teacher/requests/{req_id}/approve`
**Request:** `{ teacher_response?: str }`
**Response:** `MutationResponse[TeacherRequestSummary]`
- **Yan etki:** `request_service.apply()` çağırır — auto-rebalance + reserve mutation + email (`student_request_approved.html`).
- `invalidate: ["teacher:requests:pending", "teacher:program:<sid>", "badges:teacher:pending"]`

### `POST /api/v2/teacher/requests/{req_id}/reject`
**Request:** `{ teacher_response: str }` (red sebebi zorunlu)

### `POST /api/v2/teacher/requests/{req_id}/respond`
Soru tipindeki talebe cevap.

---

## 8) Veli Paneli (Dalga 6)

### `GET /api/v2/parent/dashboard`
**Response:**
```python
class ParentDashboard(BaseModel):
    parent: UserPublic
    students: list[ParentLinkedStudent]
    has_unread_notes: bool
    notifications_summary: NotificationsSummary
```

```python
class ParentLinkedStudent(BaseModel):
    student_id: int
    student_name: str
    relation: Literal["MOTHER", "FATHER", "GUARDIAN", "OTHER"]
    is_primary: bool
    today_completion_pct: float
    week_completion_pct: float
    exam_date: date_iso | None
    days_to_exam: int | None
    last_teacher_note: TeacherNote | None
```

### `GET /api/v2/parent/students/{student_id}` (detay)
### `GET /api/v2/parent/students/{student_id}/week`
### `GET /api/v2/parent/notifications`
### `PUT /api/v2/parent/settings`
**Request:**
```python
class ParentPreferences(BaseModel):
    email_enabled: bool
    whatsapp_enabled: bool
    quiet_hours_start: str       # "22:00"
    quiet_hours_end: str         # "08:00"
    digest_frequency: Literal["DAILY", "WEEKLY", "OFF"]
    muted_student_ids: list[int]
```

### WhatsApp doğrulama
- `POST /api/v2/parent/settings/whatsapp/start` — body: `{ phone: E164 }` → OTP gönderir (`security.OTP`)
- `POST /api/v2/parent/settings/whatsapp/verify` — body: `{ code: str }` (10dk TTL, max 5 deneme)
- `POST /api/v2/parent/settings/whatsapp/disable`

### Davet (public — token tabanlı, oturumsuz)
- `GET /api/v2/parent/invitation/{token}` → davet detayı (öğrenci adı, davet eden öğretmen, KVKK metni linki)
- `POST /api/v2/parent/invitation/{token}/accept` → user oluştur + login (cookie set et)

---

## 9) Kurum Yönetici (Dalga 4)

### `GET /api/v2/institution/dashboard`
**Response:**
```python
class InstitutionDashboard(BaseModel):
    institution: InstitutionSummary
    teachers: list[TeacherSummary]
    fleet_overview: FleetStatus     # kurum-çapı
    at_risk_count: int
    recent_activity_heatmap: HeatmapData
    subscription_status: SubscriptionStatus
    credit_summary: CreditSummary
```

### `GET /api/v2/institution/teachers` `Page[TeacherSummary]`
### `GET /api/v2/institution/teachers/{teacher_id}` detay
### `POST /api/v2/institution/teachers` (öğretmen oluştur — davetiye akışı tetikler)
### `POST /api/v2/institution/teachers/{tid}/deactivate|activate|pause-alerts|resume-alerts`

### `GET /api/v2/institution/cohorts` (kohort listesi)
### `GET /api/v2/institution/at-risk` (risk paneli)
### `GET /api/v2/institution/activity-heatmap?range=4w` (ısı haritası)
### `GET /api/v2/institution/admin-digest` (haftalık özet)

### `GET /api/v2/institution/subscription`
**Response:**
```python
class SubscriptionStatus(BaseModel):
    plan: str
    period_start: date_iso | None
    period_end: date_iso | None
    is_paused: bool
    pause_until: date_iso | None
    guarantee_enabled: bool
    next_renewal_at: datetime | None
    next_billing_amount_try: int | None
```

### Tenant isolation testi
Tüm institution endpoint'leri `require_institution_admin` + **query'de implicit `institution_id == current.institution_id`**. Regresyon: `scripts/test_tenant_isolation.py` 29/29.

---

## 10) Süper Admin (Dalga 5 — en geniş yüzey)

Burada sadece **temel kalıp** sunulur; ~110 endpoint olduğu için detay her ekran kabulünde ayrı dosyada.

### `GET /api/v2/admin/dashboard`
```python
class AdminDashboard(BaseModel):
    health: TenantHealth
    revenue_snapshot: RevenueSnapshot
    active_users: ActiveUsersStrip
    alarms: list[Alarm]
    recent_signups: list[UserPublic]
    feature_flag_changes_count: int
```

### Kategori bazlı endpoint grupları (`MutationResponse` ile):
- **Kurum yönetimi:** `/api/v2/admin/institutions` (CRUD, backup, account-history)
- **Kullanıcı yönetimi:** `/api/v2/admin/users` (CRUD, reset password, change role, **impersonate**)
- **Feature catalog:** `/api/v2/admin/feature-catalog` (kart + experiment + discovery queue)
- **Feature flags:** `/api/v2/admin/feature-flags` (toggle + per-tenant override)
- **Revenue / CRM:** `/api/v2/admin/revenue/*` (cohort, forecast, action-center, notes, actions, offers, campaigns, action-templates)
- **Security monitor:** `/api/v2/admin/security-monitor/*` (live, sessions, system, alarms, abuse, integrity, activity drill, revenue drill)
- **System:** announcements, quota, system-health, kvkk

### Impersonation
`POST /api/v2/admin/users/{uid}/impersonate` → 200, **yeni cookie set eder** (`__Host-impersonate=...`), gerçek session etkilenmez.
`POST /api/v2/admin/impersonate/end` → cookie temizle, audit yaz.
30 dakika TTL otomatik expire.

### Revenue endpoint'leri (CRUD + JSON cevaplı satır-içi UI)
Mevcut `application/json` dönen rotalar (CRM tag/note/action save) zaten yarı API; bunlar v2'ye doğal taşınır. **Form yerine JSON body olur.**

---

## 11) Plans + Addons (Dalga 8)

### `GET /api/v2/plans` (public)
**Response:** `list[PlanOption]` — pricing sayfası.

### `GET /api/v2/me/plan`
**Response:** `MyPlanResponse` — mevcut plan + addon'lar + kredi havuzu + dönem.

### `POST /api/v2/me/plan/change`
**Request:** `{ to_plan: str, addons: list[str] }`
**Response:** `MutationResponse[MyPlanResponse]` — `PlanChangeHistory` yazılır.
> Ödeme entegrasyonu eklenirse bu endpoint yerine `/api/v2/billing/checkout` akışı kurulur; webhook ayrı planlanır.

### `POST /api/v2/me/addons/{kind}/activate`
### `POST /api/v2/me/addons/{addon_id}/cancel`

---

## 12) Diğer

### Goals (4 rolde — Dalga 2-6)
- `GET /api/v2/{student|teacher|parent|institution}/goals/...`
- Pydantic: `GoalNode { id, title, target, progress, status, children: list[GoalNode] }`

### Focus / Pomodoro (Dalga 2)
- `POST /api/v2/student/focus/start` → session_id
- `POST /api/v2/student/focus/{sid}/end` → süre + kazanılan rozet listesi

### DNA (Dalga 2/3)
- `GET /api/v2/student/dna` → chronotype heatmap + burnout signal
- `GET /api/v2/teacher/students/{sid}/dna`
- `POST /api/v2/teacher/students/{sid}/dna/notify-parent`

### Review / FSRS (Dalga 2/3)
- `GET /api/v2/student/review` → due cards
- `POST /api/v2/student/review/{card_id}` → rating

### Activity heartbeat (Next.js sayfa view tracking — yeni)
**Yeni endpoint** (mevcutta yok, [[project_native_mobile_api.md]] aktivite katmanını tam saymıyor):
```
POST /api/v2/activity/heartbeat
Body: { path: str, duration_ms: int }
```
> Bunun amacı kullanıcının `activity_log` dizinine düzgün event yazmaya devam edilmesi. Henüz tasarımı netleşmiş `activity_tracking.py` yoksa, **Dalga 0'da tanımlanır.**

---

## 13) OpenAPI çıktısı

FastAPI otomatik `/api/v2/openapi.json` üretir. Bundan TypeScript tipler:
```bash
npx openapi-typescript http://localhost:8081/api/v2/openapi.json -o web/lib/types/api.d.ts
```
CI: bu komut her PR'da koşar, diff açar. Şema değişirse frontend derleme kırılır (tip uyumsuzluğu) — geç kalmış sürpriz olmaz.

---

## 14) Açık Sözleşme Noktaları (kodlamadan önce karar gerekir)

1. **Mutation response: standalone mı, paketli mi?**
   - Öneri (yukarıdaki): `{ data: T, invalidate: list[str] }` — sade.
   - Alternatif: `{ data: T, side_effects: [{ kind, key, payload }] }` — daha esnek ama overkill.
2. **Pagination: page-based mi, cursor-based mi?**
   - Öneri: 99% page-based (yeterli); audit log gibi log tablolarda gerekirse cursor opsiyonel eklenir.
3. **List endpoint'lerde filtre query syntax:**
   - Öneri: `?filter[status]=pending&filter[student_id]=7` (Rails-style nested) — Pydantic v2'de manuel parse gerek; `?status=pending&student_id=7` daha kolay.
   - Karar: ikincisi (düz query parameters).
4. **Date filter:**
   - Öneri: `?from=2026-05-01&to=2026-05-31` (ISO date).
5. **Avatar / dosya yükleme:**
   - Direct multipart upload mı, presigned URL mi (S3)? Şu an avatar yok; yapıldığında karar.
6. **WebSocket (Dalga 5 admin live monitor):**
   - Tek `GET /api/v2/admin/security-monitor/live` + 5s polling yeterli mi?
   - Veya `GET /api/v2/admin/security-monitor/stream` (SSE)?
   - Karar Dalga 5'te.

---

**Sonraki adım:** `MIGRATION_RISKS.md` — bu sözleşmeler üzerine binecek riskler.
