import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import * as React from "react";
import { Pressable, Text, View } from "react-native";

import { ackPoolWarning, getPoolDaily, poolKeys, unackPoolWarning, type PoolDailyRow } from "@/lib/pool";

/**
 * Koç — günlük görüşme listesi, havuz öğrencileri (K48/K50). Bugünkü seans üstte;
 * öğrenci başına 1 ana sinyal + ek sinyal sayısı; Gördüm (3 gün) / Geri al.
 * Havuz öğrencisi yoksa hiç render olmaz. Seans ekranı/düzenleme web'de.
 */
const DOT: Record<string, string> = { red: "bg-rose-600", amber: "bg-amber-500", green: "bg-emerald-600" };

export function PoolDailyList() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: poolKeys.daily(), queryFn: getPoolDaily });
  const refresh = () => void qc.invalidateQueries({ queryKey: poolKeys.daily() });
  const ack = useMutation({ mutationFn: (v: { student_id: number; code: string }) => ackPoolWarning(v.student_id, v.code), onSuccess: refresh });
  const unack = useMutation({ mutationFn: (v: { student_id: number; code: string }) => unackPoolWarning(v.student_id, v.code), onSuccess: refresh });
  const d = q.data;
  if (!d || d.counts.students === 0) return null;
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4 gap-2">
      <View className="flex-row items-center gap-1.5">
        <Ionicons name="today-outline" size={15} color="#155e75" />
        <Text className="flex-1 text-[11px] font-bold uppercase tracking-wide text-cyan-800">Bugünkü görüşme listesi · havuz</Text>
      </View>
      <View className="flex-row flex-wrap gap-1.5">
        <Chip bg="bg-brand-700" text="text-white" label={`bugün seans ${d.counts.sessions_today}`} />
        <Chip bg="bg-rose-600" text="text-white" label={`acil ${d.counts.red}`} />
        <Chip bg="bg-amber-500" text="text-amber-950" label={`dikkat ${d.counts.amber}`} />
        {d.counts.snoozed > 0 ? <Chip bg="bg-slate-600" text="text-white" label={`ertelenen ${d.counts.snoozed}`} /> : null}
      </View>
      {d.rows.map((r) => (
        <Row key={r.student_id} r={r}
             onAck={() => r.primary && ack.mutate({ student_id: r.student_id, code: r.primary.code })}
             onUnack={() => r.primary && unack.mutate({ student_id: r.student_id, code: r.primary.code })} />
      ))}
    </View>
  );
}

function Chip({ bg, text, label }: { bg: string; text: string; label: string }) {
  return (
    <View className={`rounded-full px-2 py-0.5 ${bg}`}><Text className={`text-[10px] font-semibold ${text}`}>{label}</Text></View>
  );
}

function Row({ r, onAck, onUnack }: { r: PoolDailyRow; onAck: () => void; onUnack: () => void }) {
  const [open, setOpen] = React.useState(false);
  const p = r.primary;
  return (
    <View className={`rounded-xl px-2 py-2 ${r.session_today ? "bg-cyan-50" : ""}`}>
      <View className="flex-row flex-wrap items-center gap-2">
        {r.session_today ? (
          <View className="flex-row items-center gap-1 rounded-full bg-brand-700 px-2 py-0.5">
            <Ionicons name="time-outline" size={11} color="#fff" />
            <Text className="text-[10px] font-semibold text-white">{r.appointment_time ? `bugün ${r.appointment_time}` : "seans günü"}</Text>
          </View>
        ) : (
          <View className={`size-2.5 rounded-full ${DOT[r.level] ?? DOT.green}`} />
        )}
        <Pressable onPress={() => router.push({ pathname: "/teacher-student", params: { id: String(r.student_id) } })} hitSlop={6}>
          <Text className="text-sm font-semibold text-slate-900">{r.student_name}</Text>
        </Pressable>
        {r.class_group ? <Text className="text-xs text-slate-500">{r.class_group}</Text> : null}
        {r.pct != null ? <Text className="text-xs text-slate-500">havuz %{r.pct}</Text> : null}
        {r.paper_student ? <Chip bg="bg-slate-600" text="text-white" label="kağıt öğrencisi" /> : null}
      </View>
      <Text className={`mt-1 text-sm ${r.primary_snoozed ? "text-slate-400 line-through" : "text-slate-800"}`}>
        {p ? <><Text className="font-semibold">{p.title}</Text> — {p.detail}</> : r.headline}
      </Text>
      <View className="mt-1 flex-row flex-wrap items-center gap-3">
        {(r.extra.length > 0 || r.good.length > 0) ? (
          <Pressable onPress={() => setOpen((v) => !v)} hitSlop={6}>
            <Text className="text-xs font-semibold text-slate-500">
              {open ? "▴" : "▾"} ek {r.extra.length}{r.good.length ? ` · iyi ${r.good.length}` : ""}
            </Text>
          </Pressable>
        ) : null}
        {p && !r.primary_snoozed ? (
          <Pressable onPress={onAck} hitSlop={6}><Text className="text-xs font-semibold text-brand-700">Gördüm (3 gün)</Text></Pressable>
        ) : null}
        {p && r.primary_snoozed ? (
          <Pressable onPress={onUnack} hitSlop={6}><Text className="text-xs font-semibold text-brand-700">Geri al</Text></Pressable>
        ) : null}
      </View>
      {open ? (
        <View className="mt-1 gap-0.5">
          {[...r.extra, ...r.good].map((f) => (
            <Text key={f.code} className="text-xs text-slate-600">• <Text className="text-slate-800">{f.title}</Text> — {f.detail}</Text>
          ))}
        </View>
      ) : null}
    </View>
  );
}
