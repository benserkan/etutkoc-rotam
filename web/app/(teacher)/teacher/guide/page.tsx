import { GuideClient } from "@/components/guide/guide-client";

/**
 * /teacher/guide — Rota ile koç rehberi (sesli, tıklamalı ekran anlatımı +
 * "şimdi sen yap" kontrol listesi). Durum sunucuda (user_guide_states).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Rehber" };

export default async function TeacherGuidePage({
  searchParams,
}: {
  searchParams: Promise<{ bolum?: string }>;
}) {
  const { bolum } = await searchParams;
  return (
    <GuideClient
      initialChapter={bolum ?? null}
      guideKey="coach_onboarding"
      title="Rehber — Rota ile başlangıç"
      description="Kitaplar, haftalık program ve deneme analizi — sistemin kalbi olan üç sayfanın adım adım eğitimi."
    />
  );
}
