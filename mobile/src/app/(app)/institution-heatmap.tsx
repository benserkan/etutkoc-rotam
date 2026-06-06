import * as React from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Pressable, ScrollView, Text, View } from "react-native";

import { Badge, Banner, Empty, InstitutionScreen } from "@/components/institution/ui";
import {
  getInstitutionHeatmap,
  institutionKeys,
  type ActivityHeatmapResponse,
  type TeacherHeatmapRow,
} from "@/lib/institution";
import { cn } from "@/lib/utils";

function cellColor(score: number): string {
  if (score <= 0) return "#f1f5f9";
  if (score < 0.25) return "#a7f3d0";
  if (score < 0.5) return "#6ee7b7";
  if (score < 0.75) return "#34d399";
  return "#059669";
}

function HeatmapRow({ t }: { t: TeacherHeatmapRow }) {
  return (
    <View className="rounded-xl border border-slate-200 bg-white p-3">
      <View className="flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-sm font-semibold text-slate-900" numberOfLines={1}>{t.full_name}</Text>
        {t.is_new ? <Badge label="yeni" tone="sky" /> : t.is_inactive ? <Badge label="pasif" tone="rose" /> : null}
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} className="mt-2">
        <View className="flex-row gap-[2px]">
          {t.cells.map((c, i) => (
            <View key={i} style={{ width: 9, height: 9, borderRadius: 2, backgroundColor: cellColor(c.activity_score) }} />
          ))}
        </View>
      </ScrollView>
      <Text className="mt-1.5 text-[11px] text-slate-400">
        {t.total_logins} giriş · {t.total_tasks} görev · {t.total_notes} not
        {t.days_since_active != null ? ` · ${t.days_since_active === 0 ? "bugün" : `${t.days_since_active}g önce`} aktif` : t.is_new ? " · henüz giriş yok" : ""}
      </Text>
    </View>
  );
}

export default function InstitutionHeatmapScreen() {
  const [weeks, setWeeks] = React.useState(4);
  const q = useQuery({
    queryKey: institutionKeys.heatmap(weeks),
    queryFn: () => getInstitutionHeatmap(weeks),
    placeholderData: keepPreviousData,
  });

  return (
    <InstitutionScreen<ActivityHeatmapResponse> title="Aktivite Haritası" query={q}>
      {(d) => (
        <>
          <View className="flex-row gap-2">
            {[4, 12].map((w) => {
              const active = w === weeks;
              return (
                <Pressable key={w} onPress={() => setWeeks(w)} className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}>
                  <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{w} hafta</Text>
                </Pressable>
              );
            })}
          </View>

          {d.inactive_count > 0 ? (
            <Banner kind="danger">
              {d.inactive_count} koç {d.inactive_threshold_days}+ gündür aktif değil. Aktiflik = giriş + görev + not.
            </Banner>
          ) : (
            <Banner kind="info">Aktiflik = giriş + görev oluşturma + not. Koyu yeşil = yoğun gün.</Banner>
          )}

          {d.teachers.length === 0 ? (
            <Empty text="Koç verisi yok." />
          ) : (
            <View className="gap-2">{d.teachers.map((t) => <HeatmapRow key={t.teacher_id} t={t} />)}</View>
          )}
        </>
      )}
    </InstitutionScreen>
  );
}
