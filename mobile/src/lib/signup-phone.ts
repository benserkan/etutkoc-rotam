/**
 * Signup-anı telefon doğrulama (#5 kapı). Kapı yalnız SMS açıkken (sunucuda
 * SMS_ENABLED=true / SMS OTP paketi alınınca) zorunlu olur. Kapalıyken
 * `fetchSignupPhoneRequired()` false döner → mobil signup eskisi gibi
 * (telefon opsiyonel, OTP yok).
 */
import { apiRequest } from "@/lib/api";

export async function fetchSignupPhoneRequired(): Promise<boolean> {
  try {
    const r = await apiRequest<{ required: boolean }>(
      "/api/v2/auth/signup/phone/required",
      { auth: false },
    );
    return !!r.required;
  } catch {
    // Hata → kapıyı kapalı varsay; signup'ı bloklama
    return false;
  }
}

export async function startSignupPhone(
  phone: string,
): Promise<{ sent: boolean; dev_code: string | null }> {
  return apiRequest("/api/v2/auth/signup/phone/start", {
    method: "POST",
    auth: false,
    body: { phone },
  });
}

export async function verifySignupPhone(
  phone: string,
  code: string,
): Promise<{ phone_token: string }> {
  return apiRequest("/api/v2/auth/signup/phone/verify", {
    method: "POST",
    auth: false,
    body: { phone, code },
  });
}
