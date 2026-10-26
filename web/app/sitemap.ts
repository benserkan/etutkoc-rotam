import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

/** Herkese açık, dizine girmesi istenen sayfalar. Yeni tanıtım sayfası = buraya satır. */
const PAGES: { path: string; priority: number; freq: MetadataRoute.Sitemap[number]["changeFrequency"] }[] = [
  { path: "/", priority: 1, freq: "weekly" },
  { path: "/yks-puan-hesaplama", priority: 0.9, freq: "monthly" },
  { path: "/ogrenci-takip-programi", priority: 0.9, freq: "monthly" },
  { path: "/deneme-analizi", priority: 0.9, freq: "monthly" },
  { path: "/kurumlar", priority: 0.9, freq: "monthly" },
  { path: "/bagimsiz-koclar", priority: 0.8, freq: "monthly" },
  { path: "/pricing", priority: 0.9, freq: "monthly" },
  { path: "/demos", priority: 0.8, freq: "monthly" },
  { path: "/iletisim", priority: 0.6, freq: "yearly" },
  { path: "/signup/teacher", priority: 0.6, freq: "yearly" },
  { path: "/kullanim-sartlari", priority: 0.2, freq: "yearly" },
  { path: "/mesafeli-satis", priority: 0.2, freq: "yearly" },
  { path: "/iade-iptal", priority: 0.2, freq: "yearly" },
  { path: "/privacy", priority: 0.2, freq: "yearly" },
  { path: "/kvkk", priority: 0.2, freq: "yearly" },
];

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return PAGES.map((p) => ({
    url: `${SITE_URL}${p.path === "/" ? "" : p.path}`,
    lastModified: now,
    changeFrequency: p.freq,
    priority: p.priority,
  }));
}
