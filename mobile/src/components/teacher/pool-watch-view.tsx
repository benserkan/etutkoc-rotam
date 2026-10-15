import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { ActivityIndicator, Alert, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import {
  UNIT_LABELS,
  approveTeacherPoolItem,
  getTeacherPool,
  getTeacherPoolPeriod,
  teacherPoolKeys,
  type PoolPeriodDay,
  type PoolPeriodDetailItem,
} from "@/lib/pool";
import { subjectColors } from "@/lib/subject-colors";
import { cn } from "@/lib/utils";

/**
 * Koç — havuz İZLE görünümü (web editörünün "İzle" modunun paritesi).
 * "Seansa kadar öğrenci ne yaptı?" sorusunun tek ekranlık cevabı: özet → gün gün →
 * ders ders → onay bekleyen öğrenci kalemleri → bekleyen kalemler (bitenler katlı).
 * Havuzu YAZMAK web'de (kalem ekleme paneli); burada yalnız izleme + onay.
 */
const DAY_SHORT = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]; // backend weekday(): Pazartesi = 0

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
}

function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d + n);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

/** K42 birimi (backend `_units`): test sayısı; etkinlik 1 birim. Öğrenci kaydı / seansta işaret ayrı. */
function split(it: PoolPeriodDetailItem): { total: number; student: number; session: number } {
  if (it.unit === "etkinlik") {
    const done = it.remaining === 0 ? 1 : 0;
    return { total: 1, student: it.completed > 0 ? done : 0, session: it.completed > 0 ? 0 : done };
  }
  const student = Math.min(it.completed, it.quantity);
  return { total: it.quantity, student, session: Math.min(it.session_marked, Math.max(0, it.quantity - student)) };
}

function pctTone(p: number): string {
  if (p >= 70) return "text-emerald-700";
  if (p >= 40) return "text-amber-700";
  return "text-rose-700";
}

function SplitBar({ total, student, session, color, h = 8 }: { total: number; student: number; session: number; color: string; h?: number }) {
  const a = total > 0 ? (100 * student) / total : 0;
  const b = total > 0 ? (100 * session) / total : 0;
  return (
    <View className="w-full flex-row overflow-hidden rounded-full bg-slate-100" style={{ height: h }}>
      <View style={{ width: `${a}%`, backgroundColor: color }} />
      <View style={{ width: `${b}%`, backgroundColor: color, opacity: 0.4 }} />
    </View>
  );
}

function SubjectChip({ name }: { name: string }) {
  return (
    <View className="self-start rounded-md px-2 py-0.5" style={{ backgroundColor: subjectColors(name).chip }}>
      <Text className="text-[11px] font-bold text-white">{name}</Text>
    </View>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <View className="flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2">
      <Text className="text-[10px] font-semibold uppercase text-slate-400">{label}</Text>
      <Text className="text-lg font-extrabold text-slate-900">{value}</Text>
      <Text className="text-[10px] text-slate-500" numberOfLines={1}>{sub}</Text>
    </View>
  );
}

function DayCells({ days, items, today, expected }: { days: PoolPeriodDay[]; items: PoolPeriodDetailItem[]; today: string; expected: string | null }) {
  const [sel, setSel] = React.useState<string | null>(null);
  const subjOf = new Map(items.map((i) => [i.id, i.subject_name]));
  const max = Math.max(1, ...days.map((d) => d.done_units));
  const future: string[] = [];
  if (expected && days.length) {
    let d = addDays(days[days.length - 1].date, 1);
    while (d <= expected && future.length < 14) { future.push(d); d = addDays(d, 1); }
  }
  const active = days.find((d) => d.date === sel) ?? null;
  const worked = days.filter((d) => d.tasks.length > 0).length;
  return (
    <View className="gap-2 rounded-2xl border border-slate-200 bg-white p-3">
      <View className="flex-row items-baseline justify-between">
        <Text className="text-[15px] font-bold text-slate-900">Gün gün</Text>
        <Text className="text-[11px] text-slate-500">kap kurulan gün {worked}/{days.length}</Text>
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="gap-2">
        {days.map((d) => {
          const by = new Map<string, number>();
          for (const t of d.tasks) {
            const n = t.item_id != null ? subjOf.get(t.item_id) ?? "Diğer" : "Diğer";
            by.set(n, (by.get(n) ?? 0) + (t.itemless ? (t.status === "completed" ? 1 : 0) : t.done));
          }
          const empty = d.tasks.length === 0;
          const open = d.tasks.filter((t) => t.status !== "completed").length;
          return (
            <Pressable
              key={d.date}
              onPress={() => setSel(sel === d.date ? null : d.date)}
              className={cn(
                "w-[78px] gap-1 rounded-xl border p-2",
                empty ? "border-dashed border-slate-300" : "border-slate-200",
                d.date === today && "border-cyan-600",
                sel === d.date && "bg-cyan-50",
              )}
            >
              <Text className="text-[11px] font-bold text-slate-800">{DAY_SHORT[d.weekday]} {fmtDate(d.date)}</Text>
              <View className="h-12 flex-col-reverse overflow-hidden rounded bg-slate-100">
                {[...by.entries()].map(([n, v]) => (
                  <View key={n} style={{ height: (48 * v) / max, backgroundColor: subjectColors(n).rail }} />
                ))}
              </View>
              <Text className="text-[10px] text-slate-500">{empty ? "kap boş" : `${d.done_units} birim`}</Text>
              {open > 0 ? <Text className="text-[10px] font-semibold text-amber-700">{open} açık</Text> : null}
            </Pressable>
          );
        })}
        {future.map((d) => {
          const [y, m, dd] = d.split("-").map(Number);
          const wd = (new Date(y, m - 1, dd).getDay() + 6) % 7;
          const isSession = d === expected;
          return (
            <View key={d} className={cn("w-[78px] gap-1 rounded-xl border border-dashed p-2", isSession ? "border-cyan-600" : "border-slate-200 opacity-60")}>
              <Text className="text-[11px] font-semibold text-slate-500">{DAY_SHORT[wd]} {fmtDate(d)}</Text>
              <View className="h-12 rounded bg-slate-50" />
              <Text className="text-[10px] text-slate-500">{isSession ? "seans" : "gelecek"}</Text>
            </View>
          );
        })}
      </ScrollView>
      {active ? (
        <View className="gap-1.5 rounded-xl bg-slate-50 p-3">
          <Text className="text-[13px] font-bold text-slate-800">{DAY_SHORT[active.weekday]} {fmtDate(active.date)}</Text>
          {active.tasks.length === 0 ? (
            <Text className="text-xs text-slate-500">Bu gün kap boş kaldı.</Text>
          ) : (
            active.tasks.map((t) => {
              const n = t.item_id != null ? subjOf.get(t.item_id) ?? "Diğer" : "Diğer";
              const done = t.status === "completed";
              return (
                <View key={t.task_id} className="gap-1 border-t border-slate-200 pt-1.5">
                  <View className="flex-row items-center gap-2">
                    <View className={cn("size-2 rounded-full", done ? "bg-emerald-500" : "bg-amber-400")} />
                    <SubjectChip name={n} />
                  </View>
                  <Text className="text-[13px] text-slate-800">{t.title}</Text>
                  <Text className="text-[11px] text-slate-500">
                    {t.itemless ? (done ? "yapıldı" : "yapılmadı") : `${t.done}${t.planned ? `/${t.planned}` : ""} test çözdü`}
                    {t.correct != null || t.wrong != null ? ` · ${t.correct ?? 0}D ${t.wrong ?? 0}Y ${t.blank ?? 0}B` : ""}
                  </Text>
                </View>
              );
            })
          )}
        </View>
      ) : (
        <Text className="text-[11px] text-slate-400">Güne dokun → o günün görevleri.</Text>
      )}
    </View>
  );
}

function ItemCard({ it, onApprove }: { it: PoolPeriodDetailItem; onApprove?: (ok: boolean) => void }) {
  const c = subjectColors(it.subject_name);
  const u = split(it);
  return (
    <View className="gap-1.5 rounded-xl border border-l-4 border-slate-200 bg-white p-3" style={{ borderLeftColor: c.rail }}>
      <Text className={cn("text-[14px] font-semibold text-slate-900", it.teacher_homework && "italic text-violet-800")}>{it.title}</Text>
      <Text className="text-[11px] text-slate-500">
        {it.quantity} {UNIT_LABELS[it.unit]} · öğrenci {it.completed} · seansta {it.session_marked} · kalan {it.remaining}
        {it.carry_count > 0 ? ` · devir ×${it.carry_count}` : ""}
      </Text>
      {it.unit !== "etkinlik" ? <SplitBar total={u.total} student={u.student} session={u.session} color={c.rail} h={5} /> : null}
      <View className="flex-row flex-wrap gap-1">
        {it.teacher_homework ? <Badge text="öğretmen ödevi" cls="bg-violet-700" /> : null}
        {it.cup_returns >= 3 && it.remaining > 0 ? <Badge text={`${it.cup_returns} kez kaptan döndü`} cls="bg-rose-700" /> : null}
        {it.cup_attempts === 0 && it.remaining > 0 && it.completed === 0 ? <Badge text="hiç kaba alınmadı" cls="bg-slate-600" /> : null}
      </View>
      {onApprove ? (
        <View className="mt-1 flex-row gap-2">
          <Pressable onPress={() => onApprove(true)} className="flex-1 items-center rounded-lg bg-emerald-700 py-2 active:bg-emerald-800">
            <Text className="text-sm font-bold text-white">Onayla</Text>
          </Pressable>
          <Pressable onPress={() => onApprove(false)} className="flex-1 items-center rounded-lg border border-slate-300 bg-white py-2 active:bg-slate-50">
            <Text className="text-sm font-semibold text-slate-700">Reddet</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function Badge({ text, cls }: { text: string; cls: string }) {
  return (
    <View className={cn("rounded-full px-2 py-0.5", cls)}>
      <Text className="text-[10px] font-bold text-white">{text}</Text>
    </View>
  );
}

export function PoolWatchView({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const bundle = useQuery({ queryKey: teacherPoolKeys.bundle(studentId), queryFn: () => getTeacherPool(studentId) });
  const periodId = bundle.data?.period?.id ?? null;
  const detail = useQuery({
    queryKey: teacherPoolKeys.period(studentId, periodId ?? 0),
    queryFn: () => getTeacherPoolPeriod(studentId, periodId!),
    enabled: periodId != null,
  });
  const [showDone, setShowDone] = React.useState(false);
  const approve = useMutation({
    mutationFn: (v: { id: number; ok: boolean }) => approveTeacherPoolItem(studentId, v.id, v.ok),
    onSuccess: () => qc.invalidateQueries({ queryKey: teacherPoolKeys.bundle(studentId) }), // dönem ayrıntısı da bu önekin altında
    onError: () => Alert.alert("Kaydedilemedi", "Tekrar dene."),
  });
  const refreshing = bundle.isRefetching || detail.isRefetching;
  const refresh = () => { bundle.refetch(); detail.refetch(); };

  if (bundle.isLoading || (periodId != null && detail.isLoading)) {
    return <View className="flex-1 items-center justify-center"><ActivityIndicator size="large" color="#0e7490" /></View>;
  }
  if (bundle.isError || !bundle.data) {
    return (
      <View className="flex-1 items-center justify-center gap-3 px-8">
        <Text className="text-base font-semibold text-slate-700">Havuz yüklenemedi</Text>
        <Pressable onPress={refresh} className="rounded-xl bg-brand-700 px-5 py-2.5"><Text className="font-semibold text-white">Tekrar dene</Text></Pressable>
      </View>
    );
  }
  const b = bundle.data;
  if (!b.period || !detail.data) {
    return (
      <View className="flex-1 items-center justify-center gap-2 px-8">
        <Ionicons name="file-tray-outline" size={34} color="#94a3b8" />
        <Text className="text-center text-sm text-slate-600">Açık havuz dönemi yok. Seans günü dönemi web panelinden aç ve havuzu yaz.</Text>
      </View>
    );
  }
  const p = b.period;
  const s = p.summary;
  const d = detail.data;
  const items = d.items;
  const counted = items.filter((i) => i.counts);
  const tot = counted.map(split).reduce((a, u) => ({ total: a.total + u.total, student: a.student + u.student, session: a.session + u.session }), { total: 0, student: 0, session: 0 });

  // ders ders
  const subj = new Map<string, { total: number; student: number; session: number; items: number; done: number }>();
  for (const it of counted) {
    const u = split(it);
    const a = subj.get(it.subject_name) ?? { total: 0, student: 0, session: 0, items: 0, done: 0 };
    a.total += u.total; a.student += u.student; a.session += u.session; a.items += 1; a.done += it.remaining === 0 ? 1 : 0;
    subj.set(it.subject_name, a);
  }
  const subjects = [...subj.entries()].sort((x, y) => y[1].total - x[1].total);
  const order = new Map(subjects.map(([n], i) => [n, i]));

  const pending = items.filter((i) => i.source === "ogrenci" && i.approval === "bekliyor");
  const open = items.filter((i) => i.remaining > 0 && !pending.includes(i));
  const done = items.filter((i) => i.remaining === 0 && !pending.includes(i));
  const groups = new Map<string, PoolPeriodDetailItem[]>();
  for (const it of open) groups.set(it.subject_name, [...(groups.get(it.subject_name) ?? []), it]);
  const grouped = [...groups.entries()].sort((a, b2) => (order.get(a[0]) ?? 99) - (order.get(b2[0]) ?? 99));
  const flag = b.flags.primary[0];

  return (
    <ScrollView
      className="flex-1 bg-slate-50"
      contentContainerClassName="gap-3 px-4 py-4"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} tintColor="#0e7490" />}
    >
      {/* özet */}
      <View className="gap-3 rounded-2xl border border-slate-200 bg-white p-4">
        <View className="flex-row items-center gap-3">
          <Text className={cn("text-4xl font-extrabold", pctTone(s.pct))}>%{s.pct}</Text>
          <Text className="flex-1 text-[13px] text-slate-600">{s.done_units}/{s.total_units} birim · açılış {fmtDate(p.opened_on)}</Text>
        </View>
        <SplitBar total={tot.total} student={tot.student} session={tot.session} color="#0e7490" h={10} />
        <Text className="text-[11px] text-slate-500">
          öğrenci kaydı <Text className="font-bold text-slate-800">{tot.student}</Text> · seansta işaret{" "}
          <Text className="font-bold text-slate-800">{tot.session}</Text> · kalan{" "}
          <Text className="font-bold text-slate-800">{Math.max(0, tot.total - tot.student - tot.session)}</Text>
        </Text>
        <View className="flex-row gap-2">
          <Stat label="Dönem" value={`${p.days_open + 1}. gün`} sub={`kalem ${s.items_done}/${s.items_total}`} />
          <Stat label="Seansa" value={`${s.days_left} gün`} sub={s.expected_next_on ? fmtDate(s.expected_next_on) : "beklenen yok"} />
          <Stat label="Günde" value={String(s.per_day_needed)} sub="birim gerekli" />
        </View>
      </View>

      {flag ? (
        <View className={cn("gap-1 rounded-2xl border p-3", flag.level === "red" ? "border-rose-200 bg-rose-50" : "border-amber-200 bg-amber-50")}>
          <Text className={cn("text-[14px] font-bold", flag.level === "red" ? "text-rose-800" : "text-amber-900")}>{flag.title}</Text>
          <Text className={cn("text-xs", flag.level === "red" ? "text-rose-800" : "text-amber-900")}>{flag.detail}</Text>
        </View>
      ) : null}

      <DayCells days={d.days} items={items} today={d.today} expected={s.expected_next_on} />

      {subjects.length > 0 ? (
        <View className="gap-3 rounded-2xl border border-slate-200 bg-white p-3">
          <Text className="text-[15px] font-bold text-slate-900">Derslere göre ilerleme</Text>
          {subjects.map(([n, a]) => {
            const pct = a.total > 0 ? Math.round((100 * (a.student + a.session)) / a.total) : 0;
            return (
              <View key={n} className="gap-1">
                <View className="flex-row items-center justify-between gap-2">
                  <SubjectChip name={n} />
                  <Text className={cn("text-base font-extrabold", pctTone(pct))}>%{pct}</Text>
                </View>
                <SplitBar total={a.total} student={a.student} session={a.session} color={subjectColors(n).rail} />
                <Text className="text-[11px] text-slate-500">
                  {a.student + a.session}/{a.total} birim · {a.done}/{a.items} kalem bitti{a.session > 0 ? ` · ${a.session} seansta` : ""}
                </Text>
              </View>
            );
          })}
          <Text className="text-[10px] text-slate-400">koyu = öğrenci kaydı · açık = seansta işaretlenen</Text>
        </View>
      ) : null}

      {pending.length > 0 ? (
        <View className="gap-2">
          <Text className="px-1 text-sm font-bold text-amber-800">Onayını bekleyen öğrenci kalemleri ({pending.length})</Text>
          {pending.map((it) => (
            <ItemCard key={it.id} it={it} onApprove={(ok) => approve.mutate({ id: it.id, ok })} />
          ))}
        </View>
      ) : null}

      <View className="gap-2">
        <Text className="px-1 text-sm font-bold text-slate-700">Bekleyen kalemler · {open.length} kalem, {done.length} bitti</Text>
        {open.length === 0 ? (
          <Text className="rounded-xl border border-dashed border-slate-300 bg-white p-4 text-center text-sm text-slate-500">
            Havuzdaki her kalem bitti.
          </Text>
        ) : (
          grouped.map(([n, list]) => (
            <View key={n} className="gap-2">
              <View className="flex-row items-center gap-2 px-1">
                <SubjectChip name={n} />
                <Text className="text-[11px] text-slate-500">
                  {list.length} kalem · {list.reduce((a, i) => a + (i.unit === "etkinlik" ? 1 : i.remaining), 0)} birim kaldı
                </Text>
              </View>
              {list.map((it) => <ItemCard key={it.id} it={it} />)}
            </View>
          ))
        )}
        {done.length > 0 ? (
          <Pressable onPress={() => setShowDone((v) => !v)} className="flex-row items-center gap-1 px-1 py-2">
            <Ionicons name={showDone ? "chevron-down" : "chevron-forward"} size={16} color="#047857" />
            <Text className="text-sm font-semibold text-emerald-700">{done.length} kalem bitti — {showDone ? "gizle" : "göster"}</Text>
          </Pressable>
        ) : null}
        {showDone ? done.map((it) => <ItemCard key={it.id} it={it} />) : null}
      </View>

      <Text className="px-1 pb-4 text-[11px] text-slate-400">Havuza kalem eklemek ve seansı bitirmek web panelinde.</Text>
    </ScrollView>
  );
}
