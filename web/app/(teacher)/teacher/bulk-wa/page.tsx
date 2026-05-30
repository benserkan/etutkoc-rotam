import { BulkSendWizard } from "@/components/messaging/bulk-send-wizard";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Toplu WhatsApp — Koç",
};

export default function TeacherBulkWaPage() {
  return <BulkSendWizard />;
}
