/*
 * Kill-switch Service Worker (alternatif yol /service-worker.js).
 * İçerik /sw.js ile aynı: eski (terk edilen PWA) SW'leri otomatik söker.
 * Bkz. /sw.js — bazı eski PWA kurulumları bu yola kaydetmiş olabilir.
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
        /* devam */
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

self.addEventListener("fetch", () => {});
