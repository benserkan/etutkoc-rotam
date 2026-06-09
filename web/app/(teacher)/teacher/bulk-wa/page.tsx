import { BulkSendWizard } from "@/components/messaging/bulk-send-wizard";
import { DemoHint } from "@/components/demos/demo-hint";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Toplu WhatsApp — Koç",
};

export default function TeacherBulkWaPage() {
  return (
    <div className="space-y-4">
      <DemoHint contextKey="whatsapp" role="teacher" />
      <BulkSendWizard />
    </div>
  );
}
