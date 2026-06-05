import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { Linking, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Brand } from "@/components/brand";
import { useAuth } from "@/lib/auth";

export default function TeacherProfileScreen() {
  const { user, signOut } = useAuth();
  const isSolo = user?.institution_id == null;

  return (
    <SafeAreaView className="flex-1 bg-slate-50">
      <ScrollView contentContainerClassName="px-5 py-6 gap-5">
        <View className="items-center gap-1 py-2">
          <Brand />
        </View>

        <View className="rounded-2xl border border-slate-200 bg-white p-5">
          <Text className="text-sm text-slate-500">Hesabın</Text>
          <Text className="mt-1 text-xl font-bold text-slate-900">{user?.full_name ?? "—"}</Text>
          <View className="mt-3 flex-row items-center gap-2">
            <View className="rounded-full bg-brand-50 px-2.5 py-1">
              <Text className="text-xs font-semibold text-brand-700">Koç</Text>
            </View>
            <Text className="text-xs text-slate-400">{user?.email}</Text>
          </View>
        </View>

        {isSolo ? (
          <Pressable
            onPress={() => router.push("/teacher-plan")}
            className="flex-row items-center justify-between rounded-2xl border border-slate-200 bg-white px-5 py-4 active:bg-slate-50"
          >
            <View className="flex-row items-center gap-3">
              <Ionicons name="diamond-outline" size={20} color="#0e7490" />
              <View>
                <Text className="text-[15px] font-medium text-slate-900">Paketim</Text>
                <Text className="mt-0.5 text-xs text-slate-500">Plan, yapay zekâ kredisi, yükseltme</Text>
              </View>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
          </Pressable>
        ) : null}

        <Pressable
          onPress={() => void Linking.openURL("https://rotam.etutkoc.com/teacher/dashboard")}
          className="rounded-2xl border border-slate-200 bg-white px-5 py-4 active:bg-slate-50"
        >
          <Text className="text-[15px] font-medium text-slate-900">Web paneli aç</Text>
          <Text className="mt-0.5 text-xs text-slate-500">Kütüphane, kaynak, akademik yıl ve daha fazlası (web)</Text>
        </Pressable>

        <Pressable
          onPress={() => void Linking.openURL("https://rotam.etutkoc.com/me/account")}
          className="rounded-2xl border border-slate-200 bg-white px-5 py-4 active:bg-slate-50"
        >
          <Text className="text-[15px] font-medium text-slate-900">Hesap & Şifre</Text>
          <Text className="mt-0.5 text-xs text-slate-500">Şifreni değiştir, hesabını yönet (web)</Text>
        </Pressable>

        <Pressable
          onPress={() => void signOut()}
          className="rounded-2xl border border-rose-200 bg-white px-5 py-4 active:bg-rose-50"
        >
          <Text className="text-[15px] font-semibold text-rose-600">Çıkış yap</Text>
        </Pressable>
      </ScrollView>
    </SafeAreaView>
  );
}
