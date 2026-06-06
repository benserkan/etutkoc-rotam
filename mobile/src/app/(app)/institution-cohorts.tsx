import * as React from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Pressable, Text, View } from "react-native";

import { Banner, Empty, InstitutionScreen, Kpi, KpiGrid, ProgressBar, pctText, toneFromColor } from "@/components/institution/ui";
import { getInstitutionCohorts, institutionKeys, type CohortsResponse } from "@/lib/institution";
import { cn } from "@/lib/utils";

export default function InstitutionCohortsScreen() {
  const [tab, setTab] = React.useState("grade");
  const q = useQuery({
    queryKey: institutionKeys.cohorts(tab),
    queryFn: () => getInstitutionCohorts(tab),
    placeholderData: keepPreviousData,
  });

  return (
    <InstitutionScreen<CohortsResponse> title="Kohort Analizi" query={q}>
      {(d) => {
        const wow = d.wow;
        const arrow = wow.direction === "up" ? "↑" : wow.direction === "down" ? "↓" : "→";
        return (
          <>
            <Banner kind="info">Öğrenci grupları (sınıf/alan/müfredat/hedef) bazında haftalık tamamlama ve risk dağılımı.</Banner>
            <KpiGrid>
              <Kpi label="Bu hafta" value={pctText(wow.this_week_rate)} />
              <Kpi label="Geçen hafta" value={pctText(wow.last_week_rate)} />
              <Kpi label="Değişim" value={`${arrow} ${wow.delta_pct == null ? "—" : `%${Math.abs(Math.round(wow.delta_pct))}`}`} tone={wow.direction === "up" ? "text-emerald-700" : wow.direction === "down" ? "text-rose-700" : "text-slate-900"} />
            </KpiGrid>

            <View className="flex-row flex-wrap gap-2">
              {d.tabs.map((t) => {
                const active = t.key === tab;
                return (
                  <Pressable key={t.key} onPress={() => setTab(t.key)} className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}>
                    <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{t.label}</Text>
                  </Pressable>
                );
              })}
            </View>

            {d.cohorts.length === 0 ? (
              <Empty text="Bu grupta veri yok." />
            ) : (
              <View className="gap-2">
                {d.cohorts.map((c) => {
                  const tone = toneFromColor(c.rate_color);
                  return (
                    <View key={c.cohort_key} className={cn("rounded-xl border border-l-4 border-slate-200 bg-white p-3", tone.border)}>
                      <View className="flex-row items-center justify-between">
                        <Text className="flex-1 text-sm font-semibold text-slate-900" numberOfLines={1}>{c.cohort_label}</Text>
                        <Text className={cn("text-base font-extrabold", tone.text)}>{pctText(c.weekly_rate_pct)}</Text>
                      </View>
                      <View className="mt-1"><ProgressBar pct={c.weekly_rate_pct} tone={tone.bar} /></View>
                      <Text className="mt-1 text-[11px] text-slate-400">
                        {c.student_count} öğrenci · {c.weekly_completed}/{c.weekly_planned} görev
                        {c.at_risk_count > 0 ? ` · ${c.at_risk_count} riskli (${pctText(c.at_risk_pct)})` : ""}
                      </Text>
                    </View>
                  );
                })}
              </View>
            )}
          </>
        );
      }}
    </InstitutionScreen>
  );
}
