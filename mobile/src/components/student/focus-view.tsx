import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, TextInput, View } from "react-native";

import type { FocusResponse } from "@/lib/student";
import { cn } from "@/lib/utils";

const DURATIONS = [25, 45, 50];

function mmss(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function FocusView({
  data,
  remainingSec,
  runningLabel,
  busy,
  onStart,
  onFinish,
  onCancel,
}: {
  data: FocusResponse;
  remainingSec: number | null; // null = boşta
  runningLabel: string | null;
  busy: boolean;
  onStart: (minutes: number, label: string) => void;
  onFinish: () => void;
  onCancel: () => void;
}) {
  const [minutes, setMinutes] = React.useState(25);
  const [label, setLabel] = React.useState("");

  const running = remainingSec != null;
  const done = running && remainingSec <= 0;

  return (
    <View className="flex-1 bg-slate-50 px-5 py-6">
      {/* Üst istatistik */}
      <View className="flex-row justify-around rounded-2xl border border-slate-200 bg-white p-4">
        <View className="items-center"><Text className="text-xl font-extrabold text-slate-900">{data.streak_days}</Text><Text className="text-[11px] text-slate-400">gün seri</Text></View>
        <View className="items-center"><Text className="text-xl font-extrabold text-slate-900">{data.today.work_minutes}</Text><Text className="text-[11px] text-slate-400">bugün dk</Text></View>
        <View className="items-center"><Text className="text-xl font-extrabold text-slate-900">{data.today.work_sessions}</Text><Text className="text-[11px] text-slate-400">oturum</Text></View>
        <View className="items-center"><Text className="text-xl font-extrabold text-amber-600">{data.points}</Text><Text className="text-[11px] text-slate-400">puan</Text></View>
      </View>

      {running ? (
        <View className="mt-10 items-center gap-6">
          <View className={cn("size-64 items-center justify-center rounded-full border-[10px]", done ? "border-emerald-500" : "border-brand-600")}>
            <Text className={cn("text-6xl font-extrabold tabular-nums", done ? "text-emerald-600" : "text-slate-900")}>
              {mmss(Math.max(0, remainingSec))}
            </Text>
            <Text className="mt-1 text-sm text-slate-400">{done ? "Süre doldu" : "odaklan"}</Text>
          </View>
          {runningLabel ? <Text className="text-base font-medium text-slate-700">{runningLabel}</Text> : null}

          <View className="w-full gap-3">
            <Pressable
              onPress={onFinish}
              disabled={busy}
              className={cn("items-center rounded-2xl py-4", done ? "bg-emerald-600 active:bg-emerald-700" : "bg-brand-700 active:bg-brand-800")}
            >
              <Text className="text-base font-bold text-white">{busy ? "…" : done ? "Tamamla" : "Bitir"}</Text>
            </Pressable>
            <Pressable onPress={onCancel} disabled={busy} className="items-center rounded-2xl border border-slate-300 py-3.5 active:bg-slate-100">
              <Text className="text-base font-semibold text-slate-600">Vazgeç</Text>
            </Pressable>
          </View>
        </View>
      ) : (
        <View className="mt-8 gap-5">
          <Text className="text-center text-base font-semibold text-slate-700">Ne kadar odaklanacaksın?</Text>
          <View className="flex-row justify-center gap-3">
            {DURATIONS.map((d) => {
              const active = d === minutes;
              return (
                <Pressable
                  key={d}
                  onPress={() => setMinutes(d)}
                  className={cn("size-20 items-center justify-center rounded-2xl border-2", active ? "border-brand-600 bg-brand-50" : "border-slate-200 bg-white")}
                >
                  <Text className={cn("text-2xl font-extrabold", active ? "text-brand-700" : "text-slate-700")}>{d}</Text>
                  <Text className="text-[11px] text-slate-400">dakika</Text>
                </Pressable>
              );
            })}
          </View>
          <View className="gap-1">
            <Text className="text-xs font-medium text-slate-600">Ne çalışıyorsun? (isteğe bağlı)</Text>
            <TextInput
              value={label}
              onChangeText={setLabel}
              placeholder="örn. Matematik — Üslü Sayılar"
              placeholderTextColor="#94a3b8"
              className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
            />
          </View>
          <Pressable
            onPress={() => onStart(minutes, label.trim())}
            disabled={busy}
            className={cn("flex-row items-center justify-center gap-2 rounded-2xl py-4", busy ? "bg-brand-700/50" : "bg-brand-700 active:bg-brand-800")}
          >
            <Ionicons name="play" size={20} color="#fff" />
            <Text className="text-base font-bold text-white">Odağa başla</Text>
          </Pressable>
          <Text className="text-center text-[11px] text-slate-400">
            Telefonu bırak, sayaç çalışsın. Bitince puan kazanır, serini sürdürürsün.
          </Text>
        </View>
      )}
    </View>
  );
}
