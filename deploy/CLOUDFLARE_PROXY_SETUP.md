# rotam.etutkoc.com — Cloudflare proxy (turuncu bulut) geçişi

Durum (2026-10-29): DNS Cloudflare'de, `rotam` kaydı **gri bulut** (yalnız DNS).
Sunucu tarafı hazır: Caddy, Cloudflare IP aralıklarından gelen isteklerde gerçek
istemci IP'sini `CF-Connecting-IP`'den okur (Caddyfile başındaki global blok).

## ÖN ŞART — açmadan önce çözülmesi gereken iki sınır

Cloudflare Free/Pro planında:

| Sınır | Değer | Bizdeki etkisi |
|---|---|---|
| İstek gövdesi | **100 MB** | Süper admin "Tam kitap tara" (≤450 MB PDF) yüklenemez |
| Yanıt bekleme | **100 sn** | Deneme karnesi PDF içe aktarma (2-5 dk), kapak+içindekiler tarama uzun sürerse **524 hatası** |

Bu yüzden turuncu bulut, bu uçlar **arka plan işine** (yükle → iş numarası → ilerlemeyi yokla)
çevrilmeden AÇILMAMALI. Kitap tarama zaten arka plan işi; yalnız dosya boyutu sorun.

## Geçiş adımları (ön şart bittikten sonra)

1. **SSL modu yalnız bizim alt alan adlarımız için Full (strict)** — UYGULANDI 2026-10-29:
   Rules → Configuration Rules → "Rotam - Full strict SSL"
   (`http.host in {"rotam.etutkoc.com" "analytics.etutkoc.com"}` → SSL: Strict).
   Bölgenin geneli **Flexible** kalır: etutkoc.com (OVH, 51.38.232.148) ona dayanıyor;
   genel modu değiştirmek koçluk sitesini bozabilir. Rotam için Flexible SEÇİLMEZ
   (Cloudflare–sunucu arası şifresiz olur, Caddy'nin https yönlendirmesiyle döngü).
2. **SSL/TLS → Edge Certificates → Always Use HTTPS: KAPALI** bırak. Yönlendirmeyi
   Caddy zaten yapıyor; açık olursa Let's Encrypt yenilemesi (port 80 HTTP-01)
   aksayabilir. Min TLS 1.2, TLS 1.3 açık, HSTS'yi Cloudflare'de AÇMA (Caddy gönderiyor).
3. **DNS → `rotam` kaydı → Proxied (turuncu)**. 1-5 dk içinde yayılır.
4. Doğrula: `curl -sI https://rotam.etutkoc.com/healthz` → `server: cloudflare` +
   `cf-ray` başlığı. Bir girişten sonra Süper Admin → Güvenlik Kamarası → Oturumlar'da
   **kendi gerçek IP'n** görünmeli (Cloudflare IP'si değil).
5. **Origin kilidi** (asıl güvenlik kazancı — UYGULANDI 2026-10-29: Hetzner Firewall `firewall-1`, 22 açık, 80/443 yalnız CF aralıkları). Bunu yapmazsan
   saldırgan Cloudflare'i atlayıp doğrudan 178.105.221.223'e gider. İki yol:
   - **Hetzner Cloud → Firewalls** (en kolay): gelen 80/443 yalnız
     https://www.cloudflare.com/ips/ aralıkları, 22 açık; sunucuya uygula.
   - **Sunucuda** (`deploy/cf-origin-lock.sh`): Docker IPv4 yayını ufw'yi atlar
     (DNAT → FORWARD → DOCKER-USER), kural oraya konur; systemd ile kalıcı:
     ```
     cp deploy/cf-origin-lock.sh /usr/local/sbin/ && chmod +x /usr/local/sbin/cf-origin-lock.sh
     # /etc/systemd/system/cf-origin-lock.service: Type=oneshot, After/Requires=docker.service,
     # ExecStart=/usr/local/sbin/cf-origin-lock.sh, RemainAfterExit=yes, WantedBy=multi-user.target
     systemctl daemon-reload && systemctl enable --now cf-origin-lock
     ```
     IPv6 docker-proxy ile INPUT'a gelir → ufw: `80/tcp`, `443/tcp` "Anywhere" kurallarını
     silip her CF v6 aralığı için `ufw allow proto tcp from <aralık> to any port 80,443`.
   Doğrula: `curl -sI https://rotam.etutkoc.com/healthz` 200 kalmalı;
   `curl -k --resolve rotam.etutkoc.com:443:178.105.221.223 https://rotam.etutkoc.com/healthz`
   (dışarıdan) zaman aşımına düşmeli.
   Durum (2026-10-29): `rotam` + `analytics` kayıtları Proxied; Bot Fight Mode KAPALI
   (bilinçli — mobil uygulama ve webhook'ları sınayabilir); Always Use HTTPS kapalı.
   Doğrulandı: Server: cloudflare + CF-RAY, Caddy loglarında client_ip gerçek ziyaretçi,
   /webhooks/zeptomail 200, /webhooks/revenuecat 403 (uygulamanın kendi yetki reddi —
   `via: 1.1 Caddy`), iyzico callback 303, Turnstile ucu çalışıyor, Plausible js 200.
6. Önerilen ayarlar: Speed → Brotli açık, HTTP/3 açık; Caching → varsayılan
   (HTML önbelleğe alınmaz, `/_next/static` zaten `immutable` → kenarda tutulur);
   Security → Bot Fight Mode (WhatsApp/iyzico/ZeptoMail webhook'larını bloklarsa
   `/webhooks/*` için WAF istisnası ekle).

## Geri alma

DNS kaydını tekrar gri buluta çevir (anında). Caddy değişikliği gri bulutta zararsız.

## Yılda bir

Cloudflare IP aralıkları değişirse Caddyfile `trusted_proxies` + Hetzner firewall güncellenir.
