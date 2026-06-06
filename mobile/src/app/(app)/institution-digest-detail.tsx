import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { Text, View } from "react-native";

import { Banner, InstitutionScreen, Kpi, KpiGrid, Section, pctText, toneFromColor } from "@/components/institution/ui";
import { getInstitutionDigest, institutionKeys, type AdminDigestDetailResponse } from "@/lib/institution";
import { cn } from "@/lib/utils";

export default function InstitutionDigestDetailScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Number(params.id);
  const q = useQuery({ queryKey: institutionKeys.digest(id), queryFn: () => getInstitutionDigest(id), enabled: Number.isFinite(id) });

  return (
    <InstitutionScreen<AdminDigestDetailResponse> title="Haftalık Özet Detayı" query={q}>
      {(d) => {
        const p = d.payload;
        if (!p) {
          return <Banner kind="info">Bu özet için detay kaydı tutulmamış.</Banner>;
        }
        const c = p.completion;
        const arrow = c.direction === "up" ? "↑" : c.direction === "down" ? "↓" : "→";
        return (
          <>
            <KpiGrid>
              <Kpi label="Öğretmen" value={String(p.totals.teacher_count)} sub={p.totals.inactive_teacher_count > 0 ? `${p.totals.inactive_teacher_count} pasif` : "hepsi aktif"} tone={p.totals.inactive_teacher_count > 0 ? "text-amber-600" : "text-slate-900"} />
              <Kpi label="Öğrenci" value={String(p.totals.student_count)} />
              <Kpi label="Tamamlama" value={pctText(c.this_week_rate)} sub={`${arrow} ${c.delta_pct == null ? "—" : `%${Math.abs(Math.round(c.delta_pct))}`}`} />
              <Kpi label="Riskli" value={String(p.at_risk.total)} sub={`${p.at_risk.critical} kritik · ${p.at_risk.high} yüksek`} tone={p.at_risk.critical > 0 ? "text-rose-600" : "text-slate-900"} />
            </KpiGrid>

            {(p.highlight.best_grade_label || p.highlight.worst_grade_label) ? (
              <Section title="Öne çıkanlar">
                {p.highlight.best_grade_label ? (
                  <View className="flex-row items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2">
                    <Text className="text-sm text-emerald-800">En iyi: {p.highlight.best_grade_label}</Text>
                    <Text className="text-sm font-bold text-emerald-800">{pctText(p.highlight.best_grade_rate)}</Text>
                  </View>
                ) : null}
                {p.highlight.worst_grade_label ? (
                  <View className="flex-row items-center justify-between rounded-xl border border-rose-200 bg-rose-50 px-3 py-2">
                    <Text className="text-sm text-rose-800">En düşük: {p.highlight.worst_grade_label}</Text>
                    <Text className="text-sm font-bold text-rose-800">{pctText(p.highlight.worst_grade_rate)}</Text>
                  </View>
                ) : null}
              </Section>
            ) : null}

            {p.grade_cohorts.length > 0 ? (
              <Section title="Sınıf kohortları">
                {p.grade_cohorts.map((g, i) => {
                  const tone = toneFromColor(g.color);
                  return (
                    <View key={i} className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
                      <Text className="flex-1 text-sm text-slate-800">{g.label} · {g.n} öğrenci</Text>
                      <Text className={cn("text-sm font-bold", tone.text)}>{pctText(g.rate)}</Text>
                    </View>
                  );
                })}
              </Section>
            ) : null}

            {p.inactive_teachers.length > 0 ? (
              <Section title="Pasif öğretmenler">
                {p.inactive_teachers.map((t) => (
                  <View key={t.id} className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2">
                    <Text className="text-sm font-medium text-amber-900">{t.name}</Text>
                    <Text className="text-[11px] text-amber-700">{t.email}</Text>
                  </View>
                ))}
              </Section>
            ) : null}

            {d.recipient_emails.length > 0 ? (
              <Section title={`Alıcılar (${d.recipient_emails.length})`}>
                <View className="rounded-xl border border-slate-200 bg-white px-3 py-2">
                  <Text className="text-[11px] text-slate-500">{d.recipient_emails.join(", ")}</Text>
                </View>
              </Section>
            ) : null}
          </>
        );
      }}
    </InstitutionScreen>
  );
}
