import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Alert, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import type { TeacherSuggestionInline, TeacherTaskRow, TeacherWeekDay, TeacherWeekResponse } from "@/lib/teacher";
import { cn } from "@/lib/utils";

export interface SuggestionHandlers {
  onAccept: (date: string, s: TeacherSuggestionInline) => void;
  onReject: (date: string, s: TeacherSuggestionInline) => void;
  onAcceptAll: (date: string, items: TeacherSuggestionInline[]) => void;
  busy: boolean;
}

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

function confMark(conf: number): { bg: string; text: string } {
  if (conf >= 0.7) return { bg: "bg-emerald-600", text: "text-white" };
  if (conf >= 0.4) return { bg: "bg-slate-700", text: "text-white" };
  return { bg: "bg-slate-300", text: "text-slate-700" };
}

function SuggestionCard({ date, s, h }: { date: string; s: TeacherSuggestionInline; h: SuggestionHandlers }) {
  const cm = confMark(s.confidence);
  const strong = s.confidence >= 0.6;
  return (
    <View className={cn("rounded-lg border bg-white p-2.5", strong ? "border-slate-200" : "border-dashed border-slate-300")} style={{ opacity: s.confidence < 0.4 ? 0.75 : 1 }}>
      <View className="flex-row items-center gap-2">
        <View className={cn("rounded px-1.5 py-1", cm.bg)}>
          <Text className={cn("text-[9px] font-bold uppercase", cm.text)}>{s.confidence_label}</Text>
        </View>
        <View className="flex-1">
          <Text className="text-[13px] font-semibold text-slate-900" numberOfLines={1}>{s.book_name}</Text>
          <Text className="text-[11px] text-slate-400" numberOfLines={1}>
            {s.section_label} · {s.subject_name} · güven %{Math.round(s.confidence * 100)}
          </Text>
        </View>
        <Text className="text-[11px] font-semibold text-slate-500">{s.planned_count} test</Text>
        <Pressable onPress={() => h.onAccept(date, s)} disabled={h.busy} className="flex-row items-center gap-1 rounded-md bg-slate-900 px-2 py-1.5 active:bg-slate-700">
          <Ionicons name="add" size={13} color="#fff" />
          <Text className="text-[12px] font-semibold text-white">Ekle</Text>
        </Pressable>
        <Pressable onPress={() => h.onReject(date, s)} disabled={h.busy} hitSlop={6} className="p-1">
          <Ionicons name="close" size={16} color="#94a3b8" />
        </Pressable>
      </View>
      {s.reasons.length > 0 ? (
        <Text className="mt-1.5 text-[10px] text-slate-400" numberOfLines={1}>• {s.reasons[0]}</Text>
      ) : null}
    </View>
  );
}

function SuggestionsPanel({ day, h }: { day: TeacherWeekDay; h: SuggestionHandlers }) {
  const [open, setOpen] = React.useState(false);
  const sugs = day.suggestions ?? [];
  const has = sugs.length > 0;
  const observed = (day.weeks_observed ?? 0) > 0 || (day.days_observed ?? 0) > 0;
  // Hiç gözlem yoksa + öneri yoksa paneli hiç gösterme (gürültü olmasın)
  if (!has && !observed) return null;

  return (
    <View className="mt-3 rounded-xl border border-l-[3px] border-slate-200 border-l-indigo-400 bg-indigo-50/40">
      <Pressable onPress={() => setOpen((v) => !v)} className="flex-row items-center gap-2 px-3 py-2.5">
        <View className="size-5 items-center justify-center rounded bg-indigo-600">
          <Ionicons name="sparkles" size={11} color="#fff" />
        </View>
        <Text className="text-[13px] font-semibold text-slate-800">Öneriler</Text>
        {has ? <View className="rounded-full bg-emerald-100 px-1.5 py-0.5"><Text className="text-[10px] font-semibold text-emerald-700">{sugs.length} hazır</Text></View> : null}
        {day.maturity_label ? <Text className="text-[10px] text-slate-400">{day.maturity_label}</Text> : null}
        <View className="flex-1" />
        {has ? <Ionicons name={open ? "chevron-up" : "chevron-down"} size={16} color="#94a3b8" /> : null}
      </Pressable>

      {open ? (
        !has ? (
          <Text className="px-3 pb-3 text-[11px] italic text-slate-400">
            {observed ? "Bu güne ek öneri yok — plan tipik düzende veya tüm bölümler ekli." : "Henüz geçmiş plan verisi yok — siz plan yaptıkça öğrenir."}
          </Text>
        ) : (
          <View className="gap-2 px-3 pb-3">
            <Pressable
              onPress={() => h.onAcceptAll(day.date, sugs)}
              disabled={h.busy}
              className="flex-row items-center justify-center gap-1.5 rounded-md bg-slate-900 py-2 active:bg-slate-700"
            >
              <Ionicons name="checkmark-done" size={15} color="#fff" />
              <Text className="text-[12px] font-semibold text-white">Tümünü ekle ({sugs.length})</Text>
            </Pressable>
            {sugs.map((s) => (
              <SuggestionCard key={`${s.book_id}-${s.section_id}`} date={day.date} s={s} h={h} />
            ))}
            <Text className="pt-0.5 text-[10px] italic text-slate-400">
              Koçun geçmiş planları + öğrencinin atanmış kitap/geride kalma verisinden türetilir. Uydurma yoktur.
            </Text>
          </View>
        )
      ) : null}
    </View>
  );
}

function DayCard({ day, onAdd, onDelete, sugg }: { day: TeacherWeekDay; onAdd: (date: string) => void; onDelete?: (id: number) => void; sugg?: SuggestionHandlers }) {
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

      {sugg ? <SuggestionsPanel day={day} h={sugg} /> : null}

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
  sugg,
  refreshing = false,
  onRefresh,
}: {
  week: TeacherWeekResponse;
  onPrev: () => void;
  onNext: () => void;
  onThisWeek: () => void;
  onAddTask: (date: string) => void;
  onDeleteTask?: (id: number) => void;
  sugg?: SuggestionHandlers;
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
        <DayCard key={d.date} day={d} onAdd={onAddTask} onDelete={onDeleteTask} sugg={sugg} />
      ))}
      <Text className="px-2 pb-2 text-center text-[11px] text-slate-400">Bir görevi silmek için basılı tut.</Text>
    </ScrollView>
  );
}
