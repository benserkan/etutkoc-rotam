import { SafeAreaView } from "react-native-safe-area-context";

import { SupportThreadView } from "@/components/support/support-thread-view";
import type { SupportDetail } from "@/lib/support";

/** UX önizleme — Destek thread (mock). Faz 7'de kaldırılacak. */
const MOCK: SupportDetail = {
  id: 2, subject: "Öğrenci hesabı kilitlendi", category: "technical", category_label: "Teknik",
  status: "answered", status_label: "Cevaplandı", audience: "super_admin", audience_label: "Süper Admin",
  requester_id: 1, requester_name: "Ben", requester_role: "teacher",
  target_user_id: null, target_user_name: null, institution_id: null, institution_name: null,
  created_at: "2026-06-03", last_activity_at: "2026-06-04T10:00:00",
  message_count: 3, last_message_preview: null, handled_by_name: "Destek", can_manage: false,
  attachments: [],
  messages: [
    { id: 1, sender_id: 1, sender_name: "Ben", sender_role: "teacher", is_me: true, body: "Öğrencim Yiğit hesabına giremiyor, kilitlenmiş.", created_at: "2026-06-03T09:00:00" },
    { id: 2, sender_id: 9, sender_name: "Destek", sender_role: "super_admin", is_me: false, body: "Merhaba, hesabı kontrol ediyoruz.", created_at: "2026-06-03T11:00:00" },
    { id: 3, sender_id: 9, sender_name: "Destek", sender_role: "super_admin", is_me: false, body: "Hesabı sıfırladık, tekrar giriş yapabilir. Geçici şifre öğrencinin e-postasına gitti.", created_at: "2026-06-04T10:00:00" },
  ],
};

export default function SupportThreadPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <SupportThreadView data={MOCK} busy={false} isTerminal={false} onReply={() => {}} onWithdraw={() => {}} />
    </SafeAreaView>
  );
}
