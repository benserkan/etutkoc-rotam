// Dönüşüm (conversion) hunisi fetcher'ı — süper admin.
import { api } from "@/lib/api";
import type { ConversionResponse } from "@/lib/types/conversion";

export const conversionKeys = {
  funnel: (days: number) => ["admin", "conversion", String(days)] as const,
};

export function getAdminConversion(days = 30): Promise<ConversionResponse> {
  return api<ConversionResponse>(`/api/v2/admin/conversion?days=${days}`);
}
