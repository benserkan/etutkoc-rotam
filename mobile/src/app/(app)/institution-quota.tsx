import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { Badge, Banner, InstitutionScreen, ProgressBar, Section } from "@/components/institution/ui";
import { getInstitutionQuota, institutionKeys, type QuotaInfoItem, type QuotaResponse } from "@/lib/institution";
import { cn } from "@/lib/utils";

function QuotaCard({ q }: { q: QuotaInfoItem }) {
  const tone = q.is_at_limit ? "bg-rose-500" : q.is_warn ? "bg-amber-400" : "bg-emerald-500";
  const limitText = q.is_unlimited ? "∞" : q.limit === 0 ? "kapalı" : String(q.limit);
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-3">
      <View className="flex-row items-center justify-between">
        <Text className="text-sm font-semibold text-slate-800">{q.label}</Text>
        {q.has_override ? <Badge label="size özel" tone="violet" /> : null}
      </View>
      <View className="mt-1 flex-row items-end gap-1">
        <Text className="text-2xl font-extrabold text-slate-900">{q.current}</Text>
        <Text className="mb-1 text-sm text-slate-400">/ {limitText}</Text>
      </View>
      {!q.is_unlimited ? <View className="mt-1.5"><ProgressBar pct={q.pct} tone={tone} /></View> : null}
      {q.override_note ? <Text className="mt-1 text-[11px] text-violet-600">{q.override_note}</Text> : null}
    </View>
  );
}

export default function InstitutionQuotaScreen() {
  const q = useQuery({ queryKey: institutionKeys.quota, queryFn: getInstitutionQuota });
  return (
    <InstitutionScreen<QuotaResponse> title="Limitler" query={q}>
      {(d) => (
        <>
          <View className="gap-2">{d.summary.map((s) => <QuotaCard key={s.key} q={s} />)}</View>

          {d.plans.length > 0 ? (
            <Section title="Plan karşılaştırması">
              <View className="rounded-xl border border-slate-200 bg-white">
                <View className="flex-row border-b border-slate-100 px-3 py-2">
                  <Text className="flex-1 text-[11px] font-semibold text-slate-400">Plan</Text>
                  <Text className="w-16 text-right text-[11px] font-semibold text-slate-400">Koç</Text>
                  <Text className="w-16 text-right text-[11px] font-semibold text-slate-400">Öğrenci</Text>
                </View>
                {d.plans.map((p) => {
                  const current = p.plan === d.plan;
                  return (
                    <View key={p.plan} className={cn("flex-row px-3 py-2", current ? "bg-emerald-50" : "")}>
                      <Text className={cn("flex-1 text-xs", current ? "font-bold text-emerald-800" : "text-slate-700")} numberOfLines={1}>{p.plan}{current ? " ✓" : ""}</Text>
                      <Text className="w-16 text-right text-xs text-slate-600">{p.teachers < 0 ? "∞" : p.teachers}</Text>
                      <Text className="w-16 text-right text-xs text-slate-600">{p.students < 0 ? "∞" : p.students}</Text>
                    </View>
                  );
                })}
              </View>
            </Section>
          ) : null}

          <Banner kind="info">Limit dolarsa yeni ekleme engellenir. Yükseltme için &quot;Hesap Ayarları&quot; ekranından plan talebi oluştur.</Banner>
        </>
      )}
    </InstitutionScreen>
  );
}
