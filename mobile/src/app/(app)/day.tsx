import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { Pressable, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { DayScreen } from "@/components/student/day-screen";

/** Hafta'dan açılan tek gün detayı (tabs üzerine push). */
export default function DayDetailRoute() {
  const { date } = useLocalSearchParams<{ date?: string }>();
  const dateStr = typeof date === "string" ? date : undefined;

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
        <Text className="text-base font-semibold text-slate-800">Gün</Text>
      </View>
      <View className="flex-1">
        <DayScreen date={dateStr} safeTop={false} />
      </View>
    </SafeAreaView>
  );
}
