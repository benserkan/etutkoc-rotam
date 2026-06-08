import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, RefreshControl, ScrollView, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import type { GoalCreateBody, GoalItem, GoalListResponse } from "@/lib/student";
import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";

const KIND: Record<string, string> = { weekly: "Haftalık", daily: "Günlük", custom: "Özel", topic: "Konu", exam_target: "Sınav", subject: "Ders" };
const CREATE_KINDS = [
  { v: "weekly", label: "Haftalık" },
  { v: "daily", label: "Günlük" },
  { v: "topic", label: "Konu" },
  { v: "custom", label: "Özel" },
];

function GoalCard({
  g,
  busy,
  onProgress,
  onAchieve,
}: {
  g: GoalItem;
  busy: boolean;
  onProgress: (g: GoalItem) => void;
  onAchieve: (g: GoalItem) => void;
}) {
  const achieved = g.status === "achieved";
  return (
    <View className={cn("rounded-2xl border bg-white p-4", achieved ? "border-emerald-200" : "border-slate-200")}>
      <View className="flex-row items-start justify-between gap-2">
        <Text className={cn("flex-1 text-[15px] font-semibold", achieved ? "text-slate-400 line-through" : "text-slate-900")} numberOfLines={2}>
          {g.title}
        </Text>
        <View className="rounded-full bg-slate-100 px-2 py-0.5">
          <Text className="text-[11px] font-medium text-slate-500">{KIND[g.kind] ?? g.kind}</Text>
        </View>
      </View>

      {g.target_value != null ? (
        <Text className="mt-1 text-xs text-slate-500">
          {g.current_value ?? 0}/{g.target_value} {g.unit ?? ""}
        </Text>
      ) : null}

      {g.progress_pct != null ? (
        <View className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <View
            className={cn("h-full rounded-full", g.progress_pct >= 100 ? "bg-emerald-500" : "bg-brand-500")}
            style={{ width: `${Math.min(100, g.progress_pct)}%` }}
          />
        </View>
      ) : null}

      {g.target_date ? <Text className="mt-1.5 text-[11px] text-slate-400">Hedef tarih: {g.target_date}</Text> : null}

      {!achieved ? (
        <View className="mt-3 flex-row gap-2">
          {g.target_value != null ? (
            <Pressable onPress={() => onProgress(g)} disabled={busy} className="flex-1 items-center rounded-xl border border-slate-300 py-2.5 active:bg-slate-50">
              <Text className="text-sm font-semibold text-slate-700">İlerleme gir</Text>
            </Pressable>
          ) : null}
          <Pressable onPress={() => onAchieve(g)} disabled={busy} className="flex-1 items-center rounded-xl bg-emerald-600 py-2.5 active:bg-emerald-700">
            <Text className="text-sm font-semibold text-white">Başardım</Text>
          </Pressable>
        </View>
      ) : (
        <View className="mt-2 flex-row items-center gap-1.5">
          <Ionicons name="checkmark-circle" size={16} color="#059669" />
          <Text className="text-xs font-medium text-emerald-700">Tamamlandı</Text>
        </View>
      )}
    </View>
  );
}

function CreateForm({ busy, onSubmit }: { busy: boolean; onSubmit: (b: GoalCreateBody) => void }) {
  const [title, setTitle] = React.useState("");
  const [kind, setKind] = React.useState<"weekly" | "daily" | "topic" | "custom">("weekly");
  const [target, setTarget] = React.useState("");
  const [unit, setUnit] = React.useState("");
  const canSave = title.trim().length >= 2 && !busy;
  return (
    <View className="gap-4 pb-2">
      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Hedef</Text>
        <TextInput value={title} onChangeText={setTitle} placeholder="örn. Bu hafta 200 test çöz" placeholderTextColor="#94a3b8" className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
      </View>
      <View className="gap-1.5">
        <Text className="text-xs font-medium text-slate-600">Tür</Text>
        <View className="flex-row flex-wrap gap-2">
          {CREATE_KINDS.map((k) => {
            const active = k.v === kind;
            return (
              <Pressable key={k.v} onPress={() => setKind(k.v as typeof kind)} className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}>
                <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{k.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>
      <View className="flex-row gap-3">
        <View className="flex-1 gap-1">
          <Text className="text-xs font-medium text-slate-600">Hedef sayı (isteğe bağlı)</Text>
          <TextInput value={target} onChangeText={(v) => setTarget(v.replace(/[^0-9]/g, "").slice(0, 5))} keyboardType="number-pad" placeholder="örn. 200" placeholderTextColor="#94a3b8" className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
        </View>
        <View className="flex-1 gap-1">
          <Text className="text-xs font-medium text-slate-600">Birim</Text>
          <TextInput value={unit} onChangeText={setUnit} placeholder="test / konu" placeholderTextColor="#94a3b8" className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900" />
        </View>
      </View>
      <Pressable
        onPress={() => onSubmit({ title: title.trim(), kind, target_value: target ? Number(target) : null, unit: unit.trim() || null })}
        disabled={!canSave}
        className={cn("items-center rounded-xl py-3.5", canSave ? "bg-brand-700 active:bg-brand-800" : "bg-brand-700/40")}
      >
        <Text className="text-base font-semibold text-white">{busy ? "Kaydediliyor…" : "Hedef ekle"}</Text>
      </Pressable>
    </View>
  );
}

export function GoalsView({
  data,
  busy,
  onCreate,
  onProgress,
  onAchieve,
  refreshing = false,
  onRefresh,
}: {
  data: GoalListResponse;
  busy: boolean;
  onCreate: (b: GoalCreateBody) => void;
  onProgress: (id: number, value: number) => void;
  onAchieve: (id: number) => void;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const [createOpen, setCreateOpen] = React.useState(false);
  const [progressGoal, setProgressGoal] = React.useState<GoalItem | null>(null);
  const [val, setVal] = React.useState("");

  const sorted = [...data.items].sort((a, b) => (a.status === "achieved" ? 1 : 0) - (b.status === "achieved" ? 1 : 0));

  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-4 gap-3"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined}
    >
      <DemoHint contextKey="goals" role="student" />
      <View className="flex-row gap-3 rounded-2xl border border-slate-200 bg-white p-4">
        <View className="flex-1 items-center"><Text className="text-xl font-extrabold text-slate-900">{data.summary.active}</Text><Text className="text-[11px] text-slate-400">aktif</Text></View>
        <View className="flex-1 items-center"><Text className="text-xl font-extrabold text-emerald-600">{data.summary.achieved}</Text><Text className="text-[11px] text-slate-400">başarıldı</Text></View>
        <View className="flex-1 items-center"><Text className="text-xl font-extrabold text-slate-900">{data.summary.overall_pct != null ? `%${data.summary.overall_pct}` : "—"}</Text><Text className="text-[11px] text-slate-400">ilerleme</Text></View>
      </View>

      <Pressable onPress={() => setCreateOpen(true)} className="flex-row items-center justify-center gap-2 rounded-2xl border border-brand-200 bg-brand-50 py-3.5 active:bg-brand-100">
        <Ionicons name="add-circle-outline" size={20} color="#0e7490" />
        <Text className="text-base font-semibold text-brand-700">Yeni hedef</Text>
      </Pressable>

      {sorted.length === 0 ? (
        <View className="mt-6 items-center gap-2 px-6">
          <Ionicons name="flag-outline" size={40} color="#94a3b8" />
          <Text className="text-center text-sm text-slate-500">Henüz hedefin yok. Küçük, ölçülebilir bir hedefle başla.</Text>
        </View>
      ) : (
        sorted.map((g) => (
          <GoalCard key={g.id} g={g} busy={busy} onProgress={(goal) => { setProgressGoal(goal); setVal(String(goal.current_value ?? 0)); }} onAchieve={(goal) => onAchieve(goal.id)} />
        ))
      )}

      <FormSheet visible={createOpen} title="Yeni hedef" onClose={() => setCreateOpen(false)}>
        <CreateForm busy={busy} onSubmit={(b) => { onCreate(b); setCreateOpen(false); }} />
      </FormSheet>

      <FormSheet visible={progressGoal != null} title="İlerleme gir" onClose={() => setProgressGoal(null)}>
        {progressGoal ? (
          <View className="gap-4 pb-2">
            <Text className="text-sm text-slate-600">{progressGoal.title}</Text>
            <View className="gap-1">
              <Text className="text-xs font-medium text-slate-600">Şu anki değer {progressGoal.unit ? `(${progressGoal.unit})` : ""}</Text>
              <TextInput value={val} onChangeText={(v) => setVal(v.replace(/[^0-9]/g, "").slice(0, 6))} keyboardType="number-pad" placeholder="0" placeholderTextColor="#94a3b8" className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-lg font-semibold text-slate-900" />
            </View>
            <Pressable
              onPress={() => { onProgress(progressGoal.id, Number(val) || 0); setProgressGoal(null); }}
              disabled={busy}
              className={cn("items-center rounded-xl py-3.5", busy ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}
            >
              <Text className="text-base font-semibold text-white">Kaydet</Text>
            </Pressable>
          </View>
        ) : null}
      </FormSheet>
    </ScrollView>
  );
}
