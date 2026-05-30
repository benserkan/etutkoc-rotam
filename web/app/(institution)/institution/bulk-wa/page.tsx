import { BulkSendWizard } from "@/components/messaging/bulk-send-wizard";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Toplu WhatsApp — Kurum",
};

export default function InstitutionBulkWaPage() {
  return <BulkSendWizard />;
}
