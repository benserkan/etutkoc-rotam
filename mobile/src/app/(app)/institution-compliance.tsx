import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import {
  Banner,
  Empty,
  InstitutionScreen,
  Kpi,
  KpiGrid,
  MiniBars,
  ProgressBar,
  Section,
  pctText,
  toneFromColor,
} from "@/components/institution/ui";
import {
  getInstitutionCompliance,
  institutionKeys,
  type ComplianceStudentRow,
  type ComplianceTeacherRow,
  type InstitutionComplianceResponse,
} from "@/lib/institution";
import { cn } from "@/lib/utils";

function weekLabel(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function TeacherRow({ t }: { t: ComplianceTeacherRow }) {
  const tone = toneFromColor(t.rate_color);
  return (
    <View className={cn("rounded-xl border border-l-4 border-slate-200 bg-white p-3", tone.border)}>
      <View className="flex-row items-center justify-between">
        <Text className="flex-1 text-sm font-semibold text-slate-900" numberOfLines={1}>{t.teacher_name}</Text>
        <Text className={cn("text-base font-extrabold", tone.text)}>{pctText(t.rate)}</Text>
      </View>
      <View className="mt-1"><ProgressBar pct={t.rate} tone={tone.bar} /></View>
      <Text className="mt-1 text-[11px] text-slate-400">
        {t.student_count} öğrenci · {t.completed}/{t.planned} test · doğruluk {pctText(t.accuracy)}
        {t.empty_students > 0 ? ` · ${t.empty_students} boş program` : ""}
      </Text>
    </View>
  );
}

function StudentRow({ s }: { s: ComplianceStudentRow }) {
  const tone = toneFromColor(s.rate_color);
  return (
    <View className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
      <View className="flex-1">
        <Text className="text-sm font-medium text-slate-800" numberOfLines={1}>{s.student_name}</Text>
        <Text className="text-[11px] text-slate-400" numberOfLines={1}>{s.teacher_name} · {s.completed}/{s.planned} test</Text>
      </View>
      <Text className={cn("text-sm font-bold", tone.text)}>{pctText(s.rate)}</Text>
    </View>
  );
}

export default function InstitutionComplianceScreen() {
  const q = useQuery({ queryKey: institutionKeys.compliance, queryFn: () => getInstitutionCompliance(8) });

  return (
    <InstitutionScreen<InstitutionComplianceResponse> title="Program Uyumu" query={q}>
      {(d) => {
        const s = d.summary;
        const deltaTxt = s.delta == null ? "" : `${s.delta >= 0 ? "↑" : "↓"} %${Math.abs(Math.round(s.delta))} geçen haftaya göre`;
        return (
          <>
            <KpiGrid>
              <Kpi label="Tamamlama (bu hafta)" value={pctText(s.rate)} sub={deltaTxt} tone={toneFromColor(s.rate_color).text} />
              <Kpi label="Doğruluk" value={pctText(s.accuracy)} />
              <Kpi label="Çözülen / Planlanan" value={`${s.completed}/${s.planned}`} sub="test" />
              <Kpi label="Boş program" value={String(s.empty_count)} sub={`${s.student_count} öğrenci`} tone={s.empty_count > 0 ? "text-rose-600" : "text-slate-900"} />
            </KpiGrid>

            {d.trend.length > 0 ? (
              <Section title="Haftalık tamamlama trendi">
                <MiniBars points={d.trend.map((p) => ({ label: weekLabel(p.week_start), value: p.rate }))} />
              </Section>
            ) : null}

            <Section title="Koç kırılımı" hint="≥%70 iyi · <%40 dikkat">
              {d.teachers.length === 0 ? <Empty text="Koç verisi yok." /> : d.teachers.map((t) => <TeacherRow key={t.teacher_id} t={t} />)}
            </Section>

            {d.attention_students.length > 0 ? (
              <Section title="Dikkat gerektiren öğrenciler" hint="en düşük 25">
                {d.attention_students.map((s2, i) => <StudentRow key={i} s={s2} />)}
              </Section>
            ) : null}

            {d.empty_program.length > 0 ? (
              <Section title="Boş program">
                <Banner kind="warn">
                  {d.empty_program.map((e) => `${e.teacher_name}: ${e.empty_count} öğrenci${e.sample_student ? ` (${e.sample_student}…)` : ""}`).join("\n")}
                </Banner>
              </Section>
            ) : null}
          </>
        );
      }}
    </InstitutionScreen>
  );
}
