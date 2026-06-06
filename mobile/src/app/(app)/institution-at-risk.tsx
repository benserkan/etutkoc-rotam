import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Pressable, Text, View } from "react-native";

import { NotifyCoachSheet, type NotifyCoachTarget } from "@/components/institution/notify-coach-sheet";
import { Banner, Empty, InstitutionScreen, Kpi, KpiGrid } from "@/components/institution/ui";
import { ApiError } from "@/lib/api";
import {
  getInstitutionAtRisk,
  institutionKeys,
  notifyCoach,
  type AtRiskResponse,
  type AtRiskRowItem,
} from "@/lib/institution";
import { cn } from "@/lib/utils";

function levelTone(level: string): { row: string; badge: string; badgeText: string } {
  switch (level) {
    case "critical":
      return { row: "border-l-rose-500 bg-rose-50/40", badge: "bg-rose-100", badgeText: "text-rose-700" };
    case "high":
      return { row: "border-l-orange-500 bg-orange-50/40", badge: "bg-orange-100", badgeText: "text-orange-700" };
    default:
      return { row: "border-l-amber-400 bg-amber-50/30", badge: "bg-amber-100", badgeText: "text-amber-700" };
  }
}

function Row({ r, onNotify }: { r: AtRiskRowItem; onNotify: () => void }) {
  const tone = levelTone(r.level);
  return (
    <View className={cn("rounded-xl border border-l-4 border-slate-200 p-3", tone.row)}>
      <View className="flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={1}>{r.full_name}</Text>
        <View className={cn("rounded-full px-2 py-0.5", tone.badge)}>
          <Text className={cn("text-[11px] font-semibold", tone.badgeText)}>{r.level_label} · {r.score}</Text>
        </View>
      </View>
      <Text className="mt-0.5 text-xs text-slate-500" numberOfLines={1}>
        {r.teacher_name ?? "Koç yok"} · {r.display_grade_label ?? (r.grade_level != null ? `${r.grade_level}. sınıf` : "Mezun")}
        {r.is_muted ? " · sessiz" : ""}{r.is_paused ? " · duraklatıldı" : ""}
      </Text>
      {r.indicators.length > 0 ? (
        <View className="mt-1.5 flex-row flex-wrap gap-1">
          {r.indicators.slice(0, 4).map((ind) => (
            <View key={ind.code} className="rounded-full bg-white px-2 py-0.5">
              <Text className="text-[10px] text-slate-500">{ind.title}</Text>
            </View>
          ))}
        </View>
      ) : null}
      {r.teacher_id != null ? (
        <Pressable onPress={onNotify} className="mt-2 flex-row items-center justify-center gap-1 rounded-lg border border-brand-200 bg-white py-2 active:bg-brand-50">
          <Text className="text-sm font-semibold text-brand-700">Koça ilet</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export default function InstitutionAtRiskScreen() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: institutionKeys.atRisk, queryFn: getInstitutionAtRisk });
  const [target, setTarget] = React.useState<NotifyCoachTarget | null>(null);

  const mut = useMutation({
    mutationFn: (v: { note: string }) =>
      notifyCoach({ teacher_id: target!.teacher_id, student_name: target!.student_name, note: v.note || undefined, context: "at_risk" }),
    onSuccess: () => {
      setTarget(null);
      qc.invalidateQueries({ queryKey: ["support"] });
      Alert.alert("Gönderildi", "Müdahale talebi koçun gelen kutusuna iletildi.");
    },
    onError: (e) => Alert.alert("Gönderilemedi", e instanceof ApiError ? e.message : "İşlem başarısız"),
  });

  return (
    <InstitutionScreen<AtRiskResponse> title="Risk Paneli" query={q}>
      {(d) => (
        <>
          <Banner kind="info">
            Gizlilik gereği öğrenci programı/notları görünmez. Müdahale için &quot;Koça ilet&quot; ile sorumlu koça talep aç.
          </Banner>
          <KpiGrid>
            <Kpi label="Kritik" value={String(d.counts.critical)} tone="text-rose-600" />
            <Kpi label="Yüksek" value={String(d.counts.high)} tone="text-orange-600" />
            <Kpi label="Orta" value={String(d.counts.medium)} tone="text-amber-600" />
            <Kpi label="Sağlıklı" value={String(d.healthy_count)} sub={`${d.total_students} öğrenci`} tone="text-emerald-700" />
          </KpiGrid>
          {d.at_risk.length === 0 ? (
            <Empty text="Risk altında öğrenci yok. Tüm öğrenciler yolunda." />
          ) : (
            <View className="gap-2">
              {d.at_risk.map((r) => (
                <Row
                  key={r.student_id}
                  r={r}
                  onNotify={() => setTarget({ teacher_id: r.teacher_id!, teacher_name: r.teacher_name, student_name: r.full_name, context: "at_risk" })}
                />
              ))}
            </View>
          )}
          <NotifyCoachSheet target={target} busy={mut.isPending} onClose={() => setTarget(null)} onSubmit={(note) => mut.mutate({ note })} />
        </>
      )}
    </InstitutionScreen>
  );
}
