import { redirect } from "next/navigation";

/**
 * /me — Jinja URL'i (Hesabım ve verilerim) Next.js'te `/me/account` altında.
 * Gelen link uyumluluğu için tek satırlık yönlendirme.
 */
export default function MeIndexPage(): never {
  redirect("/me/account");
}
