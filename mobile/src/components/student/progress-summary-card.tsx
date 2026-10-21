import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

import {
  getStudentAnalytics,
  getStudentWeeklyProgress,
  progressKeys,
  type WPDay,
} from "@/lib/student-progress";

const DAY_CLS: Record<WPDay["state"], { box: string; text: string }> = {
  done: { box: "bg-emerald-600", text: "text-white" },
  partial: { box: "bg-amber-400", text: "text-amber-950" },
  missed: { box: "bg-rose-600", text: "text-white" },
  today: { box: "bg-brand-700 border-2 border-cyan-300", text: "text-white" },
  future: { box: "bg-slate-100", text: "text-slate-500" },
  none: { box: "border border-dashed border-slate-300", text: "text-slate-400" },
};

const nf = (n: number) => n.toLocaleString("tr-TR", { maximumFractionDigits: 1 });

/** Bugün ekranında sınava hazırlık özeti (web ProgressSummaryCard ile aynı sayılar). */
export function ProgressSummaryCard() {
  const a = useQuery({ queryKey: progressKeys.analytics, queryFn: getStudentAnalytics, staleTime: 60_000 });
  const w = useQuery({ queryKey: progressKeys.weekly, queryFn: getStudentWeeklyProgress, staleTime: 60_000 });
  if (!a.data && !w.data) return null;
  const p = a.data?.projection;
  const rate = a.data?.summary.rate_7d;
  const hasInv = !!p && p.total_tests > 0;
  const wk = w.data?.has_program ? w.data : null;
  const g = wk?.headline.gorev_pct;

  const tiles = [
    {
      label: wk?.week?.kind === "donem" ? "Bu dönem görev" : "Bu hafta görev",
      value: g?.value != null ? `%${Math.round(g.value)}` : "—",
      note: g && g.low != null && g.high != null ? `genelde %${Math.round(g.low)}–${Math.round(g.high)}` : "tamamlama",
      ok: g == null || g.status === "insufficient" || g.status === "info" ? null : !(g.status === "below" || g.status === "critical"),
    },
    {
      label: "Günlük tempo",
      value: rate != null ? `${nf(rate)} test` : "—",
      note: hasInv && p!.required_rate > 0 ? `gereken ${nf(p!.required_rate)}` : "son 7 gün",
      ok: rate == null || !hasInv ? null : rate >= p!.required_rate,
    },
    {
      label: "Bu gidişle",
      value: hasInv ? (p!.remaining <= 0 ? "Bitti" : `${p!.gap >= 0 ? "+" : "−"}${Math.abs(p!.gap)} test`) : "—",
      note: hasInv ? (p!.gap >= 0 ? "yetişiyorsun" : "eksik kalır") : "kaynak atanınca",
      ok: hasInv ? p!.gap >= 0 : null,
    },
  ];

  return (
    <Pressable
      onPress={() => router.navigate("/(app)/student/gelisim")}
      className="overflow-hidden rounded-2xl border border-cyan-200 bg-white active:opacity-90"
    >
      <View className="flex-row items-center gap-3 bg-indigo-950 px-4 py-3">
        <View className="flex-1">
          <Text className="text-[10px] font-bold uppercase tracking-widest text-cyan-200">Sınava hazırlık</Text>
          <Text className="text-2xl font-extrabold text-white">
            {p?.days_left != null ? `${p.days_left} gün` : "Tarih yok"}
            {p?.exam_label ? <Text className="text-sm font-semibold text-cyan-100">  · {p.exam_label}</Text> : null}
          </Text>
        </View>
        <View className="flex-row items-center gap-1 rounded-full bg-white/15 px-3 py-1.5">
          <Text className="text-xs font-semibold text-white">Gelişimim</Text>
          <Ionicons name="arrow-forward" size={14} color="#fff" />
        </View>
      </View>
      <View className="flex-row gap-2 p-3">
        {tiles.map((t) => (
          <View key={t.label} className="flex-1 rounded-xl border border-slate-200 px-2.5 py-2">
            <View className="flex-row items-center justify-between">
              <Text className="text-[10px] font-semibold text-slate-500" numberOfLines={1}>{t.label}</Text>
              <View className={`size-2 rounded-full ${t.ok == null ? "bg-slate-300" : t.ok ? "bg-emerald-500" : "bg-amber-500"}`} />
            </View>
            <Text className="text-base font-extrabold text-slate-900">{t.value}</Text>
            <Text className="text-[10px] text-slate-500">{t.note}</Text>
          </View>
        ))}
      </View>
      {wk && wk.days.length > 0 ? (
        <View className="flex-row gap-1 border-t border-slate-100 px-3 py-2.5">
          {wk.days.map((d) => {
            const c = DAY_CLS[d.state];
            return (
              <View key={d.date} className={`flex-1 items-center rounded-md py-1 ${c.box}`}>
                <Text className={`text-[9px] font-bold uppercase ${c.text}`}>{d.day}</Text>
                <Text className={`text-[10px] font-semibold ${c.text}`}>{d.total > 0 ? `${d.done}/${d.total}` : "—"}</Text>
              </View>
            );
          })}
        </View>
      ) : null}
    </Pressable>
  );
}
