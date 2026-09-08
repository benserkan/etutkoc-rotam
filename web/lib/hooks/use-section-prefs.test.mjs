/**
 * Bölüm tercihi saf fonksiyonları — birim testi (v2, 2026-09-08).
 * Çalıştır: node web/lib/hooks/use-section-prefs.test.mjs   (web/ içinden: node lib/hooks/...)
 *
 * v1'in iki sahada yakalanan hatası burada KALICI senaryo:
 *   (a) raptiye boşken bölüm açık gelmez (simge ne diyorsa o);
 *   (b) kullanım sayısı ne olursa olsun aç/kapa kararına KARIŞMAZ
 *       (v1'de ≥2 kullanımı olan bölüm elle kapatılamıyordu).
 * Tarayıcı testi (scripts/live_section_pins.py) akışı doğrular; bu dosya karar
 * tablosunun her hücresini kapsar. TS kaynağı gerçek derleyiciyle (typescript
 * transpileModule) JS'e çevrilir — regex ile tip sıyırma yok.
 */
import { strict as assert } from "node:assert";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const ts = require("typescript");

const src = readFileSync(join(here, "use-section-prefs.ts"), "utf8");
const js = ts.transpileModule(src, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const exportsObj = {};
new Function("require", "exports", js)(
  (name) => {
    if (name === "react") return { useSyncExternalStore: () => { throw new Error("hook dışı"); } };
    throw new Error(`beklenmeyen import: ${name}`);
  },
  exportsObj,
);
const { resolveOpen, orderByUsage, pruneHits, USAGE_WINDOW_DAYS } = exportsObj;

const NOW = 1_800_000_000_000;
const DAY = 86_400_000;
let n = 0;
const t = (label, got, exp) => {
  n++;
  assert.deepEqual(got, exp, `${label}: beklenen ${JSON.stringify(exp)}, gelen ${JSON.stringify(got)}`);
  console.log(`  [PASS] ${label}`);
};

// --- resolveOpen(pinned, collapsedInSession, openedInSession)
t("sabit → açık", resolveOpen(true, false, false), true);
t("sabit + oturumda katlı → kapalı", resolveOpen(true, true, false), false);
t("sabit + katlı + (anlamsız) geçici-açık bayrağı → yine kapalı", resolveOpen(true, true, true), false);
t("(a) raptiye BOŞ → açılışta KAPALI", resolveOpen(false, false, false), false);
t("raptiye boş + şeritten geçici açıldı → açık", resolveOpen(false, false, true), true);
t("raptiye boş + geçici açık + (anlamsız) katlı bayrağı → açık", resolveOpen(false, true, true), true);

// --- (b) kullanım açık/kapalıya karışmaz: karar fonksiyonu 'hits' almaz.
t("(b) karar fonksiyonu kullanım sayısını almaz (3 parametre)", resolveOpen.length, 3);

// --- pruneHits: pencere
t("pencere dışı damga budanır",
  pruneHits([NOW - (USAGE_WINDOW_DAYS + 1) * DAY, NOW - DAY], NOW), [NOW - DAY]);

// --- orderByUsage: son 7 gün kullanımı çok olan önce; eşitlikte varsayılan sıra
const ids = ["a", "b", "c", "d"];
const pref = (hits, pinned = false) => ({ pinned, hits });
t("kullanım yok → varsayılan sıra",
  orderByUsage(ids, { a: null, b: null, c: null, d: null }, NOW), ["a", "b", "c", "d"]);
t("c en çok kullanılan → başa",
  orderByUsage(ids, { a: null, b: pref([NOW - DAY]), c: pref([NOW - DAY, NOW - 2 * DAY, NOW - 3 * DAY]), d: null }, NOW),
  ["c", "b", "a", "d"]);
t("8 gün önceki kullanım sayılmaz (söner)",
  orderByUsage(ids, { a: null, b: pref([NOW - 8 * DAY, NOW - 9 * DAY]), c: pref([NOW - DAY]), d: null }, NOW),
  ["c", "a", "b", "d"]);
t("sabitlik sırayı DEĞİŞTİRMEZ (şerit ve panel aynı düzen)",
  orderByUsage(ids, { a: null, b: null, c: pref([], true), d: pref([NOW - DAY]) }, NOW),
  ["d", "a", "b", "c"]);
t("eşit kullanımda kararlı (varsayılan sıra korunur)",
  orderByUsage(ids, { a: pref([NOW - DAY]), b: pref([NOW - 2 * DAY]), c: null, d: pref([NOW - DAY]) }, NOW),
  ["a", "b", "d", "c"]);

console.log(`\n=== ${n}/${n} geçti ===`);
