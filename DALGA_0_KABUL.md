# Dalga 0 — Kabul Raporu

**Tarih:** 2026-05-18
**Durum:** ✅ TAMAMLANDI
**Onay bekleyen:** Kullanıcı (Dalga 1 öğrenci panelinin başlatılması için)

---

## 1) Test Sonuçları (zorunlu kabul kriteri)

| Suite | Önce | Sonra | Sonuç |
|---|---|---|---|
| `/api/v1` smoke (mobile sözleşmesi) | 47/47 | **47/47** | ✅ Kontrat dondurulmuş, dokunulmadı |
| `/api/v2/me` smoke (Dalga 1) | 13/13 | **13/13** | ✅ Yeni endpoint'ler stabil |
| `/api/v2/auth` smoke (BFF cookie) | — | **14/14** | ✅ Dalga 0'da eklendi |
| Tenant isolation | 29/29 | **29/29** | ✅ Güvenlik sızıntısı yok |
| Next.js production build | — | ✅ | TypeScript 0 hata, 5 route |
| ESLint (`pnpm lint`) | — | ✅ | 0 hata, custom kurallar yakalama yapıyor |
| Sanity: kasıtlı ihlal yazıldı | — | ✅ | 3 custom kural ihlali yakaladı |

**Toplam:** **103/103** PASS. **Sıfır regresyon.** Strangler Fig prensibi
korunmuş, hiçbir eski Jinja akışı bozulmamış.

---

## 2) Mimari Çıktılar

### Backend (FastAPI)
- `/api/v2/*` namespace açıldı — `/api/v1` (mobile) ile birebir izolasyon
- 8 yeni endpoint: `auth/login`, `auth/refresh`, `auth/logout`, `auth/me`, `me`, `me/data-export`, `me/data-delete`, `me/data-delete/{id}/cancel`
- 3-kanal `get_current_user_v2`: BFF cookie → Bearer JWT → Session cookie
- BFF cookie config: `AUTH_COOKIE_ACCESS_NAME`, `AUTH_COOKIE_SECURE`, `AUTH_COOKIE_SAMESITE_*`
- Mevcut servisler (kvkk, audit, security, rate_limit, jwt_auth) **birebir çağrılır** — iş mantığı dokunulmadı

### Frontend (Next.js 16 + Tailwind 4)
- `/web` monorepo dizini iskelet (Node 22, pnpm 11)
- Tasarım sistemi: lacivert (primary) + haki (secondary) + antrasit nötr; light default, dark hazır; ETÜTKOÇ marka renkleri korunmuş
- 14 shadcn primitive (Button, Card, Dialog, Input, Label, Separator, Skeleton, Sonner, Tooltip, …)
- Foundation: `SectionPanel` (TS level zorunlu description), `JargonTooltip`, `RoleBanner`, `ThemeProvider`, `QueryProvider`
- 5 sayfa: `/` splash, `/login` stub, `/me/account` gerçek backend tüketir, `/api/auth/refresh` BFF, `/_not-found`
- `proxy.ts` (Next 16 standard adı): cookie varlığı kontrolü + public path matrix + role redirect
- `lib/api.ts` + `lib/api-server.ts`: cache no-store default, 3-channel cookie passthrough, ApiError envelope
- `lib/invalidate.ts`: `MutationResponse.invalidate` → TanStack Query invalidation köprüsü
- `lib/locale.ts`: tr-TR Intl formatter'ları (tarih/saat/yüzde/para/relatif)

### Altyapı (Docker Compose + Caddy)
- `web/Dockerfile`: 3 aşamalı standalone build, node:22-alpine, ~180-220MB hedef
- `deploy/docker-compose.yml`: 5 servis (web + worker + next + db + proxy)
- Worker tek replika (`deploy.replicas: 1`) — R-004 duplicate koruması
- Migration race: `worker depends_on: web healthy` → start.sh alembic upgrade tamam sayılır
- `deploy/Caddyfile`: Strangler Fig path routing — dalga aç/kapa = yorum satırı + `caddy reload` < 60sn
- Lightsail Static IP uyarısı README'de **prominent** + Firewall port 80/443 hatırlatması

### Codegen ve Lint (Dalga 0 finali)
- `scripts/dump_openapi_v2.py`: FastAPI'den v2-filtered OpenAPI spec → `web/openapi.v2.json`
- `web/package.json`: `pnpm gen:types` → `lib/types/api.d.ts` (83 KB, 8 endpoint + Pydantic şemaları)
- `web/eslint.config.mjs`: 3 custom kural — kullanıcının kırmızı çizgilerinin **kod seviyesinde** enforcement'ı
  - `lgs/no-bare-fetch` (error) — fetch() yalnız lib/api.ts içinde
  - `lgs/missing-invalidate` (warn) — useMutation onSuccess'inde invalidate yoksa uyar
  - `lgs/no-bare-jargon` (warn) — DAU/MRR/Churn/Tenant/NPS/LTV/CAC açıklamasız geçemez

---

## 3) Kullanıcı Kırmızı Çizgileri — Kontrol Listesi

| Çizgi | Kanıt | Durum |
|---|---|---|
| /api/v1 mobile sözleşmesi DOKUNULMAZ | 47/47 PASS, schema değişmedi | ✅ |
| Jinja /me, /login akışları çalışır | Caddyfile fallback → web | ✅ |
| Tenant isolation korunmuş | 29/29 PASS | ✅ |
| App Router cache bayatlama YASAK | cache: 'no-store' default, dynamic = "force-dynamic", invalidate listesi | ✅ |
| shadcn "yamalı görünüm" YASAK | SectionPanel description zorunlu, tek tema | ✅ |
| Admin panel jargonu açıklamasız | lgs/no-bare-jargon ESLint kuralı | ✅ |
| BFF HttpOnly cookie + XSS sıfır | `__Host-access` prod / `lgs_access` dev, HttpOnly | ✅ |
| Bcrypt 4.0.1 pin | requirements.txt korundu | ✅ |
| Worker tek replika (queue duplicate yok) | docker-compose deploy.replicas: 1 | ✅ |
| Hibrit kalıcı (email + print + KVKK) | Caddyfile @prints + /kvkk, /privacy, /legal routes | ✅ |
| Test/mock user atmayacak | Tüm testler secrets prefix + cleanup; gerçek hesaplara dokunmadı | ✅ |
| Riskli sprint'lerde kullanıcı onayı | Dalga 7 (auth) ve Dalga 8 (ödeme) Caddyfile'da KAPALI | ✅ |

---

## 4) Yazılan/Değişen Dosya Sayımı

### Backend (FastAPI)
```
app/config.py                              (+5 BFF cookie ayarı)
app/main.py                                (+2 satır api_v2_router include)
app/routes/api_v2/__init__.py              (yeni)
app/routes/api_v2/dependencies.py          (yeni, 3-kanal resolver)
app/routes/api_v2/auth.py                  (yeni)
app/routes/api_v2/me.py                    (yeni)
app/routes/api_v2/schemas/__init__.py      (yeni)
app/routes/api_v2/schemas/common.py        (yeni)
app/routes/api_v2/schemas/me.py            (yeni)
scripts/test_api_v2_me.py                  (yeni, 13 senaryo)
scripts/test_api_v2_auth.py                (yeni, 14 senaryo)
scripts/dump_openapi_v2.py                 (yeni, codegen kaynağı)
```

### Frontend (Next.js)
```
web/package.json                           (+gen:types + gen:check scripts)
web/next.config.ts                         (rewrites + output: standalone)
web/.env.local + .env.local.example
web/.dockerignore
web/Dockerfile                             (3-stage standalone)
web/eslint.config.mjs                      (3 custom kural)
web/app/globals.css                        (tasarım token'ları)
web/app/layout.tsx                         (Inter + Plus Jakarta Sans + providers)
web/app/page.tsx                           (splash + Giriş yap CTA)
web/app/login/page.tsx                     (yeni)
web/app/login/login-form.tsx               (yeni, RHF + Zod)
web/app/me/account/page.tsx                (yeni, Server Component)
web/app/me/account/me-actions.tsx          (yeni, Client Component)
web/app/api/auth/refresh/route.ts          (BFF proxy)
web/proxy.ts                               (eski middleware.ts'den rename)
web/lib/utils.ts
web/lib/api.ts                             (no-store default + ApiError)
web/lib/api-server.ts                      (Server Component fetch)
web/lib/query-client.ts                    (TanStack Query default)
web/lib/invalidate.ts                      (MutationResponse → invalidateQueries)
web/lib/locale.ts                          (tr-TR Intl)
web/lib/types/me.ts                        (manuel TS interfaces)
web/lib/types/api.d.ts                     (OpenAPI codegen — 83 KB)
web/openapi.v2.json                        (codegen kaynağı, 8 endpoint)
web/components/ui/*.tsx                    (10 primitive)
web/components/section-panel.tsx           (description ZORUNLU)
web/components/jargon-tooltip.tsx
web/components/role-banner.tsx
web/components/theme-provider.tsx
web/components/query-provider.tsx
```

### Altyapı
```
deploy/docker-compose.yml                  (5 servis)
deploy/Caddyfile                           (Strangler Fig route)
deploy/.env.example                        (production şablon)
deploy/README.md                           (deploy adımları + Lightsail uyarısı)
```

---

## 5) Sıradaki — Dalga 1 Önerisi

> **Dalga 1 zaten /me/account ile teslim edildi**. Bu Dalga 0 paketinde
> tamamlandı. Sıradaki **Dalga 2 — Öğrenci paneli**.

Dalga 2 kapsamı:
- Backend `/api/v2/student/*` endpoint'leri (day, week, tasks complete/uncomplete, requests, focus, dna, review, goals)
- 11 OOB swap → MutationResponse.invalidate kalıbının ilk gerçek kullanımı
- Sticky sidebar (Kaynak Durumu) + sinema-koltuk grid modal
- Caddyfile'da `# reverse_proxy /student next:3000` satırlarının `#`'ini kaldır
- Yeni smoke: `scripts/test_api_v2_student.py` (12-15 senaryo tahmin)
- Tüm regresyon yine yeşil kalmalı

**Tahmini efor:** 4-6 iş günü (HTMX yoğunluğu + OOB pattern → React invalidate).

---

## 6) Bilinen Açıklar / İleride Çözülecek

1. **`middleware.ts` deprecated uyarısı** → çözüldü (`proxy.ts`'e rename)
2. **`__Host-` prefix sadece HTTPS arkasında** → dev'de `lgs_*`, prod'da env override
3. **Rate limit in-memory** → web tek replika ile şimdilik OK; Redis backend gelecek dalgalarda
4. **Worker tek replika garantisi** → notification queue'da `FOR UPDATE SKIP LOCKED` eklenmeden scale yasak (R-004)
5. **OpenAPI codegen** → `lib/types/me.ts` manuel + `lib/types/api.d.ts` generated yan yana yaşıyor; gelecekte manuel olanları silebiliriz
6. **`/login` production'da Jinja** → Next.js /login stub yalnız dev test için; Dalga 7'de değişecek

---

## 7) Kabul

Dalga 0'ın 5 paketi tamamlandı:

- [x] **Paket 1** (Adım 1-4): Next.js iskelet + tasarım sistemi + foundation + lib
- [x] **Paket 2** (Adım 5-6): BFF cookie auth backend + 3-kanal dependency
- [x] **Paket 3** (Adım 7-8): Login stub + BFF refresh + /me/account canlı
- [x] **Paket 4** (Adım 9-10): Docker Compose + Caddy Strangler Fig
- [x] **Paket 5** (Adım 11-15): OpenAPI codegen + ESLint kuralları + regresyon + bu rapor

Sistem **production-deploy-ready**: `cd deploy && docker compose up -d --build`
(önce `.env` doldurulmak + Lightsail Static IP attach + DNS A kaydı + Firewall
80/443 açık şartıyla).

Frontend **Dalga 2 başlatılmaya hazır**: tasarım sistemi, invalidate pattern,
3-kanal auth, BFF cookie, Strangler Fig altyapı hepsi yerinde.

---

**Onay kullanıcıdan beklenir:** Dalga 2 (öğrenci paneli) başlatma izni.
