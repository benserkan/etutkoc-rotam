import { useQuery } from "@tanstack/react-query";
import { useLocalSearchParams } from "expo-router";
import { Text, View } from "react-native";

import {
  Banner,
  Empty,
  InfoNote,
  InstitutionScreen,
  Kpi,
  KpiGrid,
  pctText,
  rateTone,
} from "@/components/institution/ui";
import {
  getInstitutionTeacherCard,
  institutionKeys,
  type TeacherCardResponse,
  type TeacherCardStudentRow,
} from "@/lib/institution";
import { cn } from "@/lib/utils";

function StudentRow({ s }: { s: TeacherCardStudentRow }) {
  const tone = rateTone(s.weekly_rate_pct);
  const muted = !s.is_active;
  return (
    <View className={cn("rounded-xl border border-l-4 border-slate-200 bg-white p-3", muted ? "border-l-slate-200 opacity-60" : tone.border)}>
      <View className="flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={1}>{s.full_name}</Text>
        {muted ? (
          <Text className="text-[11px] font-semibold text-slate-400">Pasif</Text>
        ) : (
          <Text className={cn("text-base font-extrabold", tone.text)}>{pctText(s.weekly_rate_pct)}</Text>
        )}
      </View>
      <Text className="mt-0.5 text-xs text-slate-400">
        {s.display_grade_label ?? (s.grade_level != null ? `${s.grade_level}. sınıf` : "Mezun")} · {s.weekly_completed}/{s.weekly_planned} test (son 7 gün)
      </Text>
    </View>
  );
}

export default function InstitutionTeacherScreen() {
  const params = useLocalSearchParams<{ id: string }>();
  const id = Number(params.id);
  const q = useQuery({ queryKey: institutionKeys.teacherCard(id), queryFn: () => getInstitutionTeacherCard(id), enabled: Number.isFinite(id) });

  return (
    <InstitutionScreen<TeacherCardResponse> title={q.data?.teacher.full_name ?? "Koç detayı"} query={q} demoContext="teacher-detail">
      {(d) => (
        <>
          <Banner kind="info">
            Gizlilik gereği koçun programı, notları ve öğrenci detayları görünmez. Burada yalnızca son 7 günün
            planlanan ve çözülen test özeti yer alır.
          </Banner>

          <KpiGrid>
            <Kpi label="Öğrenci" value={String(d.students.length)} />
            <Kpi label="Planlanan (7g)" value={String(d.total_planned)} />
            <Kpi label="Çözülen (7g)" value={String(d.total_completed)} tone="text-emerald-700" />
            <Kpi label="Tamamlama" value={pctText(d.overall_rate_pct)} tone={rateTone(d.overall_rate_pct).text} />
          </KpiGrid>

          <View className="gap-2">
            <Text className="px-1 text-sm font-semibold text-slate-700">Öğrenciler — son 7 gün</Text>
            {d.students.length === 0 ? (
              <Empty text="Bu koça bağlı öğrenci yok." />
            ) : (
              d.students.map((s) => <StudentRow key={s.id} s={s} />)
            )}
          </View>
          <InfoNote>Planlanan/çözülen = son 7 günde programa eklenen ve tamamlanan test adedi.</InfoNote>
        </>
      )}
    </InstitutionScreen>
  );
}
