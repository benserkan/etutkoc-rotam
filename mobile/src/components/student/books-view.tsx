import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import type { ResourceBookItem, ResourceSubjectGroup, StudentBooksProgress } from "@/lib/student";
import { cn } from "@/lib/utils";

const TYPE_LABEL: Record<string, string> = {
  soru_bankasi: "Soru bankası",
  konu_anlatim: "Konu anlatımı",
  deneme: "Deneme",
  diger: "Diğer",
};

function pct(done: number, total: number): number {
  return total > 0 ? Math.round((done / total) * 100) : 0;
}

function Bar({ value }: { value: number }) {
  return (
    <View className="h-2 overflow-hidden rounded-full bg-slate-100">
      <View
        className={cn("h-full rounded-full", value >= 70 ? "bg-emerald-500" : value >= 40 ? "bg-amber-400" : "bg-brand-500")}
        style={{ width: `${Math.min(100, value)}%` }}
      />
    </View>
  );
}

function BookRow({ b }: { b: ResourceBookItem }) {
  const p = pct(b.completed_tests, b.total_tests);
  return (
    <View className="gap-1.5 rounded-xl bg-slate-50 p-3">
      <View className="flex-row items-start justify-between gap-2">
        <Text className="flex-1 text-[14px] font-medium text-slate-900" numberOfLines={2}>{b.book_name}</Text>
        <Text className="text-xs font-semibold text-slate-500">%{p}</Text>
      </View>
      <Bar value={p} />
      <Text className="text-[11px] text-slate-400">
        {b.completed_tests}/{b.total_tests} test · {b.remaining_tests} kalan
        {b.reserved_tests > 0 ? ` · ${b.reserved_tests} planlı` : ""}
        {TYPE_LABEL[b.book_type] ? ` · ${TYPE_LABEL[b.book_type]}` : ""}
      </Text>
    </View>
  );
}

function SubjectCard({ g }: { g: ResourceSubjectGroup }) {
  const [open, setOpen] = React.useState(false);
  const p = pct(g.completed_tests, g.total_tests);
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <Pressable onPress={() => setOpen((o) => !o)} className="flex-row items-center justify-between">
        <View className="flex-1">
          <Text className="text-[15px] font-bold text-slate-900">{g.subject_name}</Text>
          <Text className="text-xs text-slate-400">{g.books.length} kitap · {g.completed_tests}/{g.total_tests} test</Text>
        </View>
        <Text className="mr-2 text-base font-extrabold text-slate-700">%{p}</Text>
        <Ionicons name={open ? "chevron-up" : "chevron-down"} size={18} color="#94a3b8" />
      </Pressable>
      <View className="mt-2"><Bar value={p} /></View>
      {open ? (
        <View className="mt-3 gap-2">
          {g.books.map((b) => (
            <BookRow key={b.student_book_id} b={b} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

export function BooksView({
  data,
  refreshing = false,
  onRefresh,
}: {
  data: StudentBooksProgress;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const overall = pct(data.completed_tests, data.total_tests);
  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-4 gap-4"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined}
    >
      <View className="rounded-2xl bg-brand-700 p-5">
        <Text className="text-xs font-semibold uppercase tracking-wider text-brand-100">Kitap ilerlemem</Text>
        <View className="mt-2 flex-row items-end justify-between">
          <Text className="text-3xl font-extrabold text-white">
            {data.completed_tests}
            <Text className="text-lg font-semibold text-brand-100">/{data.total_tests} test</Text>
          </Text>
          <Text className="text-2xl font-bold text-white">%{overall}</Text>
        </View>
        <View className="mt-2 h-2 overflow-hidden rounded-full bg-white/25">
          <View className="h-full rounded-full bg-white" style={{ width: `${Math.min(100, overall)}%` }} />
        </View>
        <Text className="mt-2 text-xs text-brand-100">{data.remaining_tests} kalan · {data.reserved_tests} programa planlı</Text>
      </View>

      {data.subjects.length === 0 ? (
        <View className="mt-6 items-center gap-2 px-6">
          <Ionicons name="library-outline" size={40} color="#94a3b8" />
          <Text className="text-center text-sm text-slate-500">Henüz kitabın yok. Koçun kitap eklediğinde burada görünür.</Text>
        </View>
      ) : (
        data.subjects.map((g) => <SubjectCard key={g.subject_id} g={g} />)
      )}
    </ScrollView>
  );
}
