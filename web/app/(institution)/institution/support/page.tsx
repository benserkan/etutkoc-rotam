import { redirect } from "next/navigation";

/**
 * /institution/support — "Taleplerim" artık birleşik Talepler sayfasının
 * "Sistem yöneticisiyle" sekmesi (2026-09-28). Eski bağlantılar yönlenir.
 */
export default function InstitutionSupportPage() {
  redirect("/institution/support-inbox?tab=sistem");
}
