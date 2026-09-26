import { Ionicons } from "@expo/vector-icons";
import { Alert, Pressable, Text, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import { TaskVideoList } from "@/components/ui/task-video-list";
import type { TeacherTaskRow } from "@/lib/teacher";
import { activityLabel, linkButtonLabel, openTaskLink, stripUrls, taskLabel } from "@/lib/task-display";
import { cn } from "@/lib/utils";

const DENEME = new Set(["brans_denemesi", "genel_deneme"]);
const PERIOD_TR: Record<string, string> = { morning: "Sabah", noon: "Öğle", evening: "Akşam" };

function statusInfo(t: TeacherTaskRow): { label: string; cls: string } {
  if (t.status === "completed") return { label: "Tamamlandı", cls: "bg-emerald-600" };
  if (t.completed_count > 0 || t.status === "partial") return { label: "Kısmen yapıldı", cls: "bg-amber-500" };
  return { label: "Bekliyor", cls: "bg-slate-400" };
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <View className="flex-row gap-2">
      <Text className="w-24 text-xs text-slate-400">{label}</Text>
      <Text className="flex-1 text-[13px] text-slate-800">{value}</Text>
    </View>
  );
}

/**
 * Koç — görev detayı (salt-okuma + sil + bağlantı). Satıra dokununca açılır;
 * planlama/düzenleme web'de (PARITY). Çok kalemli görevde HER kalem listelenir
 * — başlıktaki tek bölüm adı yanıltmasın (Taha/Vektörler sahası).
 */
export function TaskDetailSheet({
  task,
  onClose,
  onDelete,
}: {
  task: TeacherTaskRow | null;
  onClose: () => void;
  onDelete?: (id: number) => void;
}) {
  if (!task) return null;
  const t = task;
  const st = statusInfo(t);
  const subject = t.items.find((i) => i.subject_name)?.subject_name ?? null;
  const bookItems = t.items.filter((i) => i.book_id != null);
  const otherItems = t.items.filter((i) => i.book_id == null);
  const isActivity = bookItems.length === 0 && otherItems.length === 0;
  const notes = stripUrls(t.notes);
  const isVideo = t.type === "video";

  function confirmDelete() {
    if (!onDelete) return;
    Alert.alert("Görevi sil", `"${taskLabel(t.items, t.title, { compact: true })}" silinsin mi? Rezerv kapasitesi iade edilir.`, [
      { text: "Vazgeç", style: "cancel" },
      { text: "Sil", style: "destructive", onPress: () => onDelete(t.id) },
    ]);
  }

  return (
    <FormSheet visible title="Görev detayı" onClose={onClose}>
      <View className="gap-4 pb-2">
        <View className="gap-1">
          <View className="flex-row flex-wrap items-center gap-2">
            {subject ? (
              <Text className="text-[11px] font-bold uppercase tracking-wide text-brand-700">{subject}</Text>
            ) : null}
            {t.type !== "test" ? (
              <View className="rounded-full bg-violet-600 px-2 py-0.5">
                <Text className="text-[10px] font-semibold text-white">{activityLabel(t.type)}</Text>
              </View>
            ) : null}
            {t.is_draft ? (
              <View className="rounded-full bg-amber-500 px-2 py-0.5">
                <Text className="text-[10px] font-semibold text-white">Taslak — öğrenci görmez</Text>
              </View>
            ) : null}
          </View>
          <Text className="text-[17px] font-bold text-slate-900">{taskLabel(t.items, t.title)}</Text>
          <View className="flex-row items-center gap-2">
            <View className={cn("rounded-full px-2 py-0.5", st.cls)}>
              <Text className="text-[11px] font-semibold text-white">{st.label}</Text>
            </View>
            {t.planned_count > 0 ? (
              <Text className="text-xs text-slate-500">
                {t.completed_count}/{t.planned_count}{" "}
                {bookItems[0]?.book_type && DENEME.has(bookItems[0].book_type) ? "deneme" : bookItems.length ? "test" : "soru"}
              </Text>
            ) : null}
            {t.has_pending_request ? <Text className="text-xs text-amber-700">· bekleyen talep</Text> : null}
          </View>
        </View>

        <TaskVideoList videos={t.videos} />
        {t.link_url && (t.videos?.length ?? 0) < 2 ? (
          <Pressable
            onPress={() => void openTaskLink(t.link_url!)}
            className="flex-row items-center justify-center gap-2 rounded-xl bg-brand-700 py-3 active:bg-brand-800"
          >
            <Ionicons name={isVideo ? "play-circle" : "open-outline"} size={18} color="#fff" />
            <Text className="text-[15px] font-semibold text-white">{linkButtonLabel(t.type)}</Text>
          </Pressable>
        ) : null}

        <View className="gap-1.5 rounded-xl bg-slate-50 p-3">
          <Row label="Tarih" value={t.date} />
          {t.period ? <Row label="Zaman" value={PERIOD_TR[t.period] ?? t.period} /> : null}
          {t.scheduled_hour ? <Row label="Saat" value={t.scheduled_hour} /> : null}
          {t.work_block_title ? <Row label="Blok" value={t.work_block_title} /> : null}
        </View>

        {bookItems.length > 0 ? (
          <View className="gap-2">
            <Text className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Kaynak ve konular {bookItems.length > 1 ? `(${bookItems.length} bölüm)` : ""}
            </Text>
            {bookItems.map((it) => {
              const unit = it.book_type && DENEME.has(it.book_type) ? "deneme" : "test";
              const hasResult = it.correct_count != null || it.wrong_count != null || it.blank_count != null;
              return (
                <View key={it.id} className="gap-1 rounded-xl border border-slate-200 bg-white p-3">
                  <Text className="text-[13px] font-semibold text-slate-900">{it.book_name}</Text>
                  {it.section_label ? <Text className="text-[13px] text-slate-700">Bölüm: {it.section_label}</Text> : null}
                  {it.topic_name && it.topic_name !== it.section_label ? (
                    <Text className="text-xs text-slate-500">Müfredat konusu: {it.topic_name}</Text>
                  ) : null}
                  <View className="mt-1 flex-row flex-wrap items-center gap-x-3 gap-y-1">
                    <Text className="text-xs font-medium text-slate-700">
                      {it.completed_count}/{it.planned_count} {unit}
                    </Text>
                    {hasResult ? (
                      <Text className="text-xs text-slate-500">
                        D {it.correct_count ?? 0} · Y {it.wrong_count ?? 0} · B {it.blank_count ?? 0}
                      </Text>
                    ) : null}
                    {typeof it.section_remaining === "number" ? (
                      <Text className="text-xs text-slate-400">bölümde kalan {it.section_remaining}</Text>
                    ) : null}
                  </View>
                </View>
              );
            })}
          </View>
        ) : null}

        {otherItems.map((it) => (
          <View key={it.id} className="rounded-xl border border-slate-200 bg-white p-3">
            <Text className="text-[13px] font-semibold text-slate-900">{it.book_name}</Text>
            <Text className="text-xs text-slate-500">{it.completed_count}/{it.planned_count} soru</Text>
          </View>
        ))}

        {isActivity && (t.solved_count ?? 0) > 0 ? (
          <Text className="text-xs text-slate-500">Öğrenci {t.solved_count} soru çözdüğünü girdi.</Text>
        ) : null}

        {notes ? (
          <View className="rounded-xl border-l-4 border-slate-300 bg-slate-50 p-3">
            <Text className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Not</Text>
            <Text className="mt-0.5 text-[13px] text-slate-700">{notes}</Text>
          </View>
        ) : null}

        <Text className="text-[11px] text-slate-400">Düzenleme (kaynak, sayı, tarih) web panelinden yapılır.</Text>

        {onDelete ? (
          <Pressable onPress={confirmDelete} className="items-center rounded-xl border border-rose-200 py-3 active:bg-rose-50">
            <Text className="text-sm font-semibold text-rose-600">Görevi sil</Text>
          </Pressable>
        ) : null}
      </View>
    </FormSheet>
  );
}
