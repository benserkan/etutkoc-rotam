import { Ionicons } from "@expo/vector-icons";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";

import type { BookSectionOption, PickBook, PickSubjectGroup } from "@/lib/student";

/** Adım 1 — kitap seç (ders gruplu). */
export function BookPickStep({
  groups,
  onPick,
}: {
  groups: PickSubjectGroup[];
  onPick: (book: PickBook) => void;
}) {
  return (
    <ScrollView contentContainerClassName="px-4 py-3 gap-4">
      <Text className="text-sm text-slate-500">Hangi kitaptan?</Text>
      {groups.length === 0 ? (
        <Text className="text-sm text-slate-400">Sana atanmış kitap yok.</Text>
      ) : (
        groups.map((g) => (
          <View key={g.subject_id} className="gap-1.5">
            <Text className="text-[11px] font-bold uppercase tracking-wide text-brand-700">
              {g.subject_name}
            </Text>
            {g.books.map((b) => (
              <Pressable
                key={b.book_id}
                onPress={() => onPick(b)}
                className="flex-row items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 active:bg-slate-50"
              >
                <Text className="flex-1 text-[15px] text-slate-900" numberOfLines={1}>
                  {b.book_name}
                </Text>
                <Text className="text-xs text-slate-400">{b.remaining_tests} kalan</Text>
                <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
              </Pressable>
            ))}
          </View>
        ))
      )}
    </ScrollView>
  );
}

/** Adım 2 — bölüm seç. */
export function SectionPickStep({
  bookName,
  sections,
  onPick,
}: {
  bookName: string;
  sections: BookSectionOption[];
  onPick: (section: BookSectionOption) => void;
}) {
  return (
    <ScrollView contentContainerClassName="px-4 py-3 gap-2">
      <Text className="text-sm text-slate-500">
        <Text className="font-semibold text-slate-700">{bookName}</Text> · hangi bölüm?
      </Text>
      {sections.length === 0 ? (
        <Text className="text-sm text-slate-400">Bu kitapta uygun bölüm yok.</Text>
      ) : (
        sections.map((s) => {
          const full = s.remaining <= 0;
          return (
            <Pressable
              key={s.id}
              onPress={() => !full && onPick(s)}
              disabled={full}
              className={`flex-row items-center gap-2 rounded-xl border px-4 py-3 ${
                full ? "border-slate-100 bg-slate-50 opacity-50" : "border-slate-200 bg-white active:bg-slate-50"
              }`}
            >
              <View className="flex-1">
                <Text className="text-[15px] text-slate-900" numberOfLines={1}>{s.label}</Text>
                {s.topic_name ? <Text className="text-xs text-slate-400">{s.topic_name}</Text> : null}
              </View>
              <Text className="text-xs text-slate-400">{s.remaining}/{s.total} kalan</Text>
            </Pressable>
          );
        })
      )}
    </ScrollView>
  );
}

/** Adım 3 — sayı + not + gönder. */
export function CountStep({
  bookName,
  sectionLabel,
  max,
  count,
  setCount,
  message,
  setMessage,
  busy,
  error,
  submitLabel,
  onSubmit,
}: {
  bookName: string;
  sectionLabel: string;
  max: number;
  count: string;
  setCount: (v: string) => void;
  message: string;
  setMessage: (v: string) => void;
  busy: boolean;
  error: string | null;
  submitLabel: string;
  onSubmit: () => void;
}) {
  const n = Number(count);
  const invalid = !count.trim() || !(n > 0);
  return (
    <ScrollView contentContainerClassName="px-4 py-3 gap-4" keyboardShouldPersistTaps="handled">
      <View className="rounded-2xl border border-slate-200 bg-white p-4">
        <Text className="text-[11px] font-bold uppercase tracking-wide text-brand-700">Seçtiğin kaynak</Text>
        <Text className="mt-0.5 text-[15px] font-semibold text-slate-900">{bookName}</Text>
        <Text className="text-sm text-slate-500">{sectionLabel}</Text>
      </View>

      <View className="gap-1.5">
        <Text className="text-xs font-medium text-slate-600">Kaç test? (en fazla {max})</Text>
        <View className="flex-row items-center gap-3">
          <Pressable
            onPress={() => setCount(String(Math.max(1, n - 1)))}
            className="size-11 items-center justify-center rounded-full border border-slate-300 active:bg-slate-100"
          >
            <Text className="text-xl font-bold text-slate-700">−</Text>
          </Pressable>
          <TextInput
            value={count}
            onChangeText={(v) => setCount(v.replace(/[^0-9]/g, "").slice(0, 4))}
            keyboardType="number-pad"
            className="w-20 rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-center text-lg font-bold text-slate-900"
          />
          <Pressable
            onPress={() => setCount(String(Math.min(max, n + 1)))}
            className="size-11 items-center justify-center rounded-full border border-slate-300 active:bg-slate-100"
          >
            <Text className="text-xl font-bold text-slate-700">+</Text>
          </Pressable>
        </View>
      </View>

      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Koça not (isteğe bağlı)</Text>
        <TextInput
          value={message}
          onChangeText={setMessage}
          placeholder="Kısa açıklama…"
          placeholderTextColor="#94a3b8"
          multiline
          className="min-h-[60px] rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>

      {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}

      <Pressable
        onPress={onSubmit}
        disabled={busy || invalid}
        className={`items-center rounded-xl py-3.5 ${busy || invalid ? "bg-brand-700/50" : "bg-brand-700 active:bg-brand-800"}`}
      >
        <Text className="text-base font-semibold text-white">{busy ? "Gönderiliyor…" : submitLabel}</Text>
      </Pressable>
    </ScrollView>
  );
}
