import { Loader2 } from "lucide-react";

interface Props {
  /** Spinner altında gösterilecek satır — default "Yükleniyor…" */
  label?: string;
  /** Sayfanın tamamını kaplasın mı? Default false (component scope). */
  fullPage?: boolean;
}

/**
 * Standart yükleniyor durumu — sayfa veya bölüm bekleyişi için.
 *
 * Düz, sade ve erişilebilir. role="status" + aria-live="polite" ile ekran
 * okuyucular için sessizce duyurulur.
 */
export function LoadingState({ label = "Yükleniyor…", fullPage = false }: Props) {
  const cls = fullPage
    ? "min-h-[50vh] flex flex-col items-center justify-center gap-3 text-muted-foreground"
    : "flex items-center gap-3 text-sm text-muted-foreground py-6";

  return (
    <div className={cls} role="status" aria-live="polite">
      <Loader2 className="size-5 animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}
