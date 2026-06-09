import * as React from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, View } from "react-native";

import { Empty, InstitutionScreen } from "@/components/institution/ui";
import { getInstitutionActivityStream, institutionKeys, type ActivityStreamItem, type ActivityStreamResponse } from "@/lib/institution";
import { cn } from "@/lib/utils";

const CAT: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap; color: string }> = {
  signup: { label: "Kayıt", icon: "person-add", color: "#0284c7" },
  invitation: { label: "Davet", icon: "mail", color: "#7c3aed" },
  commercial: { label: "Ticari", icon: "card", color: "#059669" },
  change: { label: "Değişim", icon: "swap-horizontal", color: "#d97706" },
};

function when(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function Item({ a }: { a: ActivityStreamItem }) {
  const c = CAT[a.category] ?? { label: a.category, icon: "ellipse" as const, color: "#64748b" };
  const isUpgrade = a.type === "plan_upgrade" || a.is_commercial;
  return (
    <View className={cn("flex-row gap-3 rounded-xl border bg-white p-3", isUpgrade ? "border-emerald-200" : "border-slate-200")}>
      <Ionicons name={c.icon} size={20} color={isUpgrade ? "#059669" : c.color} />
      <View className="flex-1">
        <Text className="text-sm font-semibold text-slate-900">{a.title}</Text>
        {a.subtitle ? <Text className="text-xs text-slate-500" numberOfLines={2}>{a.subtitle}</Text> : null}
        <Text className="mt-0.5 text-[11px] text-slate-400" numberOfLines={1}>
          {when(a.occurred_at)}{a.actor_name ? ` · ${a.actor_name}` : ""}{a.target_label ? ` · ${a.target_label}` : ""}
        </Text>
      </View>
    </View>
  );
}

export default function InstitutionActivityScreen() {
  const [days, setDays] = React.useState(30);
  const [type, setType] = React.useState<string | null>(null);
  const q = useQuery({
    queryKey: institutionKeys.activityStream(days),
    queryFn: () => getInstitutionActivityStream(days),
    placeholderData: keepPreviousData,
  });

  return (
    <InstitutionScreen<ActivityStreamResponse> title="Aktivite Akışı" query={q} demoContext="activity-stream">
      {(d) => {
        const items = type ? d.items.filter((i) => i.category === type) : d.items;
        return (
          <>
            <View className="flex-row gap-2">
              {[7, 14, 30].map((dd) => {
                const active = dd === days;
                return (
                  <Pressable key={dd} onPress={() => setDays(dd)} className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}>
                    <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{dd} gün</Text>
                  </Pressable>
                );
              })}
            </View>

            <View className="flex-row flex-wrap gap-2">
              <Pressable onPress={() => setType(null)} className={cn("rounded-full border px-3 py-1.5", type == null ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}>
                <Text className={cn("text-xs font-medium", type == null ? "text-brand-700" : "text-slate-600")}>Tümü ({d.items.length})</Text>
              </Pressable>
              {Object.entries(CAT).map(([key, c]) => {
                const n = d.counts[key] ?? 0;
                if (n === 0) return null;
                const active = type === key;
                return (
                  <Pressable key={key} onPress={() => setType(active ? null : key)} className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}>
                    <Text className={cn("text-xs font-medium", active ? "text-brand-700" : "text-slate-600")}>{c.label} ({n})</Text>
                  </Pressable>
                );
              })}
            </View>

            {items.length === 0 ? (
              <Empty text="Bu dönemde aktivite yok." />
            ) : (
              <View className="gap-2">{items.map((a) => <Item key={a.id} a={a} />)}</View>
            )}
          </>
        );
      }}
    </InstitutionScreen>
  );
}
