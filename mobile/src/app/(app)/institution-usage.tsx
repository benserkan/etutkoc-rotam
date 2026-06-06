import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { Banner, InstitutionScreen, ProgressBar, Section } from "@/components/institution/ui";
import { getInstitutionUsage, institutionKeys, type UsageResponse } from "@/lib/institution";
import { cn } from "@/lib/utils";

function dt(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function InstitutionUsageScreen() {
  const q = useQuery({ queryKey: institutionKeys.usage, queryFn: () => getInstitutionUsage(30) });
  return (
    <InstitutionScreen<UsageResponse> title="Kredi Kullanımı" query={q}>
      {(d) => {
        const a = d.account;
        const pct = a.usage_pct ?? 0;
        const tone = a.hard_block_enabled || pct >= 100 ? "bg-rose-500" : pct >= d.warn_threshold_pct ? "bg-amber-400" : "bg-emerald-500";
        return (
          <>
            {a.hard_block_enabled ? (
              <Banner kind="danger">Yapay zekâ özellikleri ekip tarafından geçici olarak durduruldu.</Banner>
            ) : pct >= 100 ? (
              <Banner kind="danger">Bu dönem kredisi doldu. Ek kredi için destekle iletişime geçin.</Banner>
            ) : pct >= d.warn_threshold_pct ? (
              <Banner kind="warn">Kredinin %{Math.round(pct)}&apos;i kullanıldı.</Banner>
            ) : null}

            <View className="rounded-2xl border border-slate-200 bg-white p-4">
              <Text className="text-xs font-medium text-slate-400">{a.period_year_month} dönemi</Text>
              <View className="mt-1 flex-row items-end gap-2">
                <Text className="text-2xl font-extrabold text-slate-900">{a.used_credits}</Text>
                <Text className="mb-1 text-sm text-slate-400">/ {a.total_allocated} kredi</Text>
              </View>
              <View className="mt-2"><ProgressBar pct={pct} tone={tone} /></View>
              <Text className="mt-1.5 text-xs text-slate-500">
                Kalan {a.remaining_credits} · {a.allocated_credits} plan{a.bonus_credits > 0 ? ` + ${a.bonus_credits} bonus` : ""} · {a.total_event_count} işlem
              </Text>
            </View>

            {d.breakdown.length > 0 ? (
              <Section title="Tür kırılımı">
                {d.breakdown.map((b) => (
                  <View key={b.kind} className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <Text className="flex-1 text-sm text-slate-800">{b.kind_label}</Text>
                    <Text className="text-sm font-semibold text-slate-900">{b.credits} kredi</Text>
                  </View>
                ))}
              </Section>
            ) : null}

            {d.events.length > 0 ? (
              <Section title="Son işlemler">
                {d.events.slice(0, 50).map((e) => (
                  <View key={e.id} className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white px-3 py-2">
                    <View className="flex-1">
                      <Text className="text-sm text-slate-800" numberOfLines={1}>{e.kind_label}</Text>
                      <Text className="text-[11px] text-slate-400">{dt(e.occurred_at)}{e.actor_name ? ` · ${e.actor_name}` : ""}</Text>
                    </View>
                    <Text className={cn("text-sm font-bold", e.credits >= 0 ? "text-rose-600" : "text-emerald-600")}>{e.credits >= 0 ? `-${e.credits}` : `+${-e.credits}`}</Text>
                  </View>
                ))}
              </Section>
            ) : null}
          </>
        );
      }}
    </InstitutionScreen>
  );
}
