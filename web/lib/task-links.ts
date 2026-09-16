/**
 * Görev bağlantısı yardımcıları (2026-09-16) — backend `task_links.py` aynası.
 *
 * `link_url` artık API'den gelir (kolon > notes içindeki URL). Eski kayıtlarda
 * URL hâlâ notes'ta da durabilir → gösterimde ayıklanır ki aynı bağlantı hem
 * "Videoyu izle" düğmesi hem düz metin olarak iki kez görünmesin.
 */
const URL_RE = /https?:\/\/[^\s<>"']+/gi;

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

/** "Videoyu izle" / "Bağlantıyı aç" — tip video ise izle. */
export function linkButtonLabel(type: string): string {
  return type === "video" ? "Videoyu izle" : "Bağlantıyı aç";
}
