import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { SessionsTabView } from "@/components/teacher/sessions-tab";
import type { StudentSessionListResponse } from "@/lib/teacher";

/** UX önizleme — Koç: öğrenci seansları (mock). Faz 7'de kaldırılacak. */
const MOCK: StudentSessionListResponse = {
  summary: {
    total: 3, done_count: 2, postponed_count: 1, cancelled_count: 0, no_show_count: 0,
    last_session_date: "2026-06-02",
  },
  rows: [
    {
      id: 3, session_date: "2026-06-02", status: "done", status_label: "Yapıldı", duration_min: 45,
      channel: "in_person", channel_label: "Yüz yüze",
      agenda: "Matematik problemlerinde hız çalışması yapıldı. Geometri tekrarına başlandı.",
      next_change: "Her gün 20 dakika geometri tekrarı.",
      coach_note: "Motivasyonu yüksek, sınav kaygısı azalmış görünüyor.",
      mood: 4, tags: [], capture_source: "manual", created_at: "2026-06-02",
    },
    {
      id: 2, session_date: "2026-05-26", status: "done", status_label: "Yapıldı", duration_min: 40,
      channel: "online", channel_label: "Online",
      agenda: "Haftalık program değerlendirmesi. Fen netleri konuşuldu.",
      next_change: null, coach_note: null, mood: 3, tags: [], capture_source: "manual", created_at: "2026-05-26",
    },
    {
      id: 1, session_date: "2026-05-19", status: "postponed", status_label: "Ertelendi", duration_min: null,
      channel: null, channel_label: null,
      agenda: "Öğrenci rahatsızlandı, seans ertelendi.",
      next_change: null, coach_note: null, mood: null, tags: [], capture_source: "manual", created_at: "2026-05-19",
    },
  ],
};

export default function TeacherSessionsPreview() {
  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ScrollView className="flex-1">
        <View className="flex-1">
          <SessionsTabView data={MOCK} addBusy={false} addError={null} onAdd={() => {}} />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
