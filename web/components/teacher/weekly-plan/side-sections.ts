/**
 * Sağ panel bölüm KAYDI — şerit (rail) ve panel aynı listeden beslenir (2026-09-08).
 *
 * Yeni bölüm eklemek = buraya bir satır + week-board'da bileşen eşlemesi.
 * `id` localStorage anahtarıdır; bileşen yeri değişse de koçun tercihi kalır.
 */

import type { LucideIcon } from "lucide-react";
import { Boxes, Compass, History, Library, ListChecks } from "lucide-react";

export type SideTone = "neutral" | "cyan" | "violet" | "amber";

export interface SideSectionDef {
  id: string;
  /** Panel başlığı */
  title: string;
  /** Şeritteki kısa etiket (≤8 karakter — 44px şeride sığmalı) */
  short: string;
  /** Şerit tooltip'i: bölüm ne işe yarar */
  hint: string;
  icon: LucideIcon;
  tone: SideTone;
  /** Hiç tercih yokken sabit mi (panelde açık gelir) */
  defaultPinned: boolean;
}

export const SIDE_SECTIONS: readonly SideSectionDef[] = [
  {
    id: "week:carryover",
    title: "Geçen haftadan eksikler",
    short: "Devret",
    hint: "Yapılmadan kalan görevler — sürükle ya da Ekle ile bu haftaya taşı",
    icon: History,
    tone: "amber",
    defaultPinned: false,
  },
  {
    // Canlı veriye göre en çok kullanılan bölüm → tek varsayılan sabit.
    id: "week:resources",
    title: "Kaynak Durumu",
    short: "Kaynak",
    hint: "Kitap ve bölümlerde kalan test kapasitesi",
    icon: Library,
    tone: "neutral",
    defaultPinned: true,
  },
  {
    id: "week:curriculum",
    title: "Müfredat",
    short: "Müfredat",
    hint: "Konu durumu · kapatayım mı, ek görev mi?",
    icon: ListChecks,
    tone: "neutral",
    defaultPinned: false,
  },
  {
    id: "week:next-units",
    title: "Sıradaki üniteler",
    short: "Sıradaki",
    hint: "Müfredatta sırada — tek tıkla göreve çevir",
    icon: Compass,
    tone: "cyan",
    defaultPinned: false,
  },
  {
    id: "week:work-blocks",
    title: "Serbest Bloklar",
    short: "Bloklar",
    hint: "Sistem dışı ödevleri (özel ders vb.) günlere dağıt",
    icon: Boxes,
    tone: "violet",
    defaultPinned: false,
  },
];

export const SIDE_SECTION_IDS: readonly string[] = SIDE_SECTIONS.map((s) => s.id);

export const SIDE_SECTION_DEFAULTS: Record<string, boolean> = Object.fromEntries(
  SIDE_SECTIONS.map((s) => [s.id, s.defaultPinned]),
);

export function sideSectionDef(id: string): SideSectionDef | undefined {
  return SIDE_SECTIONS.find((s) => s.id === id);
}

/** Panel genişliği (sabit bölüm varken) ve şerit genişliği — tek yerde. */
export const SIDE_PANEL_W = 320;
export const SIDE_RAIL_W = 56; // etiketler ("Müfredat", "Sıradaki") 44/52px'te kırpılıyordu
