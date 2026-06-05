import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Alert, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import type { TeacherPlanOption, TeacherPlanResponse } from "@/lib/teacher";
import { cn } from "@/lib/utils";

const STATUS: Record<string, { bg: string; text: string; label: string }> = {
  trialing: { bg: "bg-cyan-50", text: "text-cyan-700", label: "Deneme" },
  active: { bg: "bg-emerald-50", text: "text-emerald-700", label: "Aktif" },
  past_due: { bg: "bg-rose-50", text: "text-rose-700", label: "Ödeme gerekli" },
  free: { bg: "bg-slate-100", text: "text-slate-600", label: "Ücretsiz" },
  managed: { bg: "bg-violet-50", text: "text-violet-700", label: "Kurum yönetir" },
};

function tl(n: number | null | undefined): string {
  return `${(n ?? 0).toLocaleString("tr-TR")} ₺`;
}

function OptionCard({
  opt,
  current,
  recommended,
  busy,
  onPick,
}: {
  opt: TeacherPlanOption;
  current: boolean;
  recommended: boolean;
  busy: boolean;
  onPick: (code: string) => void;
}) {
  return (
    <View className={cn("rounded-2xl border bg-white p-4", current ? "border-brand-500" : "border-slate-200")}>
      <View className="flex-row items-center justify-between">
        <Text className="text-[15px] font-bold text-slate-900">{opt.label}</Text>
        {current ? (
          <View className="rounded-full bg-brand-50 px-2 py-0.5"><Text className="text-[11px] font-semibold text-brand-700">Mevcut</Text></View>
        ) : recommended ? (
          <View className="rounded-full bg-amber-100 px-2 py-0.5"><Text className="text-[11px] font-semibold text-amber-700">Sana uygun</Text></View>
        ) : null}
      </View>
      <Text className="mt-1 text-2xl font-extrabold text-slate-900">{tl(opt.price_monthly_try)}<Text className="text-sm font-medium text-slate-400">/ay</Text></Text>
      <Text className="mt-0.5 text-xs text-slate-400">
        {opt.max_students == null ? "Sınırsız öğrenci" : `${opt.max_students} öğrenciye kadar`}
      </Text>
      {!current ? (
        <Pressable
          onPress={() => onPick(opt.code)}
          disabled={busy}
          className="mt-3 items-center rounded-xl bg-brand-700 py-2.5 active:bg-brand-800"
        >
          <Text className="text-sm font-semibold text-white">Bu pakete geç</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

export function PlanView({
  data,
  busy,
  onUpgrade,
  onRequestSubscription,
  refreshing = false,
  onRefresh,
}: {
  data: TeacherPlanResponse;
  busy: boolean;
  onUpgrade: (code: string) => void;
  onRequestSubscription?: (plan: string, cycle: string) => void;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const st = STATUS[data.status] ?? STATUS.free;
  const aiPct = data.ai_credits_allocated > 0 ? Math.round((data.ai_credits_used / data.ai_credits_allocated) * 100) : 0;
  const [cycle, setCycle] = React.useState<"monthly" | "academic_year">("monthly");

  // "Öde ve devam et" hedefi: önerilen → deneme sonrası → mevcut plan
  const targetCode = data.recommended_plan || data.post_trial_plan || data.plan_code;
  const targetOpt =
    data.options.find((o) => o.code === targetCode) ??
    data.options.find((o) => o.code === data.recommended_plan) ??
    data.options[0] ??
    null;
  const renewLabel =
    data.status === "trialing" ? "Üyeliğini başlat" :
    data.status === "past_due" ? "Aboneliğini yenile" :
    data.status === "active" ? "Aboneliği yenile" :
    "Üyeliğe geç";

  function requestSub() {
    if (!targetOpt || !onRequestSubscription) return;
    const cycleLabel = cycle === "academic_year" ? "akademik yıl" : "aylık";
    Alert.alert(
      renewLabel,
      `${targetOpt.label} · ${cycleLabel} için ödeme talebi gönderilsin mi? Talebin satış ekibine iletilir, ödeme sonrası aktive edilir.`,
      [
        { text: "Vazgeç", style: "cancel" },
        { text: "Talep gönder", onPress: () => onRequestSubscription(targetOpt.code, cycle) },
      ],
    );
  }

  function pick(code: string, label: string) {
    Alert.alert(
      "Paketi değiştir",
      `${label} paketine geçmek istiyor musun? Ödeme/aktivasyon ayrıca düzenlenir.`,
      [
        { text: "Vazgeç", style: "cancel" },
        { text: "Geç", onPress: () => onUpgrade(code) },
      ],
    );
  }

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

      {/* AI durumu */}
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
          <Text className="mt-1 text-xs text-slate-400">Foto/ses not ve koçluk içgörüsü ücretli pakette açılır.</Text>
        ) : null}
      </View>

      {/* Öde ve devam et / yenile */}
      {onRequestSubscription && data.is_solo && targetOpt && data.status !== "managed" ? (
        <View className="rounded-2xl border border-brand-200 bg-brand-50 p-4">
          <View className="flex-row items-center gap-2">
            <Ionicons name="card-outline" size={18} color="#0e7490" />
            <Text className="text-[15px] font-bold text-brand-800">{renewLabel}</Text>
          </View>
          <Text className="mt-1 text-xs text-brand-700">{targetOpt.label}</Text>

          {/* Döngü seçici */}
          <View className="mt-3 flex-row gap-2">
            <Pressable
              onPress={() => setCycle("monthly")}
              className={cn("flex-1 items-center rounded-xl border py-2", cycle === "monthly" ? "border-brand-600 bg-white" : "border-brand-200 bg-brand-50")}
            >
              <Text className={cn("text-sm font-semibold", cycle === "monthly" ? "text-brand-700" : "text-brand-600")}>Aylık</Text>
              <Text className="text-[11px] text-slate-500">{tl(targetOpt.price_monthly_try)}/ay</Text>
            </Pressable>
            <Pressable
              onPress={() => setCycle("academic_year")}
              className={cn("flex-1 items-center rounded-xl border py-2", cycle === "academic_year" ? "border-brand-600 bg-white" : "border-brand-200 bg-brand-50")}
            >
              <Text className={cn("text-sm font-semibold", cycle === "academic_year" ? "text-brand-700" : "text-brand-600")}>Akademik yıl</Text>
              <Text className="text-[11px] text-slate-500">{tl(targetOpt.price_monthly_try * data.annual_paid_months)} ({data.annual_paid_months} ay)</Text>
            </Pressable>
          </View>

          <Pressable
            onPress={requestSub}
            disabled={busy}
            className={cn("mt-3 items-center rounded-xl bg-brand-700 py-3", busy ? "opacity-50" : "active:bg-brand-800")}
          >
            <Text className="text-sm font-semibold text-white">Ödeme talebi gönder</Text>
          </Pressable>
          <Text className="mt-2 text-center text-[11px] text-brand-700">
            Talebin satış ekibine iletilir; ödeme sonrası aktive edilir.
          </Text>
        </View>
      ) : null}

      {/* Yükseltme seçenekleri */}
      {data.is_solo && data.options.length > 0 ? (
        <View className="gap-3">
          <Text className="px-1 text-sm font-semibold text-slate-700">Paketleri karşılaştır</Text>
          {data.options.map((o) => (
            <OptionCard
              key={o.code}
              opt={o}
              current={o.code === data.plan_code}
              recommended={o.code === data.recommended_plan && o.code !== data.plan_code}
              busy={busy}
              onPick={(c) => pick(c, o.label)}
            />
          ))}
        </View>
      ) : data.note ? (
        <View className="rounded-2xl border border-slate-200 bg-white p-4">
          <Text className="text-sm text-slate-600">{data.note}</Text>
        </View>
      ) : null}

      {data.sales_email ? (
        <Text className="px-2 text-center text-[11px] text-slate-400">
          Ödeme ve aktivasyon: {data.sales_email}
        </Text>
      ) : null}
    </ScrollView>
  );
}
