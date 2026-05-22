import { api } from "@/lib/api";
import type { PricingCatalog } from "@/lib/types/pricing";

export const pricingKeys = {
  catalog: () => ["pricing", "catalog"] as const,
};

export function getPricingCatalog(): Promise<PricingCatalog> {
  return api<PricingCatalog>("/api/v2/pricing");
}

export interface ContactRequestInput {
  name: string;
  email: string;
  phone?: string;
  institution_name?: string;
  coach_count?: number | null;
  message?: string;
  source?: string;
}

export interface ContactRequestResult {
  ok: boolean;
  message: string;
}

export function submitContactRequest(body: ContactRequestInput): Promise<ContactRequestResult> {
  return api<ContactRequestResult>("/api/v2/contact", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
