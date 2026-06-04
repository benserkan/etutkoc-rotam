import { Redirect } from "expo-router";
import { Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Brand } from "@/components/brand";
import { useAuth } from "@/lib/auth";

const ROLE_LABELS: Record<string, string> = {
  student: "Öğrenci",
  parent: "Veli",
  teacher: "Koç",
  institution_admin: "Kurum Yöneticisi",
  super_admin: "Süper Admin",
};

export default function AppHome() {
  const { user, signOut } = useAuth();

  // Öğrenci → kendi sekmeli app'ine. Diğer roller (koç/veli/kurum) sırayla
  // ekleniyor; o ana dek bilgilendirme ekranı.
  if (user?.role === "student") return <Redirect href="/(app)/student/today" />;

  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <ScrollView contentContainerClassName="px-5 py-6 gap-5">
        <View className="flex-row items-center justify-between">
          <Brand />
          <Pressable
            onPress={() => void signOut()}
            className="rounded-lg border border-slate-300 px-3 py-1.5 active:bg-slate-100"
          >
            <Text className="text-sm font-medium text-slate-600">Çıkış</Text>
          </Pressable>
        </View>

        <View className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <Text className="text-sm text-slate-500">Hoş geldin</Text>
          <Text className="mt-1 text-xl font-bold text-slate-900">
            {user?.full_name ?? "—"}
          </Text>
          <View className="mt-3 flex-row items-center gap-2">
            <View className="rounded-full bg-brand-50 px-2.5 py-1">
              <Text className="text-xs font-semibold text-brand-700">
                {user ? (ROLE_LABELS[user.role] ?? user.role) : "—"}
              </Text>
            </View>
            <Text className="text-xs text-slate-400">{user?.email}</Text>
          </View>
        </View>

        <View className="rounded-2xl border border-dashed border-slate-300 bg-white p-5">
          <Text className="text-base font-semibold text-slate-900">Mobil uygulama kuruluyor</Text>
          <Text className="mt-1 text-sm leading-relaxed text-slate-500">
            Giriş ve hesap altyapısı hazır. Rolüne özel ekranlar (program, denemeler,
            bildirimler) sırayla ekleniyor.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}
