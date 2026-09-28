import { redirect } from "next/navigation";

/**
 * /institution/invitations — Davet bağlantıları artık Öğretmenler sayfasının
 * bir sekmesi (2026-09-28: "Öğretmen ekle" ile "Davet" aynı şey mi? karışıklığı).
 * Eski bağlantılar kırılmasın diye yönlendirir.
 */
export default function InstitutionInvitationsPage() {
  redirect("/institution/teachers?tab=davet");
}
