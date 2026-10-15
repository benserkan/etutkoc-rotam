import { useQuery, type QueryKey } from "@tanstack/react-query";
import * as React from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import { UNIT_LABELS, type PoolPeriodDetailItem, type PoolPeriodDetailResponse, type PoolUnit } from "@/lib/pool";

/**
 * Geçmiş dönem penceresi (havuz) — öğrenci + veli ORTAK (web `shared/pool-period-dialog.tsx` paritesi).
 * İki sekme: Havuz kalemleri (ne verildi, ne bitti) · Gün gün (hangi gün ne çalıştı; kap boş gün açık yazılır).
 * Salt okuma; veri sunucuda yüzeye göre süzülür (öğrenci kaçınma sayacı görmez, veli onay bekleyeni görmez).
 */
const DAY_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

export function PeriodDetailSheet({ visible, onClose, queryKey, queryFn }: {
  visible: boolean; onClose: () => void; queryKey: QueryKey; queryFn: () => Promise<PoolPeriodDetailResponse>;
}) {
  const q = useQuery({ queryKey, queryFn, enabled: visible });
  const [tab, setTab] = React.useState<"items" | "days">("items");
  const d = q.data;
  const title = d ? `Dönem ${fmtDate(d.period.opened_on)} → ${d.period.closed_on ? fmtDate(d.period.closed_on) : "açık"}` : "Dönem";
  return (
    <FormSheet visible={visible} title={title} onClose={onClose}>
      {!d ? (
        <View className="items-center py-8">
          {q.isError ? <Text className="text-sm text-slate-600">Dönem yüklenemedi.</Text> : <ActivityIndicator />}
        </View>
      ) : (
        <View>
          <Text className="text-xs text-slate-600">
            {d.period.status_label} · %{d.period.pct} · {d.period.done_units}/{d.period.total_units} birim · {d.period.items_done}/{d.period.items_total} kalem bitti
            {d.period.carried_out > 0 ? ` · devredildi ${d.period.carried_out}` : ""}
          </Text>
          {d.period.subjects.length > 0 ? (
            <View className="mt-2 flex-row flex-wrap gap-1">
              {d.period.subjects.map((s) => (
                <View key={s.subject} className="rounded-full bg-slate-100 px-2 py-0.5">
                  <Text className="text-[11px] text-slate-700">{s.subject} {s.done}/{s.total} · %{s.pct}</Text>
                </View>
              ))}
            </View>
          ) : null}
          <View className="mt-3 flex-row gap-1 rounded-xl bg-slate-100 p-1">
            <TabButton active={tab === "items"} onPress={() => setTab("items")} label="Havuz kalemleri" />
            <TabButton active={tab === "days"} onPress={() => setTab("days")} label="Gün gün" />
          </View>
          <ScrollView className="mt-3 max-h-[60vh]" showsVerticalScrollIndicator={false}>
            {tab === "items" ? <ItemsTab data={d} /> : <DaysTab data={d} />}
          </ScrollView>
        </View>
      )}
    </FormSheet>
  );
}

function TabButton({ active, onPress, label }: { active: boolean; onPress: () => void; label: string }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="tab" accessibilityState={{ selected: active }}
               className={`flex-1 items-center rounded-lg px-3 py-2 ${active ? "bg-cyan-700" : ""}`}>
      <Text className={`text-sm font-semibold ${active ? "text-white" : "text-slate-600"}`}>{label}</Text>
    </Pressable>
  );
}

function ItemsTab({ data }: { data: PoolPeriodDetailResponse }) {
  const groups = new Map<string, PoolPeriodDetailItem[]>();
  for (const it of data.items) {
    const g = groups.get(it.subject_name) ?? [];
    g.push(it);
    groups.set(it.subject_name, g);
  }
  if (data.items.length === 0) return <Text className="text-sm text-slate-500">Bu dönemde kalem yok.</Text>;
  return (
    <View className="gap-3">
      {[...groups.entries()].map(([name, list]) => (
        <View key={name}>
          <Text className="mb-1 text-[11px] font-bold uppercase tracking-wide text-slate-500">{name}</Text>
          <View className="rounded-xl border border-slate-200">
            {list.map((it, i) => {
              const done = it.done >= it.quantity;
              const unit = UNIT_LABELS[it.unit as PoolUnit] ?? it.unit;
              return (
                <View key={it.id} className={`px-3 py-2 ${i > 0 ? "border-t border-slate-100" : ""}`}>
                  <Text className={`text-sm ${done ? "text-slate-400 line-through" : "text-slate-900"} ${it.teacher_homework ? "italic" : ""}`}>{it.title}</Text>
                  <Text className="mt-0.5 text-xs text-slate-500">
                    {it.quantity} {unit} verildi · öğrenci {it.completed}
                    {it.session_marked > 0 ? ` · seansta ${it.session_marked}` : ""}
                    {it.remaining > 0 ? ` · kalan ${it.remaining}` : " · bitti"}
                  </Text>
                  <View className="mt-1 flex-row flex-wrap gap-1">
                    {it.source === "ogrenci" ? (
                      <Badge tone={it.approval === "onaylandi" ? "emerald" : it.approval === "reddedildi" ? "rose" : "amber"}
                             text={`öğrenci ekledi${it.approval === "bekliyor" ? " · onay bekliyor" : it.approval === "reddedildi" ? " · reddedildi" : ""}`} />
                    ) : null}
                    {it.teacher_homework ? <Badge tone="violet" text="öğretmen ödevi" /> : null}
                    {it.exam_linked ? <Badge tone="sky" text="denemeden" /> : null}
                    {it.source === "devir" ? <Badge tone="slate" text={`devir ×${it.carry_count}`} /> : null}
                    {it.carried_out ? <Badge tone="cyan" text="sonraki döneme devredildi" /> : null}
                  </View>
                </View>
              );
            })}
          </View>
        </View>
      ))}
    </View>
  );
}

const TONES: Record<string, { bg: string; fg: string }> = {
  emerald: { bg: "bg-emerald-700", fg: "text-white" },
  rose: { bg: "bg-rose-700", fg: "text-white" },
  amber: { bg: "bg-amber-400", fg: "text-amber-950" },
  violet: { bg: "bg-violet-600", fg: "text-white" },
  sky: { bg: "bg-sky-700", fg: "text-white" },
  cyan: { bg: "bg-cyan-700", fg: "text-white" },
  slate: { bg: "bg-slate-600", fg: "text-white" },
};

function Badge({ tone, text }: { tone: keyof typeof TONES; text: string }) {
  return (
    <View className={`rounded-full px-2 py-0.5 ${TONES[tone].bg}`}>
      <Text className={`text-[11px] font-semibold ${TONES[tone].fg}`}>{text}</Text>
    </View>
  );
}

function DaysTab({ data }: { data: PoolPeriodDetailResponse }) {
  return (
    <View className="gap-1.5">
      <Text className="text-xs text-slate-500">
        Her gün kaba alıp işlediğin görevler. Kap boş kalan gün &quot;kap boş&quot; yazar; kaba alınıp hiç dokunulmayan görev gün sonunda havuza döndüğü için burada görünmez.
      </Text>
      {data.days.map((d) => (
        <View key={d.date} className={`rounded-xl border px-3 py-2 ${d.tasks.length === 0 ? "border-dashed border-slate-200 bg-slate-50" : "border-slate-200"}`}>
          <View className="flex-row items-center">
            <Text className="text-sm font-semibold text-slate-800">{DAY_SHORT[d.weekday]} {fmtDate(d.date)}</Text>
            {d.tasks.length === 0
              ? <Text className="ml-2 text-xs text-slate-500">kap boş</Text>
              : <Text className="ml-auto text-xs text-slate-500">{d.done_units} birim</Text>}
          </View>
          {d.tasks.map((t) => {
            const done = t.status === "completed";
            const dyb = t.correct != null || t.wrong != null || t.blank != null;
            return (
              <View key={t.task_id} className="mt-1 flex-row items-start gap-2">
                <View className={`mt-1.5 size-1.5 rounded-full ${done ? "bg-emerald-500" : "bg-amber-400"}`} />
                <View className="flex-1">
                  <Text className={`text-xs ${done ? "text-slate-800" : "text-slate-500"}`}>{t.title}</Text>
                  <Text className="text-[11px] text-slate-500">
                    {t.itemless ? (done ? "yapıldı" : "yapılmadı") : `${t.done} test çözdü`}
                    {dyb ? ` · ${t.correct ?? 0}D ${t.wrong ?? 0}Y ${t.blank ?? 0}B` : ""}
                  </Text>
                </View>
              </View>
            );
          })}
        </View>
      ))}
    </View>
  );
}
