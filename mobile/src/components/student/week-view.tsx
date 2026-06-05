import { Ionicons } from "@expo/vector-icons";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import type { StudentWeekDay, StudentWeekResponse } from "@/lib/student";

const TR_MONTHS_SHORT = [
  "Oca", "Şub", "Mar", "Nis", "May", "Haz",
  "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara",
];
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}

function distinctSubjects(day: StudentWeekDay): string[] {
  const set = new Set<string>();
  for (const t of day.tasks) {
    for (const it of t.items) {
      if (it.subject_name) set.add(it.subject_name);
    }
  }
  return Array.from(set);
}

function DayCard({ day, onPress }: { day: StudentWeekDay; onPress: () => void }) {
  const total = day.gorev_total;
  const done = day.gorev_done;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const subjects = distinctSubjects(day);
  const hasTasks = total > 0 || day.tasks.length > 0;

  return (
    <Pressable
      onPress={onPress}
      className={`rounded-2xl border bg-white p-4 active:bg-slate-50 ${
        day.is_today ? "border-brand-400" : "border-slate-200"
      }`}
    >
      <View className="flex-row items-center justify-between">
        <View className="flex-row items-center gap-2">
          <Text className="text-[15px] font-bold text-slate-900">{day.dow_label}</Text>
          <Text className="text-xs text-slate-400">{shortDate(day.date)}</Text>
          {day.is_today ? (
            <View className="rounded-full bg-brand-50 px-2 py-0.5">
              <Text className="text-[10px] font-semibold text-brand-700">Bugün</Text>
            </View>
          ) : null}
        </View>
        <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
      </View>

      {hasTasks ? (
        <>
          <View className="mt-2 flex-row items-center justify-between">
            <Text className="text-sm font-medium text-slate-700">
              {done}/{total} görev
              {day.test_planned > 0 ? (
                <Text className="text-xs font-normal text-slate-400">  ·  {day.test_completed}/{day.test_planned} test</Text>
              ) : null}
            </Text>
            <Text className="text-xs font-semibold text-slate-500">%{pct}</Text>
          </View>
          <View className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <View
              className={`h-full rounded-full ${pct >= 100 ? "bg-emerald-500" : pct > 0 ? "bg-amber-400" : "bg-slate-200"}`}
              style={{ width: `${Math.min(100, pct)}%` }}
            />
          </View>
          {subjects.length > 0 ? (
            <View className="mt-2.5 flex-row flex-wrap gap-1.5">
              {subjects.slice(0, 4).map((s) => (
                <View key={s} className="rounded-md bg-slate-100 px-2 py-0.5">
                  <Text className="text-[11px] text-slate-600">{s}</Text>
                </View>
              ))}
              {subjects.length > 4 ? (
                <Text className="text-[11px] text-slate-400">+{subjects.length - 4}</Text>
              ) : null}
            </View>
          ) : null}
        </>
      ) : (
        <Text className="mt-1.5 text-sm text-slate-400">Görev yok</Text>
      )}
    </Pressable>
  );
}

export function WeekView({
  week,
  onPrev,
  onNext,
  onThisWeek,
  onOpenDay,
  refreshing = false,
  onRefresh,
}: {
  week: StudentWeekResponse;
  onPrev: () => void;
  onNext: () => void;
  onThisWeek: () => void;
  onOpenDay: (date: string) => void;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const pct = Math.round((week.total_pct ?? 0) * 100);

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <ScrollView
        contentContainerClassName="px-4 py-3 gap-3"
        refreshControl={
          onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined
        }
      >
        {/* Hafta gezinme */}
        <View className="flex-row items-center justify-between">
          <Pressable
            onPress={onPrev}
            hitSlop={8}
            className="size-10 items-center justify-center rounded-full border border-slate-200 bg-white active:bg-slate-100"
          >
            <Ionicons name="chevron-back" size={20} color="#334155" />
          </Pressable>
          <View className="items-center">
            <Text className="text-sm font-bold text-slate-900">
              {shortDate(week.start_date)} – {shortDate(week.end_date)}
            </Text>
            <Pressable onPress={onThisWeek} hitSlop={6}>
              <Text className="text-xs font-medium text-brand-700">Bu hafta</Text>
            </Pressable>
          </View>
          <Pressable
            onPress={onNext}
            hitSlop={8}
            className="size-10 items-center justify-center rounded-full border border-slate-200 bg-white active:bg-slate-100"
          >
            <Ionicons name="chevron-forward" size={20} color="#334155" />
          </Pressable>
        </View>

        <Text className="text-center text-xs text-slate-500">
          Bu hafta {week.total_gorev_done}/{week.total_gorev} görev · %{pct}
        </Text>

        {week.days.map((d) => (
          <DayCard key={d.date} day={d} onPress={() => onOpenDay(d.date)} />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
