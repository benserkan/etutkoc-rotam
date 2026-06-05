import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { TaskSheetContent } from "@/components/student/task-sheet";
import type { StudentTask } from "@/lib/student";

/** UX önizleme — doğru/yanlış giriş sayfası (sheet içeriği). Faz 7'de kaldırılacak. */
const MOCK_TASK: StudentTask = {
  id: 3,
  title: "",
  type: "test",
  status: "in_progress",
  date: "2026-06-05",
  period: null,
  planned_count: 8,
  completed_count: 3,
  pct: 0.375,
  is_future_blocked: false,
  is_past: false,
  has_pending_request: false,
  items: [
    {
      id: 3,
      book_id: 1,
      book_name: "3D Yayınları",
      book_type: "soru_bankasi",
      subject_id: 20,
      subject_name: "Fen Bilimleri",
      section_id: 5,
      section_label: "Basınç",
      topic_name: null,
      planned: 8,
      completed: 3,
      is_full: false,
      correct: null,
      wrong: null,
    },
  ],
};

export default function TaskSheetPreview() {
  return (
    <SafeAreaView className="flex-1 justify-end bg-black/40">
      <View className="rounded-t-3xl bg-white px-5 pb-8 pt-3">
        <View className="mb-2 items-center">
          <View className="h-1.5 w-10 rounded-full bg-slate-300" />
        </View>
        <TaskSheetContent
          task={MOCK_TASK}
          busy={false}
          error={null}
          onSaveItems={() => {}}
          onCompleteActivity={() => {}}
          onUncomplete={() => {}}
          canRequest={{ change: true, replace: true, remove: true, question: true, add: true }}
          hasPendingRequest={false}
          requestBusy={false}
          onSubmitRequest={() => {}}
        />
      </View>
    </SafeAreaView>
  );
}
