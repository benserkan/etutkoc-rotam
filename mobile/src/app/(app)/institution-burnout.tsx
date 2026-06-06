import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, Pressable, Text, View } from "react-native";

import { NotifyCoachSheet, type NotifyCoachTarget } from "@/components/institution/notify-coach-sheet";
import { Banner, Empty, InstitutionScreen } from "@/components/institution/ui";
import { ApiError } from "@/lib/api";
import {
  buildInterventionMap,
  getInstitutionBurnout,
  getInstitutionCoachInterventions,
  institutionKeys,
  notifyCoach,
  type BurnoutResponse,
  type BurnoutRowItem,
  type CoachInterventionItem,
} from "@/lib/institution";
import { cn } from "@/lib/utils";

function InterventionBadge({ it }: { it: CoachInterventionItem }) {
  const d = new Date(it.created_at);
  const dt = `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
  return (
    <View className="mt-1.5 flex-row items-center gap-1 self-start rounded-md bg-emerald-50 px-1.5 py-0.5">
      <Text className="text-[10px] font-semibold text-emerald-700">✓ {dt} koça iletildi · {it.status_label}</Text>
    </View>
  );
}

function levelTone(level: string): { text: string; row: string } {
  switch (level) {
    case "critical":
      return { text: "text-rose-700", row: "border-l-rose-500" };
    case "warn":
      return { text: "text-amber-700", row: "border-l-amber-400" };
    case "watch":
      return { text: "text-sky-700", row: "border-l-sky-400" };
    default:
      return { text: "text-emerald-700", row: "border-l-emerald-500" };
  }
}

function Row({ r, intervention, onNotify }: { r: BurnoutRowItem; intervention?: CoachInterventionItem | null; onNotify: () => void }) {
  const tone = levelTone(r.risk_level);
  return (
    <View className={cn("rounded-xl border border-l-4 border-slate-200 bg-white p-3", tone.row)}>
      <View className="flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={1}>{r.full_name}</Text>
        <Text className={cn("text-base font-extrabold", tone.text)}>{r.risk_score}</Text>
      </View>
      {intervention ? <InterventionBadge it={intervention} /> : null}
      <Text className="mt-0.5 text-xs text-slate-500" numberOfLines={1}>
        {r.teacher_name ?? "Koç yok"} · {r.display_grade_label ?? (r.grade_level != null ? `${r.grade_level}. sınıf` : "Mezun")} · {r.signal_count} sinyal
      </Text>
      {r.signals.length > 0 ? (
        <View className="mt-1.5 gap-1">
          {r.signals.slice(0, 3).map((s, i) => (
            <Text key={i} className="text-[11px] text-slate-500">• {s.label}{s.detail ? ` — ${s.detail}` : ""}</Text>
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

export default function InstitutionBurnoutScreen() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: institutionKeys.burnout, queryFn: getInstitutionBurnout });
  const intQ = useQuery({ queryKey: ["institution", "interventions"], queryFn: getInstitutionCoachInterventions, staleTime: 30_000 });
  const intMap = React.useMemo(() => buildInterventionMap(intQ.data?.items ?? []), [intQ.data]);
  const [target, setTarget] = React.useState<NotifyCoachTarget | null>(null);

  const mut = useMutation({
    mutationFn: (v: { note: string }) =>
      notifyCoach({ teacher_id: target!.teacher_id, student_name: target!.student_name, note: v.note || undefined, context: "burnout" }),
    onSuccess: () => {
      setTarget(null);
      qc.invalidateQueries({ queryKey: ["support"] });
      qc.invalidateQueries({ queryKey: ["institution", "interventions"] });
      Alert.alert("Gönderildi", "Müdahale talebi koçun gelen kutusuna iletildi.");
    },
    onError: (e) => Alert.alert("Gönderilemedi", e instanceof ApiError ? e.message : "İşlem başarısız"),
  });

  return (
    <InstitutionScreen<BurnoutResponse> title="Tükenmişlik Panosu" query={q}>
      {(d) => (
        <>
          <Banner kind="info">
            Yük ve düşüş sinyallerinden hesaplanır. Gizlilik gereği detay sayfası yoktur; müdahale için &quot;Koça ilet&quot;.
          </Banner>
          {d.items.length === 0 ? (
            <Empty text="Tükenmişlik sinyali olan öğrenci yok." />
          ) : (
            <View className="gap-2">
              {d.items.map((r) => (
                <Row
                  key={r.student_id}
                  r={r}
                  intervention={intMap.get(r.full_name.trim().toLocaleLowerCase("tr")) ?? null}
                  onNotify={() => setTarget({ teacher_id: r.teacher_id!, teacher_name: r.teacher_name, student_name: r.full_name, context: "burnout" })}
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
