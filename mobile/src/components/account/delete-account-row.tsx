import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

/**
 * Profil ekranlarında "Hesabı sil" girişi (Apple 5.1.1(v)).
 * 4 rolün profilinde de aynı satır → /account-delete tam akışına gider.
 */
export function DeleteAccountRow() {
  return (
    <Pressable
      onPress={() => router.push("/account-delete")}
      className="flex-row items-center justify-between rounded-2xl border border-rose-200 bg-white px-5 py-4 active:bg-rose-50"
    >
      <View className="flex-row items-center gap-3">
        <Ionicons name="trash-outline" size={20} color="#e11d48" />
        <View>
          <Text className="text-[15px] font-medium text-rose-600">Hesabı sil</Text>
          <Text className="mt-0.5 text-xs text-slate-400">Hesabını ve verilerini kalıcı olarak sil</Text>
        </View>
      </View>
      <Ionicons name="chevron-forward" size={18} color="#fda4af" />
    </Pressable>
  );
}
