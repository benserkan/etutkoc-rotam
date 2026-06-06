import { Ionicons } from "@expo/vector-icons";
import { Pressable, ScrollView, Text, View } from "react-native";

import type { GorevBreakdown, TeacherStudentDetail, WarningLevel } from "@/lib/teacher";
import { cn } from "@/lib/utils";

const WARN: Record<WarningLevel, { dot: string; label: string; text: string }> = {
  red: { dot: "bg-rose-500", label: "Acil", text: "text-rose-700" },
  amber: { dot: "bg-amber-400", label: "Dikkat", text: "text-amber-700" },
  green: { dot: "bg-emerald-500", label: "Yolunda", text: "text-emerald-700" },
};

function WarnRow({ level, title, detail }: { level: string; title: string; detail: string }) {
  const tone =
    level === "red" ? "border-l-rose-500" : level === "amber" ? "border-l-amber-400" : "border-l-emerald-500";
  const txt = level === "red" ? "text-rose-700" : level === "amber" ? "text-amber-700" : "text-emerald-700";
  return (
    <View className={cn("rounded-xl border border-l-4 border-slate-200 bg-white p-3", tone)}>
      <Text className={cn("text-sm font-semibold", txt)}>{title}</Text>
      {detail ? <Text className="mt-0.5 text-xs text-slate-500">{detail}</Text> : null}
    </View>
  );
}

function GorevCard({ title, g }: { title: string; g: GorevBreakdown }) {
  return (
    <View className="flex-1 rounded-2xl border border-slate-200 bg-white p-4">
      <Text className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</Text>
      <Text className="mt-1 text-2xl font-extrabold text-slate-900">
        {g.gorev_done}
        <Text className="text-base font-semibold text-slate-400">/{g.gorev_total}</Text>
        <Text className="text-sm font-medium text-slate-400"> görev</Text>
      </Text>
      <View className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <View
          className={cn(
            "h-full rounded-full",
            g.gorev_pct >= 100 ? "bg-emerald-500" : g.gorev_pct > 0 ? "bg-amber-400" : "bg-slate-200",
          )}
          style={{ width: `${Math.min(100, g.gorev_pct)}%` }}
        />
      </View>
      <Text className="mt-2 text-[11px] text-slate-500">
        {g.test_planned > 0 ? `${g.test_completed}/${g.test_planned} test` : "test yok"}
        {g.deneme_count > 0 ? ` · ${g.deneme_done}/${g.deneme_count} deneme` : ""}
        {g.etkinlik_count > 0 ? ` · ${g.etkinlik_done}/${g.etkinlik_count} etkinlik` : ""}
      </Text>
    </View>
  );
}

export function StudentDetailView({
  data,
  onOpenDev,
  onOpenTopics,
  onSendWa,
  onToggleActive,
  togglingActive = false,
}: {
  data: TeacherStudentDetail;
  onOpenDev?: () => void;
  onOpenTopics?: () => void;
  onSendWa?: () => void;
  onToggleActive?: () => void;
  togglingActive?: boolean;
}) {
  const w = WARN[data.worst_warning_level];
  const s = data.student;
  const grade = s.display_grade_label ?? (s.grade_level != null ? `${s.grade_level}. sınıf` : "");
  const reds = data.warning_items.filter((i) => i.level !== "green");

  return (
    <ScrollView className="flex-1 bg-slate-50" contentContainerClassName="px-4 py-4 gap-4">
      {/* Üst kart */}
      <View className="rounded-2xl bg-brand-700 p-5">
        <View className="flex-row items-center justify-between">
          <Text className="text-lg font-bold text-white">{s.full_name}</Text>
          <View className="flex-row items-center gap-1.5 rounded-full bg-white/15 px-2.5 py-1">
            <View className={cn("size-2 rounded-full", w.dot)} />
            <Text className="text-xs font-semibold text-white">{w.label}</Text>
          </View>
        </View>
        <Text className="mt-0.5 text-xs text-brand-100">
          {grade}
          {s.track_label ? ` · ${s.track_label}` : ""}
          {!s.is_active ? " · pasif" : ""}
        </Text>
        {data.pending_request_count > 0 ? (
          <View className="mt-3 self-start rounded-full bg-amber-400 px-2.5 py-1">
            <Text className="text-xs font-semibold text-amber-950">{data.pending_request_count} bekleyen talep</Text>
          </View>
        ) : null}
      </View>

      {/* Bugün / Hafta görev */}
      {data.gorev_today && data.gorev_week ? (
        <View className="flex-row gap-3">
          <GorevCard title="Bugün" g={data.gorev_today} />
          <GorevCard title="Bu hafta" g={data.gorev_week} />
        </View>
      ) : null}

      {/* Durum özeti */}
      <View className="gap-2">
        <Text className="px-1 text-sm font-semibold text-slate-700">Durum</Text>
        {reds.length === 0 ? (
          <View className="rounded-xl border border-l-4 border-l-emerald-500 border-slate-200 bg-white p-3">
            <Text className="text-sm font-semibold text-emerald-700">Yolunda</Text>
            <Text className="mt-0.5 text-xs text-slate-500">Dikkat gerektiren bir durum yok.</Text>
          </View>
        ) : (
          reds.map((i) => <WarnRow key={i.code} level={i.level} title={i.title} detail={i.detail} />)
        )}
      </View>

      {/* Gelişim izleme — koçluğun derin analizi */}
      {onOpenDev ? (
        <Pressable
          onPress={onOpenDev}
          className="flex-row items-center justify-between rounded-2xl border border-brand-200 bg-brand-50 px-5 py-4 active:bg-brand-100"
        >
          <View className="flex-1 flex-row items-center gap-3">
            <Ionicons name="pulse-outline" size={22} color="#0e7490" />
            <View className="flex-1">
              <Text className="text-[15px] font-semibold text-brand-800">Gelişim izleme</Text>
              <Text className="mt-0.5 text-xs text-brand-700">Çalışma DNA · Odak · Tekrar · Hedefler</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#0e7490" />
        </Pressable>
      ) : null}

      {/* Konu Performansı — ders/konu bazlı çözülen test + doğru/yanlış */}
      {onOpenTopics ? (
        <Pressable
          onPress={onOpenTopics}
          className="flex-row items-center justify-between rounded-2xl border border-indigo-200 bg-indigo-50 px-5 py-4 active:bg-indigo-100"
        >
          <View className="flex-1 flex-row items-center gap-3">
            <Ionicons name="locate-outline" size={22} color="#4f46e5" />
            <View className="flex-1">
              <Text className="text-[15px] font-semibold text-indigo-800">Konu Performansı</Text>
              <Text className="mt-0.5 text-xs text-indigo-700">Derslerin konularında çözülen test + doğru/yanlış</Text>
            </View>
          </View>
          <Ionicons name="chevron-forward" size={18} color="#4f46e5" />
        </Pressable>
      ) : null}

      {/* Hızlı işlemler */}
      <View className="gap-2">
        {onSendWa ? (
          <Pressable
            onPress={onSendWa}
            className="flex-row items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-5 py-4 active:bg-emerald-100"
          >
            <Ionicons name="logo-whatsapp" size={22} color="#16a34a" />
            <View className="flex-1">
              <Text className="text-[15px] font-semibold text-emerald-800">WhatsApp gönder</Text>
              <Text className="mt-0.5 text-xs text-emerald-700">Öğrenciye hazır şablonla mesaj</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color="#16a34a" />
          </Pressable>
        ) : null}

        {onToggleActive ? (
          <Pressable
            onPress={onToggleActive}
            disabled={togglingActive}
            className={cn(
              "flex-row items-center gap-3 rounded-2xl border px-5 py-4",
              s.is_active
                ? "border-slate-200 bg-white active:bg-slate-50"
                : "border-emerald-200 bg-emerald-50 active:bg-emerald-100",
              togglingActive && "opacity-50",
            )}
          >
            <Ionicons
              name={s.is_active ? "pause-circle-outline" : "play-circle-outline"}
              size={22}
              color={s.is_active ? "#64748b" : "#16a34a"}
            />
            <View className="flex-1">
              <Text className={cn("text-[15px] font-semibold", s.is_active ? "text-slate-800" : "text-emerald-800")}>
                {s.is_active ? "Öğrenciyi pasife al" : "Öğrenciyi aktif et"}
              </Text>
              <Text className={cn("mt-0.5 text-xs", s.is_active ? "text-slate-500" : "text-emerald-700")}>
                {s.is_active
                  ? "Kotadan düşer; veri silinmez, sonra tekrar aktif edebilirsin"
                  : "Tekrar aktif öğrenci olur"}
              </Text>
            </View>
          </Pressable>
        ) : null}
      </View>

      {/* Diğer işlemler */}
      <View className="rounded-2xl border border-dashed border-slate-300 bg-white p-4">
        <Text className="text-sm font-semibold text-slate-800">Diğer işlemler</Text>
        <Text className="mt-1 text-xs leading-relaxed text-slate-500">
          Deneme sonucu ve seans kaydı için yukarıdaki sekmeleri kullan. Kütüphane, kitap atama ve
          günlük/haftalık program düzenleme web panelinde.
        </Text>
      </View>
    </ScrollView>
  );
}
