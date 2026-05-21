import { AlertTriangle, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

interface Props {
  title?: string;
  description?: string;
  onRetry?: () => void;
  retryLabel?: string;
}

/**
 * Standart hata kutusu — useQuery/useMutation hata akışlarında fallback.
 *
 * Sade renkli kart (destructive accent), tek başlık + tek açıklama + opsiyonel
 * "Tekrar dene" butonu. Backend hata zarfından `detail.message` doğrudan
 * `description` olarak geçilebilir.
 */
export function ErrorState({
  title = "Bir şeyler ters gitti",
  description = "Sayfayı yenilemeyi deneyin. Sorun sürerse koçunuza haber verin.",
  onRetry,
  retryLabel = "Tekrar dene",
}: Props) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-5 sm:px-6 sm:py-6 space-y-3"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="size-5 text-destructive shrink-0 mt-0.5" aria-hidden="true" />
        <div className="space-y-1.5">
          <p className="font-medium leading-tight">{title}</p>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      {onRetry ? (
        <div className="pl-8">
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCcw className="size-3.5" /> {retryLabel}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
