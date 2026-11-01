import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Alert, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ReviewView } from "@/components/student/review-view";
import { ApiError } from "@/lib/api";
import {
  getStudentReview,
  rateReviewCard,
  studentDevKeys,
  undoReviewCard,
  type ReviewCardItem,
} from "@/lib/student";

function rateMessage(card: ReviewCardItem, rating: number): string {
  if (card.state === "mastered") return "Bu konu artık kalıcı — tekrar kuyruğundan çıktı.";
  const days = card.due_at
    ? Math.max(1, Math.round((new Date(card.due_at).getTime() - Date.now()) / 86_400_000))
    : null;
  const when = days == null ? "" : `${days} gün sonra`;
  if (rating === 1) return `Bu hafta bu konuyu çalış; ${when} yeniden soracağım.`;
  return when ? `Sıradaki tekrar ${when}.` : "Kaydedildi.";
}

export default function StudentReviewRoute() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: studentDevKeys.review, queryFn: getStudentReview });

  // Oturum başında due kartları sabitlenir; index ilerler.
  const [cards, setCards] = React.useState<ReviewCardItem[] | null>(null);
  const [index, setIndex] = React.useState(0);

  React.useEffect(() => {
    if (cards == null && q.data) setCards(q.data.due_cards);
  }, [q.data, cards]);

  // Son işaretlenen kart — "Geri al" şeridi için.
  const [last, setLast] = React.useState<{ cardId: number; topic: string; msg: string } | null>(null);

  const rateMut = useMutation({
    mutationFn: (v: { cardId: number; rating: number; topic: string }) => rateReviewCard(v.cardId, v.rating),
    onSuccess: (res, v) => {
      setLast({ cardId: v.cardId, topic: v.topic, msg: rateMessage(res.data, v.rating) });
      setIndex((i) => i + 1);
      qc.invalidateQueries({ queryKey: ["student", "review"] });
    },
  });
  const undoMut = useMutation({
    mutationFn: (cardId: number) => undoReviewCard(cardId),
    onSuccess: () => {
      setLast(null);
      setIndex((i) => Math.max(0, i - 1));
      qc.invalidateQueries({ queryKey: ["student", "review"] });
    },
    onError: (e) => {
      setLast(null);
      Alert.alert("Geri alınamadı", e instanceof ApiError ? e.message : "İşlem başarısız.");
    },
  });

  const total = cards?.length ?? 0;
  const current = cards && index < total ? cards[index] : null;
  const done = cards != null && index >= total;

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-200" accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Tekrar</Text>
      </View>

      {q.isLoading || cards == null ? (
        <View className="flex-1 items-center justify-center"><ActivityIndicator size="large" color="#0e7490" /></View>
      ) : q.isError ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <ReviewView
          card={current}
          index={index}
          total={total}
          done={done}
          busy={rateMut.isPending || undoMut.isPending}
          onRate={(cardId, rating) =>
            rateMut.mutate({ cardId, rating, topic: current?.topic_name ?? "" })
          }
          onClose={() => router.back()}
          waiting={q.data?.breakdown.new_waiting ?? 0}
          perDay={q.data?.breakdown.new_per_day ?? 10}
        />
      )}
      {last && !undoMut.isPending ? (
        <View className="mx-4 mb-4 flex-row items-center gap-3 rounded-2xl bg-slate-800 px-4 py-3">
          <View className="flex-1">
            <Text className="text-sm font-semibold text-white">{last.topic}</Text>
            <Text className="text-xs text-slate-200">{last.msg}</Text>
          </View>
          <Pressable
            onPress={() => undoMut.mutate(last.cardId)}
            hitSlop={8}
            className="rounded-xl bg-white px-3 py-2 active:bg-slate-200"
            accessibilityLabel="Son işaretlemeyi geri al"
          >
            <Text className="text-sm font-bold text-slate-900">Geri al</Text>
          </Pressable>
        </View>
      ) : null}
    </SafeAreaView>
  );
}
