import { RefreshControl, ScrollView, Text, View } from "react-native";

import type { ParentWeekDay, ParentWeekResponse } from "@/lib/parent";
import { cn } from "@/lib/utils";

const DAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const TR_MONTHS_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}

function totals(days: ParentWeekDay[]) {
  let gd = 0, gt = 0, tc = 0, tp = 0;
  for (const d of days) {
    gd += d.gorev_done;
    gt += d.gorev_total;
    tc += d.test_completed;
    tp += d.test_planned;
  }
  const pct = gt > 0 ? Math.round((gd / gt) * 100) : 0;
  return { gd, gt, tc, tp, pct };
}

function toneFor(pct: number): { ring: string; text: string; label: string } {
  if (pct >= 70) return { ring: "border-emerald-500", text: "text-emerald-600", label: "İyi gidiyor" };
  if (pct >= 40) return { ring: "border-amber-400", text: "text-amber-600", label: "Dikkat" };
  return { ring: "border-rose-500", text: "text-rose-600", label: "Düşük" };
}

function DayBar({ day }: { day: ParentWeekDay }) {
  const pct = day.gorev_total > 0 ? Math.round((day.gorev_done / day.gorev_total) * 100) : 0;
  return (
    <View className="flex-row items-center gap-3">
      <Text className="w-10 text-xs font-medium text-slate-500">{DAYS[day.weekday] ?? ""}</Text>
      <View className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
        <View
          className={cn("h-full rounded-full", pct >= 100 ? "bg-emerald-500" : pct > 0 ? "bg-amber-400" : "bg-slate-200")}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </View>
      <Text className="w-14 text-right text-xs text-slate-500">
        {day.gorev_total > 0 ? `${day.gorev_done}/${day.gorev_total}` : "—"}
      </Text>
    </View>
  );
}

export function ParentChildReportView({
  week,
  refreshing = false,
  onRefresh,
}: {
  week: ParentWeekResponse;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const t = totals(week.days);
  const tone = toneFor(t.pct);

  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-4 gap-4"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined}
    >
      <View>
        <Text className="text-xs font-semibold uppercase tracking-wide text-slate-400">Haftalık ilerleme raporu</Text>
        <Text className="mt-0.5 text-lg font-bold text-slate-900">{week.student.full_name}</Text>
        <Text className="text-xs text-slate-400">{shortDate(week.start)} – {shortDate(week.end)}</Text>
      </View>

      {/* Performans halkası */}
      <View className="items-center rounded-2xl border border-slate-200 bg-white p-6">
        <View className={cn("size-32 items-center justify-center rounded-full border-8", tone.ring)}>
          <Text className={cn("text-4xl font-extrabold", tone.text)}>%{t.pct}</Text>
          <Text className="text-[11px] text-slate-400">tamamlama</Text>
        </View>
        <Text className={cn("mt-3 text-sm font-semibold", tone.text)}>{tone.label}</Text>
        <View className="mt-3 flex-row gap-6">
          <View className="items-center">
            <Text className="text-xl font-extrabold text-slate-900">{t.gd}/{t.gt}</Text>
            <Text className="text-[11px] text-slate-400">görev</Text>
          </View>
          {t.tp > 0 ? (
            <View className="items-center">
              <Text className="text-xl font-extrabold text-slate-900">{t.tc}/{t.tp}</Text>
              <Text className="text-[11px] text-slate-400">test</Text>
            </View>
          ) : null}
        </View>
      </View>

      {/* Gün gün */}
      <View className="rounded-2xl border border-slate-200 bg-white p-4">
        <Text className="mb-3 text-sm font-semibold text-slate-700">Gün gün tamamlama</Text>
        <View className="gap-2.5">
          {week.days.map((d) => (
            <DayBar key={d.date} day={d} />
          ))}
        </View>
      </View>

      {t.gt === 0 ? (
        <Text className="px-2 text-center text-sm text-slate-400">
          Bu hafta için planlanmış görev bulunamadı.
        </Text>
      ) : null}
    </ScrollView>
  );
}
