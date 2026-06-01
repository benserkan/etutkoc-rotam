/*
 * Kill-switch Service Worker.
 *
 * Mevcut ETÜTKOÇ uygulaması Service Worker KULLANMAZ (PWA terk edildi). Bu dosya
 * yalnızca, terk edilen PWA döneminden kalma ve hâlâ tarayıcısında /sw.js kayıtlı
 * olan kullanıcıların eski SW'sini KENDİLİĞİNDEN sökmek için vardır.
 *
 * Eski SW, periyodik güncelleme kontrolünde (her gezinmede / ~24 saatte bir) bu
 * yeni script'i ağdan çeker (SW güncelleme fetch'i eski SW'yi bypass eder, spec
 * gereği). İçerik değiştiği için yeni sürüm install→activate olur; activate'te:
 *   1) tüm Cache Storage anahtarlarını siler (eski cache-first içerik gider),
 *   2) kendini unregister eder (SW tamamen kalkar),
 *   3) açık sekmeleri taze yükler (eski authenticated görünüm temizlenir).
 *
 * Böylece "çıkış yaptım ama cache'li korumalı sayfa açılıyor" sorunu, kullanıcı
 * DevTools'a girmeden otomatik çözülür.
 */
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      try {
        const keys = await caches.keys();
        await Promise.all(keys.map((k) => caches.delete(k)));
      } catch {
        // cache silme başarısız olsa da unregister + reload'a devam et
      }
      try {
        await self.registration.unregister();
      } catch {
        /* yoksay */
      }
      try {
        const clients = await self.clients.matchAll({ type: "window" });
        for (const client of clients) {
          client.navigate(client.url);
        }
      } catch {
        /* yoksay */
      }
    })(),
  );
});

// Hiçbir isteği INTERCEPT etme — varsayılan ağ davranışı (eski cache-first
// davranışını nötrler). respondWith çağrılmaz → tarayıcı ağdan çeker.
self.addEventListener("fetch", () => {});
