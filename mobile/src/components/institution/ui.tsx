import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { ActivityIndicator, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";

/** Backend renk ipucu (rate_color/net_pct_color/score_color) → mobil ton. */
export function toneFromColor(color: string | null | undefined): { text: string; bg: string; bar: string; border: string } {
  switch ((color ?? "").toLowerCase()) {
    case "emerald":
    case "green":
      return { text: "text-emerald-700", bg: "bg-emerald-50", bar: "bg-emerald-500", border: "border-l-emerald-500" };
    case "amber":
    case "yellow":
    case "orange":
      return { text: "text-amber-700", bg: "bg-amber-50", bar: "bg-amber-400", border: "border-l-amber-400" };
    case "rose":
    case "red":
      return { text: "text-rose-700", bg: "bg-rose-50", bar: "bg-rose-500", border: "border-l-rose-500" };
    case "sky":
    case "blue":
      return { text: "text-sky-700", bg: "bg-sky-50", bar: "bg-sky-500", border: "border-l-sky-500" };
    case "violet":
      return { text: "text-violet-700", bg: "bg-violet-50", bar: "bg-violet-500", border: "border-l-violet-500" };
    default:
      return { text: "text-slate-600", bg: "bg-slate-50", bar: "bg-slate-300", border: "border-l-slate-200" };
  }
}

/** Sayısal orana göre D4 eşikleri (≥70 yeşil / ≥40 amber / <40 kırmızı). */
export function rateTone(pct: number | null | undefined) {
  if (pct == null) return toneFromColor("slate");
  if (pct >= 70) return toneFromColor("emerald");
  if (pct >= 40) return toneFromColor("amber");
  return toneFromColor("rose");
}

export function pctText(v: number | null | undefined): string {
  return v == null ? "—" : `%${Math.round(v)}`;
}

/** Standart ekran iskeleti: başlık + geri + query loading/error/refresh. */
export function InstitutionScreen<T>({
  title,
  query,
  headerRight,
  demoContext,
  children,
}: {
  title: string;
  query: {
    isLoading: boolean;
    isError: boolean;
    data: T | undefined;
    refetch: () => void;
    isRefetching: boolean;
  };
  headerRight?: React.ReactNode;
  /** Verilirse ScrollView başında "▶ Nasıl kullanılır?" rozeti (kurum demosu). */
  demoContext?: string;
  children: (data: T) => React.ReactNode;
}) {
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
        <Text className="flex-1 text-base font-semibold text-slate-800" numberOfLines={1}>
          {title}
        </Text>
        {headerRight}
      </View>

      {query.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : query.isError || query.data === undefined ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => query.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView
          className="flex-1"
          contentContainerClassName="px-4 py-4 gap-3"
          refreshControl={<RefreshControl refreshing={query.isRefetching} onRefresh={() => query.refetch()} tintColor="#0e7490" />}
        >
          {demoContext ? <DemoHint contextKey={demoContext} role="institution_admin" /> : null}
          {children(query.data)}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

export function Kpi({ label, value, sub, tone = "text-slate-900" }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <View className="flex-1 rounded-2xl border border-slate-200 bg-white p-3">
      <Text className="text-[11px] font-medium text-slate-400">{label}</Text>
      <Text className={cn("mt-1 text-xl font-extrabold", tone)} numberOfLines={1}>
        {value}
      </Text>
      {sub ? <Text className="text-[10px] text-slate-400" numberOfLines={1}>{sub}</Text> : null}
    </View>
  );
}

/** KPI'ları satır satır 2'li gruplar. */
export function KpiGrid({ children }: { children: React.ReactNode }) {
  const items = React.Children.toArray(children);
  const rows: React.ReactNode[][] = [];
  for (let i = 0; i < items.length; i += 2) rows.push(items.slice(i, i + 2));
  return (
    <View className="gap-3">
      {rows.map((row, i) => (
        <View key={i} className="flex-row gap-3">
          {row}
          {row.length === 1 ? <View className="flex-1" /> : null}
        </View>
      ))}
    </View>
  );
}

export function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <View className="gap-2">
      <View className="flex-row items-center justify-between px-1">
        <Text className="text-sm font-semibold text-slate-700">{title}</Text>
        {hint ? <Text className="text-[11px] text-slate-400">{hint}</Text> : null}
      </View>
      <View className="gap-2">{children}</View>
    </View>
  );
}

export function ProgressBar({ pct, tone = "bg-brand-600" }: { pct: number | null | undefined; tone?: string }) {
  const w = Math.max(0, Math.min(100, pct ?? 0));
  return (
    <View className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
      <View className={cn("h-2 rounded-full", tone)} style={{ width: `${w}%` }} />
    </View>
  );
}

export function Badge({ label, tone = "slate" }: { label: string; tone?: "slate" | "emerald" | "amber" | "rose" | "sky" | "violet" }) {
  const map = {
    slate: "bg-slate-100 text-slate-600",
    emerald: "bg-emerald-100 text-emerald-700",
    amber: "bg-amber-100 text-amber-700",
    rose: "bg-rose-100 text-rose-700",
    sky: "bg-sky-100 text-sky-700",
    violet: "bg-violet-100 text-violet-700",
  } as const;
  return (
    <View className={cn("self-start rounded-full px-2 py-0.5", map[tone].split(" ")[0])}>
      <Text className={cn("text-[11px] font-semibold", map[tone].split(" ")[1])}>{label}</Text>
    </View>
  );
}

export function Banner({ kind = "info", children }: { kind?: "info" | "warn" | "danger"; children: React.ReactNode }) {
  const map = {
    info: { box: "border-sky-200 bg-sky-50", text: "text-sky-800", icon: "information-circle" as const, color: "#0369a1" },
    warn: { box: "border-amber-200 bg-amber-50", text: "text-amber-800", icon: "warning" as const, color: "#b45309" },
    danger: { box: "border-rose-200 bg-rose-50", text: "text-rose-800", icon: "alert-circle" as const, color: "#be123c" },
  };
  const s = map[kind];
  return (
    <View className={cn("flex-row gap-2 rounded-xl border p-3", s.box)}>
      <Ionicons name={s.icon} size={16} color={s.color} />
      <Text className={cn("flex-1 text-xs", s.text)}>{children}</Text>
    </View>
  );
}

export function Empty({ text }: { text: string }) {
  return (
    <View className="items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white px-6 py-10">
      <Ionicons name="checkmark-circle-outline" size={32} color="#94a3b8" />
      <Text className="mt-2 text-center text-sm text-slate-500">{text}</Text>
    </View>
  );
}

export function InfoNote({ children }: { children: React.ReactNode }) {
  return <Text className="px-1 text-[11px] leading-4 text-slate-400">{children}</Text>;
}

/** Recharts yerine basit dikey bar trendi (haftalık oranlar gibi). */
export function MiniBars({ points }: { points: { label: string; value: number | null }[] }) {
  if (points.length === 0) return null;
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-3">
      <View className="h-24 flex-row items-end justify-between gap-1">
        {points.map((p, i) => {
          const v = p.value ?? 0;
          const t = rateTone(p.value);
          return (
            <View key={i} className="flex-1 items-center justify-end gap-1">
              <Text className="text-[8px] text-slate-400">{p.value == null ? "" : Math.round(v)}</Text>
              <View className={cn("w-full rounded-t", t.bar)} style={{ height: Math.max(3, (v / 100) * 72) }} />
              <Text className="text-[8px] text-slate-400" numberOfLines={1}>{p.label}</Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}
