"use client";

import { useQuery } from "@tanstack/react-query";

import { getPricingCatalog, pricingKeys } from "@/lib/api/pricing";
import { FloatingWhatsApp } from "@/components/contact/floating-whatsapp";

/**
 * Kataloğu kendi çeken yüzen WhatsApp — landing gibi contact'ı prop almayan
 * public sayfalarda kullanılır. Numara boşsa hiç render etmez.
 */
export function FloatingWhatsAppAuto() {
  const { data } = useQuery({
    queryKey: pricingKeys.catalog(),
    queryFn: getPricingCatalog,
    staleTime: 5 * 60_000,
  });
  return <FloatingWhatsApp phone={data?.contact?.whatsapp} />;
}
