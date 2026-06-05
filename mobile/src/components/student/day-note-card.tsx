import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Text, TextInput, View } from "react-native";

import { saveDayNote } from "@/lib/student";

type SaveState = "idle" | "saving" | "saved" | "error";

/**
 * Günün düşünce notu — yazdıkça otomatik kaydeder (700ms debounce, web ile aynı).
 * Buton yok; öğrenci yazar, sistem saklar.
 */
export function DayNoteCard({ date, initial }: { date: string; initial: string }) {
  const [text, setText] = React.useState(initial);
  const [state, setState] = React.useState<SaveState>("idle");
  const timer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSaved = React.useRef(initial);

  // Gün/öğrenci değişince notu sıfırla (prop değişince render'da).
  const dateRef = React.useRef(date);
  if (dateRef.current !== date) {
    dateRef.current = date;
    lastSaved.current = initial;
    if (text !== initial) setText(initial);
    setState("idle");
  }

  React.useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  function onChange(v: string) {
    setText(v);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void flush(v), 700);
  }

  async function flush(v: string) {
    if (v === lastSaved.current) return;
    setState("saving");
    try {
      await saveDayNote(date, v);
      lastSaved.current = v;
      setState("saved");
    } catch {
      setState("error");
    }
  }

  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="mb-2 flex-row items-center justify-between">
        <View className="flex-row items-center gap-2">
          <Ionicons name="create-outline" size={16} color="#0e7490" />
          <Text className="text-sm font-semibold text-slate-800">Günün notu</Text>
        </View>
        {state === "saving" ? (
          <Text className="text-[11px] text-slate-400">Kaydediliyor…</Text>
        ) : state === "saved" ? (
          <Text className="text-[11px] text-emerald-600">Kaydedildi</Text>
        ) : state === "error" ? (
          <Text className="text-[11px] text-rose-500">Kaydedilemedi</Text>
        ) : null}
      </View>
      <TextInput
        value={text}
        onChangeText={onChange}
        placeholder="Bugün nasıl geçti? Aklındakileri yaz… (otomatik kaydedilir)"
        placeholderTextColor="#94a3b8"
        multiline
        className="min-h-[64px] text-[15px] leading-relaxed text-slate-900"
        textAlignVertical="top"
      />
    </View>
  );
}
