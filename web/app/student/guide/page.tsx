import { GuideClient } from "@/components/guide/guide-client";

/**
 * /student/guide — Rota ile öğrenci rehberi (sesli, tıklamalı ekran anlatımı).
 * Durum sunucuda (user_guide_states, guide_key=student_onboarding).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Rehber" };

export default function StudentGuidePage() {
  return (
    <GuideClient
      guideKey="student_onboarding"
      title="Rehber — Rota ile Rotam'ı keşfet"
      description="Günlük görevlerinden yanlış soru arşivine, deneme analizinden hedeflerine — bütün araçların tek turda."
    />
  );
}
