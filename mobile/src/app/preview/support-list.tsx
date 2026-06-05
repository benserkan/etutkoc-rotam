import * as React from "react";
import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { SupportListView } from "@/components/support/support-list-view";
import type { SupportListItem } from "@/lib/support";

/** UX önizleme — Destek listesi (mock). Faz 7'de kaldırılacak. */
const ITEMS: SupportListItem[] = [
  {
    id: 2, subject: "Öğrenci hesabı kilitlendi", category: "technical", category_label: "Teknik",
    status: "answered", status_label: "Cevaplandı", audience: "super_admin", audience_label: "Süper Admin",
    requester_id: 1, requester_name: "Ben", requester_role: "teacher",
    target_user_id: null, target_user_name: null, institution_id: null, institution_name: null,
    created_at: "2026-06-03", last_activity_at: "2026-06-04T10:00:00",
    message_count: 3, last_message_preview: "Hesabı sıfırladık, tekrar giriş yapabilir.", handled_by_name: "Destek",
  },
  {
    id: 1, subject: "Faturamı göremiyorum", category: "billing", category_label: "Ödeme",
    status: "open", status_label: "Açık", audience: "super_admin", audience_label: "Süper Admin",
    requester_id: 1, requester_name: "Ben", requester_role: "teacher",
    target_user_id: null, target_user_name: null, institution_id: null, institution_name: null,
    created_at: "2026-06-02", last_activity_at: "2026-06-02T14:00:00",
    message_count: 1, last_message_preview: "Geçen ayki ödememi panelimde göremiyorum.", handled_by_name: null,
  },
];

export default function SupportListPreview() {
  const [view, setView] = React.useState<"mine" | "inbox">("mine");
  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <ScrollView className="flex-1">
        <View className="flex-1">
          <SupportListView
            view={view}
            onChangeView={setView}
            showInbox={false}
            data={{ items: ITEMS, categories: [{ value: "technical", label: "Teknik" }, { value: "billing", label: "Ödeme" }, { value: "other", label: "Diğer" }] }}
            createBusy={false}
            onCreate={() => {}}
            onOpen={() => {}}
          />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
