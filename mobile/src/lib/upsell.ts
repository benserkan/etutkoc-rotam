/**
 * Koç ödeme-duvarı / kredi-bitti yönlendirmesi — Paketim (IAP) ekranına.
 *
 * Apple 3.1.1 uyumu: bu yönlendirme UYGULAMA İÇİ satın almaya (StoreKit /
 * Paketim ekranı) gider — dış ödeme yönlendirmesi DEĞİLDİR. Ret #3 döneminde
 * nötrlenen "kullanım sınırına ulaşıldı" mesajları, IAP entegrasyonuyla
 * (2026-07-19) yeniden satın almaya bağlanabilir hale geldi.
 */
import { router } from "expo-router";
import { Alert } from "react-native";

export function showCoachUpgradeAlert(title: string, message: string): void {
  Alert.alert(title, message, [
    { text: "Kapat", style: "cancel" },
    { text: "Paketleri gör", onPress: () => router.push("/teacher-plan") },
  ]);
}

/** AI kapı/kredi hata kodları için ortak koç mesajı. true = ele alındı. */
export function handleCoachAiGateError(code: string | null | undefined): boolean {
  if (code === "plan_upgrade_required") {
    showCoachUpgradeAlert(
      "Ücretli pakette",
      "Yapay zekâ özellikleri ücretli pakette (ve aktif denemede) açıktır. Paketini uygulama içinden seçebilirsin.",
    );
    return true;
  }
  if (code === "ai_credit_exhausted") {
    showCoachUpgradeAlert(
      "Yapay zekâ kredin bitti",
      "Bu ay için yapay zekâ kredin doldu. Daha yüksek pakete geçerek kesintisiz devam edebilirsin.",
    );
    return true;
  }
  return false;
}
