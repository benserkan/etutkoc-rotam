/**
 * Paketim — mobil (2026-10-03 yeniden tasarım; web /teacher/plan ile aynı dil).
 *
 * Üç blok: DURUM (renkli etiket + üç temel bilgi) · PAKETLER (yalnız iOS,
 * App Store / StoreKit ile satın alma) · YARDIM (paket asistanı).
 * App Store 3.1.1: uygulama-dışı ödemeye (kart/web) yönlendirme YOK; web'den
 * alınmış abonelik yalnız durum olarak gösterilir. Android'de satın alma
 * yüzeyi yoktur (App Store'dan da söz edilmez).
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Alert, Linking, Platform, Pressable, Text, View } from "react-native";

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
const IOS = Platform.OS === "ios";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
}

function capLabel(max: number | null): string {
  return max == null ? "Sınırsız öğrenci" : `${max} öğrenciye kadar`;
}

type Tone = "emerald" | "amber" | "rose" | "slate";
const TONE: Record<Tone, { chip: string; border: string; bar: string }> = {
  emerald: { chip: "bg-emerald-600", border: "border-emerald-300", bar: "bg-emerald-500" },
  amber: { chip: "bg-amber-500", border: "border-amber-300", bar: "bg-amber-500" },
  rose: { chip: "bg-rose-600", border: "border-rose-300", bar: "bg-rose-500" },
  slate: { chip: "bg-slate-600", border: "border-slate-200", bar: "bg-slate-400" },
};

function statusInfo(d: TeacherPlanResponse): { tone: Tone; label: string } {
  if (!d.is_solo || d.status === "managed") return { tone: "slate", label: "Kurum yönetiyor" };
  if (d.status === "trialing") return { tone: "amber", label: `Deneme · ${d.trial_days_left ?? 0} gün kaldı` };
  if (d.status === "active")
    return d.subscription_status === "canceled"
      ? { tone: "amber", label: "İptal edildi" }
      : { tone: "emerald", label: "Aktif" };
  if (d.status === "past_due") return { tone: "rose", label: "Süresi doldu" };
  if ((d.status as string) === "payment_required") return { tone: "rose", label: "Ödeme bekleniyor" };
  return { tone: "slate", label: "Ücretsiz" };
}

function sentenceFor(d: TeacherPlanResponse, freeLimit: number): string {
  const appStore = d.subscription_platform === "app_store";
  const webManaged = d.subscription_platform === "iyzico" || d.subscription_platform === "manual";
  if (!d.is_solo) return d.note ?? "Paketin kurumun tarafından yönetilir.";
  if (d.status === "trialing")
    return `Denemen ${d.trial_days_left ?? 0} gün sonra bitiyor. Bitince ücretsiz pakete (${freeLimit} öğrenci, yapay zekâ kapalı) geçersin; verilerin silinmez.`;
  if (d.status === "active" && d.subscription_status === "canceled")
    return `İptal edildi. ${fmtDate(d.subscription_period_end)} tarihine kadar her şey açık.`;
  if (d.status === "active" && appStore) return "Aboneliğin App Store üzerinden kendiliğinden yenilenir.";
  if (d.status === "active" && webManaged)
    return `Her şey açık. Aboneliğin web hesabın üzerinden yönetiliyor; dönem sonu ${fmtDate(d.subscription_period_end)}.`;
  if (d.status === "active") return `Her şey açık. Dönem sonu ${fmtDate(d.subscription_period_end)}.`;
  if (d.status === "past_due")
    return "Aboneliğinin süresi doldu. Yenilenene kadar yeni program kuramazsın; öğrencilerin ve verilerin duruyor.";
  const over = d.student_count > freeLimit ? ` ${d.student_count} öğrencin olduğu için yeni programlama kilitli.` : "";
  return `Ücretsiz pakettesin: ${freeLimit} öğrenciye kadar takip, yapay zekâ kapalı.${over}`;
}

function Fact({ icon, label, value, hint, alert }: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  hint?: string;
  alert?: boolean;
}) {
  return (
    <View className="rounded-2xl bg-slate-100 px-4 py-3">
      <View className="flex-row items-center gap-1.5">
        <Ionicons name={icon} size={14} color="#64748b" />
        <Text className="text-xs font-medium text-slate-500">{label}</Text>
      </View>
      <Text className={cn("mt-1 text-lg font-bold", alert ? "text-rose-700" : "text-slate-900")}>{value}</Text>
      {hint ? <Text className="text-xs text-slate-500">{hint}</Text> : null}
    </View>
  );
}

function StatusHero({ data }: { data: TeacherPlanResponse }) {
  const s = statusInfo(data);
  const freeLimit = data.options.find((o) => o.code === "solo_free")?.max_students ?? 3;
  const current = data.options.find((o) => o.code === data.plan_code);
  const title =
    data.status === "trialing" && data.post_trial_plan && data.post_trial_plan !== "solo_free"
      ? `${data.post_trial_plan_label} denemesi`
      : data.plan_label;
  const aiOn = data.ai_premium && (data.status === "trialing" || data.status === "active");
  const aiLeft = Math.max(0, data.ai_credits_allocated - data.ai_credits_used);
  let dateLabel = "Durum";
  let dateValue = "—";
  if (data.status === "trialing") {
    dateLabel = "Deneme bitişi";
    dateValue = `${data.trial_days_left ?? 0} gün sonra`;
  } else if (data.status === "active") {
    dateLabel = data.subscription_status === "canceled" ? "Bitiş" : "Dönem sonu";
    dateValue = fmtDate(data.subscription_period_end);
  } else if (data.status === "past_due") {
    dateLabel = "Süre";
    dateValue = "Doldu";
  }
  return (
    <View className={cn("rounded-3xl border-2 bg-white p-5", TONE[s.tone].border)}>
      <View className={cn("self-start flex-row items-center gap-1.5 rounded-full px-3 py-1", TONE[s.tone].chip)}>
        <View className="h-1.5 w-1.5 rounded-full bg-white" />
        <Text className="text-xs font-semibold text-white">{s.label}</Text>
      </View>
      <Text className="mt-3 text-3xl font-extrabold text-slate-900">{title}</Text>
      <Text className="mt-2 text-base leading-6 text-slate-600">{sentenceFor(data, freeLimit)}</Text>
      {data.is_solo ? (
        <View className="mt-5 gap-2.5">
          <Fact
            icon="people-outline"
            label="Öğrenci"
            value={`${data.student_count} aktif`}
            hint={data.status === "trialing" ? "denemede sınırsız" : current ? capLabel(current.max_students).toLowerCase() : undefined}
            alert={data.status === "free" && data.student_count > freeLimit}
          />
          <Fact
            icon="sparkles-outline"
            label="Yapay zekâ"
            value={aiOn ? `${aiLeft.toLocaleString("tr-TR")} kredi` : "Kapalı"}
            hint={aiOn ? "bu ay kalan" : "ücretli pakette açılır"}
          />
          {data.status !== "free" ? <Fact icon="calendar-outline" label={dateLabel} value={dateValue} /> : null}
        </View>
      ) : null}
    </View>
  );
}

function TierRow({ option, selected, fits, n, price, credits, tag, onSelect }: {
  option: TeacherPlanOption;
  selected: boolean;
  fits: boolean;
  n: number;
  price: string;
  credits: number | null;
  tag: string | null;
  onSelect: () => void;
}) {
  return (
    <Pressable
      onPress={onSelect}
      disabled={!fits}
      accessibilityRole="radio"
      accessibilityState={{ checked: selected, disabled: !fits }}
      className={cn(
        "flex-row items-start gap-3 rounded-2xl border-2 bg-white p-4",
        selected ? "border-brand-600" : "border-slate-200",
        !fits && "opacity-60",
      )}
    >
      <View
        className={cn(
          "mt-1 h-5 w-5 items-center justify-center rounded-full border-2",
          selected ? "border-brand-600 bg-brand-600" : "border-slate-300",
        )}
      >
        {selected ? <Ionicons name="checkmark" size={12} color="#fff" /> : null}
      </View>
      <View className="flex-1">
        {tag ? (
          <View className="mb-1.5 self-start rounded-full bg-brand-700 px-2 py-0.5">
            <Text className="text-[11px] font-semibold text-white">{tag}</Text>
          </View>
        ) : null}
        <Text className="text-lg font-bold text-slate-900">{option.label}</Text>
        <Text className="text-sm text-slate-500">{capLabel(option.max_students)}</Text>
        <View className="mt-2 flex-row items-baseline gap-1">
          <Text className="text-2xl font-extrabold text-slate-900">{price}</Text>
          <Text className="text-sm text-slate-500">/ay</Text>
        </View>
        {credits ? (
          <Text className="mt-0.5 text-sm text-slate-500">Ayda {credits.toLocaleString("tr-TR")} yapay zekâ kredisi</Text>
        ) : null}
        {!fits ? <Text className="mt-1.5 text-xs font-semibold text-rose-700">{n} öğrencine yetmiyor</Text> : null}
      </View>
    </Pressable>
  );
}

export default function TeacherPlanScreen() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const params = useLocalSearchParams<{ select?: string }>();
  const q = useQuery({ queryKey: teacherPlanKeys.plan, queryFn: getTeacherPlan });
  const featuresQ = useQuery({ queryKey: ["pricing", "plan-features"], queryFn: getPlanFeatures, staleTime: 10 * 60_000 });
  const planFeatures = featuresQ.data ?? {};

  const [packages, setPackages] = React.useState<IapPackage[]>([]);
  const [pkgError, setPkgError] = React.useState(false);
  const [buying, setBuying] = React.useState<string | null>(null);
  const [restoring, setRestoring] = React.useState(false);
  const [picked, setPicked] = React.useState<string | null>(null);

  React.useEffect(() => {
    let mounted = true;
    if (!iapSupported()) return;
    getIapPackages()
      .then((p) => mounted && setPackages(p))
      .catch(() => mounted && setPkgError(true));
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
      Alert.alert(res.active ? "Tamamdır" : "Satın alma alındı",
        res.active ? res.message || "Aboneliğin aktif." : "Aboneliğin birkaç dakika içinde otomatik aktifleşecek.");
    } catch {
      Alert.alert("Satın alma alındı", "Doğrulama birkaç dakika sürebilir; paketin otomatik aktifleşecek.");
    }
  }, [syncMut]);

  const buy = React.useCallback(async (pkg: IapPackage) => {
    setBuying(pkg.productId);
    try {
      const r = await purchaseIapPackage(pkg);
      if (r.ok) await finishPurchase();
    } catch {
      Alert.alert("Satın alma tamamlanamadı", "Tekrar dene. Sorun sürerse Yardım'a yaz.");
    } finally {
      setBuying(null);
    }
  }, [finishPurchase]);

  const restore = React.useCallback(async () => {
    setRestoring(true);
    try {
      await restoreIapPurchases();
      await finishPurchase();
    } catch {
      Alert.alert("Geri yükleme tamamlanamadı", "Tekrar dene.");
    } finally {
      setRestoring(false);
    }
  }, [finishPurchase]);

  const helpButton = (
    <Pressable
      onPress={() => router.push({ pathname: "/assistant", params: { page: "/teacher/plan" } } as never)}
      accessibilityLabel="Paket asistanı"
      className="flex-row items-center gap-1.5 rounded-full bg-brand-700 px-3.5 py-2 active:bg-brand-800"
    >
      <Ionicons name="chatbubble-ellipses-outline" size={16} color="#fff" />
      <Text className="text-sm font-semibold text-white">Yardım</Text>
    </Pressable>
  );

  return (
    <InstitutionScreen title="Paketim" query={q} headerRight={helpButton}>
      {(data: TeacherPlanResponse) => {
        if (user?.institution_id != null || !data.is_solo) {
          return <StatusHero data={data} />;
        }
        const n = data.student_count;
        const webManaged =
          (data.subscription_platform === "iyzico" || data.subscription_platform === "manual") &&
          (data.subscription_status === "active" || data.subscription_status === "canceled");
        const appStoreActive =
          data.subscription_platform === "app_store" &&
          (data.subscription_status === "active" || data.subscription_status === "canceled");
        const tiers = data.options.filter((o) => (PAID_TIERS as readonly string[]).includes(o.code));
        const fits = (o: TeacherPlanOption) => o.max_students == null || n <= o.max_students;
        const pkgFor = (code: string) => packages.find((p) => p.tierCode === code);
        const isPaidState = data.status === "active" || data.status === "past_due";
        const pref =
          tiers.find((t) => t.code === (params.select ?? "")) ??
          (isPaidState ? tiers.find((t) => t.code === data.plan_code) : undefined) ??
          tiers.find((t) => t.code === data.post_trial_plan) ??
          tiers.find((t) => t.code === data.recommended_plan);
        const suggested = pref && fits(pref) ? pref : tiers.find(fits);
        const selected = tiers.find((t) => t.code === picked) ?? suggested;
        const showStore = IOS && iapSupported() && !webManaged;
        const pct = data.ai_credits_allocated > 0 ? Math.min(100, Math.round((data.ai_credits_used / data.ai_credits_allocated) * 100)) : 0;
        const left = Math.max(0, data.ai_credits_allocated - data.ai_credits_used);
        const barTone: Tone = left === 0 ? "rose" : pct >= 80 ? "amber" : "emerald";

        return (
          <View className="gap-6 pb-8">
            <StatusHero data={data} />

            {(data.status === "trialing" || data.status === "active") && data.ai_credits_allocated > 0 ? (
              <View className="rounded-3xl border border-slate-200 bg-white p-5">
                <View className="flex-row items-baseline justify-between">
                  <Text className="text-lg font-bold text-slate-900">Yapay zekâ kredisi</Text>
                  <Text className="text-sm text-slate-500">
                    <Text className="font-bold text-slate-900">{left.toLocaleString("tr-TR")}</Text> / {data.ai_credits_allocated.toLocaleString("tr-TR")}
                  </Text>
                </View>
                <View className="mt-3 h-3 overflow-hidden rounded-full bg-slate-100">
                  <View className={cn("h-full rounded-full", TONE[barTone].bar)} style={{ width: `${pct}%` }} />
                </View>
                <Text className="mt-3 text-sm leading-5 text-slate-500">
                  Karne okuma, veli yorumu, seans notu gibi yapay zekâ işlerinde harcanır; her ay başında yenilenir.
                </Text>
              </View>
            ) : null}

            {webManaged || appStoreActive ? null : showStore ? (
              <View className="gap-3">
                <Text className="text-lg font-bold text-slate-900">Paketler</Text>
                <Text className="-mt-2 text-sm text-slate-500">
                  {n} aktif öğrencin var. Öğrenci sayına yetmeyen paket seçilemez.
                </Text>
                {pkgError || packages.length === 0 ? (
                  <View className="rounded-2xl border border-slate-200 bg-white p-4">
                    <Text className="text-sm text-slate-600">
                      Paketler yüklenemedi. İnternet bağlantını kontrol edip ekranı aşağı çekerek yenile.
                    </Text>
                  </View>
                ) : null}
                {tiers.map((o) => (
                  <TierRow
                    key={o.code}
                    option={o}
                    selected={o.code === selected?.code}
                    fits={fits(o)}
                    n={n}
                    price={pkgFor(o.code)?.priceString || `${o.price_monthly_try.toLocaleString("tr-TR")} ₺`}
                    credits={null}
                    tag={
                      isPaidState && o.code === data.plan_code
                        ? "Mevcut paketin"
                        : o.code === data.post_trial_plan
                          ? "Kayıtta seçtiğin"
                          : o.code === data.recommended_plan
                            ? "Öğrenci sayına uygun"
                            : null
                    }
                    onSelect={() => setPicked(o.code)}
                  />
                ))}
                {selected ? (
                  <View className="rounded-3xl bg-slate-100 p-5">
                    <Text className="text-base font-bold text-slate-900">{selected.label} paketinde neler var?</Text>
                    <View className="mt-3 gap-2">
                      {(planFeatures[selected.code] ?? []).map((f) => (
                        <View key={f} className="flex-row items-start gap-2">
                          <Ionicons name="checkmark" size={16} color="#059669" style={{ marginTop: 2 }} />
                          <Text className="flex-1 text-sm leading-5 text-slate-700">{f}</Text>
                        </View>
                      ))}
                    </View>
                    {pkgFor(selected.code) ? (
                      <Pressable
                        disabled={!!buying || !fits(selected)}
                        onPress={() => void buy(pkgFor(selected.code)!)}
                        className={cn(
                          "mt-5 h-12 flex-row items-center justify-center gap-2 rounded-2xl",
                          buying ? "bg-slate-300" : "bg-brand-700 active:bg-brand-800",
                        )}
                      >
                        {buying ? (
                          <ActivityIndicator color="#fff" />
                        ) : (
                          <Text className="text-base font-bold text-white">
                            Satın al · {pkgFor(selected.code)!.priceString}/ay
                          </Text>
                        )}
                      </Pressable>
                    ) : null}
                  </View>
                ) : null}
                <Text className="text-xs leading-5 text-slate-400">
                  Abonelik App Store hesabından tahsil edilir ve dönem sonunda kendiliğinden yenilenir.
                  App Store → Abonelikler&apos;den istediğin zaman iptal edebilirsin; iptal dönem sonunda geçerli olur.
                </Text>
                <Pressable
                  disabled={restoring}
                  onPress={() => void restore()}
                  className="items-center rounded-2xl border border-slate-300 py-3 active:bg-slate-100"
                >
                  {restoring ? (
                    <ActivityIndicator size="small" color="#334155" />
                  ) : (
                    <Text className="text-sm font-semibold text-slate-700">Satın alımları geri yükle</Text>
                  )}
                </Pressable>
              </View>
            ) : (
              <View className="rounded-3xl border border-slate-200 bg-white p-5">
                <Text className="text-base font-semibold text-slate-900">
                  {IOS ? "Satın alma bu sürümde kullanılamıyor" : "Paket işlemleri bu cihazda yapılamıyor"}
                </Text>
                <Text className="mt-1 text-sm leading-5 text-slate-500">
                  {IOS
                    ? "Paket almak için uygulamayı App Store'dan güncelle."
                    : "Bir sorunun varsa Yardım'dan bize yazabilirsin."}
                </Text>
              </View>
            )}

            {appStoreActive ? (
              <Pressable
                onPress={() => void Linking.openURL("https://apps.apple.com/account/subscriptions")}
                className="flex-row items-center justify-center gap-2 rounded-2xl border border-slate-300 bg-white py-3.5 active:bg-slate-50"
              >
                <Ionicons name="settings-outline" size={18} color="#0e7490" />
                <Text className="text-sm font-semibold text-brand-700">Aboneliği yönet (App Store)</Text>
              </Pressable>
            ) : null}

            <Pressable
              onPress={() => router.push({ pathname: "/assistant", params: { page: "/teacher/plan" } } as never)}
              className="flex-row items-center gap-3 rounded-3xl bg-slate-100 px-5 py-4 active:bg-slate-200"
            >
              <Ionicons name="chatbubble-ellipses-outline" size={22} color="#0e7490" />
              <View className="flex-1">
                <Text className="text-sm font-semibold text-slate-900">Kafana takılan bir şey mi var?</Text>
                <Text className="text-xs leading-4 text-slate-500">
                  Paket asistanı hangi paketin uygun olduğunu ve krediyi anında anlatır.
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#94a3b8" />
            </Pressable>

            <View className="flex-row items-center justify-center gap-4">
              <Pressable onPress={() => void Linking.openURL("https://rotam.etutkoc.com/kullanim-sartlari")}>
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
