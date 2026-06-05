import { Ionicons } from "@expo/vector-icons";
import { Alert, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import type { TeacherTaskRow, TeacherWeekDay, TeacherWeekResponse } from "@/lib/teacher";
import { cn } from "@/lib/utils";

const TR_MONTHS_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}

const DENEME = new Set(["brans_denemesi", "genel_deneme"]);
function taskLabel(t: TeacherTaskRow): string {
  const it = t.items.find((x) => x.book_id != null) ?? t.items[0];
  if (it?.book_id) return it.book_name + (it.section_label ? ` · ${it.section_label}` : "");
  const sep = t.title.indexOf(" · ");
  if (sep > 0) return t.title.substring(sep + 3);
  return t.title || "Görev";
}
function taskUnit(t: TeacherTaskRow): string {
  const it = t.items.find((x) => x.book_id != null) ?? t.items[0];
  if (it && it.book_id == null) return "soru";
  if (it?.book_type && DENEME.has(it.book_type)) return "deneme";
  if (t.planned_count <= 0) return "";
  return "test";
}

// Tamamlandı = durum COMPLETED (etkinlik/itemless/deneme dahil) VEYA soru-hacimli
// görevde çözülen ≥ planlanan. Yalnız pct'ye bakmak itemless görevi (planned=0 →
// pct=0) hatalı "yapılmadı" gösteriyordu (web `status === "completed"` kullanır).
function taskDone(t: TeacherTaskRow): boolean {
  return t.status === "completed" || (t.planned_count > 0 && t.pct >= 1);
}

function TaskRow({ t, onDelete }: { t: TeacherTaskRow; onDelete?: (id: number) => void }) {
  const done = taskDone(t);
  const unit = taskUnit(t);
  return (
    <Pressable
      onLongPress={
        onDelete
          ? () =>
              Alert.alert("Görevi sil", `"${taskLabel(t)}" silinsin mi?`, [
                { text: "Vazgeç", style: "cancel" },
                { text: "Sil", style: "destructive", onPress: () => onDelete(t.id) },
              ])
          : undefined
      }
      className="flex-row items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 active:bg-slate-100"
    >
      <View className={cn("size-2 rounded-full", done ? "bg-emerald-500" : t.completed_count > 0 ? "bg-amber-400" : "bg-slate-300")} />
      <Text className="flex-1 text-[13px] text-slate-800" numberOfLines={1}>{taskLabel(t)}</Text>
      {t.is_draft ? <Text className="text-[10px] font-semibold text-amber-600">taslak</Text> : null}
      {unit ? (
        <Text className="text-[11px] text-slate-400">{t.completed_count}/{t.planned_count} {unit}</Text>
      ) : (
        <Text className="text-[11px] text-slate-400">etkinlik</Text>
      )}
    </Pressable>
  );
}

function DayCard({ day, onAdd, onDelete }: { day: TeacherWeekDay; onAdd: (date: string) => void; onDelete?: (id: number) => void }) {
  const pct = Math.round(day.pct * 100);
  return (
    <View className="rounded-2xl border border-slate-200 bg-white p-4">
      <View className="flex-row items-center justify-between">
        <View className="flex-row items-center gap-2">
          <Text className={cn("text-[15px] font-bold", day.is_today ? "text-brand-700" : "text-slate-900")}>{day.dow_label}</Text>
          <Text className="text-xs text-slate-400">{shortDate(day.date)}</Text>
        </View>
        {day.tasks_count > 0 ? (
          <Text className="text-xs font-semibold text-slate-500">
            {day.tasks.filter(taskDone).length}/{day.tasks_count} · %{pct}
          </Text>
        ) : null}
      </View>

      {day.tasks.length > 0 ? (
        <View className="mt-3 gap-1.5">
          {day.tasks.map((t) => (
            <TaskRow key={t.id} t={t} onDelete={onDelete} />
          ))}
        </View>
      ) : (
        <Text className="mt-2 text-sm text-slate-400">Görev yok</Text>
      )}

      <Pressable
        onPress={() => onAdd(day.date)}
        className="mt-3 flex-row items-center justify-center gap-1.5 rounded-lg border border-dashed border-brand-300 py-2 active:bg-brand-50"
      >
        <Ionicons name="add" size={16} color="#0e7490" />
        <Text className="text-[13px] font-semibold text-brand-700">Görev ekle</Text>
      </Pressable>
    </View>
  );
}

export function TeacherWeekView({
  week,
  onPrev,
  onNext,
  onThisWeek,
  onAddTask,
  onDeleteTask,
  refreshing = false,
  onRefresh,
}: {
  week: TeacherWeekResponse;
  onPrev: () => void;
  onNext: () => void;
  onThisWeek: () => void;
  onAddTask: (date: string) => void;
  onDeleteTask?: (id: number) => void;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  const pct = Math.round(week.total_pct * 100);
  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="px-4 py-3 gap-3"
      refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" /> : undefined}
    >
      <View className="flex-row items-center justify-between">
        <Pressable onPress={onPrev} hitSlop={8} className="size-9 items-center justify-center rounded-full border border-slate-200 bg-white active:bg-slate-100">
          <Ionicons name="chevron-back" size={18} color="#334155" />
        </Pressable>
        <View className="items-center">
          <Text className="text-sm font-bold text-slate-900">{shortDate(week.start_date)} – {shortDate(week.end_date)}</Text>
          <View className="flex-row items-center gap-2">
            <Pressable onPress={onThisWeek} hitSlop={6}><Text className="text-xs font-medium text-brand-700">Bu hafta</Text></Pressable>
            <Text className="text-xs text-slate-400">· {week.total_completed}/{week.total_planned} · %{pct}</Text>
          </View>
        </View>
        <Pressable onPress={onNext} hitSlop={8} className="size-9 items-center justify-center rounded-full border border-slate-200 bg-white active:bg-slate-100">
          <Ionicons name="chevron-forward" size={18} color="#334155" />
        </Pressable>
      </View>

      {week.days.map((d) => (
        <DayCard key={d.date} day={d} onAdd={onAddTask} onDelete={onDeleteTask} />
      ))}
      <Text className="px-2 pb-2 text-center text-[11px] text-slate-400">Bir görevi silmek için basılı tut.</Text>
    </ScrollView>
  );
}
