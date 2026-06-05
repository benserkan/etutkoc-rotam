import { Ionicons } from "@expo/vector-icons";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import type { ParentWeekDay, ParentWeekResponse } from "@/lib/parent";
import { cn } from "@/lib/utils";

const DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
const TR_MONTHS_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}

function distinctSubjects(day: ParentWeekDay): string[] {
  const set = new Set<string>();
  for (const t of day.tasks) for (const it of t.book_items) if (it.subject_name) set.add(it.subject_name);
  return Array.from(set);
}

function DayCard({ day }: { day: ParentWeekDay }) {
  const total = day.gorev_total;
  const done = day.gorev_done;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  const subjects = distinctSubjects(day);
  const hasTasks = total > 0 || day.tasks.length > 0;

  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="flex-row items-center justify-between">
        <View className="flex-row items-center gap-2">
          <Text className="text-[15px] font-bold text-slate-900">{DAYS[day.weekday] ?? ""}</Text>
          <Text className="text-xs text-slate-400">{shortDate(day.date)}</Text>
        </View>
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
              className={cn(
                "h-full rounded-full",
                pct >= 100 ? "bg-emerald-500" : pct > 0 ? "bg-amber-400" : "bg-slate-200",
              )}
              style={{ width: `${Math.min(100, pct)}%` }}
            />
          </View>
          {subjects.length > 0 ? (
            <View className="mt-2.5 flex-row flex-wrap gap-1.5">
              {subjects.slice(0, 5).map((s) => (
                <View key={s} className="rounded-md bg-slate-100 px-2 py-0.5">
                  <Text className="text-[11px] text-slate-600">{s}</Text>
                </View>
              ))}
            </View>
          ) : null}
        </>
      ) : (
        <Text className="mt-1.5 text-sm text-slate-400">Görev yok</Text>
      )}
    </View>
  );
}

export function ParentChildWeekView({
  week,
  onPrev,
  onNext,
  onThisWeek,
  refreshing = false,
  onRefresh,
}: {
  week: ParentWeekResponse;
  onPrev: () => void;
  onNext: () => void;
  onThisWeek: () => void;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-3 gap-3"
      refreshControl={
        onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined
      }
    >
      <View className="flex-row items-center justify-between">
        <Pressable onPress={onPrev} hitSlop={8} className="size-10 items-center justify-center rounded-full border border-slate-200 bg-white active:bg-slate-100">
          <Ionicons name="chevron-back" size={20} color="#334155" />
        </Pressable>
        <View className="items-center">
          <Text className="text-sm font-bold text-slate-900">
            {shortDate(week.start)} – {shortDate(week.end)}
          </Text>
          <Pressable onPress={onThisWeek} hitSlop={6}>
            <Text className="text-xs font-medium text-brand-700">Bu hafta</Text>
          </Pressable>
        </View>
        <Pressable onPress={onNext} hitSlop={8} className="size-10 items-center justify-center rounded-full border border-slate-200 bg-white active:bg-slate-100">
          <Ionicons name="chevron-forward" size={20} color="#334155" />
        </Pressable>
      </View>

      {week.days.map((d) => (
        <DayCard key={d.date} day={d} />
      ))}
    </ScrollView>
  );
}
