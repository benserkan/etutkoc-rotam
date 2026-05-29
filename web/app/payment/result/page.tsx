import { redirect } from "next/navigation";

import { apiServer } from "@/lib/api-server";
import type { PaymentResult } from "@/lib/types/payment";
import { PaymentResultClient } from "@/components/payment/payment-result-client";

/**
 * /payment/result?tx=<id> — Iyzico callback sonrası kullanıcı buraya döner.
 *
 * Akış:
 *   - Backend `/api/v2/payment/iyzico/callback` 3DS sonrası 303 ile buraya
 *     redirect eder + `?tx={id}` query parametresi.
 *   - error= durumu: `?error=payment_provider_unavailable` gibi (backend
 *     verify_callback başarısız olduğunda).
 *   - Sayfa GET ile transaction'ı çeker (login gerekir; sahibi değilse 404).
 *
 * Login gerektirir (paylaşılan path — proxy returnUrl ile yönlendirir,
 * safeReturnUrl `/payment/*` paylaşılan olarak izinli).
 */
export const dynamic = "force-dynamic";
export const metadata = { title: "Ödeme Sonucu — ETÜTKOÇ Rotam" };

interface PageProps {
  searchParams: Promise<{ tx?: string; error?: string }>;
}

export default async function PaymentResultPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const errorCode = sp.error ?? null;
  const txId = sp.tx ? Number(sp.tx) : null;

  // Hata query'si varsa (callback fail) → error ekranı
  if (errorCode) {
    return <PaymentResultClient errorCode={errorCode} />;
  }

  if (!txId || Number.isNaN(txId)) {
    redirect("/");
  }

  let result: PaymentResult | null = null;
  try {
    result = await apiServer<PaymentResult>(`/api/v2/payment/transactions/${txId}`);
  } catch {
    // 404 / 401 — sahip değil veya transaction yok
    return <PaymentResultClient errorCode="not_found" />;
  }

  return <PaymentResultClient result={result} />;
}
