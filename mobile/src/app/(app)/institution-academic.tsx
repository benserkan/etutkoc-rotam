import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import {
  Banner,
  Empty,
  InstitutionScreen,
  Kpi,
  KpiGrid,
  MiniBars,
  Section,
  pctText,
  toneFromColor,
} from "@/components/institution/ui";
import {
  getInstitutionAcademic,
  institutionKeys,
  type AcademicMoverRow,
  type InstitutionAcademicResponse,
} from "@/lib/institution";
import { cn } from "@/lib/utils";

function weekLabel(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function MoverRow({ m, up }: { m: AcademicMoverRow; up: boolean }) {
  const tone = up ? "text-emerald-700" : "text-rose-700";
  const sign = (m.delta ?? 0) >= 0 ? "+" : "";
  return (
    <View className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
      <View className="flex-1">
        <Text className="text-sm font-medium text-slate-800" numberOfLines={1}>{m.student_name}</Text>
        <Text className="text-[11px] text-slate-400" numberOfLines={1}>
          {m.teacher_name} · {pctText(m.first_net_pct)} → {pctText(m.last_net_pct)} · {m.exam_count} deneme
        </Text>
      </View>
      <Text className={cn("text-sm font-bold", tone)}>{sign}{m.delta == null ? "—" : Math.round(m.delta)}</Text>
    </View>
  );
}

export default function InstitutionAcademicScreen() {
  const q = useQuery({ queryKey: institutionKeys.academic, queryFn: () => getInstitutionAcademic(8) });

  return (
    <InstitutionScreen<InstitutionAcademicResponse> title="Akademik Çıktı" query={q} demoContext="analysis">
      {(d) => {
        const s = d.summary;
        const deltaTxt = s.delta == null ? "" : `${s.delta >= 0 ? "↑" : "↓"} %${Math.abs(Math.round(s.delta))}`;
        return (
          <>
            <Banner kind="info">
              &quot;Net başarı oranı&quot; = denemede yapılan net ÷ soru sayısı (%). Farklı sınav türlerini (LGS/TYT/AYT)
              karşılaştırılabilir kılar.
            </Banner>

            <KpiGrid>
              <Kpi label="Deneme kapsama" value={pctText(s.coverage_pct)} sub={`${s.students_with_exam}/${s.total_students} öğrenci`} />
              <Kpi label="Ort. net başarı" value={pctText(s.avg_net_pct)} sub={deltaTxt} tone={toneFromColor(s.net_pct_color).text} />
              <Kpi label="Toplam deneme" value={String(s.total_exams)} sub={`son 30g: ${s.recent_exams}`} />
              <Kpi label="Deneme girmeyen" value={String(s.no_exam_count)} tone={s.no_exam_count > 0 ? "text-amber-600" : "text-slate-900"} />
            </KpiGrid>

            {d.trend.length > 0 ? (
              <Section title="Haftalık net başarı trendi">
                <MiniBars points={d.trend.map((p) => ({ label: weekLabel(p.week_start), value: p.avg_net_pct }))} />
              </Section>
            ) : null}

            {d.sections.length > 0 ? (
              <Section title="Sınav türü kırılımı">
                {d.sections.map((sec, i) => {
                  const tone = toneFromColor(sec.net_pct_color);
                  return (
                    <View key={i} className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
                      <View className="flex-1">
                        <Text className="text-sm font-medium text-slate-800">{sec.section_label ?? sec.section}</Text>
                        <Text className="text-[11px] text-slate-400">{sec.exam_count} deneme · {sec.student_count} öğrenci · ort. net {sec.avg_net == null ? "—" : Math.round(sec.avg_net)}</Text>
                      </View>
                      <Text className={cn("text-sm font-bold", tone.text)}>{pctText(sec.avg_net_pct)}</Text>
                    </View>
                  );
                })}
              </Section>
            ) : null}

            <Section title="Koç kırılımı">
              {d.teachers.length === 0 ? <Empty text="Koç verisi yok." /> : d.teachers.map((t) => {
                const tone = toneFromColor(t.net_pct_color);
                return (
                  <View key={t.teacher_id} className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <View className="flex-1">
                      <Text className="text-sm font-medium text-slate-800" numberOfLines={1}>{t.teacher_name}</Text>
                      <Text className="text-[11px] text-slate-400">{t.student_count} öğrenci · {t.exam_count} deneme</Text>
                    </View>
                    <Text className={cn("text-sm font-bold", tone.text)}>{pctText(t.avg_net_pct)}</Text>
                  </View>
                );
              })}
            </Section>

            {d.improving.length > 0 ? (
              <Section title="En çok gelişen"><View className="gap-2">{d.improving.map((m, i) => <MoverRow key={i} m={m} up />)}</View></Section>
            ) : null}
            {d.declining.length > 0 ? (
              <Section title="Gerileyen"><View className="gap-2">{d.declining.map((m, i) => <MoverRow key={i} m={m} up={false} />)}</View></Section>
            ) : null}

            {d.no_exam_program.length > 0 ? (
              <Banner kind="warn">
                Deneme girmeyen: {d.no_exam_program.map((e) => `${e.teacher_name} (${e.no_exam_count})`).join(", ")}
              </Banner>
            ) : null}
          </>
        );
      }}
    </InstitutionScreen>
  );
}
