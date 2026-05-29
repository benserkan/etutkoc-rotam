import { apiServer } from "@/lib/api-server";
import type { PaymentLinkListResponse } from "@/lib/types/payment";
import { AdminPaymentLinksClient } from "@/components/admin/admin-payment-links-client";

/**
 * /admin/payment-links — süper admin ödeme linki yönetimi (Paket Ö2b).
 *
 * Kurum self-serve ödeme yapamaz (fiyat "özel teklif" olabilir). Süper admin
 * bu sayfada link oluşturur (kurum + plan + tutar + döngü) → URL'i kuruma
 * gönderir → kurum yöneticisi linkten öder.
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Ödeme Linkleri — Süper Admin" };

export default async function AdminPaymentLinksPage() {
  const initial = await apiServer<PaymentLinkListResponse>(
    "/api/v2/payment/admin/links",
  );
  return <AdminPaymentLinksClient initial={initial} />;
}
