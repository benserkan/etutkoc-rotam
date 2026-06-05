import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { FocusView } from "@/components/student/focus-view";
import {
  cancelFocus,
  getStudentFocus,
  startFocus,
  stopFocus,
  studentDevKeys,
} from "@/lib/student";

export default function StudentFocusRoute() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: studentDevKeys.focus, queryFn: getStudentFocus });

  const active = q.data?.active_session ?? null;

  // Sayaç bitiş zamanı — aktif oturum görülünce bir kez hesaplanır.
  const endAtRef = React.useRef<number | null>(null);
  const [now, setNow] = React.useState(() => Date.now());

  React.useEffect(() => {
    if (active && endAtRef.current == null) {
      const totalSec = active.planned_minutes * 60;
      const remaining = Math.max(0, totalSec - active.elapsed_seconds);
      endAtRef.current = Date.now() + remaining * 1000;
    } else if (!active) {
      endAtRef.current = null;
    }
  }, [active]);

  React.useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const remainingSec = active && endAtRef.current != null ? Math.round((endAtRef.current - now) / 1000) : null;

  function invalidate() {
    endAtRef.current = null;
    qc.invalidateQueries({ queryKey: ["student", "focus"] });
    qc.invalidateQueries({ queryKey: ["student", "dna"] });
  }

  const startMut = useMutation({
    mutationFn: (v: { minutes: number; label: string }) =>
      startFocus({ planned_minutes: v.minutes, kind: "work", label: v.label || null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student", "focus"] }),
  });
  const stopMut = useMutation({
    mutationFn: () => {
      const planned = active!.planned_minutes;
      const elapsedMin = Math.max(1, Math.round((planned * 60 - Math.max(0, remainingSec ?? 0)) / 60));
      const interrupted = (remainingSec ?? 0) > 5;
      return stopFocus(active!.id, { actual_minutes: interrupted ? elapsedMin : planned, interrupted });
    },
    onSuccess: invalidate,
  });
  const cancelMut = useMutation({
    mutationFn: () => cancelFocus(active!.id),
    onSuccess: invalidate,
  });

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-200" accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Odak</Text>
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center"><ActivityIndicator size="large" color="#0e7490" /></View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <FocusView
          data={q.data}
          remainingSec={remainingSec}
          runningLabel={active?.label ?? null}
          busy={startMut.isPending || stopMut.isPending || cancelMut.isPending}
          onStart={(minutes, label) => startMut.mutate({ minutes, label })}
          onFinish={() => stopMut.mutate()}
          onCancel={() => cancelMut.mutate()}
        />
      )}
    </SafeAreaView>
  );
}
