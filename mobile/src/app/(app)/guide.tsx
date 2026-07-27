import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { GuidePlayer } from "@/components/guide/guide-player";
import { useAuth } from "@/lib/auth";
import {
  getGuide,
  GUIDE_KEY_BY_ROLE,
  GUIDES,
  guideKeys,
  postGuideProgress,
  type GuideProgressAction,
} from "@/lib/guide";

/**
 * Rehber — rol bazlı sesli tanıtım turu (Rota anlatır).
 * Öğrenci/veli/koç kendi rehberini görür; ilerleme sunucuda tutulur
 * (web'de kaldığın yerden mobilde devam edebilirsin, tersi de).
 */
export default function GuideRoute() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const guideKey = user ? GUIDE_KEY_BY_ROLE[user.role] : undefined;
  const content = guideKey ? GUIDES[guideKey] : undefined;

  const q = useQuery({
    queryKey: guideKeys.state(guideKey ?? "none"),
    queryFn: () => getGuide(guideKey!),
    enabled: Boolean(guideKey),
  });

  const progress = useMutation({
    mutationFn: (body: {
      action: GuideProgressAction;
      chapter?: string;
      step?: number;
    }) => postGuideProgress(guideKey!, body),
    onSuccess: (_res, vars) => {
      // watch adım başına gider — churn yaratmasın (web ile aynı karar)
      if (vars.action !== "watch") {
        void qc.invalidateQueries({ queryKey: guideKeys.state(guideKey!) });
      }
    },
  });

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable
          onPress={() => router.back()}
          hitSlop={8}
          className="size-10 items-center justify-center rounded-full active:bg-slate-200"
          accessibilityLabel="Geri"
        >
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Rehber</Text>
      </View>

      {!guideKey || !content ? (
        <View className="flex-1 items-center justify-center px-8">
          <Text className="text-center text-sm text-slate-500">
            Bu hesap türü için rehber henüz yok.
          </Text>
        </View>
      ) : q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">
            Yüklenemedi
          </Text>
          <Pressable
            onPress={() => q.refetch()}
            className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"
          >
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView
          contentContainerClassName="px-4 py-3 pb-12"
          refreshControl={
            <RefreshControl
              refreshing={q.isRefetching}
              onRefresh={() => q.refetch()}
            />
          }
        >
          <GuidePlayer
            // Bölüm tamamlanınca state tazelenir → oynatıcı güncel checklist'le
            // yeniden kurulur (izlenenler sunucudan geri gelir).
            key={`${guideKey}-${q.data.state.chapters_done.length}-${q.data.state.status}`}
            content={content}
            guide={q.data}
            onProgress={(body) => progress.mutate(body)}
          />
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
