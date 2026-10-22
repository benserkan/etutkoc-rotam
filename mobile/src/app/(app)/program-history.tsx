import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import * as React from "react";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { PeriodDetailSheet } from "@/components/pool/period-detail-sheet";
import {
  getStudentPoolPeriod, getTeacherPoolPeriod, poolPeriodKeys, teacherPoolKeys,
} from "@/lib/pool";
import {
  getStudentProgramHistory, getTeacherProgramHistory, programHistoryKeys,
  type HistoryEntry, type HistoryWeek,
} from "@/lib/program-history";
import { getStudentWeek } from "@/lib/student";
import { getTeacherStudentWeek } from "@/lib/teacher";

/**
 * Program geçmişi (2026-10-22) — web "Program geçmişi" sekmesinin mobil karşılığı.
 * `?student=ID` ile koç, parametresiz öğrenci kendi geçmişini görür. Gün gün haftalar SALT OKUNUR
 * açılır (gün gün görevler + sonuçlar), havuz dönemleri mevcut dönem sayfasında.
 */
const MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const MS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];

function parse(d: string) {
  const [y, m, day] = d.split("-").map(Number);
  return new Date(y, m - 1, day);
}
function short(d: string) {
  const x = parse(d);
  return `${x.getDate()} ${MS[x.getMonth()]}`;
}
function range(a: string, b: string | null) {
  if (!b) return `${short(a)} → sürüyor`;
  const x = parse(a), y = parse(b);
  return x.getMonth() === y.getMonth() ? `${x.getDate()}–${y.getDate()} ${MS[y.getMonth()]}` : `${short(a)} – ${short(b)}`;
}
function tone(p: number) {
  return p >= 70 ? { text: "text-emerald-700", bar: "bg-emerald-500" }
    : p >= 40 ? { text: "text-amber-700", bar: "bg-amber-500" }
    : { text: "text-rose-700", bar: "bg-rose-500" };
}
function entryDate(e: HistoryEntry) {
  return e.week?.start ?? e.period?.opened_on ?? e.switch?.date ?? "";
}

export default function ProgramHistoryRoute() {
  const params = useLocalSearchParams<{ student?: string }>();
  const studentId = params.student ? Number(params.student) : null;
  const q = useQuery({
    queryKey: studentId ? programHistoryKeys.teacher(studentId) : programHistoryKeys.student(),
    queryFn: () => (studentId ? getTeacherProgramHistory(studentId) : getStudentProgramHistory()),
  });
  const [openWeek, setOpenWeek] = React.useState<string | null>(null);
  const [periodId, setPeriodId] = React.useState<number | null>(null);
  const [filter, setFilter] = React.useState<"all" | "gun_gun" | "havuz">("all");

  const entries = (q.data?.entries ?? []).filter((e) =>
    filter === "all" ? true : filter === "gun_gun" ? e.kind !== "period" : e.kind !== "week");
  const groups: { label: string; rows: HistoryEntry[] }[] = [];
  for (const e of entries) {
    const d = parse(entryDate(e));
    const label = `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.rows.push(e);
    else groups.push({ label, rows: [e] });
  }

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-200" accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="flex-1 text-base font-semibold text-slate-800">{studentId ? "Program geçmişi" : "Program geçmişim"}</Text>
      </View>
      {q.isLoading ? (
        <View className="flex-1 items-center justify-center"><ActivityIndicator size="large" color="#0e7490" /></View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"><Text className="font-semibold text-white">Tekrar dene</Text></Pressable>
        </View>
      ) : (
        <ScrollView className="flex-1" contentContainerClassName="gap-3 px-4 pb-10"
                    refreshControl={<RefreshControl refreshing={q.isRefetching} onRefresh={() => q.refetch()} />}>
          <View className="flex-row flex-wrap items-center gap-2">
            <View className="rounded-full bg-cyan-700 px-2.5 py-0.5"><Text className="text-xs font-semibold text-white">Şu an: {q.data.program_mode_label}</Text></View>
            <Text className="text-xs text-slate-500">{q.data.weeks_count} gün gün hafta · {q.data.periods_count} havuz dönemi</Text>
          </View>
          <View className="flex-row rounded-xl bg-slate-200 p-0.5">
            {([["all", "Tümü"], ["gun_gun", "Gün gün"], ["havuz", "Havuz"]] as const).map(([k, l]) => (
              <Pressable key={k} onPress={() => setFilter(k)} className={`flex-1 items-center rounded-lg py-1.5 ${filter === k ? "bg-cyan-700" : ""}`}>
                <Text className={`text-xs font-semibold ${filter === k ? "text-white" : "text-slate-600"}`}>{l}</Text>
              </Pressable>
            ))}
          </View>
          {groups.length === 0 ? (
            <Text className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">Henüz geçmiş program yok.</Text>
          ) : groups.map((g) => (
            <View key={g.label} className="gap-2">
              <Text className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{g.label}</Text>
              {g.rows.map((e, i) => (
                <Row key={`${e.kind}-${entryDate(e)}-${i}`} e={e} studentId={studentId}
                     open={e.week ? openWeek === `${e.week.start}_${e.week.end}` : false}
                     onToggle={() => e.week && setOpenWeek((v) => (v === `${e.week!.start}_${e.week!.end}` ? null : `${e.week!.start}_${e.week!.end}`))}
                     onOpenPeriod={() => e.period && setPeriodId(e.period.id)} />
              ))}
            </View>
          ))}
        </ScrollView>
      )}
      <PeriodDetailSheet
        visible={periodId != null}
        onClose={() => setPeriodId(null)}
        queryKey={studentId ? teacherPoolKeys.period(studentId, periodId ?? 0) : poolPeriodKeys.student(periodId ?? 0)}
        queryFn={() => (studentId ? getTeacherPoolPeriod(studentId, periodId!) : getStudentPoolPeriod(periodId!))}
      />
    </SafeAreaView>
  );
}

function Row({ e, studentId, open, onToggle, onOpenPeriod }: {
  e: HistoryEntry; studentId: number | null; open: boolean; onToggle: () => void; onOpenPeriod: () => void;
}) {
  if (e.kind === "switch" && e.switch) {
    return (
      <View className="rounded-xl border border-violet-300 bg-violet-50 px-3 py-2">
        <View className="flex-row items-center gap-2">
          <Ionicons name="swap-horizontal" size={16} color="#6d28d9" />
          <Text className="flex-1 text-sm font-semibold text-violet-900">{short(e.switch.date)} · {e.switch.from_label} → {e.switch.to_label}</Text>
        </View>
        {e.switch.note ? <Text className="mt-0.5 text-xs text-violet-800">{e.switch.note}</Text> : null}
      </View>
    );
  }
  if (e.kind === "period" && e.period) {
    const p = e.period;
    const t = tone(p.pct);
    const empty = p.items_total === 0;
    return (
      <Pressable onPress={onOpenPeriod} className="rounded-xl border border-cyan-300 bg-white px-3 py-2.5 active:bg-cyan-50">
        <View className="flex-row items-center gap-2">
          <Ionicons name="layers-outline" size={18} color="#0e7490" />
          <View className="flex-1">
            <Text className="text-sm font-semibold text-slate-800">{range(p.opened_on, p.closed_on ?? (e.period_current ? null : p.expected_next_on))}</Text>
            <Text className="text-[11px] text-slate-500">Havuz dönemi{e.period_current && p.expected_next_on ? ` · seans ${short(p.expected_next_on)}` : ""}</Text>
          </View>
          <View className={`rounded-full px-2 py-0.5 ${e.period_current ? "bg-cyan-700" : "bg-slate-600"}`}>
            <Text className="text-[10px] font-semibold text-white">{e.period_current ? "Açık dönem" : p.status_label}</Text>
          </View>
        </View>
        <View className="mt-2 flex-row items-center gap-2">
          <Text className="text-xs text-slate-500">{empty ? "Havuz henüz boş" : `Kalem ${p.items_done}/${p.items_total} · Birim ${p.done_units}/${p.total_units}`}</Text>
          <View className="ml-auto h-1.5 w-16 overflow-hidden rounded-full bg-slate-200"><View className={`h-full ${t.bar}`} style={{ width: `${Math.min(100, p.pct)}%` }} /></View>
          <Text className={`w-10 text-right text-sm font-bold ${empty ? "text-slate-400" : t.text}`}>{empty ? "—" : `%${p.pct}`}</Text>
        </View>
      </Pressable>
    );
  }
  const w = e.week!;
  const t = tone(w.pct);
  return (
    <View className={`overflow-hidden rounded-xl border bg-white ${open ? "border-cyan-600" : "border-slate-200"}`}>
      <Pressable onPress={onToggle} className="px-3 py-2.5 active:bg-slate-50" accessibilityState={{ expanded: open }}>
        <View className="flex-row items-center gap-2">
          <Ionicons name={open ? "chevron-down" : "chevron-forward"} size={16} color="#64748b" />
          <View className="flex-1">
            <Text className="text-sm font-semibold text-slate-800">{range(w.start, w.end)}</Text>
            <Text className="text-[11px] text-slate-500">{w.week_kind === "takvim" ? "Programsız görev günleri" : "Gün gün hafta"}</Text>
          </View>
          {w.cut ? <View className="rounded-full bg-violet-700 px-2 py-0.5"><Text className="text-[10px] font-semibold text-white">Mod geçişiyle kısaldı</Text></View> : null}
          {w.current ? <View className="rounded-full bg-slate-700 px-2 py-0.5"><Text className="text-[10px] font-semibold text-white">Bu hafta</Text></View> : null}
        </View>
        <View className="mt-2 flex-row items-center gap-2">
          <Text className="text-xs text-slate-500">
            Görev {w.gorev_done}/{w.gorev_total}{w.test_planned ? ` · Test ${w.test_completed}/${w.test_planned}` : ""}{w.deneme_units ? ` · Deneme ${w.deneme_done}/${w.deneme_units}` : ""}
          </Text>
          <View className="ml-auto h-1.5 w-16 overflow-hidden rounded-full bg-slate-200"><View className={`h-full ${t.bar}`} style={{ width: `${Math.min(100, w.pct)}%` }} /></View>
          <Text className={`w-10 text-right text-sm font-bold ${w.gorev_total ? t.text : "text-slate-400"}`}>{w.gorev_total ? `%${w.pct}` : "—"}</Text>
        </View>
      </Pressable>
      {open ? <WeekDays week={w} studentId={studentId} /> : null}
    </View>
  );
}

type DayRow = { date: string; dow: string; tasks: { id: number; title: string; status: string; lines: string[] }[] };

function WeekDays({ week, studentId }: { week: HistoryWeek; studentId: number | null }) {
  const q = useQuery({
    queryKey: ["program-history-week", studentId ?? "me", week.start, week.end],
    queryFn: async (): Promise<DayRow[]> => {
      if (studentId) {
        const r = await getTeacherStudentWeek(studentId, week.start, week.end);
        return r.days.filter((d) => d.date >= week.start && d.date <= week.end).map((d) => ({
          date: d.date, dow: d.dow_label,
          tasks: d.tasks.filter((t) => !t.is_draft).map((t) => ({
            id: t.id, title: t.title, status: t.status,
            lines: t.items.map((it) => `${[it.book_name, it.section_label ?? it.topic_name].filter(Boolean).join(" — ")}: ${it.completed_count}/${it.planned_count}${it.correct_count != null ? ` · ${it.correct_count}D ${it.wrong_count ?? 0}Y ${it.blank_count ?? 0}B` : ""}`),
          })),
        }));
      }
      const r = await getStudentWeek(week.start);
      return r.days.filter((d) => d.date >= week.start && d.date <= week.end).map((d) => ({
        date: d.date, dow: d.dow_label,
        tasks: d.tasks.map((t) => ({
          id: t.id, title: t.title, status: t.status,
          lines: t.items.map((it) => `${[it.book_name, it.section_label ?? it.topic_name].filter(Boolean).join(" — ")}: ${it.completed}/${it.planned}${it.correct != null ? ` · ${it.correct}D ${it.wrong ?? 0}Y ${it.blank ?? 0}B` : ""}`),
        })),
      }));
    },
  });
  if (q.isLoading) return <View className="border-t border-slate-100 p-4"><ActivityIndicator color="#0e7490" /></View>;
  if (!q.data) return <Text className="border-t border-slate-100 p-3 text-sm text-rose-700">Hafta yüklenemedi.</Text>;
  return (
    <View className="border-t border-slate-100 px-3 pb-3 pt-1">
      <Text className="py-1 text-[11px] text-slate-500">Salt okunur — düzenleme yalnız güncel programda.</Text>
      {q.data.map((d) => (
        <View key={d.date} className="mt-2">
          <Text className="text-xs font-semibold text-slate-700">{d.dow} · {short(d.date)} <Text className="font-normal text-slate-400">({d.tasks.length} görev)</Text></Text>
          {d.tasks.length === 0 ? <Text className="mt-0.5 text-xs text-slate-400">Görev yok</Text> : d.tasks.map((t) => {
            const done = t.status === "completed";
            const partial = t.status === "partial";
            return (
              <View key={t.id} className="mt-1 flex-row gap-2">
                <Ionicons name={done ? "checkmark-circle" : partial ? "ellipse-outline" : "close-circle-outline"} size={16}
                          color={done ? "#047857" : partial ? "#b45309" : "#94a3b8"} />
                <View className="flex-1">
                  <Text className="text-xs text-slate-800">{t.title}</Text>
                  {t.lines.map((l, i) => <Text key={i} className="text-[11px] text-slate-500">{l}</Text>)}
                </View>
              </View>
            );
          })}
        </View>
      ))}
    </View>
  );
}
