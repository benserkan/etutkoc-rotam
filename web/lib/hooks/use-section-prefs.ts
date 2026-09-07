"use client";

/**
 * Bölüm göster/gizle tercihi + kullanım alışkanlığı (2026-09-08).
 *
 * KOÇ: sağ paneldeki dört bölüm (Müfredat · Sıradaki üniteler · Serbest
 * Bloklar · Kaynak Durumu) ve sol gün fihristi tek anahtarla ya hep vardı ya
 * hiç yoktu; anahtar da başlıkta, bölümlerin 600px üstündeydi. İstek: her
 * bölüm başında RAPTİYE; yoğun kullanılan açık gelsin, diğerleri tek tıkla açılsın.
 *
 * MODEL — iki durum, tek simge:
 *   · pinned  → raptiye DOLU: her açılışta açık, alışkanlıktan bağımsız.
 *   · auto    → raptiye BOŞ: son USAGE_WINDOW_DAYS içinde ≥ USAGE_MIN_HITS
 *               kullanım varsa açık, yoksa katlı. Başlığa tıklamak aç/kapa
 *               yapar VE kullanım sayar → kullanılan bölüm açık kalır,
 *               kullanılmayan bir hafta sonra kendiliğinden katlanır.
 *
 * KALICILIK: tarayıcı (localStorage) — kullanıcı kararı. Daha önce panel
 * tercihi localStorage'a yazılmaktan kaçınılmıştı (effect'te setState React
 * Compiler kuralına takılıyor; lazy initializer SSR/hydration uyuşmazlığı
 * üretiyor). Doğru çözüm `useSyncExternalStore`: sunucu render'ında
 * varsayılan snapshot, istemcide gerçek değer, uyuşmazlık yok, effect yok.
 *
 * Her okuma/yazma try/catch: gizli pencere / engellenmiş depolama → varsayılan
 * davranış, sayfa çökmez.
 */

import { useSyncExternalStore } from "react";

export type SectionMode = "pinned" | "auto";

export interface SectionPref {
  mode: SectionMode;
  /** Kullanım damgaları (epoch ms) — pencere dışındakiler budanır */
  hits: number[];
  /** Otomatik modda son elle aç/kapa (bu oturum ve sonrası için ipucu) */
  lastManualOpen: boolean | null;
}

export const USAGE_WINDOW_DAYS = 7;
export const USAGE_MIN_HITS = 2;

const KEY_PREFIX = "rotam:section:";
const listeners = new Set<() => void>();
// Sabit bölümün OTURUM İÇİ geçici katlanması. Koç "sabit" dediyse her
// açılışta açık gelir; ama bir anlığına katlamak da isteyebilir. Bellekte
// tutulur, yenilemede sıfırlanır (sessionStorage DEĞİL — kasıtlı: yeni
// sekmede/yenilemede raptiye kazanır).
const sessionCollapsed = new Set<string>();

function key(id: string): string {
  return `${KEY_PREFIX}${id}`;
}

function readRaw(id: string): SectionPref | null {
  try {
    const raw = window.localStorage.getItem(key(id));
    if (!raw) return null;
    const p = JSON.parse(raw) as Partial<SectionPref>;
    return {
      mode: p.mode === "pinned" ? "pinned" : "auto",
      hits: Array.isArray(p.hits) ? p.hits.filter((n) => typeof n === "number") : [],
      lastManualOpen:
        typeof p.lastManualOpen === "boolean" ? p.lastManualOpen : null,
    };
  } catch {
    return null;
  }
}

function writeRaw(id: string, pref: SectionPref): void {
  try {
    window.localStorage.setItem(key(id), JSON.stringify(pref));
  } catch {
    /* depolama yoksa sessiz */
  }
  for (const l of listeners) l();
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

function pruneHits(hits: number[], now: number): number[] {
  const cutoff = now - USAGE_WINDOW_DAYS * 86_400_000;
  return hits.filter((t) => t >= cutoff);
}

/** Bölüm açık mı? Saf karar fonksiyonu — testlenebilir. */
export function resolveOpen(
  pref: SectionPref | null,
  defaultOpen: boolean,
  now: number = Date.now(),
): boolean {
  if (!pref) return defaultOpen;
  if (pref.mode === "pinned") return true;
  const recent = pruneHits(pref.hits, now);
  if (recent.length >= USAGE_MIN_HITS) return true;
  if (pref.lastManualOpen === null) {
    // Koç hiç elle aç/kapa yapmadı: varsayılan geçerli. Az kullanım (1 tık)
    // varsayılanı DEĞİŞTİRMEZ — CANLI TESTTE YAKALANDI: açık gelen Müfredat
    // bölümünde bir konuya tıklamak `touch` ile 1 hit yazıyordu ve bölüm
    // anında KATLANIYORDU (koçun ilk tıklaması paneli kapatırdı).
    return defaultOpen;
  }
  // Elle karar var: açıksa ve hâlâ kullanılıyorsa açık kalır; kullanım
  // pencere dışına düşünce (recent=0) katlanır — alışkanlık söner.
  return pref.lastManualOpen === true && recent.length > 0;
}

/**
 * Bölüm tercihi. `defaultOpen` = hiç veri yokken varsayılan (canlı veriye göre
 * en çok kullanılan iki bölüm — Kaynak Durumu + Müfredat — açık gelir).
 */
export function useSectionPref(id: string, defaultOpen: boolean) {
  // Snapshot string: useSyncExternalStore referans eşitliği ister; JSON
  // string aynı kaldığı sürece yeniden render yok.
  const raw = useSyncExternalStore(
    subscribe,
    () => {
      try {
        const v = window.localStorage.getItem(key(id)) ?? "";
        // sessionCollapsed değişimi de yeniden render tetiklemeli → snapshot'a ekle
        return (sessionCollapsed.has(id) ? "~" : "") + v;
      } catch {
        return "";
      }
    },
    () => "", // sunucu: veri yok → defaultOpen
  );
  const snapshot = raw.startsWith("~") ? raw.slice(1) : raw;

  const pref: SectionPref | null = snapshot ? safeParse(snapshot) : null;
  const pinned = pref?.mode === "pinned";
  // useSyncExternalStore snapshot'ı sessionCollapsed'ı da kapsasın diye
  // anahtar string'e ekliyoruz (aşağıdaki subscribe aynı listener'ı tetikler)
  const open = pinned
    ? !sessionCollapsed.has(id)
    : resolveOpen(pref, defaultOpen);

  function current(): SectionPref {
    return (
      readRaw(id) ?? { mode: "auto", hits: [], lastManualOpen: null }
    );
  }

  /** Başlığa tıklama: aç/kapa + kullanım say (açarken). */
  function toggle(): void {
    const p = current();
    const now = Date.now();
    const nextOpen = !open;
    if (p.mode === "pinned") {
      // Sabit bölüm: yalnız bu oturumda katlanır/açılır; tercih değişmez
      if (nextOpen) sessionCollapsed.delete(id);
      else sessionCollapsed.add(id);
      for (const l of listeners) l();
      return;
    }
    writeRaw(id, {
      ...p,
      hits: nextOpen ? [...pruneHits(p.hits, now), now] : pruneHits(p.hits, now),
      lastManualOpen: nextOpen,
    });
  }

  /** İçerikle etkileşim (tıklama) — bölüm "kullanıldı" sayılır. */
  function touch(): void {
    const p = current();
    const now = Date.now();
    const recent = pruneHits(p.hits, now);
    // Aynı dakika içinde tekrar sayma (çift tık gürültüsü)
    if (recent.length && now - recent[recent.length - 1] < 60_000) return;
    writeRaw(id, { ...p, hits: [...recent, now] });
  }

  /** Raptiye: sabitle / sabitlemeyi kaldır. */
  function togglePin(): void {
    const p = current();
    sessionCollapsed.delete(id);
    writeRaw(id, {
      ...p,
      mode: p.mode === "pinned" ? "auto" : "pinned",
      // Sabitleme kaldırılınca bölüm o an açık kalsın (sürpriz kapanma yok)
      lastManualOpen: p.mode === "pinned" ? true : p.lastManualOpen,
      hits: p.mode === "pinned" ? [...pruneHits(p.hits, Date.now()), Date.now()] : p.hits,
    });
  }

  return { open, pinned, toggle, togglePin, touch };
}

function safeParse(raw: string): SectionPref | null {
  try {
    const p = JSON.parse(raw) as Partial<SectionPref>;
    return {
      mode: p.mode === "pinned" ? "pinned" : "auto",
      hits: Array.isArray(p.hits) ? p.hits.filter((n) => typeof n === "number") : [],
      lastManualOpen:
        typeof p.lastManualOpen === "boolean" ? p.lastManualOpen : null,
    };
  } catch {
    return null;
  }
}
