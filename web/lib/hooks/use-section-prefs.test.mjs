/**
 * resolveOpen — saf karar fonksiyonu birim testi (2026-09-08).
 * Çalıştır: node web/lib/hooks/use-section-prefs.test.mjs
 *
 * Tarayıcı testi (scripts/live_section_pins.py) kullanıcı akışını doğrular;
 * bu dosya karar tablosunun HER hücresini kapsar. Canlı testte yakalanan bug
 * (1 kullanım varsayılanı eziyordu → ilk tıklama bölümü katlıyordu) burada
 * kalıcı senaryo.
 */
import { strict as assert } from "node:assert";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// TS dosyasını derlemeden test etmek için resolveOpen'ı metinden çıkarıp
// değerlendiriyoruz (fonksiyon saf, dış bağımlılığı yok).
const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, "use-section-prefs.ts"), "utf8");
const WINDOW = Number(src.match(/USAGE_WINDOW_DAYS = (\d+)/)[1]);
const MIN = Number(src.match(/USAGE_MIN_HITS = (\d+)/)[1]);
const body = src.slice(
  src.indexOf("export function resolveOpen("),
  src.indexOf("\n}\n", src.indexOf("export function resolveOpen(")) + 3,
);
const prune = `function pruneHits(hits, now){const c=now-${WINDOW}*86400000;return hits.filter(t=>t>=c);}`;
const resolveOpen = new Function(
  `${prune}\nconst USAGE_MIN_HITS=${MIN};\n${body
    .replace("export function", "function")
    .replace(/: SectionPref \| null/g, "")
    .replace(/: boolean/g, "")
    .replace(/: number = Date\.now\(\)/, " = Date.now()")}\nreturn resolveOpen;`,
)();

const NOW = 1_800_000_000_000;
const DAY = 86_400_000;
const pref = (o) => ({ mode: "auto", hits: [], lastManualOpen: null, ...o });
let n = 0;
const t = (label, got, exp) => {
  n++;
  assert.equal(got, exp, `${label}: beklenen ${exp}, gelen ${got}`);
  console.log(`  [PASS] ${label}`);
};

// --- varsayılan
t("tercih yok → varsayılan (açık)", resolveOpen(null, true, NOW), true);
t("tercih yok → varsayılan (katlı)", resolveOpen(null, false, NOW), false);

// --- sabit
t("sabit → hep açık", resolveOpen(pref({ mode: "pinned" }), false, NOW), true);

// --- BUG SENARYOSU: 1 kullanım varsayılanı EZMEZ
t("açık varsayılan + 1 iç tıklama → AÇIK KALIR",
  resolveOpen(pref({ hits: [NOW - 1000] }), true, NOW), true);
t("katlı varsayılan + 1 iç tıklama → katlı kalır",
  resolveOpen(pref({ hits: [NOW - 1000] }), false, NOW), false);

// --- alışkanlık
t("≥2 taze kullanım → açık (varsayılan katlı olsa da)",
  resolveOpen(pref({ hits: [NOW - DAY, NOW - 2 * DAY] }), false, NOW), true);
t("2 kullanım ama 8 gün önce → söner, katlı",
  resolveOpen(pref({ hits: [NOW - 8 * DAY, NOW - 9 * DAY], lastManualOpen: true }), false, NOW), false);

// --- elle karar
t("elle açtı (1 hit) → açık",
  resolveOpen(pref({ hits: [NOW - 1000], lastManualOpen: true }), false, NOW), true);
t("elle kapattı → katlı (taze kullanım olsa da 1 tane)",
  resolveOpen(pref({ hits: [NOW - 1000], lastManualOpen: false }), true, NOW), false);
t("elle kapattı ama ≥2 kullanım → alışkanlık kazanır, açık",
  resolveOpen(pref({ hits: [NOW - 1000, NOW - 2000], lastManualOpen: false }), false, NOW), true);
t("elle açtı, sonra 8 gün kullanmadı → katlanır",
  resolveOpen(pref({ hits: [NOW - 8 * DAY], lastManualOpen: true }), true, NOW), false);

console.log(`\n=== ${n}/${n} geçti ===`);
