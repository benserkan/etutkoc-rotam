import { apiServer } from "@/lib/api-server";
import type {
  MembershipHavaleInfo,
  MembershipOfferListResponse,
} from "@/lib/types/membership";
import { AdminMembershipClient } from "@/components/admin/admin-membership-client";

/**
 * /admin/membership-offers — Süper admin WhatsApp üyelik teklifi oluşturucu (P2).
 *
 * Hedef koç + yeni üyelik/yenileme + plan/fiyat/mesaj → link üret → kopyala /
 * WhatsApp'ta aç. Havale/EFT bilgisi ayarı. Public sayfa: /membership/[token].
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "WhatsApp Üyelik Teklifleri — Süper Admin" };

export default async function AdminMembershipOffersPage() {
  const [offers, havale] = await Promise.all([
    apiServer<MembershipOfferListResponse>("/api/v2/admin/membership-offers"),
    apiServer<MembershipHavaleInfo>("/api/v2/admin/membership-offers/havale"),
  ]);
  return <AdminMembershipClient initialOffers={offers} initialHavale={havale} />;
}
