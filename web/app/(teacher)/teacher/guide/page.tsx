import { GuideClient } from "@/components/guide/guide-client";

/**
 * /teacher/guide — Rota ile koç rehberi (sesli, tıklamalı ekran anlatımı +
 * "şimdi sen yap" kontrol listesi). Durum sunucuda (user_guide_states).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Rehber" };

export default function TeacherGuidePage() {
  return (
    <GuideClient
      guideKey="coach_onboarding"
      title="Rehber — Rota ile başlangıç"
      description="Kitap eklemekten deneme analizine, bir haftalık koçluk akışının tamamı."
    />
  );
}
