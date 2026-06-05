import { Ionicons } from "@expo/vector-icons";
import { Text } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

export default function TeacherBillingScreen() {
  return (
    <SafeAreaView className="flex-1 items-center justify-center gap-3 bg-slate-50 px-8">
      <Ionicons name="wallet-outline" size={40} color="#94a3b8" />
      <Text className="text-base font-semibold text-slate-700">Tahsilat</Text>
      <Text className="text-center text-sm text-slate-500">
        Öğrenci başına ücret, yapılan seans ve ödeme takibi yakında bu sekmede.
      </Text>
    </SafeAreaView>
  );
}
