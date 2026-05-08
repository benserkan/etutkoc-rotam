# Deploy Rehberi

LGS Takip uygulamasını uzak sunucuya yükleme yolları.

## Hızlı Karar

| Durum | Öneri |
|---|---|
| İlk deploy, az öğrenci, hızlı başlamak istiyorum | **PaaS (Render)** — aşağıdaki §1 |
| Çok öğrenci olacak, esneklik / düşük maliyet öncelik | **VPS (Hetzner / DigitalOcean)** — §2 |
| Sadece denemek (geçici) | **PaaS Free Tier** — §1 |

---

## §1 — PaaS Deploy (Render.com)

### Hazırlık (tek seferlik)

1. **GitHub hesabı** ve uzak repo. Bu projeyi push'la:
   ```bash
   cd D:\LGS-Program
   git init
   git add .
   git commit -m "ilk commit"
   # GitHub'da boş repo aç, sonra:
   git remote add origin https://github.com/SENİNADIN/lgs-takip.git
   git push -u origin main
   ```

2. **Render hesabı** aç: https://render.com (GitHub ile sign in)

3. **Blueprint deploy**:
   - Render dashboard → **New > Blueprint**
   - Repo'yu bağla
   - Render `render.yaml`'ı bulur, otomatik kurar:
     - Web servisi (Docker, gunicorn)
     - Postgres veritabanı (free tier)
   - Deploy başlar (~5 dakika)

4. **İlk açılış** sonrası dashboard'da:
   - URL'yi kopyala (örn. `https://lgs-takip.onrender.com`)
   - **Environment** sekmesine geç:
     - `APP_BASE_URL=https://lgs-takip.onrender.com` (mail linkleri için)
     - SMTP istiyorsan: `SMTP_HOST`, `SMTP_USER`, vs. ekle, `EMAIL_ENABLED=true`
   - "Save, Rebuild" — sunucu yeniden başlar

5. **Müfredat seed**:
   - Render shell tab'ından (web servisi → Shell):
     ```
     python -m scripts.seed --teacher
     ```
   - Bu öğretmen hesabı oluşturur: `ogretmen@lgs.local` / `ogretmen123` — **hemen değiştir!**

### Güncelleme (her seferinde)
```bash
git add . && git commit -m "değişiklik" && git push
```
Render otomatik yeniden deploy eder.

### Maliyet
- **Free tier**: web 512MB RAM (15 dk inaktivite sonrası uyur, ilk istek 30sn yavaş), Postgres 1GB (90 gün retention)
- **Starter** ($7/ay web + $7/ay db): hep açık, 256MB+ DB

---

## §2 — VPS Deploy (Hetzner CX22 / DigitalOcean Droplet)

### Sunucu kurulumu (~30 dk, tek seferlik)

#### 2.1 Sunucu Kirala
- Hetzner: https://hetzner.cloud — **CX22** (€4.5/ay, 2 vCPU, 4GB RAM)
- DigitalOcean: $6/ay basic droplet
- İşletim sistemi: **Ubuntu 24.04 LTS**

#### 2.2 SSH ile Bağlan
```bash
ssh root@SUNUCU_IP
```

#### 2.3 Temel Paketler
```bash
apt update && apt upgrade -y
apt install -y python3.12 python3.12-venv python3-pip nginx postgresql certbot python3-certbot-nginx git
```

#### 2.4 Postgres Hazırla
```bash
sudo -u postgres psql -c "CREATE USER lgs WITH PASSWORD 'GÜVENLİ_ŞİFRE';"
sudo -u postgres psql -c "CREATE DATABASE lgs OWNER lgs;"
```

#### 2.5 Uygulamayı Çek
```bash
cd /opt
git clone https://github.com/SENİNADIN/lgs-takip.git
cd lgs-takip
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

#### 2.6 .env oluştur
```bash
cat > .env <<EOF
DATABASE_URL=postgresql://lgs:GÜVENLİ_ŞİFRE@localhost/lgs
SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
DEBUG=false
APP_BASE_URL=https://etutkoc.com
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=app-password
SMTP_FROM=ETÜTKOÇ <your@gmail.com>
SMTP_USE_TLS=true
EOF
chmod 600 .env
```

#### 2.7 Migration + Seed
```bash
.venv/bin/alembic upgrade head
.venv/bin/python -m scripts.seed --teacher
```

#### 2.8 systemd Servisi
`/etc/systemd/system/lgs-takip.service`:
```ini
[Unit]
Description=LGS Takip
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/lgs-takip
EnvironmentFile=/opt/lgs-takip/.env
ExecStart=/opt/lgs-takip/.venv/bin/gunicorn app.main:app -w 2 -k uvicorn.workers.UvicornWorker -b 127.0.0.1:8000 --timeout 60
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
chown -R www-data:www-data /opt/lgs-takip
systemctl daemon-reload
systemctl enable --now lgs-takip
systemctl status lgs-takip   # "active (running)" görmelisin
```

#### 2.9 Nginx Reverse Proxy
`/etc/nginx/sites-available/lgs-takip`:
```nginx
server {
    listen 80;
    server_name etutkoc.com www.etutkoc.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
```bash
ln -s /etc/nginx/sites-available/lgs-takip /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

#### 2.10 Domain & SSL
1. Domain sağlayıcında DNS A kaydını sunucu IP'sine yönlendir (`etutkoc.com → 1.2.3.4`)
2. DNS aktif olunca:
   ```bash
   certbot --nginx -d etutkoc.com -d www.etutkoc.com
   ```
3. Otomatik yenileme: `systemctl status certbot.timer` (varsayılan aktif)

### Güncelleme
```bash
ssh root@etutkoc.com
cd /opt/lgs-takip
git pull
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
systemctl restart lgs-takip
```

İsteğe bağlı kısa script `deploy.sh` içine konabilir.

### Maliyet
- Hetzner CX22: €4.5/ay (≈$5)
- Domain: ~$10/yıl
- Toplam: ~$60/yıl

---

## Genel Sonrası Notlar

### Şifre Güvenliği
- `SESSION_SECRET` mutlaka random uzun string olmalı (yukarıdaki secrets.token_urlsafe ile)
- Demo öğretmen hesabı `ogretmen@lgs.local` ilk girişte şifre değiştirilmeli (bu özelliği Sprint 11+ ekleyeceğiz)

### Yedekleme
- **Render**: paid tier'larda otomatik (free'de yok)
- **VPS**: cron + `pg_dump`:
  ```cron
  0 3 * * * pg_dump -U lgs lgs | gzip > /var/backups/lgs-$(date +\%F).sql.gz
  ```

### İzleme
- `https://etutkoc.com/healthz` JSON döner (`{"status":"ok","db":"up"}`)
- Uptime servisi (UptimeRobot — bedava): bu URL'i her 5 dk kontrol eder, çökerse mail atar

### Sonraki adımlar
- Sprint 11: ilk girişte şifre değiştirme zorunluluğu
- Sprint 12: mobile uygulama (PWA veya React Native)
