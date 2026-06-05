import { Ionicons } from "@expo/vector-icons";
import { Text, View, Pressable } from "react-native";

import type { ReviewCardItem } from "@/lib/student";
import { cn } from "@/lib/utils";

const RATINGS = [
  { v: 1, label: "Hatırlamadım", tone: "bg-rose-600 active:bg-rose-700" },
  { v: 2, label: "Zor", tone: "bg-amber-500 active:bg-amber-600" },
  { v: 3, label: "İyi", tone: "bg-emerald-600 active:bg-emerald-700" },
  { v: 4, label: "Kolay", tone: "bg-sky-600 active:bg-sky-700" },
];

export function ReviewView({
  card,
  index,
  total,
  done,
  busy,
  onRate,
  onClose,
}: {
  card: ReviewCardItem | null;
  index: number;
  total: number;
  done: boolean;
  busy: boolean;
  onRate: (cardId: number, rating: number) => void;
  onClose: () => void;
}) {
  if (done || !card) {
    return (
      <View className="flex-1 items-center justify-center gap-4 bg-slate-50 px-8">
        <View className="size-20 items-center justify-center rounded-full bg-emerald-100">
          <Ionicons name="checkmark-done" size={42} color="#059669" />
        </View>
        <Text className="text-center text-xl font-bold text-slate-900">Tekrar tamamlandı</Text>
        <Text className="text-center text-sm text-slate-500">
          {total > 0 ? `${total} kartı tekrar ettin. Harika!` : "Şu an tekrar edilecek kart yok."}
        </Text>
        <Pressable onPress={onClose} className="mt-2 rounded-xl bg-brand-700 px-6 py-3 active:bg-brand-800">
          <Text className="text-base font-semibold text-white">Bitir</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <View className="flex-1 bg-slate-50 px-5 py-6">
      {/* İlerleme */}
      <View className="flex-row items-center gap-3">
        <View className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
          <View className="h-full rounded-full bg-brand-600" style={{ width: `${Math.round((index / Math.max(1, total)) * 100)}%` }} />
        </View>
        <Text className="text-xs font-semibold text-slate-500">{index + 1}/{total}</Text>
      </View>

      {/* Kart */}
      <View className="mt-8 flex-1 items-center justify-center">
        <View className="w-full items-center rounded-3xl border border-slate-200 bg-white p-8">
          {card.subject_name ? (
            <Text className="text-sm font-bold uppercase tracking-wide text-brand-700">{card.subject_name}</Text>
          ) : null}
          <Text className="mt-3 text-center text-2xl font-extrabold text-slate-900">{card.topic_name}</Text>
          <Text className="mt-4 text-center text-sm text-slate-500">
            Bu konuyu ne kadar hatırlıyorsun?
          </Text>
        </View>
      </View>

      {/* Değerlendirme */}
      <View className="gap-2.5">
        {RATINGS.map((r) => (
          <Pressable
            key={r.v}
            onPress={() => onRate(card.id, r.v)}
            disabled={busy}
            className={cn("items-center rounded-2xl py-3.5", r.tone, busy && "opacity-60")}
          >
            <Text className="text-base font-bold text-white">{r.label}</Text>
          </Pressable>
        ))}
        <Text className="mt-1 text-center text-[11px] text-slate-400">
          Dürüst ol — sistem bir sonraki tekrarı buna göre planlar.
        </Text>
      </View>
    </View>
  );
}
