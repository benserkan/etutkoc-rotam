import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import type { TeacherPlanResponse } from "@/lib/teacher";
import { cn } from "@/lib/utils";

const STATUS: Record<string, { bg: string; text: string; label: string }> = {
  trialing: { bg: "bg-cyan-50", text: "text-cyan-700", label: "Deneme" },
  active: { bg: "bg-emerald-50", text: "text-emerald-700", label: "Aktif" },
  past_due: { bg: "bg-rose-50", text: "text-rose-700", label: "Yenileme gerekli" },
  free: { bg: "bg-slate-100", text: "text-slate-600", label: "Ücretsiz" },
  managed: { bg: "bg-violet-50", text: "text-violet-700", label: "Kurum yönetir" },
};

// NOT (Apple App Store yönergesi 3.1.1 — 2026-06-30 reddi): mobil uygulamada
// fiyat, paket yükseltme/satın alma çağrısı, "ödeme uygulama dışında düzenlenir"
// tarzı metin ve satış e-postası GÖSTERİLMEZ. Fiyatsız "yükseltme talebi" bile
// reddedildi (uygulama-dışı ödemeye yönlendirme sayıldı). Bu ekran YALNIZ mevcut
// paket durumu + yapay zekâ kullanımını gösterir; tüm satış/yükseltme web'de.
export function PlanView({
  data,
  refreshing = false,
  onRefresh,
}: {
  data: TeacherPlanResponse;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const st = STATUS[data.status] ?? STATUS.free;
  const aiPct = data.ai_credits_allocated > 0 ? Math.round((data.ai_credits_used / data.ai_credits_allocated) * 100) : 0;

  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-4 gap-4"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined}
    >
      {/* Durum kartı */}
      <View className="rounded-2xl bg-brand-700 p-5">
        <View className="flex-row items-center justify-between">
          <Text className="text-lg font-bold text-white">{data.plan_label}</Text>
          <View className={cn("rounded-full px-2.5 py-1", st.bg)}>
            <Text className={cn("text-xs font-semibold", st.text)}>{st.label}</Text>
          </View>
        </View>
        {data.trial_active && data.trial_days_left != null ? (
          <Text className="mt-1 text-xs text-brand-100">Deneme bitişine {data.trial_days_left} gün</Text>
        ) : data.subscription_period_end ? (
          <Text className="mt-1 text-xs text-brand-100">Yenileme: {data.subscription_period_end}</Text>
        ) : null}
        <Text className="mt-3 text-xs text-brand-100">{data.student_count} aktif öğrenci</Text>
      </View>

      {/* AI durumu (bilgi) */}
      <View className="rounded-2xl border border-slate-200 bg-white p-4">
        <View className="flex-row items-center gap-2">
          <Ionicons name="sparkles-outline" size={18} color="#0e7490" />
          <Text className="text-[15px] font-bold text-slate-900">Yapay zekâ</Text>
          <View className={cn("ml-auto rounded-full px-2 py-0.5", data.ai_premium ? "bg-emerald-50" : "bg-slate-100")}>
            <Text className={cn("text-[11px] font-semibold", data.ai_premium ? "text-emerald-700" : "text-slate-500")}>
              {data.ai_premium ? (data.trial_active ? "Denemede açık" : "Açık") : "Kapalı"}
            </Text>
          </View>
        </View>
        {data.ai_premium && data.ai_credits_allocated > 0 ? (
          <>
            <Text className="mt-2 text-sm text-slate-600">{data.ai_credits_used}/{data.ai_credits_allocated} kredi kullanıldı</Text>
            <View className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
              <View
                className={cn("h-full rounded-full", aiPct >= 90 ? "bg-rose-500" : aiPct >= 70 ? "bg-amber-400" : "bg-emerald-500")}
                style={{ width: `${Math.min(100, aiPct)}%` }}
              />
            </View>
          </>
        ) : !data.ai_premium ? (
          <Text className="mt-1 text-xs text-slate-400">Bu hesapta kapalı.</Text>
        ) : null}
      </View>

      {data.note ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-4">
          <Text className="text-sm text-slate-600">{data.note}</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}
