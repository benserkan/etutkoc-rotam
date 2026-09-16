import { Alert, Linking } from "react-native";

/**
 * Görev gösterim yardımcıları — koç + öğrenci ekranları ortak (2026-09-16).
 *
 * Saha (Emir/Taha programı): video görevi "etkinlik" diye görünüyordu, linke
 * ulaşılamıyordu; çok kalemli görev (haftaya yay sıradaki bölüme geçmiş)
 * yalnız İLK bölümün adını gösteriyordu ("Vektörler" yazıp Tork testleri
 * içermek gibi). Buradaki etiketler her iki rolde de aynı kuralla üretilir.
 */

export const TASK_TYPE_LABEL: Record<string, string> = {
  test: "Test",
  video: "Video dersi",
  ozet: "Özet",
  tekrar: "Tekrar",
  other: "Etkinlik",
};

export function activityLabel(type: string | null | undefined): string {
  return TASK_TYPE_LABEL[type ?? ""] ?? "Etkinlik";
}

export function linkButtonLabel(type: string | null | undefined): string {
  return type === "video" ? "Videoyu izle" : "Bağlantıyı aç";
}

const URL_RE = /https?:\/\/[^\s<>"']+/gi;

/** Notlardan URL'leri ayıkla — bağlantı zaten düğme olarak gösteriliyor. */
export function stripUrls(text: string | null | undefined): string | null {
  if (!text) return null;
  const cleaned = text
    .replace(URL_RE, "")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .join("\n");
  return cleaned || null;
}

/** Bağlantıyı cihazın tarayıcısında/YouTube uygulamasında aç (hata → uyarı). */
export async function openTaskLink(url: string): Promise<void> {
  try {
    await Linking.openURL(url);
  } catch {
    Alert.alert("Bağlantı açılamadı", "Bu bağlantı cihazında açılamadı. Koçuna bildirebilirsin.");
  }
}

interface ItemLike {
  book_id: number | null;
  book_name: string;
  section_label: string | null;
  planned?: number;
  planned_count?: number;
}

function plannedOf(it: ItemLike): number {
  return it.planned ?? it.planned_count ?? 0;
}

/** Başlıktaki "{Ders} · {içerik}" biçiminden içerik kısmı (etkinlik görevleri). */
export function titleTail(title: string): string {
  const sep = title.indexOf(" · ");
  if (sep > 0 && sep < title.length - 3) return title.substring(sep + 3);
  return title || "Görev";
}

/**
 * Görev etiketi.
 *  · tek kitap kalemi   → "Kitap · Bölüm"
 *  · çok kitap kalemi   → "Kitap · Bölüm A 3 · Bölüm B 1" (compact: "Kitap · Bölüm A +1")
 *  · kitapsız / etkinlik → başlığın içerik kısmı
 */
export function taskLabel(items: ItemLike[], title: string, opts?: { compact?: boolean }): string {
  const bookItems = items.filter((it) => it.book_id != null);
  if (bookItems.length === 0) return titleTail(title);
  const first = bookItems[0];
  if (bookItems.length === 1) {
    return first.book_name + (first.section_label ? ` · ${first.section_label}` : "");
  }
  if (opts?.compact) {
    return `${first.book_name} · ${first.section_label ?? ""} +${bookItems.length - 1}`;
  }
  const parts = bookItems.map((it) => `${it.section_label ?? "Bölüm"} ${plannedOf(it)}`);
  return `${first.book_name} · ${parts.join(" · ")}`;
}
