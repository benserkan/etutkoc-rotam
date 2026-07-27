import { GuideClient } from "@/components/guide/guide-client";

/**
 * /parent/guide — Rota ile veli rehberi (sesli, tıklamalı ekran anlatımı).
 * Durum sunucuda (user_guide_states, guide_key=parent_onboarding).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Rehber" };

export default function ParentGuidePage() {
  return (
    <GuideClient
      guideKey="parent_onboarding"
      title="Rehber — Rota ile veli panelini keşfet"
      description="Çocuğunun gidişatını sayı ezberlemeden takip et: Rota'nın yorumları, sesli soru-cevap, haftalık rapor ve koçla iletişim — hepsi uygulamalı, adım adım."
    />
  );
}
