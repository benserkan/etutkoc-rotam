import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { TodayView } from "@/components/student/today-view";
import type { StudentDayResponse } from "@/lib/student";

/**
 * UX döngüsü önizleme route'u (auth'suz, sabit mock veri) — ekran görüntüsü +
 * tasarım analizi için. Mağaza build'inden ÖNCE (Faz 7) kaldırılacak.
 */
function mockItem(over: Partial<import("@/lib/student").StudentTaskItem>) {
  return {
    id: Math.floor(over.id ?? 1),
    book_id: 1,
    book_name: "Kitap",
    book_type: "soru_bankasi",
    subject_id: null,
    subject_name: null,
    section_id: 1,
    section_label: null,
    topic_name: null,
    planned: 0,
    completed: 0,
    is_full: false,
    correct: null,
    wrong: null,
    ...over,
  };
}

const MOCK_DAY: StudentDayResponse = {
  date: "2026-06-05",
  is_today: true,
  is_future: false,
  is_past: false,
  prev_date: "2026-06-04",
  next_date: "2026-06-06",
  summary: {
    total_tasks: 5,
    planned_count: 29,
    completed_count: 18,
    pct: 0.4,
    gorev_total: 5,
    gorev_done: 2,
    test_planned: 29,
    test_completed: 18,
    deneme_count: 0,
    etkinlik_count: 1,
  },
  day_note: "",
  can_request: { change: true, replace: true, remove: true, question: true, add: true },
  tasks: [
    {
      id: 1, title: "", type: "test", status: "completed", date: "2026-06-05", period: null,
      planned_count: 5, completed_count: 5, pct: 1, is_future_blocked: false, is_past: false,
      has_pending_request: false,
      items: [mockItem({ id: 1, subject_id: 10, subject_name: "Matematik", book_name: "Karekök Yayınları", section_label: "Üslü Sayılar", planned: 5, completed: 5 })],
    },
    {
      id: 2, title: "", type: "test", status: "completed", date: "2026-06-05", period: null,
      planned_count: 10, completed_count: 10, pct: 1, is_future_blocked: false, is_past: false,
      has_pending_request: false,
      items: [mockItem({ id: 2, subject_id: 10, subject_name: "Matematik", book_name: "Apotemi", section_label: "Köklü Sayılar", planned: 10, completed: 10 })],
    },
    {
      id: 3, title: "", type: "test", status: "in_progress", date: "2026-06-05", period: null,
      planned_count: 8, completed_count: 3, pct: 0.375, is_future_blocked: false, is_past: false,
      has_pending_request: false,
      items: [mockItem({ id: 3, subject_id: 20, subject_name: "Fen Bilimleri", book_name: "3D Yayınları", section_label: "Basınç", planned: 8, completed: 3 })],
    },
    {
      id: 4, title: "", type: "test", status: "pending", date: "2026-06-05", period: null,
      planned_count: 6, completed_count: 0, pct: 0, is_future_blocked: false, is_past: false,
      has_pending_request: false,
      items: [mockItem({ id: 4, subject_id: 30, subject_name: "Türkçe", book_name: "Bilgi Sarmal", section_label: "Sözcükte Anlam", planned: 6, completed: 0 })],
    },
    {
      id: 5, title: "Fen Bilimleri · Kuvvet ve Hareket videosu", type: "video", status: "pending",
      date: "2026-06-05", period: null, planned_count: 0, completed_count: 0, pct: 0,
      is_future_blocked: false, is_past: false, has_pending_request: false,
      items: [],
    },
  ],
};

export default function StudentTodayPreview() {
  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <View className="flex-1">
        <TodayView day={MOCK_DAY} busyTaskId={null} onQuickToggle={() => {}} onOpenTask={() => {}} />
      </View>
    </SafeAreaView>
  );
}
