import * as React from "react";
import { Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import { cn } from "@/lib/utils";

export interface NotifyCoachTarget {
  teacher_id: number;
  teacher_name: string | null;
  student_name: string;
  context: "at_risk" | "burnout";
}

/** Risk/tükenmişlik panosundan sorumlu koça müdahale talebi açar. */
export function NotifyCoachSheet({
  target,
  busy,
  onClose,
  onSubmit,
}: {
  target: NotifyCoachTarget | null;
  busy: boolean;
  onClose: () => void;
  onSubmit: (note: string) => void;
}) {
  const [note, setNote] = React.useState("");
  const visRef = React.useRef<NotifyCoachTarget | null>(null);
  if (visRef.current !== target) {
    visRef.current = target;
    if (target) setNote("");
  }

  return (
    <FormSheet visible={!!target} title="Koça ilet" onClose={onClose}>
      {target ? (
        <View className="gap-4 pb-2">
          <View className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <Text className="text-xs text-slate-500">Öğrenci</Text>
            <Text className="text-sm font-semibold text-slate-900">{target.student_name}</Text>
            <Text className="mt-1 text-xs text-slate-500">Sorumlu koç</Text>
            <Text className="text-sm font-semibold text-slate-900">{target.teacher_name ?? "—"}</Text>
          </View>
          <View className="gap-1">
            <Text className="text-xs font-medium text-slate-600">Not (opsiyonel)</Text>
            <TextInput
              value={note}
              onChangeText={setNote}
              placeholder="Koça iletmek istediğin kısa not…"
              placeholderTextColor="#94a3b8"
              multiline
              className="min-h-20 rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
            />
          </View>
          <Text className="text-[11px] text-slate-400">
            Gizlilik gereği öğrenci detayına eremezsin; tek müdahale yolu sorumlu koçtur. Talep koçun gelen
            kutusuna düşer.
          </Text>
          <Pressable
            onPress={() => onSubmit(note.trim())}
            disabled={busy}
            className={cn("items-center rounded-xl py-3.5", busy ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}
          >
            <Text className="text-base font-semibold text-white">{busy ? "Gönderiliyor…" : "Koça gönder"}</Text>
          </Pressable>
        </View>
      ) : null}
    </FormSheet>
  );
}
