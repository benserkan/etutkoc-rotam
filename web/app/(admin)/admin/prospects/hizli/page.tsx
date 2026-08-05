import type { Metadata } from "next";

import { ProspectQuickAdd } from "@/components/admin/prospect-quick-add";

/**
 * /admin/prospects/hizli — telefondan (iOS Safari) hızlı aday ekleme.
 * Instagram'da koç gezerken kullanılır; ana ekrana eklenebilir.
 */
export const metadata: Metadata = {
  title: "Hızlı ekle — Hedef Havuzu",
  robots: { index: false, follow: false },
};

export default function ProspectQuickAddPage() {
  return <ProspectQuickAdd />;
}
