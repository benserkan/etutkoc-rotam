import { api } from "@/lib/api";
import type {
  MembershipAudienceResponse,
  MembershipOfferListResponse,
} from "@/lib/types/membership";

export const membershipKeys = {
  offers: () => ["admin", "me", "membership-offers"] as const,
  audience: () => ["admin", "me", "membership-audience"] as const,
};

export function getMembershipOffers(): Promise<MembershipOfferListResponse> {
  return api<MembershipOfferListResponse>("/api/v2/admin/membership-offers");
}

export function getMembershipAudience(): Promise<MembershipAudienceResponse> {
  return api<MembershipAudienceResponse>("/api/v2/admin/membership-offers/audience");
}
