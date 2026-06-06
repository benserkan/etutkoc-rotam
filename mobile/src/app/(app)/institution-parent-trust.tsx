import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { Banner, InstitutionScreen, Kpi, KpiGrid, Section, pctText } from "@/components/institution/ui";
import { getInstitutionParentTrust, institutionKeys, type ParentTrustResponse } from "@/lib/institution";
import { cn } from "@/lib/utils";

function successTone(pct: number | null): string {
  if (pct == null) return "text-slate-900";
  if (pct >= 95) return "text-emerald-700";
  if (pct >= 80) return "text-amber-700";
  return "text-rose-700";
}

export default function InstitutionParentTrustScreen() {
  const q = useQuery({ queryKey: institutionKeys.parentTrust, queryFn: () => getInstitutionParentTrust(30) });
  return (
    <InstitutionScreen<ParentTrustResponse> title="Veli Güveni" query={q}>
      {(d) => {
        const s = d.summary;
        return (
          <>
            <KpiGrid>
              <Kpi label="Veli kapsaması" value={pctText(s.coverage_pct)} sub={`${s.covered_students}/${s.total_students} öğrenci`} />
              <Kpi label="Aktif veli" value={String(s.active_parents)} sub={`${s.parent_count} kayıtlı`} />
              <Kpi label="Bekleyen davet" value={String(s.pending_invites)} tone={s.pending_invites > 0 ? "text-amber-600" : "text-slate-900"} />
              <Kpi label="Bildirim başarısı" value={pctText(s.notif_success_pct)} sub={`son ${s.days} gün`} tone={successTone(s.notif_success_pct)} />
            </KpiGrid>

            <Section title="Kanal teslim kırılımı">
              {d.channels.length === 0 ? (
                <Text className="px-1 text-sm text-slate-400">Bu dönem bildirim yok.</Text>
              ) : (
                d.channels.map((c) => (
                  <View key={c.channel} className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <View className="flex-1">
                      <Text className="text-sm font-medium text-slate-800">{c.channel_label}</Text>
                      <Text className="text-[11px] text-slate-400">{c.sent} gönderildi · {c.failed} başarısız · {c.suppressed} engellendi</Text>
                    </View>
                    <Text className={cn("text-sm font-bold", successTone(c.success_pct))}>{pctText(c.success_pct)}</Text>
                  </View>
                ))
              )}
            </Section>

            {(s.coverage_pct ?? 100) < 60 ? (
              <Banner kind="warn">
                Veli kapsaması düşük (%{Math.round(s.coverage_pct ?? 0)}). Daha fazla veli davet edilerek bilgilendirme ve
                güven artırılabilir.
              </Banner>
            ) : null}
          </>
        );
      }}
    </InstitutionScreen>
  );
}
