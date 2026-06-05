import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { RequestsView } from "@/components/student/requests-view";
import type { StudentRequestItem, StudentRequestListResponse } from "@/lib/student";

/** UX önizleme — Taleplerim (mock). Faz 7'de kaldırılacak. */
function req(over: Partial<StudentRequestItem>): StudentRequestItem {
  return {
    id: 1, type: "question", status: "pending", task_id: 1,
    task_title: null, task_date: null, message: null,
    proposed_book_name: null, proposed_section_label: null, proposed_count: null,
    proposed_date: null, teacher_response: null,
    created_at: "2026-06-04T10:00:00Z", responded_at: null, ...over,
  };
}

const MOCK: StudentRequestListResponse = {
  total: 3,
  pending_count: 1,
  items: [
    req({
      id: 3, type: "question", status: "pending",
      task_title: "3D Yayınları · Basınç", task_date: "2026-06-05",
      message: "Basınç konusunda 5. soruyu anlamadım, yardım eder misin?",
    }),
    req({
      id: 2, type: "change", status: "approved",
      task_title: "Karekök Yayınları · Üslü Sayılar", task_date: "2026-06-03",
      proposed_count: 3, message: "8 test çok geldi, 3'e indirebilir miyiz?",
      teacher_response: "Tamam, 3 teste indirdim. Kolay gelsin!",
      responded_at: "2026-06-03T18:00:00Z",
    }),
    req({
      id: 1, type: "remove", status: "rejected",
      task_title: "Bilgi Sarmal · Sözcükte Anlam", task_date: "2026-06-02",
      message: "Bugün hastaydım yapamadım.",
      teacher_response: "Yarına erteledim, bugün dinlen.",
      responded_at: "2026-06-02T20:00:00Z",
    }),
  ],
};

export default function StudentRequestsPreview() {
  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <View className="flex-1">
        <RequestsView data={MOCK} onWithdraw={() => {}} />
      </View>
    </SafeAreaView>
  );
}
