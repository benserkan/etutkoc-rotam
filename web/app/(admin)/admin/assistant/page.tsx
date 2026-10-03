import { AdminAssistantClient } from "@/components/admin/admin-assistant-client";

/** /admin/assistant — Rota asistanına sorulanlar + ekibe aktarılanlar. */
export const dynamic = "force-dynamic";
export const metadata = { title: "Asistan Soruları — Süper Admin" };

export default function AdminAssistantPage() {
  return <AdminAssistantClient />;
}
