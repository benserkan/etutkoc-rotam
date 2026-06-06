import { Ionicons } from "@expo/vector-icons";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import type { InstitutionDashboardResponse, TeacherSummaryItem } from "@/lib/institution";
import { cn } from "@/lib/utils";

function rateTone(pct: number | null): { row: string; text: string } {
  if (pct == null) return { row: "border-l-slate-200", text: "text-slate-500" };
  if (pct >= 70) return { row: "border-l-emerald-500", text: "text-emerald-700" };
  if (pct >= 40) return { row: "border-l-amber-400", text: "text-amber-700" };
  return { row: "border-l-rose-500", text: "text-rose-700" };
}

function Kpi({ label, value, sub, tone = "text-slate-900" }: { label: string; value: string; sub?: string; tone?: string }) {
  return (
    <View className="flex-1 rounded-2xl border border-slate-200 bg-white p-3">
      <Text className="text-[11px] font-medium text-slate-400">{label}</Text>
      <Text className={cn("mt-1 text-xl font-extrabold", tone)}>{value}</Text>
      {sub ? <Text className="text-[10px] text-slate-400">{sub}</Text> : null}
    </View>
  );
}

function TeacherRow({ t, onPress }: { t: TeacherSummaryItem; onPress?: () => void }) {
  const tone = rateTone(t.weekly_rate_pct);
  const muted = !t.is_active || t.is_paused;
  return (
    <Pressable
      onPress={onPress}
      className={cn(
        "flex-row items-center gap-2 rounded-xl border border-l-4 border-slate-200 bg-white p-3 active:bg-slate-50",
        muted ? "border-l-slate-200 opacity-60" : tone.row,
      )}
    >
      <View className="flex-1">
        <View className="flex-row items-center justify-between gap-2">
          <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={1}>
            {t.full_name}
          </Text>
          {muted ? (
            <Text className="text-[11px] font-semibold text-slate-400">{t.is_paused ? "Duraklatıldı" : "Pasif"}</Text>
          ) : (
            <Text className={cn("text-base font-extrabold", tone.text)}>
              {t.weekly_rate_pct != null ? `%${t.weekly_rate_pct}` : "—"}
            </Text>
          )}
        </View>
        <Text className="mt-0.5 text-xs text-slate-400">
          {t.student_count} öğrenci · {t.weekly_completed}/{t.weekly_planned} görev
          {t.last_login_days != null ? ` · ${t.last_login_days === 0 ? "bugün" : `${t.last_login_days}g önce`} giriş` : ""}
        </Text>
      </View>
      <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
    </Pressable>
  );
}

export function InstitutionDashboardView({
  data,
  refreshing = false,
  onRefresh,
  onOpenTeacher,
}: {
  data: InstitutionDashboardResponse;
  refreshing?: boolean;
  onRefresh?: () => void;
  onOpenTeacher?: (id: number) => void;
}) {
  const a = data.aggregate;
  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-4 gap-4"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined}
    >
      {/* Kurum başlık */}
      <View className="rounded-2xl bg-brand-700 p-5">
        <Text className="text-lg font-bold text-white">{data.institution.name}</Text>
        <Text className="mt-0.5 text-xs text-brand-100">
          {a.active_teacher_count}/{a.teacher_count} aktif koç · {a.student_count} öğrenci
        </Text>
        <View className="mt-3 flex-row items-end gap-2">
          <Text className="text-3xl font-extrabold text-white">
            {a.weekly_rate_pct != null ? `%${a.weekly_rate_pct}` : "—"}
          </Text>
          <Text className="mb-1 text-xs text-brand-100">son 7 gün görev tamamlama</Text>
        </View>
      </View>

      {/* Risk + pasif */}
      <View className="flex-row gap-3">
        <Kpi
          label="Riskli öğrenci"
          value={String(data.risk.at_risk_count)}
          sub={data.risk.at_risk_critical > 0 ? `${data.risk.at_risk_critical} kritik` : "kritik yok"}
          tone={data.risk.at_risk_critical > 0 ? "text-rose-600" : "text-slate-900"}
        />
        <Kpi
          label="Pasif koç"
          value={String(data.inactive.inactive_teacher_count)}
          sub={data.inactive.inactive_teacher_count > 0 ? "giriş yok" : "hepsi aktif"}
          tone={data.inactive.inactive_teacher_count > 0 ? "text-amber-600" : "text-slate-900"}
        />
      </View>

      {/* Koç performansı */}
      <View className="gap-2">
        <View className="flex-row items-center justify-between px-1">
          <Text className="text-sm font-semibold text-slate-700">Koçlar — son 7 gün</Text>
          <Text className="text-[11px] text-slate-400">≥%70 iyi · &lt;%40 dikkat</Text>
        </View>
        {data.teacher_summaries.length === 0 ? (
          <Text className="px-1 text-sm text-slate-400">Henüz koç yok.</Text>
        ) : (
          <View className="gap-2">
            {data.teacher_summaries.map((t) => (
              <TeacherRow key={t.id} t={t} onPress={onOpenTeacher ? () => onOpenTeacher(t.id) : undefined} />
            ))}
          </View>
        )}
      </View>
    </ScrollView>
  );
}
