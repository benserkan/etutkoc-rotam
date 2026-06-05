import { Ionicons } from "@expo/vector-icons";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import type { DnaResponse, FocusResponse, GoalListResponse, ReviewResponse } from "@/lib/student";
import { cn } from "@/lib/utils";

const CHRONO: Record<string, { label: string; icon: keyof typeof Ionicons.glyphMap }> = {
  morning: { label: "Sabahçı", icon: "sunny-outline" },
  afternoon: { label: "Öğlenci", icon: "partly-sunny-outline" },
  evening: { label: "Akşamcı", icon: "moon-outline" },
  night: { label: "Gececi", icon: "moon" },
  unknown: { label: "Belirsiz", icon: "help-circle-outline" },
};
const GOAL_KIND: Record<string, string> = {
  exam_target: "Sınav hedefi", subject: "Ders", topic: "Konu",
  weekly: "Haftalık", daily: "Günlük", custom: "Özel",
};

function Section({
  icon,
  title,
  children,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="mb-3 flex-row items-center gap-2">
        <Ionicons name={icon} size={18} color="#0e7490" />
        <Text className="text-[15px] font-bold text-slate-900">{title}</Text>
      </View>
      {children}
    </View>
  );
}

function PeriodBar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <View className="flex-row items-center gap-2">
      <Text className="w-16 text-xs text-slate-500">{label}</Text>
      <View className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
        <View className="h-full rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
      </View>
      <Text className="w-7 text-right text-xs text-slate-500">{value}</Text>
    </View>
  );
}

export function DevHubView({
  dna,
  focus,
  review,
  goals,
  onOpenBooks,
  refreshing = false,
  onRefresh,
}: {
  dna: DnaResponse;
  focus: FocusResponse;
  review: ReviewResponse;
  goals: GoalListResponse;
  onOpenBooks: () => void;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const chrono = CHRONO[dna.chronotype] ?? CHRONO.unknown;
  const maxPeriod = Math.max(1, dna.morning_count, dna.afternoon_count, dna.evening_count, dna.night_count);
  const activeGoals = goals.items.filter((g) => g.status === "active").slice(0, 4);

  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-4 gap-4"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined}
    >
      {/* Kitaplarım kısayolu */}
      <Pressable
        onPress={onOpenBooks}
        className="flex-row items-center justify-between rounded-2xl bg-brand-700 px-5 py-4 active:opacity-90"
      >
        <View className="flex-row items-center gap-3">
          <Ionicons name="library-outline" size={22} color="#e0f2fe" />
          <Text className="text-[15px] font-semibold text-white">Kitaplarım ve ilerlemem</Text>
        </View>
        <Ionicons name="chevron-forward" size={18} color="#bae6fd" />
      </Pressable>

      {/* Çalışma DNA */}
      <Section icon="pulse-outline" title="Çalışma DNA'm">
        {!dna.has_enough_data ? (
          <Text className="text-sm text-slate-400">Yeterli veri birikince çalışma alışkanlıkların burada görünür.</Text>
        ) : (
          <>
            <View className="flex-row items-center gap-2">
              <Ionicons name={chrono.icon} size={18} color="#0e7490" />
              <Text className="text-sm font-semibold text-slate-800">{chrono.label}</Text>
              {dna.peak_day_name ? (
                <Text className="text-xs text-slate-400">· en verimli {dna.peak_day_name}{dna.peak_hour != null ? ` ~${dna.peak_hour}:00` : ""}</Text>
              ) : null}
            </View>
            <View className="mt-3 gap-2">
              <PeriodBar label="Sabah" value={dna.morning_count} max={maxPeriod} />
              <PeriodBar label="Öğlen" value={dna.afternoon_count} max={maxPeriod} />
              <PeriodBar label="Akşam" value={dna.evening_count} max={maxPeriod} />
              <PeriodBar label="Gece" value={dna.night_count} max={maxPeriod} />
            </View>
            <Text className="mt-3 text-xs text-slate-400">
              Son {dna.window_days} gün · hafta içi {dna.weekday_count} / hafta sonu {dna.weekend_count} oturum
            </Text>
          </>
        )}
      </Section>

      {/* Hedefler */}
      <Section icon="flag-outline" title="Hedeflerim">
        <View className="flex-row gap-4">
          <View><Text className="text-xl font-extrabold text-slate-900">{goals.summary.active}</Text><Text className="text-[11px] text-slate-400">aktif</Text></View>
          <View><Text className="text-xl font-extrabold text-emerald-600">{goals.summary.achieved}</Text><Text className="text-[11px] text-slate-400">başarıldı</Text></View>
          {goals.summary.overall_pct != null ? (
            <View><Text className="text-xl font-extrabold text-slate-900">%{goals.summary.overall_pct}</Text><Text className="text-[11px] text-slate-400">ilerleme</Text></View>
          ) : null}
        </View>
        {activeGoals.length > 0 ? (
          <View className="mt-3 gap-2.5">
            {activeGoals.map((g) => (
              <View key={g.id} className="gap-1">
                <View className="flex-row items-center justify-between">
                  <Text className="flex-1 text-[13px] text-slate-700" numberOfLines={1}>{g.title}</Text>
                  <Text className="text-[11px] text-slate-400">{GOAL_KIND[g.kind] ?? ""}{g.progress_pct != null ? ` · %${g.progress_pct}` : ""}</Text>
                </View>
                {g.progress_pct != null ? (
                  <View className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <View className={cn("h-full rounded-full", g.progress_pct >= 100 ? "bg-emerald-500" : "bg-brand-500")} style={{ width: `${Math.min(100, g.progress_pct)}%` }} />
                  </View>
                ) : null}
              </View>
            ))}
          </View>
        ) : (
          <Text className="mt-2 text-sm text-slate-400">Aktif hedef yok.</Text>
        )}
      </Section>

      {/* Odak */}
      <Section icon="timer-outline" title="Odak">
        <View className="flex-row gap-5">
          <View><Text className="text-xl font-extrabold text-slate-900">{focus.streak_days}</Text><Text className="text-[11px] text-slate-400">gün seri</Text></View>
          <View><Text className="text-xl font-extrabold text-slate-900">{focus.today.work_minutes}</Text><Text className="text-[11px] text-slate-400">bugün dk</Text></View>
          <View><Text className="text-xl font-extrabold text-slate-900">{focus.today.work_sessions}</Text><Text className="text-[11px] text-slate-400">oturum</Text></View>
          <View><Text className="text-xl font-extrabold text-amber-600">{focus.points}</Text><Text className="text-[11px] text-slate-400">puan</Text></View>
        </View>
        <Text className="mt-2 text-xs text-slate-400">Odak sayacını web panelinden başlatabilirsin; burada özetini görürsün.</Text>
      </Section>

      {/* Tekrar */}
      <Section icon="repeat-outline" title="Tekrar (aralıklı)">
        <View className="flex-row items-end justify-between">
          <View>
            <Text className="text-3xl font-extrabold text-slate-900">{review.breakdown.due_now}</Text>
            <Text className="text-[11px] text-slate-400">şimdi tekrar zamanı</Text>
          </View>
          <Text className="text-xs text-slate-500">
            {review.breakdown.review} öğrenildi · {review.breakdown.learning} öğreniliyor · {review.breakdown.new} yeni
          </Text>
        </View>
        {review.due_cards.length > 0 ? (
          <View className="mt-3 flex-row flex-wrap gap-1.5">
            {review.due_cards.slice(0, 6).map((c) => (
              <View key={c.id} className="rounded-md bg-amber-50 px-2 py-1">
                <Text className="text-[11px] text-amber-700">{c.topic_name}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </Section>
    </ScrollView>
  );
}
