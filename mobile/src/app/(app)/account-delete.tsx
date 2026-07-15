import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  cancelAccountDelete,
  getMyAccount,
  meKeys,
  requestAccountDelete,
} from "@/lib/me";

/**
 * Hesap silme (Apple 5.1.1(v)) — uygulama içi tam akış.
 *
 * KVKK gereği silme 30 gün sonra KALICI olarak uygulanır; bu süre içinde
 * kullanıcı talebi iptal edebilir. Geçici "dondurma" DEĞİLDİR — süre sonunda
 * hesap ve kişisel veriler geri getirilemez şekilde silinir.
 */

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
}

export default function AccountDeleteScreen() {
  const { signOut } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: meKeys.account, queryFn: getMyAccount });
  const [error, setError] = React.useState<string | null>(null);

  const deleteMut = useMutation({
    mutationFn: () => requestAccountDelete(),
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: meKeys.account });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "İşlem tamamlanamadı. Tekrar dene."),
  });

  const cancelMut = useMutation({
    mutationFn: (id: number) => cancelAccountDelete(id),
    onSuccess: () => {
      setError(null);
      void qc.invalidateQueries({ queryKey: meKeys.account });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : "İşlem tamamlanamadı. Tekrar dene."),
  });

  function confirmDelete() {
    Alert.alert(
      "Hesabını silmek istiyor musun?",
      "Hesabın ve kişisel verilerin 30 gün sonra kalıcı olarak silinir. Bu süre içinde fikrini değiştirirsen talebi iptal edebilirsin.",
      [
        { text: "Vazgeç", style: "cancel" },
        { text: "Hesabımı sil", style: "destructive", onPress: () => deleteMut.mutate() },
      ],
    );
  }

  const kvkk = q.data?.kvkk_status;
  const pending = kvkk?.has_pending_delete === true;

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
        <Text className="text-base font-semibold text-slate-800">Hesabı sil</Text>
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView contentContainerClassName="px-5 py-4 gap-4">
          {pending ? (
            <>
              {/* Bekleyen silme talebi */}
              <View className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <View className="flex-row items-center gap-2">
                  <Ionicons name="time-outline" size={20} color="#b45309" />
                  <Text className="flex-1 text-[15px] font-bold text-amber-900">Silme talebin alındı</Text>
                </View>
                <Text className="mt-2 text-sm leading-relaxed text-amber-800">
                  Hesabın ve kişisel verilerin{" "}
                  <Text className="font-bold">{fmtDate(kvkk?.pending_delete_scheduled_at ?? null)}</Text>{" "}
                  tarihinde kalıcı olarak silinecek. O tarihe kadar talebi iptal edebilirsin.
                </Text>
              </View>

              {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}

              <Pressable
                onPress={() => {
                  const id = kvkk?.pending_delete_request_id;
                  if (id != null) cancelMut.mutate(id);
                }}
                disabled={cancelMut.isPending}
                className="items-center rounded-2xl border border-slate-300 bg-white py-4 active:bg-slate-50"
              >
                {cancelMut.isPending ? (
                  <ActivityIndicator color="#334155" />
                ) : (
                  <Text className="text-base font-semibold text-slate-700">Silme talebini iptal et</Text>
                )}
              </Pressable>

              <Pressable
                onPress={() => void signOut()}
                className="items-center rounded-2xl border border-slate-200 bg-white py-4 active:bg-slate-50"
              >
                <Text className="text-base font-medium text-slate-500">Çıkış yap</Text>
              </Pressable>
            </>
          ) : (
            <>
              {/* Bilgilendirme */}
              <View className="rounded-2xl border border-rose-200 bg-rose-50 p-4">
                <View className="flex-row items-center gap-2">
                  <Ionicons name="warning-outline" size={20} color="#be123c" />
                  <Text className="flex-1 text-[15px] font-bold text-rose-900">Bu işlem kalıcıdır</Text>
                </View>
                <Text className="mt-2 text-sm leading-relaxed text-rose-800">
                  Hesabını sildiğinde profil bilgilerin, programların, deneme sonuçların ve
                  hesabına bağlı tüm kişisel veriler silinir.
                </Text>
              </View>

              <View className="rounded-2xl border border-slate-200 bg-white p-4">
                <Text className="text-[15px] font-bold text-slate-900">Nasıl işler?</Text>
                <View className="mt-2 gap-2">
                  <Bullet text="Talebin hemen kaydedilir; hesabın 30 gün sonra kalıcı olarak silinir (yasal saklama süreci)." />
                  <Bullet text="Bu 30 gün içinde fikrini değiştirirsen bu ekrandan talebi iptal edebilirsin." />
                  <Bullet text="Süre dolduğunda silme geri alınamaz." />
                </View>
              </View>

              {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}

              <Pressable
                onPress={confirmDelete}
                disabled={deleteMut.isPending}
                className="items-center rounded-2xl bg-rose-600 py-4 active:bg-rose-700"
              >
                {deleteMut.isPending ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text className="text-base font-bold text-white">Hesabımı kalıcı olarak sil</Text>
                )}
              </Pressable>

              <Pressable onPress={() => router.back()} className="items-center py-2">
                <Text className="text-sm text-slate-500">Vazgeç</Text>
              </Pressable>
            </>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

function Bullet({ text }: { text: string }) {
  return (
    <View className="flex-row gap-2">
      <Text className="text-sm text-slate-400">•</Text>
      <Text className="flex-1 text-sm leading-relaxed text-slate-600">{text}</Text>
    </View>
  );
}
