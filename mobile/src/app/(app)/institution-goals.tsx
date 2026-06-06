import { useQuery } from "@tanstack/react-query";

import { Banner, InstitutionScreen, Kpi, KpiGrid, pctText } from "@/components/institution/ui";
import { getInstitutionGoals, institutionKeys, type InstitutionGoalsResponse } from "@/lib/institution";

export default function InstitutionGoalsScreen() {
  const q = useQuery({ queryKey: institutionKeys.goals, queryFn: getInstitutionGoals });
  return (
    <InstitutionScreen<InstitutionGoalsResponse> title="Hedef Analizi" query={q}>
      {(d) => (
        <>
          <KpiGrid>
            <Kpi label="Hedefi olan öğrenci" value={String(d.students_with_goals)} sub={d.students_without_goals > 0 ? `${d.students_without_goals} hedefsiz` : "hepsinde var"} />
            <Kpi label="Toplam hedef" value={String(d.total_goals)} sub={`${d.active_goals} aktif · ${d.achieved_goals} başarıldı`} />
            <Kpi label="Ortalama ilerleme" value={pctText(d.avg_overall_pct)} tone="text-emerald-700" />
          </KpiGrid>
          {d.students_without_goals > 0 ? (
            <Banner kind="warn">
              {d.students_without_goals} öğrencinin tanımlı hedefi yok. Koçların öğrencilerine somut hedef belirlemesi
              motivasyonu ve takibi güçlendirir.
            </Banner>
          ) : null}
          <Banner kind="info">
            Gizlilik gereği öğrenci bazlı hedef detayı görünmez; yalnızca kurum geneli özet ve hedefsiz öğrenci uyarısı yer alır.
          </Banner>
        </>
      )}
    </InstitutionScreen>
  );
}
