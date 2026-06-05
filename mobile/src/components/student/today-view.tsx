import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import type { StudentDayResponse, StudentTask } from "@/lib/student";

const TR_DAYS = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
const TR_MONTHS = [
  "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
];

function fmtLongDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  const dow = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return `${d} ${TR_MONTHS[m - 1]} ${TR_DAYS[dow]}`;
}

type GState = "done" | "partial" | "todo";
function gorevState(t: StudentTask): GState {
  const done = t.status === "completed" || (t.planned_count > 0 && t.completed_count >= t.planned_count);
  if (done) return "done";
  return t.completed_count > 0 ? "partial" : "todo";
}

const DENEME_TYPES = new Set(["brans_denemesi", "genel_deneme"]);
function taskUnit(t: StudentTask): string {
  if (t.work_block_unit) return t.work_block_unit;
  const it = t.items.find((x) => x.book_id != null) ?? t.items[0];
  if (it && it.book_id == null) return "soru";
  if (it?.book_type && DENEME_TYPES.has(it.book_type)) return "deneme";
  return "test";
}
function isActivity(t: StudentTask): boolean {
  return t.planned_count <= 0 && t.items.every((it) => (it.planned ?? 0) <= 0);
}
function taskLabel(t: StudentTask): string {
  const first = t.items.find((it) => it.book_id != null) ?? t.items[0];
  if (first?.book_id) {
    return first.book_name + (first.section_label ? ` · ${first.section_label}` : "");
  }
  const sep = t.title.indexOf(" · ");
  if (sep > 0 && sep < t.title.length - 3) return t.title.substring(sep + 3);
  return t.title || "Görev";
}
function subjectOf(t: StudentTask): string | null {
  const it = t.items.find((x) => x.subject_id != null);
  return it?.subject_name ?? null;
}

function CheckCircle({ state }: { state: GState }) {
  if (state === "done") {
    return (
      <View className="size-8 items-center justify-center rounded-full bg-emerald-500">
        <Text className="text-base font-bold text-white">✓</Text>
      </View>
    );
  }
  if (state === "partial") {
    return (
      <View className="size-8 items-center justify-center rounded-full border-2 border-amber-400">
        <View className="size-3 rounded-full bg-amber-400" />
      </View>
    );
  }
  return <View className="size-8 rounded-full border-2 border-slate-300" />;
}

export function TodayView({
  day,
  busyTaskId,
  onQuickToggle,
  onOpenTask,
  refreshing = false,
  onRefresh,
  safeTop = true,
}: {
  day: StudentDayResponse;
  busyTaskId: number | null;
  onQuickToggle: (task: StudentTask) => void;
  onOpenTask: (task: StudentTask) => void;
  refreshing?: boolean;
  onRefresh?: () => void;
  safeTop?: boolean; // false: üstte kendi başlık çubuğu olan ekran (çift inset olmasın)
}) {
  const s = day.summary;
  const pct = Math.round((s.pct ?? 0) * 100);

  return (
    <SafeAreaView edges={safeTop ? ["top"] : []} className="flex-1 bg-slate-50">
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-4 gap-4"
      refreshControl={
        onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined
      }
    >
      {/* Özet kart (gradient native'de çalışmaz → solid marka rengi) */}
      <View className="rounded-2xl bg-brand-700 p-5">
        <Text className="text-xs font-semibold uppercase tracking-wider text-brand-100">
          {day.is_today ? "Bugün" : "Gün"}
        </Text>
        <Text className="mt-0.5 text-lg font-bold text-white">{fmtLongDate(day.date)}</Text>

        <View className="mt-4 flex-row items-end justify-between">
          <Text className="text-3xl font-extrabold text-white">
            {s.gorev_done}
            <Text className="text-lg font-semibold text-brand-100">/{s.gorev_total} görev</Text>
          </Text>
          <Text className="text-2xl font-bold text-white">%{pct}</Text>
        </View>
        <View className="mt-2 h-2 overflow-hidden rounded-full bg-white/25">
          <View className="h-full rounded-full bg-white" style={{ width: `${Math.min(100, pct)}%` }} />
        </View>
        {s.test_planned > 0 ? (
          <Text className="mt-2 text-xs text-brand-100">
            {s.test_completed}/{s.test_planned} test çözüldü
          </Text>
        ) : null}
      </View>

      {/* Görevler */}
      {day.tasks.length === 0 ? (
        <View className="items-center rounded-2xl border border-dashed border-slate-300 bg-white p-8">
          <Text className="text-base font-semibold text-slate-700">Bugün görev yok</Text>
          <Text className="mt-1 text-center text-sm text-slate-500">
            Koçun program eklediğinde burada görünür.
          </Text>
        </View>
      ) : (
        <View className="gap-2.5">
          <Text className="px-1 text-xs text-slate-500">
            Yaptıysan yuvarlağa dokun. Kaç yaptığını / doğru-yanlışı girmek için karta dokun.
          </Text>
          {day.tasks.map((t) => {
            const st = gorevState(t);
            const subj = subjectOf(t);
            const busy = busyTaskId === t.id;
            const blocked = t.is_future_blocked;
            return (
              <View
                key={t.id}
                className={`flex-row items-center gap-3 rounded-2xl border bg-white p-4 ${
                  st === "done" ? "border-emerald-200" : "border-slate-200"
                } ${blocked ? "opacity-50" : ""}`}
              >
                {/* Sol: hızlı "yaptım" (sayı sormaz) */}
                <Pressable
                  onPress={() => onQuickToggle(t)}
                  disabled={busy || blocked}
                  hitSlop={10}
                  accessibilityLabel={st === "done" ? "Geri al" : "Yaptım olarak işaretle"}
                >
                  {busy ? (
                    <View className="size-8 items-center justify-center">
                      <ActivityIndicator color="#0e7490" />
                    </View>
                  ) : (
                    <CheckCircle state={st} />
                  )}
                </Pressable>
                {/* Sağ: detay (kısmi + doğru/yanlış) */}
                <Pressable
                  className="flex-1 flex-row items-center gap-2 active:opacity-60"
                  onPress={() => onOpenTask(t)}
                  disabled={blocked}
                >
                  <View className="flex-1">
                    {subj ? (
                      <Text className="text-[11px] font-bold uppercase tracking-wide text-brand-700">{subj}</Text>
                    ) : null}
                    <Text
                      className={`text-[15px] font-medium ${st === "done" ? "text-slate-400 line-through" : "text-slate-900"}`}
                      numberOfLines={2}
                    >
                      {taskLabel(t)}
                    </Text>
                    <Text className="mt-0.5 text-xs text-slate-500">
                      {isActivity(t)
                        ? (t.solved_count ?? 0) > 0
                          ? `Etkinlik · ${t.solved_count} soru`
                          : "Etkinlik"
                        : `${t.completed_count}/${t.planned_count} ${taskUnit(t)}`}
                    </Text>
                  </View>
                  {!blocked ? (
                    <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
                  ) : null}
                </Pressable>
              </View>
            );
          })}
        </View>
      )}
    </ScrollView>
    </SafeAreaView>
  );
}
