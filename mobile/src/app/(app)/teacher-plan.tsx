/**
 * Paketim — Apple IAP abonelik ekranı (App Store 3.1.1 çözümü).
 *
 * Solo koç paketleri burada App Store'un kendi satın alma sayfası (StoreKit)
 * ile satılır; fiyatlar StoreKit'ten yerelleştirilmiş gelir. Uygulama-dışı
 * ödemeye yönlendirme YOKTUR. Web'den (iyzico) satın alınmış abonelik yalnız
 * durum olarak gösterilir (3.1.3(b): aynı abonelik burada IAP ile de satılır).
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { ActivityIndicator, Alert, Linking, Pressable, Text, View } from "react-native";

import { InstitutionScreen } from "@/components/institution/ui";
import { useAuth } from "@/lib/auth";
import {
  getIapPackages,
  iapSupported,
  purchaseIapPackage,
  restoreIapPurchases,
  type IapPackage,
} from "@/lib/iap";
import {
  getPlanFeatures,
  getTeacherPlan,
  syncIapPurchase,
  teacherPlanKeys,
  type TeacherPlanOption,
  type TeacherPlanResponse,
} from "@/lib/teacher";
import { cn } from "@/lib/utils";

const PAID_TIERS = ["solo_pro", "solo_elite", "solo_unlimited"] as const;

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
}

function StatusBadge({ data }: { data: TeacherPlanResponse }) {
  let label = "Ücretsiz";
  let cls = "bg-slate-100 text-slate-700";
  if (data.status === "trialing") {
    label = `Deneme — ${data.trial_days_left ?? 0} gün kaldı`;
    cls = "bg-cyan-100 text-cyan-800";
  } else if (data.status === "active") {
    label = data.subscription_status === "canceled" ? "İptal edildi (dönem sonuna kadar)" : "Aktif";
    cls = data.subscription_status === "canceled" ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800";
  } else if (data.status === "past_due") {
    label = "Yenileme gerekli";
    cls = "bg-rose-100 text-rose-800";
  }
  return (
    <View className={cn("rounded-full px-2.5 py-1", cls.split(" ")[0])}>
      <Text className={cn("text-xs font-semibold", cls.split(" ").slice(1).join(" "))}>{label}</Text>
    </View>
  );
}

function CurrentPlanCard({ data }: { data: TeacherPlanResponse }) {
  const appStore = data.subscription_platform === "app_store";
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-5">
      <View className="flex-row items-center justify-between gap-2">
        <Text className="text-sm text-slate-500">Mevcut paket</Text>
        <StatusBadge data={data} />
      </View>
      <Text className="mt-1 text-xl font-bold text-slate-900">{data.plan_label}</Text>
      {data.status === "active" && data.subscription_period_end ? (
        <Text className="mt-1 text-xs text-slate-500">
          {data.subscription_status === "canceled" ? "Erişim bitişi: " : "Yenileme: "}
          {fmtDate(data.subscription_period_end)}
        </Text>
      ) : null}
      {data.status === "trialing" && data.post_trial_plan_label ? (
        <Text className="mt-1 text-xs text-slate-500">
          Deneme bitince seçtiğin paket: {data.post_trial_plan_label}
        </Text>
      ) : null}
      {data.ai_credits_allocated > 0 ? (
        <Text className="mt-2 text-xs text-slate-500">
          Yapay zekâ kredisi: {data.ai_credits_used}/{data.ai_credits_allocated} kullanıldı
        </Text>
      ) : null}
      {appStore ? (
        <Pressable
          onPress={() => void Linking.openURL("https://apps.apple.com/account/subscriptions")}
          className="mt-3 flex-row items-center justify-center gap-1.5 rounded-xl border border-slate-300 py-2.5 active:bg-slate-50"
        >
          <Ionicons name="settings-outline" size={16} color="#0e7490" />
          <Text className="text-sm font-semibold text-brand-700">Aboneliği yönet (App Store)</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function TierCard({
  option,
  pkg,
  features,
  isBusy,
  onBuy,
}: {
  option: TeacherPlanOption;
  pkg: IapPackage | undefined;
  features: string[];
  isBusy: boolean;
  onBuy: (pkg: IapPackage) => void;
}) {
  const capacity =
    option.max_students == null ? "Sınırsız öğrenci" : `${option.max_students} öğrenciye kadar`;
  const price = pkg?.priceString || `${option.price_monthly_try.toLocaleString("tr-TR")} ₺`;
  return (
    <View
      className={cn(
        "rounded-2xl border bg-white p-4",
        option.is_current ? "border-emerald-300" : option.is_recommended ? "border-cyan-300" : "border-slate-200",
      )}
    >
      <View className="flex-row items-center justify-between gap-2">
        <Text className="text-base font-bold text-slate-900">{option.label}</Text>
        {option.is_current ? (
          <View className="rounded-full bg-emerald-100 px-2 py-0.5">
            <Text className="text-[11px] font-semibold text-emerald-800">Aktif paket</Text>
          </View>
        ) : option.is_recommended ? (
          <View className="rounded-full bg-cyan-100 px-2 py-0.5">
            <Text className="text-[11px] font-semibold text-cyan-800">Sana uygun</Text>
          </View>
        ) : null}
      </View>
      <Text className="mt-0.5 text-xs text-slate-500">{capacity} · yapay zekâ dahil</Text>
      <View className="mt-2 flex-row items-baseline gap-1">
        <Text className="text-2xl font-extrabold text-slate-900">{price}</Text>
        <Text className="text-xs text-slate-500">/ ay</Text>
      </View>
      {features.length > 0 ? (
        <View className="mt-2 gap-1">
          {features.slice(0, 4).map((f) => (
            <View key={f} className="flex-row items-start gap-1.5">
              <Ionicons name="checkmark-circle" size={14} color="#059669" style={{ marginTop: 2 }} />
              <Text className="flex-1 text-xs leading-4 text-slate-600">{f}</Text>
            </View>
          ))}
        </View>
      ) : null}
      {pkg && !option.is_current ? (
        <Pressable
          disabled={isBusy}
          onPress={() => onBuy(pkg)}
          className={cn(
            "mt-3 items-center rounded-xl py-2.5",
            isBusy ? "bg-slate-300" : "bg-brand-700 active:bg-brand-800",
          )}
        >
          {isBusy ? (
            <ActivityIndicator color="#ffffff" size="small" />
          ) : (
            <Text className="text-sm font-semibold text-white">Satın al</Text>
          )}
        </Pressable>
      ) : null}
    </View>
  );
}

export default function TeacherPlanScreen() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: teacherPlanKeys.plan, queryFn: getTeacherPlan });
  // Paket bullet'ları — /api/v2/pricing plan_features TEK KAYNAĞI (web ile aynı).
  const featuresQ = useQuery({
    queryKey: ["pricing", "plan-features"],
    queryFn: getPlanFeatures,
    staleTime: 10 * 60_000,
  });
  const planFeatures = featuresQ.data ?? {};

  const [packages, setPackages] = React.useState<IapPackage[]>([]);
  const [pkgError, setPkgError] = React.useState(false);
  const [buying, setBuying] = React.useState<string | null>(null);
  const [restoring, setRestoring] = React.useState(false);

  React.useEffect(() => {
    let mounted = true;
    if (!iapSupported()) return;
    getIapPackages()
      .then((p) => {
        if (mounted) setPackages(p);
      })
      .catch(() => {
        if (mounted) setPkgError(true);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const syncMut = useMutation({
    mutationFn: syncIapPurchase,
    onSettled: () => void qc.invalidateQueries({ queryKey: teacherPlanKeys.plan }),
  });

  const finishPurchase = React.useCallback(async () => {
    try {
      const res = await syncMut.mutateAsync();
      if (res.active) {
        Alert.alert("Tamamdır", res.message || "Aboneliğin aktif.");
      } else {
        Alert.alert(
          "Satın alma alındı",
          "Aboneliğin birkaç dakika içinde otomatik aktifleşecek.",
        );
      }
    } catch {
      Alert.alert(
        "Satın alma alındı",
        "Doğrulama birkaç dakika sürebilir; paketin otomatik aktifleşecek.",
      );
    }
  }, [syncMut]);

  const buy = React.useCallback(
    async (pkg: IapPackage) => {
      setBuying(pkg.productId);
      try {
        const r = await purchaseIapPackage(pkg);
        if (r.ok) await finishPurchase();
      } catch {
        Alert.alert("Satın alma tamamlanamadı", "Lütfen tekrar dene.");
      } finally {
        setBuying(null);
      }
    },
    [finishPurchase],
  );

  const restore = React.useCallback(async () => {
    setRestoring(true);
    try {
      await restoreIapPurchases();
      await finishPurchase();
    } catch {
      Alert.alert("Geri yükleme tamamlanamadı", "Lütfen tekrar dene.");
    } finally {
      setRestoring(false);
    }
  }, [finishPurchase]);

  return (
    <InstitutionScreen title="Paketim" query={q}>
      {(data: TeacherPlanResponse) => {
        if (user?.institution_id != null || !data.is_solo) {
          return (
            <View className="rounded-2xl border border-slate-200 bg-white p-5">
              <Text className="text-sm text-slate-600">
                Paketin kurumun tarafından yönetiliyor. Yapay zekâ özellikleri kurumunun
                planına bağlıdır.
              </Text>
            </View>
          );
        }

        const webManaged =
          (data.subscription_platform === "iyzico" || data.subscription_platform === "manual") &&
          (data.subscription_status === "active" || data.subscription_status === "canceled");
        const paidOptions = data.options.filter((o) =>
          (PAID_TIERS as readonly string[]).includes(o.code),
        );
        const pkgFor = (code: string) => packages.find((p) => p.tierCode === code);
        const showStore = !webManaged;

        return (
          <View className="gap-4">
            <CurrentPlanCard data={data} />

            {webManaged ? (
              <View className="rounded-2xl border border-slate-200 bg-white p-4">
                <Text className="text-sm text-slate-600">
                  Aboneliğin web hesabın üzerinden yönetiliyor.
                </Text>
              </View>
            ) : null}

            {showStore && !iapSupported() ? (
              <View className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                <Text className="text-sm font-semibold text-amber-900">
                  Satın alma bu sürümde kullanılamıyor
                </Text>
                <Text className="mt-1 text-xs text-amber-800">
                  Paket satın almak için uygulamayı App Store&apos;dan güncelle.
                </Text>
              </View>
            ) : null}

            {showStore && iapSupported() ? (
              <View className="gap-3">
                <Text className="text-sm font-semibold text-slate-700">Paketler</Text>
                {pkgError || packages.length === 0 ? (
                  <View className="rounded-2xl border border-slate-200 bg-white p-4">
                    <Text className="text-sm text-slate-600">
                      Paketler şu an yüklenemedi. İnternet bağlantını kontrol edip ekranı
                      aşağı çekerek yenile.
                    </Text>
                  </View>
                ) : null}
                {paidOptions.map((o) => (
                  <TierCard
                    key={o.code}
                    option={o}
                    pkg={pkgFor(o.code)}
                    features={planFeatures[o.code] ?? []}
                    isBusy={buying === pkgFor(o.code)?.productId}
                    onBuy={(pkg) => void buy(pkg)}
                  />
                ))}
                <Text className="text-[11px] leading-4 text-slate-400">
                  Abonelik App Store hesabından tahsil edilir ve dönem sonunda otomatik
                  yenilenir. Dilediğin zaman App Store → Abonelikler&apos;den iptal
                  edebilirsin; iptal, mevcut dönemin sonunda geçerli olur.
                </Text>
              </View>
            ) : null}

            {iapSupported() ? (
              <Pressable
                disabled={restoring}
                onPress={() => void restore()}
                className="items-center rounded-xl border border-slate-300 py-2.5 active:bg-slate-100"
              >
                {restoring ? (
                  <ActivityIndicator size="small" color="#334155" />
                ) : (
                  <Text className="text-sm font-medium text-slate-700">
                    Satın alımları geri yükle
                  </Text>
                )}
              </Pressable>
            ) : null}

            <View className="flex-row items-center justify-center gap-4 pb-6">
              <Pressable
                onPress={() => void Linking.openURL("https://rotam.etutkoc.com/kullanim-sartlari")}
              >
                <Text className="text-xs text-slate-500 underline">Kullanım Şartları</Text>
              </Pressable>
              <Pressable onPress={() => void Linking.openURL("https://rotam.etutkoc.com/kvkk")}>
                <Text className="text-xs text-slate-500 underline">Gizlilik (KVKK)</Text>
              </Pressable>
            </View>
          </View>
        );
      }}
    </InstitutionScreen>
  );
}
