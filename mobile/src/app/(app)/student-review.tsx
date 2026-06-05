import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ReviewView } from "@/components/student/review-view";
import { getStudentReview, rateReviewCard, studentDevKeys, type ReviewCardItem } from "@/lib/student";

export default function StudentReviewRoute() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: studentDevKeys.review, queryFn: getStudentReview });

  // Oturum başında due kartları sabitlenir; index ilerler.
  const [cards, setCards] = React.useState<ReviewCardItem[] | null>(null);
  const [index, setIndex] = React.useState(0);

  React.useEffect(() => {
    if (cards == null && q.data) setCards(q.data.due_cards);
  }, [q.data, cards]);

  const rateMut = useMutation({
    mutationFn: (v: { cardId: number; rating: number }) => rateReviewCard(v.cardId, v.rating),
    onSuccess: () => {
      setIndex((i) => i + 1);
      qc.invalidateQueries({ queryKey: ["student", "review"] });
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
          busy={rateMut.isPending}
          onRate={(cardId, rating) => rateMut.mutate({ cardId, rating })}
          onClose={() => router.back()}
        />
      )}
    </SafeAreaView>
  );
}
