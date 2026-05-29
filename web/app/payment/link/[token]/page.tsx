import { apiServer } from "@/lib/api-server";
import type { PaymentLinkPublicInfo } from "@/lib/types/payment";
import { PaymentLinkClient } from "@/components/payment/payment-link-client";

/**
 * /payment/link/<token> — süper adminin oluşturduğu ödeme linki.
 *
 * Akış:
 *   - Login zorunlu (token bilgisi public DEĞİL — kurum adı + tutar sızmasın).
 *   - Login yoksa proxy /login'e yönlendirir (safeReturnUrl /payment/* paylaşılan).
 *   - Sayfa link bilgisini gösterir (plan/tutar/kurum + can_pay).
 *   - "Şimdi Öde" → POST /api/v2/payment/link/{token}/checkout → Iyzico URL.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Ödeme — ETÜTKOÇ Rotam" };

interface PageProps {
  params: Promise<{ token: string }>;
}

export default async function PaymentLinkPage({ params }: PageProps) {
  const { token } = await params;
  let info: PaymentLinkPublicInfo | null = null;
  try {
    info = await apiServer<PaymentLinkPublicInfo>(
      `/api/v2/payment/link/${encodeURIComponent(token)}`,
    );
  } catch {
    info = null;
  }
  return <PaymentLinkClient token={token} info={info} />;
}
