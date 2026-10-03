import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, View } from "react-native";

/**
 * Deneme ekleme yolları (2026-10-03) — web ExamAddActions paritesi.
 * PDF aktarımı ASIL yol (konu analizi yalnız soru soru okunan denemelerden
 * beslenir) → büyük dolgulu mor kutu; elle giriş ikincil, sade kutu.
 */
export function ExamAddActions({
  onImport,
  onManual,
  note,
}: {
  onImport?: () => void;
  onManual?: () => void;
  note?: string;
}) {
  return (
    <View className="gap-3">
      {onImport ? (
        <Pressable
          onPress={onImport}
          accessibilityRole="button"
          accessibilityLabel="Deneme sonuç PDF'ini yükle"
          className="flex-row items-center gap-4 rounded-2xl bg-violet-600 p-4 active:bg-violet-700"
        >
          <View className="h-12 w-12 items-center justify-center rounded-xl bg-white/20">
            <Ionicons name="document-attach-outline" size={24} color="#ffffff" />
          </View>
          <View className="flex-1">
            <Text className="text-base font-bold text-white">Deneme sonuç PDF&apos;ini yükle</Text>
            <Text className="mt-0.5 text-sm leading-5 text-violet-100">
              Sorular tek tek okunur; konu analizi ve unutulan konular kendiliğinden dolar.
              {note ? ` ${note}` : ""}
            </Text>
            <View className="mt-2 flex-row flex-wrap gap-1.5">
              <View className="rounded-full bg-white/20 px-2 py-0.5">
                <Text className="text-xs text-white">en çok 10 MB</Text>
              </View>
              <View className="rounded-full bg-white/20 px-2 py-0.5">
                <Text className="text-xs text-white">okuma 3-5 dakika</Text>
              </View>
            </View>
          </View>
        </Pressable>
      ) : null}

      {onManual ? (
        <Pressable
          onPress={onManual}
          accessibilityRole="button"
          className="flex-row items-center gap-3 rounded-2xl border border-slate-200 bg-white p-4 active:bg-slate-50"
        >
          <View className="h-10 w-10 items-center justify-center rounded-xl bg-slate-100">
            <Ionicons name="add" size={22} color="#334155" />
          </View>
          <View className="flex-1">
            <Text className="text-sm font-semibold text-slate-900">Elle deneme gir</Text>
            <Text className="mt-0.5 text-xs leading-4 text-slate-500">
              PDF yoksa netleri yaz. Soru bilgisi olmadığı için konu analizine girmez.
            </Text>
          </View>
        </Pressable>
      ) : null}
    </View>
  );
}
