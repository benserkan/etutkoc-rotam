import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { Empty, InstitutionScreen, Kpi, KpiGrid, ProgressBar, pctText, toneFromColor } from "@/components/institution/ui";
import {
  getInstitutionScorecard,
  institutionKeys,
  type TeacherScorecardResponse,
  type TeacherScorecardRow,
} from "@/lib/institution";
import { cn } from "@/lib/utils";

function Row({ r }: { r: TeacherScorecardRow }) {
  const tone = toneFromColor(r.score_color);
  return (
    <View className={cn("rounded-xl border border-l-4 border-slate-200 bg-white p-3", tone.border)}>
      <View className="flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={1}>{r.teacher_name}</Text>
        <View className="items-end">
          <Text className={cn("text-lg font-extrabold", tone.text)}>{r.score == null ? "—" : r.score}</Text>
          <Text className={cn("text-[10px] font-semibold", tone.text)}>{r.score_label}</Text>
        </View>
      </View>
      <View className="mt-1"><ProgressBar pct={r.score} tone={tone.bar} /></View>
      <Text className="mt-1.5 text-[11px] text-slate-500">
        {r.student_count} öğrenci · tamamlama {pctText(r.completion_rate)} · doğruluk {pctText(r.accuracy)} · disiplin {pctText(r.discipline_pct)}
        {r.risk_students > 0 ? ` · ${r.risk_students} riskli` : ""}
      </Text>
    </View>
  );
}

export default function InstitutionScorecardScreen() {
  const q = useQuery({ queryKey: institutionKeys.scorecard, queryFn: () => getInstitutionScorecard(4) });
  return (
    <InstitutionScreen<TeacherScorecardResponse> title="Öğretmen Karnesi" query={q}>
      {(d) => (
        <>
          <KpiGrid>
            <Kpi label="Ortalama skor" value={d.summary.avg_score == null ? "—" : String(Math.round(d.summary.avg_score))} sub={`${d.summary.teacher_count} koç · son ${d.summary.weeks} hafta`} />
            <Kpi label="En etkili koç" value={d.summary.top_score == null ? "—" : String(d.summary.top_score)} sub={d.summary.top_name ?? ""} tone="text-emerald-700" />
          </KpiGrid>
          <View className="gap-2">
            {d.teachers.length === 0 ? <Empty text="Koç verisi yok." /> : d.teachers.map((r) => <Row key={r.teacher_id} r={r} />)}
          </View>
        </>
      )}
    </InstitutionScreen>
  );
}
