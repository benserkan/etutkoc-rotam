# Plausible (self-host) — Site Analitiği Kurulumu

Gizlilik-dostu, çerezsiz, KVKK-uyumlu site analitiği. Veri kendi sunucumuzda kalır.
İzleme script'i **ana alan adından (first-party)** sunulur → reklam engelleyiciler
engellemez → doğru ölçüm.

Mimari:
- `plausible` (uygulama) + `plausible_events_db` (ClickHouse, olaylar) +
  `plausible_db` (Postgres, meta) — hepsi `docker-compose.yml`'de hazır.
- **Tracking** (script `/js/*` + olaylar `/api/event`) → Caddy ana alan adından
  `plausible`'a proxy (first-party). Bu satırlar Caddyfile'da ZATEN aktif.
- **Pano** → ayrı alt alan adı `analytics.etutkoc.com` (Caddyfile'da yorumlu blok;
  aşağıda açılır). Süper admin `/admin/analytics`'te bu pano **gömülü** gösterilir.

---

## 1. Gizli anahtarları üret + `.env`'e yaz

Sunucuda `/opt/etutkoc/deploy/.env` içine:

```bash
# Güçlü gizli anahtarlar
openssl rand -base64 48   # → PLAUSIBLE_SECRET_KEY_BASE
openssl rand -base64 32   # → PLAUSIBLE_TOTP_VAULT_KEY
openssl rand -hex 24      # → PLAUSIBLE_DB_PASSWORD
```

`.env`:
```
PLAUSIBLE_HOST=analytics.etutkoc.com
PLAUSIBLE_SECRET_KEY_BASE=<üretilen>
PLAUSIBLE_TOTP_VAULT_KEY=<üretilen>
PLAUSIBLE_DB_PASSWORD=<üretilen>
PLAUSIBLE_DISABLE_REGISTRATION=false   # İLK admin'i oluşturmak için geçici false
```

> Next.js tarafı (`PLAUSIBLE_DOMAIN`, `PLAUSIBLE_SHARED_URL`, ...) 4. adımda doldurulur.

## 2. DNS — analitik alt alan adı

Cloudflare'de `analytics` A kaydı → sunucu IP (**178.105.221.223**), **DNS-only
(gri bulut)** — Caddy Let's Encrypt için. (Ana site `rotam` ile aynı desen.)

## 3. Plausible'ı ayağa kaldır + Caddy panosunu aç

```bash
cd /opt/etutkoc/deploy
docker compose up -d plausible_db plausible_events_db plausible
docker compose logs -f plausible        # "Access ... at ..." görene kadar bekle
```

Caddyfile'da **analitik pano bloğunu** aç (en alttaki yorumlu 3 satır):
```
analytics.etutkoc.com {
    reverse_proxy plausible:8000
}
```
Sonra:
```bash
docker compose restart proxy            # Caddy yeni site için otomatik HTTPS alır
```

`https://analytics.etutkoc.com` açılmalı (Plausible kurulum ekranı).

## 4. İlk admin + site + paylaşım bağlantısı

1. `https://analytics.etutkoc.com` → **Register** ile ilk admin hesabını oluştur.
2. Sonra `.env`'de `PLAUSIBLE_DISABLE_REGISTRATION=true` yap +
   `docker compose up -d plausible` (açık kayıt kapanır).
3. Plausible panelinde **+ Add Website** → domain: `rotam.etutkoc.com` (timezone:
   Europe/Istanbul). Bu, izleme script'inin `data-domain`'i ile AYNI olmalı.
4. **Site Settings → Visibility → Shared Links → + New Link** → (şifre opsiyonel) →
   üretilen bağlantıyı kopyala. Gömme için sonuna `&embed=true&theme=light` ekle.
   Örn: `https://analytics.etutkoc.com/share/rotam.etutkoc.com?auth=XXXX&embed=true&theme=light`

## 5. Next.js'i analitiğe bağla

`.env`:
```
PLAUSIBLE_DOMAIN=rotam.etutkoc.com
PLAUSIBLE_SRC=/js/script.js
PLAUSIBLE_SHARED_URL=https://analytics.etutkoc.com/share/rotam.etutkoc.com?auth=XXXX&embed=true&theme=light
PLAUSIBLE_DASHBOARD_URL=https://analytics.etutkoc.com
```
```bash
docker compose up -d next
```

Artık:
- Her sayfa görüntüleme Plausible'a düşer (first-party, çerezsiz).
- Süper admin → **Site Analitiği** (`/admin/analytics`) → gömülü pano.

---

## Doğrulama

```bash
# Script first-party geliyor mu (200 + JS)
curl -sI https://rotam.etutkoc.com/js/script.js | head -5
# Olay ucu (Plausible 202 döner)
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://rotam.etutkoc.com/api/event \
  -H "Content-Type: application/json" \
  -d '{"name":"pageview","url":"https://rotam.etutkoc.com/","domain":"rotam.etutkoc.com"}'
```
Tarayıcıda anasayfayı aç → Plausible "Realtime" 1 ziyaretçi göstermeli.

## Kapatma / geri alma (rollback)

- Analitiği kapat: `.env`'de `PLAUSIBLE_DOMAIN=` (boş) + `docker compose up -d next`
  → script basılmaz, panel kurulum rehberine döner. Uygulama etkilenmez.
- Servisleri durdur: `docker compose stop plausible plausible_events_db plausible_db`.

## Kaynak kullanımı (CPX notu)

ClickHouse en aç servis. `deploy/clickhouse/*.xml` log/diski kıstı. Bellek darsa
`plausible_events_db`'ye compose'da `mem_limit: 1g` eklenebilir. İlk kurulumda
RAM'i izle (`docker stats`).
