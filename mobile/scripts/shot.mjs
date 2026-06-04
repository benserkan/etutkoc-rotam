// Mobil ekran görüntüsü (UX döngüsü A) — exported web build'i mobil viewport'ta
// render edip PNG alır. Kendi clean-URL statik sunucusunu açar (expo-router
// /login bekler, /login.html değil).
// Kullanım: node scripts/shot.mjs <distDir> <route> <out.png>
import { chromium } from "playwright";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const DIST = path.resolve(process.argv[2] || "dist");
const route = process.argv[3] || "/login";
const out = process.argv[4] || "shot.png";
const PORT = 8123;

const MIME = {
  ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".png": "image/png",
  ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml",
  ".ico": "image/x-icon", ".woff": "font/woff", ".woff2": "font/woff2",
  ".ttf": "font/ttf", ".map": "application/json",
};

function resolveFile(urlPath) {
  let p = decodeURIComponent((urlPath || "/").split("?")[0]);
  if (p === "/") p = "/index.html";
  for (const c of [p, p + ".html", path.join(p, "index.html")]) {
    const fp = path.join(DIST, c);
    if (fp.startsWith(DIST) && fs.existsSync(fp) && fs.statSync(fp).isFile()) return fp;
  }
  return null;
}

const server = http.createServer((req, res) => {
  const fp = resolveFile(req.url);
  if (!fp) {
    res.statusCode = 404;
    res.end("not found");
    return;
  }
  res.setHeader("content-type", MIME[path.extname(fp)] || "application/octet-stream");
  fs.createReadStream(fp).pipe(res);
});

await new Promise((r) => server.listen(PORT, "127.0.0.1", r));
const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 2,
});
const page = await ctx.newPage();
await page.goto(`http://127.0.0.1:${PORT}${route}`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(1800);
await page.screenshot({ path: out });
await browser.close();
server.close();
console.log("shot saved:", out);
