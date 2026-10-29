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

1. **Cloudflare → SSL/TLS → Overview → Full (strict)**.
   (Flexible SEÇME: Cloudflare–sunucu arası şifresiz olur ve Caddy'nin https
   yönlendirmesiyle sonsuz döngüye girer.)
2. **SSL/TLS → Edge Certificates → Always Use HTTPS: KAPALI** bırak. Yönlendirmeyi
   Caddy zaten yapıyor; açık olursa Let's Encrypt yenilemesi (port 80 HTTP-01)
   aksayabilir. Min TLS 1.2, TLS 1.3 açık, HSTS'yi Cloudflare'de AÇMA (Caddy gönderiyor).
3. **DNS → `rotam` kaydı → Proxied (turuncu)**. 1-5 dk içinde yayılır.
4. Doğrula: `curl -sI https://rotam.etutkoc.com/healthz` → `server: cloudflare` +
   `cf-ray` başlığı. Bir girişten sonra Süper Admin → Güvenlik Kamarası → Oturumlar'da
   **kendi gerçek IP'n** görünmeli (Cloudflare IP'si değil).
5. **Origin kilidi** (asıl güvenlik kazancı): Hetzner Cloud → Firewalls → 80/443
   yalnız Cloudflare aralıklarına açık (https://www.cloudflare.com/ips/), 22 (SSH)
   kendi IP'ne. Bunu yapmazsan saldırgan Cloudflare'i atlayıp doğrudan sunucuya gider.
6. Önerilen ayarlar: Speed → Brotli açık, HTTP/3 açık; Caching → varsayılan
   (HTML önbelleğe alınmaz, `/_next/static` zaten `immutable` → kenarda tutulur);
   Security → Bot Fight Mode (WhatsApp/iyzico/ZeptoMail webhook'larını bloklarsa
   `/webhooks/*` için WAF istisnası ekle).

## Geri alma

DNS kaydını tekrar gri buluta çevir (anında). Caddy değişikliği gri bulutta zararsız.

## Yılda bir

Cloudflare IP aralıkları değişirse Caddyfile `trusted_proxies` + Hetzner firewall güncellenir.
