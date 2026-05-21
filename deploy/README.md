# ETÜTKOÇ — Lightsail Docker Compose Deploy

Bu dizin, AWS Lightsail VPS üzerinde 5 container'lı Docker Compose ile sistemi
production'a çıkaracak konfigürasyonu içerir.

## Mimari

```
                    [Internet]
                        │
                        ▼ :80, :443
              ┌──────────────────┐
              │ proxy (Caddy)    │  ◀── Let's Encrypt otomatik HTTPS
              │  Strangler Fig   │      Path-based routing
              └────────┬─────────┘
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐    ┌─────────┐    ┌──────────┐
   │  web    │    │  next   │    │  worker  │ ◀── replicas: 1
   │ FastAPI │    │ Next.js │    │ cron +   │     (duplicate yasak)
   │ Jinja + │    │ SSR/RSC │    │ dispatch │
   │ /api/v* │    └────┬────┘    └────┬─────┘
   └────┬────┘         │              │
        └──────────────┼──────────────┘
                       ▼
                  ┌─────────┐
                  │  db     │
                  │ Postgres│
                  └─────────┘
```

## Servisler

| Servis | İmaj | Görev | Background |
|---|---|---|---|
| `db` | postgres:16-alpine | Veritabanı (volume'da kalıcı) | — |
| `web` | lgs-backend (Dockerfile) | FastAPI + Jinja sayfaları + /api/v1 + /api/v2 + webhooks | **KAPALI** |
| `worker` | lgs-backend (aynı image) | Cron job + notification dispatcher | **AÇIK** (sadece burada) |
| `next` | lgs-next (web/Dockerfile) | Next.js App Router | — |
| `proxy` | caddy:2-alpine | Reverse proxy + HTTPS + path routing | — |

## Hazırlık

### 1. .env dosyası

```bash
cp .env.example .env
# .env'yi düzenle — tüm __STRONG_RANDOM__ ve __META_*__ alanlarını doldur
# Güçlü secret üretim örnekleri:
#   openssl rand -hex 32         # SESSION_SECRET, JWT_SECRET, POSTGRES_PASSWORD
```

### 2. DNS — ⚠️ ÖNEMLİ ADIM

> **🔴 LIGHTSAIL STATIC IP ZORUNLU**
>
> Lightsail instance'ının varsayılan public IP'si **yeniden başlatma sonrası
> değişebilir**. Caddy bir kez Let's Encrypt sertifikası alıp DNS'e bağlandıktan
> sonra IP değişirse SSL bozulur ve sistem erişilemez hale gelir.
>
> **Yapılması gereken (kurulum sırasında):**
> 1. Lightsail console → **Networking → Static IPs → Create static IP**
> 2. Bu Static IP'yi **attach** ile mevcut instance'a bağla (ücretsiz)
> 3. Static IP'yi domain'inizin DNS A kaydına yazın (Cloudflare/Route53/vs.)
> 4. Bu adımı atlamak = ileride saatlerce kayıp + sertifika kotası tüketimi

Caddy DNS doğrulaması yapmaz; HTTP-01 challenge için 80 portunun açık olması
yeterli. Lightsail firewall'da varsayılan olarak 80/443 açık değildir —
**Networking → Firewall'a 80 ve 443'ü ekleyin**.

### 3. Meta WhatsApp (varsa)

Meta Business Manager'da webhook URL:
```
https://app.etutkoc.com/webhooks/whatsapp
```
Verify token = `WHATSAPP_WEBHOOK_VERIFY_TOKEN` (.env'de yazılan değerle aynı).

## Çalıştırma

```bash
cd deploy
docker compose up -d --build
```

İlk açılış sırası (compose otomatik bekler):

1. `db` ayağa kalkar, `pg_isready` yeşil
2. `web` başlar → `./start.sh`:
   - `alembic upgrade head` — şema göçü
   - `python -m scripts.seed` — müfredat seed (idempotent)
   - `gunicorn` çalışmaya başlar → `/healthz` 200
3. `worker` web sağlıklı olduğunda başlar → `app.dispatcher --loop`
4. `next` web sağlıklı olduğunda başlar → server.js (port 3000)
5. `proxy` HTTPS sertifikası alır (~10-30 sn) → public servis hazır

Logları takip et:

```bash
docker compose logs -f                # tüm servisler
docker compose logs -f web            # sadece FastAPI
docker compose logs -f worker         # cron + dispatcher
docker compose logs -f proxy          # Caddy + Let's Encrypt
```

## Strangler Fig dalga aç/kapa

Bir dalganın Next.js teslim edildiğinde:

1. `Caddyfile` içinde ilgili `# reverse_proxy /xxx next:3000` satırının `#`'ini kaldır
2. Caddy'yi reload et (graceful, downtime yok):

```bash
docker compose exec proxy caddy reload --config /etc/caddy/Caddyfile
```

Geri dönüş için (< 60 saniye rollback — R-020 garantisi):

1. Aynı satıra `#` geri ekle
2. `caddy reload`

## Yardımcı komutlar

```bash
# Postgres'e bağlan (sorgulama, debug)
docker compose exec db psql -U lgs -d lgs

# FastAPI içinde shell — REPL veya scripts
docker compose exec web python -c "from app.database import SessionLocal; ..."

# Manuel migration (gerekirse)
docker compose exec web alembic upgrade head

# Worker'ı yeniden başlat (cron sıkışırsa)
docker compose restart worker

# Tüm durdurma + temizlik
docker compose down                   # container'ları sil, volume kalsın
docker compose down -v                # volume'leri de sil (DİKKAT: tüm veri gider)

# Image boyutlarını kontrol et
docker images | grep -E '(lgs-|caddy|postgres)'
```

## Yedekleme

```bash
# Postgres dump (cron job ile günlük yapılması önerilir)
docker compose exec db pg_dump -U lgs lgs > /backups/lgs-$(date +%F).sql

# Caddy sertifikaları
docker run --rm -v lgs-caddy-data:/data alpine tar czf - -C /data . > caddy-data.tar.gz
```

## Güvenlik notları

- `web` ve `worker` sadece `internal` network'te — dışa kapalı
- `db` sadece `internal` network'te — dışa kapalı
- Sadece `proxy` 80/443 dışa açık
- `__Host-` cookie prefix HTTPS ardında devreye giriyor (Caddy SSL sağlıyor)
- Postgres parolası env'den; volume root yetkisi gerektirir

## Bilinen sınırlamalar

- **Worker scale yasak**: `notification_log` queue'da SELECT...FOR UPDATE SKIP LOCKED
  yok; tek replika ile garanti ediliyor. Birden fazla worker → duplicate email/WhatsApp
  riski (R-004).
- **Rate limit in-memory**: `web` çoklu replikada `lgs_login_limiter` cache'i replikalar
  arasında paylaşılmaz. Şimdilik web=1 replika önerilir veya Redis backend
  (gelecekteki dalga).
- **Web replicate**: `WEB_WORKERS` env ile gunicorn worker sayısı ayarlanabilir; tek
  proses içinde — yatay scale yapılmaz.
