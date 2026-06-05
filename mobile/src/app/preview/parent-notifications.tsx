import { SafeAreaView } from "react-native-safe-area-context";

import { NotificationsView } from "@/components/parent/notifications-view";
import type { ParentNotificationsResponse } from "@/lib/parent";

/** UX önizleme — Veli: Bildirimler (mock). Faz 7'de kaldırılacak. */
const MOCK: ParentNotificationsResponse = {
  total: 3,
  items: [
    {
      id: 3, kind: "weekly_report", channel: "email", status: "sent",
      subject: "Elif'in haftalık çalışma raporu", student_name: "Elif Yıldız",
      sent_at: "2026-06-02T12:00:00", queued_at: null,
    },
    {
      id: 2, kind: "drop_alert", channel: "whatsapp", status: "sent",
      subject: "Yiğit son 3 gündür program dışı", student_name: "Yiğit Demir",
      sent_at: "2026-06-01T18:30:00", queued_at: null,
    },
    {
      id: 1, kind: "daily_summary", channel: "email", status: "queued",
      subject: null, student_name: "Elif Yıldız",
      sent_at: null, queued_at: "2026-06-05T07:00:00",
    },
  ],
};

export default function ParentNotificationsPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <NotificationsView data={MOCK} />
    </SafeAreaView>
  );
}
