import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, RefreshControl, ScrollView, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import type { TeacherStudentListItem, WarningLevel } from "@/lib/teacher";
import { cn } from "@/lib/utils";

const WARN: Record<WarningLevel, { border: string; dot: string }> = {
  red: { border: "border-l-rose-500", dot: "bg-rose-500" },
  amber: { border: "border-l-amber-400", dot: "bg-amber-400" },
  green: { border: "border-l-emerald-500", dot: "bg-emerald-500" },
};

function StudentRow({ s, onPress }: { s: TeacherStudentListItem; onPress: () => void }) {
  const w = WARN[s.worst_warning_level];
  const pct = Math.round((s.week_pct ?? 0) * 100);
  const grade = s.grade_level != null ? `${s.grade_level}. sınıf` : "";
  return (
    <Pressable
      onPress={onPress}
      className={cn(
        "flex-row items-center gap-3 rounded-2xl border border-l-4 border-slate-200 bg-white p-4 active:bg-slate-50",
        w.border,
        !s.is_active && "opacity-60",
      )}
    >
      <View className="flex-1">
        <View className="flex-row items-center gap-2">
          <Text className="text-[15px] font-bold text-slate-900" numberOfLines={1}>{s.full_name}</Text>
          {!s.is_active ? (
            <View className="rounded bg-slate-100 px-1.5 py-0.5">
              <Text className="text-[10px] text-slate-500">pasif</Text>
            </View>
          ) : null}
          {s.has_pending_request ? (
            <View className="rounded bg-amber-100 px-1.5 py-0.5">
              <Text className="text-[10px] font-medium text-amber-700">talep</Text>
            </View>
          ) : null}
        </View>
        <Text className="text-xs text-slate-400">{grade || s.email}</Text>
        {s.worst_warning_level !== "green" && s.worst_warning_title ? (
          <Text
            className={cn("mt-0.5 text-[12px]", s.worst_warning_level === "red" ? "text-rose-600" : "text-amber-700")}
            numberOfLines={1}
          >
            {s.worst_warning_title}
          </Text>
        ) : null}
        <Text className="mt-1 text-xs text-slate-500">
          Bugün {s.today_gorev_done}/{s.today_gorev_total} görev · Hafta %{pct}
        </Text>
      </View>
      <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
    </Pressable>
  );
}

export function StudentsListView({
  items,
  onOpenStudent,
  onInvite,
  refreshing = false,
  onRefresh,
}: {
  items: TeacherStudentListItem[];
  onOpenStudent: (id: number) => void;
  onInvite?: () => void;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const [q, setQ] = React.useState("");
  const filtered = React.useMemo(() => {
    const t = q.trim().toLocaleLowerCase("tr-TR");
    if (!t) return items;
    return items.filter(
      (s) =>
        s.full_name.toLocaleLowerCase("tr-TR").includes(t) ||
        s.email.toLocaleLowerCase("tr-TR").includes(t),
    );
  }, [items, q]);

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="px-4 pt-3 pb-1 gap-3">
        <View className="flex-row items-center justify-between">
          <Text className="text-xl font-bold text-slate-900">Öğrencilerim</Text>
          {onInvite ? (
            <Pressable
              onPress={onInvite}
              className="flex-row items-center gap-1 rounded-full bg-brand-700 px-3 py-1.5 active:bg-brand-800"
            >
              <Ionicons name="person-add-outline" size={16} color="#fff" />
              <Text className="text-sm font-semibold text-white">Davet</Text>
            </Pressable>
          ) : null}
        </View>
        <View className="flex-row items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2.5">
          <Ionicons name="search" size={18} color="#94a3b8" />
          <TextInput
            value={q}
            onChangeText={setQ}
            placeholder="Öğrenci ara (ad / e-posta)"
            placeholderTextColor="#94a3b8"
            className="flex-1 text-base text-slate-900"
          />
          {q ? (
            <Pressable onPress={() => setQ("")} hitSlop={8}>
              <Ionicons name="close-circle" size={18} color="#cbd5e1" />
            </Pressable>
          ) : null}
        </View>
      </View>

      <ScrollView
        contentContainerClassName="px-4 pb-4 pt-2 gap-2.5"
        keyboardShouldPersistTaps="handled"
        refreshControl={
          onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined
        }
      >
        {filtered.length === 0 ? (
          <View className="mt-10 items-center gap-3 px-6">
            <Ionicons name="people-outline" size={44} color="#94a3b8" />
            <Text className="text-center text-sm text-slate-500">
              {items.length === 0 ? "Henüz öğrencin yok." : "Aramanla eşleşen öğrenci yok."}
            </Text>
          </View>
        ) : (
          filtered.map((s) => <StudentRow key={s.id} s={s} onPress={() => onOpenStudent(s.id)} />)
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
