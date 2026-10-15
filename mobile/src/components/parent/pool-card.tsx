import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import { Pressable, Text, View } from "react-native";

import { PeriodDetailSheet } from "@/components/pool/period-detail-sheet";
import { getParentPoolPeriod, getParentStudentPool, poolKeys, poolPeriodKeys, type ParentPoolResponse } from "@/lib/pool";

/**
 * Veli — haftalık görev havuzu + bugünün kabı (K52, SALT OKUMA, uyarı yok).
 * Yalnız çocuk havuz modundaysa render olur; gün gün programdaki çocukta hiç görünmez.
 */
function fmt(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export function ParentPoolCard({ studentId }: { studentId: number }) {
  const q = useQuery({ queryKey: poolKeys.parent(studentId), queryFn: () => getParentStudentPool(studentId) });
  const d = q.data;
  if (!d || d.mode !== "havuz") return null;
  if (!d.period_id || !d.summary) {
    return (
      <View className="rounded-2xl border border-slate-200 bg-white p-4">
        <View className="flex-row items-center gap-1.5">
          <Ionicons name="layers-outline" size={15} color="#155e75" />
          <Text className="text-[11px] font-bold uppercase tracking-wide text-cyan-800">Haftalık görev havuzu</Text>
        </View>
        <Text className="mt-1 text-sm text-slate-600">
          {d.on_break ? `Ara (tatil) — ${fmt(d.on_break.since)} tarihinden beri; yeni dönem açılınca havuz burada görünür.` : "Rehber yeni dönemin havuzunu seansta yazınca burada görünür."}
        </Text>
        <PreviousPeriods studentId={studentId} previous={d.previous} />
      </View>
    );
  }
  const s = d.summary;
  const groups = new Map<string, typeof d.items>();
  for (const it of d.items) {
    const g = groups.get(it.subject_name) ?? [];
    g.push(it);
    groups.set(it.subject_name, g);
  }
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4 gap-3">
      <View className="flex-row flex-wrap items-center justify-between gap-2">
        <View className="flex-row items-center gap-1.5">
          <Ionicons name="layers-outline" size={15} color="#155e75" />
          <Text className="text-[11px] font-bold uppercase tracking-wide text-cyan-800">Haftalık görev havuzu</Text>
        </View>
        <Text className="text-xs text-slate-500">
          dönem {fmt(d.opened_on)} → {d.expected_next_on ? `beklenen seans ${fmt(d.expected_next_on)}` : "seans günü belirsiz"}
        </Text>
      </View>
      <View className="rounded-xl bg-brand-700 p-4">
        <View className="flex-row items-end justify-between">
          <Text className="text-2xl font-extrabold text-white">
            {s.done_units}<Text className="text-base font-semibold text-brand-100">/{s.total_units} birim</Text>
          </Text>
          <Text className="text-xl font-bold text-white">%{s.pct}</Text>
        </View>
        <View className="mt-2 h-2 overflow-hidden rounded-full bg-white/25">
          <View className="h-full rounded-full bg-white" style={{ width: `${Math.min(100, s.pct)}%` }} />
        </View>
        <Text className="mt-1 text-xs text-brand-100">
          {s.items_done}/{s.items_total} kalem · seansa {s.days_left} gün · birim = test sayısı (video/deneme 1)
        </Text>
      </View>
      <Text className="text-xs text-slate-500">
        Rehber seansta haftanın havuzunu yazar; çocuğunuz her gün havuzdan kabını kendisi kurar. Bu görünüm bilgi amaçlıdır; uyarı üretmez.
      </Text>
      <View>
        <Text className="text-sm font-semibold text-slate-800">Bugünün kabı</Text>
        {d.cup.length === 0 ? (
          <Text className="text-sm text-slate-500">Bugün henüz havuzdan kalem alınmadı.</Text>
        ) : (
          d.cup.map((t, i) => (
            <View key={i} className="mt-1 flex-row items-center gap-2">
              <View className={`size-2 rounded-full ${t.status === "completed" ? "bg-emerald-600" : "bg-slate-400"}`} />
              <Text className={`flex-1 text-sm ${t.status === "completed" ? "text-emerald-800" : "text-slate-800"}`}>{t.title}</Text>
            </View>
          ))
        )}
      </View>
      <View className="gap-2">
        <Text className="text-sm font-semibold text-slate-800">Havuz</Text>
        {[...groups.entries()].map(([name, list]) => (
          <View key={name}>
            <Text className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{name}</Text>
            {list.map((it) => (
              <View key={it.id} className="flex-row flex-wrap items-center gap-2">
                <Text className={`text-sm ${it.remaining === 0 ? "text-slate-400 line-through" : "text-slate-800"} ${it.teacher_homework ? "italic" : ""}`}>{it.title}</Text>
                <Text className="text-xs text-slate-500">{it.done}/{it.quantity} {it.unit}</Text>
                {it.in_cup_today ? (
                  <View className="rounded-full bg-brand-700 px-2 py-0.5"><Text className="text-[10px] font-semibold text-white">bugün kapta</Text></View>
                ) : null}
              </View>
            ))}
          </View>
        ))}
      </View>
      <PreviousPeriods studentId={studentId} previous={d.previous} />
    </View>
  );
}

/** K52/K60: önceki dönemler — dokununca kalem kalem + gün gün (salt okuma, uyarı yok). */
function PreviousPeriods({ studentId, previous }: { studentId: number; previous: ParentPoolResponse["previous"] }) {
  const [openId, setOpenId] = React.useState<number | null>(null);
  if (previous.length === 0) return null;
  return (
    <View className="mt-2">
      <Text className="text-xs text-slate-500">Önceki dönemler (dokun → ayrıntı)</Text>
      <View className="mt-1 flex-row flex-wrap gap-1.5">
        {previous.map((p) => (
          <Pressable key={p.id} onPress={() => setOpenId(p.id)} className="rounded-full border border-slate-300 bg-white px-3 py-1 active:bg-slate-100">
            <Text className="text-xs font-medium text-slate-800">{fmt(p.opened_on)} %{p.pct}</Text>
          </Pressable>
        ))}
      </View>
      <PeriodDetailSheet visible={openId != null} onClose={() => setOpenId(null)}
                         queryKey={poolPeriodKeys.parent(studentId, openId ?? 0)} queryFn={() => getParentPoolPeriod(studentId, openId!)} />
    </View>
  );
}
