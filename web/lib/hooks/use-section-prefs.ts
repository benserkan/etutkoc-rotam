"use client";

/**
 * Bölüm sabitleme (raptiye) + oturum-içi aç/kapa + kullanım sayacı (v2, 2026-09-08).
 *
 * v1 (aynı gün) iki durumu tek simgeye sıkıştırmıştı: raptiye BOŞ ama bölüm
 * "alışkanlık" nedeniyle AÇIK gelebiliyordu; ≥2 kullanımı olan bölüm başlığa
 * tıklanınca KAPANMIYORDU (alışkanlık elle kapatmayı eziyordu). Koç: "sabitleme
 * devre dışı görünüyor ama menü açık — mantık ters" + "bastığımda kapanmıyor".
 *
 * v2 — simge ne diyorsa o:
 *   · pinned (raptiye DOLU)  → her açılışta panelde AÇIK (docked).
 *                              Oturum içinde başlıktan katlanabilir; yenilemede
 *                              yine açık.
 *   · unpinned (raptiye BOŞ) → açılışta KAPALI; şeritteki simgesinden tek tıkla
 *                              GEÇİCİ açılır (peek). Yenilemede kapanır.
 *   Kullanım sayacı (son 7 gün) artık açık/kapalıya KARIŞMAZ; yalnız SIRALAMAYI
 *   belirler: en çok kullanılan bölüm şeritte ve panelde üstte. Sıra sayfa
 *   yüklenişinde dondurulur (oturum içinde bölümler yer değiştirmez).
 *
 * KALICILIK: tarayıcı (localStorage) — kullanıcı kararı. `useSyncExternalStore`
 * (sunucu snapshot'ı varsayılan, istemci gerçek değer → hydration uyuşmazlığı
 * yok, effect yok). Her okuma/yazma try/catch: depolama yoksa varsayılan davranış.
 *
 * Eski v1 kaydı (`mode: "pinned" | "auto"`) okunur: pinned → pinned, auto → unpinned.
 */

import { useSyncExternalStore } from "react";

export interface SectionPref {
  pinned: boolean;
  /** Kullanım damgaları (epoch ms) — pencere dışındakiler budanır */
  hits: number[];
}

export const USAGE_WINDOW_DAYS = 7;

const KEY_PREFIX = "rotam:section:";
const listeners = new Set<() => void>();
/** Sabit bölümün OTURUM İÇİ katlanması (bellekte; yenilemede raptiye kazanır). */
const sessionCollapsed = new Set<string>();
/** Sabit olmayan bölümün OTURUM İÇİ geçici açılışı (peek). */
const sessionOpen = new Set<string>();

function emit(): void {
  for (const l of listeners) l();
}

function key(id: string): string {
  return `${KEY_PREFIX}${id}`;
}

function safeParse(raw: string): SectionPref | null {
  try {
    const p = JSON.parse(raw) as Partial<SectionPref> & { mode?: string };
    return {
      pinned: p.pinned === true || p.mode === "pinned",
      hits: Array.isArray(p.hits) ? p.hits.filter((n) => typeof n === "number") : [],
    };
  } catch {
    return null;
  }
}

function readRaw(id: string): string {
  try {
    return window.localStorage.getItem(key(id)) ?? "";
  } catch {
    return "";
  }
}

function readPref(id: string): SectionPref | null {
  const raw = readRaw(id);
  return raw ? safeParse(raw) : null;
}

function writePref(id: string, pref: SectionPref): void {
  try {
    window.localStorage.setItem(key(id), JSON.stringify(pref));
  } catch {
    /* depolama yoksa sessiz */
  }
  emit();
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => {
    if (e.key && e.key.startsWith(KEY_PREFIX)) cb();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

export function pruneHits(hits: number[], now: number): number[] {
  const cutoff = now - USAGE_WINDOW_DAYS * 86_400_000;
  return hits.filter((t) => t >= cutoff);
}

/**
 * Saf karar: bölüm görünür mü?
 *   pinned   → oturumda katlanmadıysa açık
 *   unpinned → oturumda geçici açıldıysa açık
 */
export function resolveOpen(
  pinned: boolean,
  collapsedInSession: boolean,
  openedInSession: boolean,
): boolean {
  return pinned ? !collapsedInSession : openedInSession;
}

/**
 * Saf sıralama: en çok kullanılan (son 7 gün) önce; eşitlikte varsayılan sıra.
 * Sabitler ayrıca öne alınmaz — şerit ve panel aynı sırayı paylaşır, koç her
 * iki yerde de aynı düzeni görür.
 */
export function orderByUsage(
  ids: readonly string[],
  prefs: Record<string, SectionPref | null>,
  now: number,
): string[] {
  const score = (id: string) => {
    const p = prefs[id];
    return p ? pruneHits(p.hits, now).length : 0;
  };
  return ids
    .map((id, i) => ({ id, i, s: score(id) }))
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .map((x) => x.id);
}

/** Grup içinde YALNIZ bir geçici bölüm açık kalır (peek). */
export function openExclusive(id: string, group: readonly string[]): void {
  for (const g of group) if (g !== id) sessionOpen.delete(g);
  sessionOpen.add(id);
  emit();
}

export function closeSession(id: string): void {
  if (sessionOpen.delete(id)) emit();
}

export function closeSessionGroup(group: readonly string[]): void {
  let changed = false;
  for (const g of group) changed = sessionOpen.delete(g) || changed;
  if (changed) emit();
}

/** Snapshot: `flags|raw` — bayraklar oturum durumu, raw localStorage kaydı. */
function snapshotFor(id: string): string {
  return (
    (sessionCollapsed.has(id) ? "~" : "-") +
    (sessionOpen.has(id) ? "+" : "-") +
    "|" +
    readRaw(id)
  );
}

function decode(snap: string, defaultPinned: boolean) {
  const bar = snap.indexOf("|");
  const flags = bar >= 0 ? snap.slice(0, bar) : "--";
  const raw = bar >= 0 ? snap.slice(bar + 1) : "";
  const pref = raw ? safeParse(raw) : null;
  const pinned = pref ? pref.pinned : defaultPinned;
  const open = resolveOpen(pinned, flags[0] === "~", flags[1] === "+");
  return { pref, pinned, open };
}

/**
 * Tek bölüm tercihi.
 * @param group  Aynı anda tek geçici bölüm açık kalacak grup (sağ panel). Yoksa
 *               (gün fihristi) geçici açılış bağımsızdır.
 */
export function useSectionPref(
  id: string,
  defaultPinned = false,
  group?: readonly string[],
) {
  const snap = useSyncExternalStore(
    subscribe,
    () => snapshotFor(id),
    () => "--|", // sunucu: veri yok → varsayılan
  );
  const { pref, pinned, open } = decode(snap, defaultPinned);

  function current(): SectionPref {
    return readPref(id) ?? { pinned: defaultPinned, hits: [] };
  }

  /** İçerikle etkileşim — bölüm "kullanıldı" (sıralama için). 1 dk tekilleştirme. */
  function touch(): void {
    const p = current();
    const now = Date.now();
    const recent = pruneHits(p.hits, now);
    if (recent.length && now - recent[recent.length - 1] < 60_000) return;
    writePref(id, { ...p, hits: [...recent, now] });
  }

  /** Başlık/şerit tıklaması: sabitse oturumda katla/aç; değilse geçici aç/kapa. */
  function toggle(): void {
    if (pinned) {
      if (sessionCollapsed.has(id)) sessionCollapsed.delete(id);
      else sessionCollapsed.add(id);
      emit();
      return;
    }
    if (sessionOpen.has(id)) {
      sessionOpen.delete(id);
      emit();
      return;
    }
    if (group) openExclusive(id, group);
    else {
      sessionOpen.add(id);
      emit();
    }
    touch();
  }

  /** Raptiye: sabitle (panele yerleş) / kaldır (şeride in — bu oturumda açık kalır). */
  function togglePin(): void {
    const p = current();
    const now = Date.now();
    if (pinned) {
      sessionCollapsed.delete(id);
      // Sürpriz kapanma yok: bölüm bu oturumda geçici açık kalır (peek)
      if (group) openExclusive(id, group);
      else sessionOpen.add(id);
      writePref(id, { pinned: false, hits: p.hits });
      return;
    }
    sessionOpen.delete(id);
    sessionCollapsed.delete(id);
    writePref(id, { pinned: true, hits: [...pruneHits(p.hits, now), now] });
  }

  return { open, pinned, toggle, togglePin, touch, pref };
}

/** Bir grubun sabit/açık durumları tek snapshot'ta (panel yerleşimi için). */
export function useSectionStates(
  ids: readonly string[],
  defaults: Record<string, boolean>,
): Record<string, { pinned: boolean; open: boolean }> {
  const snap = useSyncExternalStore(
    subscribe,
    () => ids.map((id) => snapshotFor(id)).join(" "),
    () => ids.map(() => "--|").join(" "),
  );
  const parts = snap.split(" ");
  const out: Record<string, { pinned: boolean; open: boolean }> = {};
  ids.forEach((id, i) => {
    const d = decode(parts[i] ?? "--|", defaults[id] ?? false);
    out[id] = { pinned: d.pinned, open: d.open };
  });
  return out;
}

/**
 * Kullanıma göre sıra — sayfa yüklenişinde DONDURULUR (oturum içinde bölümler
 * yer değiştirmez; koç "az önce oradaydı" demesin). Sunucu snapshot'ı varsayılan
 * sıra; istemci ilk render'da localStorage'dan hesaplar ve saklar.
 */
const frozenOrder = new Map<string, string>();
const noopSubscribe = () => () => {};

export function useSectionOrder(ids: readonly string[]): string[] {
  const groupKey = ids.join("|");
  const snap = useSyncExternalStore(
    noopSubscribe,
    () => {
      const cached = frozenOrder.get(groupKey);
      if (cached) return cached;
      const prefs: Record<string, SectionPref | null> = {};
      for (const id of ids) prefs[id] = readPref(id);
      const s = JSON.stringify(orderByUsage(ids, prefs, Date.now()));
      frozenOrder.set(groupKey, s);
      return s;
    },
    () => JSON.stringify(ids),
  );
  return JSON.parse(snap) as string[];
}

/** Test/teşhis: donmuş sırayı sıfırla (oturum içinde yeniden hesaplansın). */
export function resetFrozenOrder(): void {
  frozenOrder.clear();
}
