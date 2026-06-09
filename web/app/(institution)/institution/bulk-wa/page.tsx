import { BulkSendWizard } from "@/components/messaging/bulk-send-wizard";
import { DemoHint } from "@/components/demos/demo-hint";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Toplu WhatsApp — Kurum",
};

export default function InstitutionBulkWaPage() {
  return (
    <div className="space-y-4">
      <DemoHint contextKey="whatsapp" role="institution_admin" />
      <BulkSendWizard />
    </div>
  );
}
