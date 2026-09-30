import { GuideClient } from "@/components/guide/guide-client";
import { apiServer } from "@/lib/api-server";
import type { MyAccountResponse } from "@/lib/types/me";

/**
 * /student/guide — Rota ile öğrenci rehberi (sesli, tıklamalı ekran anlatımı).
 * Durum sunucuda (user_guide_states, guide_key=student_onboarding).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Rehber" };

export default async function StudentGuidePage() {
  // Kurumsal kimlik: kuruma bağlı öğrenci kurumun adıyla karşılanır.
  const me = await apiServer<MyAccountResponse>("/api/v2/me").catch(() => null);
  const brandName = me?.brand?.name ?? null;
  return (
    <GuideClient
      guideKey="student_onboarding"
      title={brandName ? `Rehber — Rota ile ${brandName} sistemini keşfet` : "Rehber — Rota ile Rotam'ı keşfet"}
      description="Günlük görevlerinden yanlış soru arşivine, deneme analizinden hedeflerine — bütün araçların tek turda."
    />
  );
}
