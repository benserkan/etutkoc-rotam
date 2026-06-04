import { Ionicons } from "@expo/vector-icons";
import { Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

export default function StudentExamsScreen() {
  return (
    <SafeAreaView className="flex-1 items-center justify-center gap-3 bg-slate-50 px-8">
      <Ionicons name="bar-chart-outline" size={40} color="#94a3b8" />
      <Text className="text-base font-semibold text-slate-700">Denemeler</Text>
      <Text className="text-center text-sm text-slate-500">
        Deneme sonuçların ve net gelişim grafiğin yakında bu sekmede.
      </Text>
    </SafeAreaView>
  );
}
