import { Ionicons } from "@expo/vector-icons";
import { Pressable, ScrollView, Text, View } from "react-native";

import type { WarningLevel } from "@/lib/parent";
import type { ParentStudentOverview } from "@/lib/parent-detail";
import { cn } from "@/lib/utils";

const WARN: Record<WarningLevel, { dot: string; label: string; text: string }> = {
  red: { dot: "bg-rose-500", label: "Acil", text: "text-rose-700" },
  amber: { dot: "bg-amber-400", label: "Dikkat", text: "text-amber-700" },
  green: { dot: "bg-emerald-500", label: "Yolunda", text: "text-emerald-700" },
};
const PROJ_LABEL: Record<WarningLevel, string> = {
  green: "Sınava yetişiyor",
  amber: "Tempo sıkışık",
  red: "Tempo yetersiz",
};

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <View className="flex-1 items-center">
      <Text className="text-xl font-extrabold text-white">{value}</Text>
      <Text className="text-[11px] text-brand-100">{label}</Text>
      {sub ? <Text className="text-[10px] text-brand-100/80">{sub}</Text> : null}
    </View>
  );
}

export function ParentChildDetailView({
  data,
  onOpenWeek,
  onOpenReport,
}: {
  data: ParentStudentOverview;
  onOpenWeek?: () => void;
  onOpenReport?: () => void;
}) {
  const w = WARN[data.warning_level];
  const grade =
    data.student.display_grade_label ??
    (data.student.grade_level != null ? `${data.student.grade_level}. sınıf` : "");
  const proj = data.projection;

  return (
    <ScrollView className="flex-1 bg-slate-50" contentContainerClassName="px-4 py-4 gap-4">
      {/* Üst özet (marka) */}
      <View className="rounded-2xl bg-brand-700 p-5">
        <View className="flex-row items-center justify-between">
          <Text className="text-lg font-bold text-white">{data.student.full_name}</Text>
          <View className="flex-row items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1">
            <View className={cn("size-2 rounded-full", w.dot)} />
            <Text className="text-xs font-semibold text-white">{w.label}</Text>
          </View>
        </View>
        <Text className="mt-0.5 text-xs text-brand-100">
          {grade}
          {data.student.exam_label && data.student.exam_date ? ` · ${data.student.exam_label}` : ""}
        </Text>
        <View className="mt-4 flex-row">
          <Stat label="Bugün" value={`${data.today.gorev_done}/${data.today.gorev_total}`} sub="görev" />
          <Stat label="Son 7 gün" value={data.week.gorev_rate != null ? `%${data.week.gorev_rate}` : "—"} sub="tutturma" />
          <Stat label="Tutarlılık" value={data.consistency_7d_pct != null ? `%${data.consistency_7d_pct}` : "—"} />
        </View>
      </View>

      <View className="flex-row gap-3">
        {onOpenWeek ? (
          <Pressable
            onPress={onOpenWeek}
            className="flex-1 flex-row items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-4 active:bg-slate-50"
          >
            <Ionicons name="calendar-outline" size={20} color="#0e7490" />
            <Text className="text-[14px] font-medium text-slate-900">Haftalık program</Text>
          </Pressable>
        ) : null}
        {onOpenReport ? (
          <Pressable
            onPress={onOpenReport}
            className="flex-1 flex-row items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-4 active:bg-slate-50"
          >
            <Ionicons name="stats-chart-outline" size={20} color="#0e7490" />
            <Text className="text-[14px] font-medium text-slate-900">Haftalık rapor</Text>
          </Pressable>
        ) : null}
      </View>

      {/* Projeksiyon */}
      {proj && proj.total_tests > 0 ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-4">
          <View className="flex-row items-center justify-between">
            <Text className="text-sm font-semibold text-slate-800">Sınava hazırlık</Text>
            <Text className={cn("text-xs font-semibold", WARN[proj.status].text)}>{PROJ_LABEL[proj.status]}</Text>
          </View>
          <View className="mt-2 flex-row items-center justify-between">
            <Text className="text-sm text-slate-600">
              {proj.completed_tests}/{proj.total_tests} test · {proj.remaining_tests} kalan
            </Text>
            {proj.days_left_to_exam != null ? (
              <Text className="text-sm font-semibold text-slate-700">Sınava {proj.days_left_to_exam} gün</Text>
            ) : null}
          </View>
          {proj.rate_per_day != null ? (
            <Text className="mt-1 text-xs text-slate-400">Günlük tempo: {proj.rate_per_day} test</Text>
          ) : null}
        </View>
      ) : null}

      {/* Dersler */}
      {data.subjects.length > 0 ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-4 gap-3">
          <Text className="text-sm font-semibold text-slate-800">Ders ilerlemesi</Text>
          {data.subjects.map((s) => (
            <View key={s.subject_id ?? s.name} className="gap-1">
              <View className="flex-row items-center justify-between">
                <Text className="text-[13px] text-slate-700">{s.name}</Text>
                <Text className="text-xs font-semibold text-slate-500">%{s.percent_done}</Text>
              </View>
              <View className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                <View
                  className={cn(
                    "h-full rounded-full",
                    s.percent_done >= 70 ? "bg-emerald-500" : s.percent_done >= 40 ? "bg-amber-400" : "bg-rose-400",
                  )}
                  style={{ width: `${Math.min(100, s.percent_done)}%` }}
                />
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {/* Koç notları */}
      {data.teacher_notes.length > 0 ? (
        <View className="gap-2">
          <Text className="px-1 text-sm font-semibold text-slate-700">Koç notları</Text>
          {data.teacher_notes.map((n) => (
            <View key={n.id} className="rounded-2xl border-l-4 border-l-brand-500 border border-slate-200 bg-white p-4">
              <Text className="text-sm text-slate-800">{n.body}</Text>
              {n.teacher_name ? (
                <Text className="mt-1 text-[11px] text-slate-400">{n.teacher_name}</Text>
              ) : null}
            </View>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}
