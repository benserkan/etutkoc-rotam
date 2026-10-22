import { Ionicons } from "@expo/vector-icons";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import * as React from "react";
import { ActivityIndicator, Alert, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { PeriodDetailSheet } from "@/components/pool/period-detail-sheet";
import { StudentAddItemSheet } from "@/components/pool/student-add-item-sheet";
import { FormSheet } from "@/components/ui/form-sheet";
import { ApiError } from "@/lib/api";
import {
  addStudentPoolItem, cupAdd, cupReturn, getStudentPool, getStudentPoolPeriod, poolKeys, poolPeriodKeys, UNIT_LABELS,
  type StudentPoolItem, type StudentPoolResponse,
} from "@/lib/pool";

/**
 * Havuzum — haftalık görev havuzu (dershane modu, K34–K41).
 * Öğrenci bugünün kabını havuzdan kendisi kurar; kap = Bugün ekranındaki görev.
 * Yapılmayan kalem gece havuza döner. Rehber yeni havuzu seansta yazar.
 */
export default function StudentPoolRoute() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: poolKeys.pool, queryFn: getStudentPool });
  const [busy, setBusy] = React.useState(false);
  const [pick, setPick] = React.useState<StudentPoolItem | null>(null);
  const [addOpen, setAddOpen] = React.useState(false);
  const [showProjection, setShowProjection] = React.useState(false);

  async function run(fn: () => Promise<unknown>, after?: () => void) {
    setBusy(true);
    try {
      await fn();
      await qc.invalidateQueries({ queryKey: ["student"] });
      after?.();
    } catch (e) {
      Alert.alert("Olmadı", e instanceof ApiError ? e.message : "Bağlantını kontrol et.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-200" accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="flex-1 text-base font-semibold text-slate-800">Havuzum</Text>
        <Pressable onPress={() => router.push("/program-history")} hitSlop={6} accessibilityLabel="Program geçmişim"
                   className="size-9 items-center justify-center rounded-full active:bg-slate-200">
          <Ionicons name="time-outline" size={20} color="#334155" />
        </Pressable>
        {q.data?.mode === "havuz" && q.data.period_id ? (
          <Pressable onPress={() => setAddOpen(true)} className="flex-row items-center gap-1 rounded-full bg-brand-700 px-3 py-1.5 active:bg-brand-800">
            <Ionicons name="add" size={16} color="#fff" />
            <Text className="text-xs font-semibold text-white">Kalem ekle</Text>
          </Pressable>
        ) : null}
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center"><ActivityIndicator size="large" color="#0e7490" /></View>
      ) : q.isError || !q.data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800"><Text className="font-semibold text-white">Tekrar dene</Text></Pressable>
        </View>
      ) : q.data.mode !== "havuz" ? (
        <View className="flex-1 items-center justify-center gap-2 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Haftalık havuz modu kapalı</Text>
          <Text className="text-center text-sm text-slate-500">Programın gün gün hazırlanıyor; Bugün sekmesine dön.</Text>
        </View>
      ) : !q.data.period_id || !q.data.summary ? (
        <View className="flex-1 items-center justify-center gap-2 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">{q.data.on_break ? "Ara (tatil)" : "Havuz henüz yazılmadı"}</Text>
          <Text className="text-center text-sm text-slate-500">
            {q.data.on_break
              ? `${fmtDate(q.data.on_break.since)} tarihinden beri aradasın; hatırlatma gelmez. Rehberin yeni dönemi açınca havuzun burada görünür.`
              : "Rehberin seansta haftanın havuzunu yazınca burada görünür."}
          </Text>
          <PreviousPeriods previous={q.data.previous ?? []} center />
        </View>
      ) : (
        <PoolBody
          data={q.data}
          busy={busy}
          refreshing={q.isRefetching}
          onRefresh={() => q.refetch()}
          showProjection={showProjection}
          onToggleProjection={() => setShowProjection((v) => !v)}
          onPick={(it) => (it.unit === "etkinlik" || it.remaining === 1 ? run(() => cupAdd(it.id)) : setPick(it))}
          onReturn={(taskId) => run(() => cupReturn(taskId))}
        />
      )}

      {pick ? (
        <CountSheet
          item={pick}
          busy={busy}
          onClose={() => setPick(null)}
          onPick={(n) => run(() => cupAdd(pick.id, n), () => setPick(null))}
        />
      ) : null}
      {q.data ? (
        <StudentAddItemSheet
          visible={addOpen}
          data={q.data}
          busy={busy}
          onClose={() => setAddOpen(false)}
          onSubmit={(b) => run(() => addStudentPoolItem(b), () => setAddOpen(false))}
        />
      ) : null}
    </SafeAreaView>
  );
}

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", weekday: "short" });
}

function PoolBody({
  data, busy, refreshing, onRefresh, showProjection, onToggleProjection, onPick, onReturn,
}: {
  data: StudentPoolResponse; busy: boolean; refreshing: boolean; onRefresh: () => void;
  showProjection: boolean; onToggleProjection: () => void;
  onPick: (it: StudentPoolItem) => void; onReturn: (taskId: number) => void;
}) {
  const s = data.summary!;
  const suggested = data.items.filter((i) => i.suggested);
  const groups = new Map<string, StudentPoolItem[]>();
  for (const it of data.items) {
    const g = groups.get(it.subject_name) ?? [];
    g.push(it);
    groups.set(it.subject_name, g);
  }
  const paceColor = s.pace === "geride" ? "text-amber-100" : "text-brand-100";
  return (
    <ScrollView
      className="flex-1"
      contentContainerClassName="px-4 pb-10 gap-4"
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#0e7490" />}
    >
      {/* Özet (K41) */}
      <View className="rounded-2xl bg-brand-700 p-5">
        <Text className="text-xs font-semibold uppercase tracking-wider text-brand-100">Bu haftanın havuzu</Text>
        <View className="mt-2 flex-row items-end justify-between">
          <Text className="text-3xl font-extrabold text-white">
            {s.done_units}<Text className="text-lg font-semibold text-brand-100">/{s.total_units} birim</Text>
          </Text>
          <Text className="text-2xl font-bold text-white">%{s.pct}</Text>
        </View>
        <View className="mt-2 h-2 overflow-hidden rounded-full bg-white/25">
          <View className="h-full rounded-full bg-white" style={{ width: `${Math.min(100, s.pct)}%` }} />
        </View>
        <Text className="mt-2 text-xs text-brand-100">
          {s.items_done}/{s.items_total} kalem · seansa {s.days_left} gün{s.expected_next_on ? ` (${fmtDate(s.expected_next_on)})` : ""}
        </Text>
        {/* "Tempo biraz geride" ipucu aynı cümleyi zaten söylüyor — tekrar etme */}
        {!(s.pace === "geride" && (data.hints ?? []).some((h) => h.code === "pool_behind")) ? (
          <Text className={`mt-1 text-sm font-medium ${paceColor}`}>{s.pace_note}</Text>
        ) : null}
      </View>

      {/* Bugün dershanede */}
      {data.lesson_today.length > 0 ? (
        <Text className="text-xs text-slate-500">Bugün dershanede: {data.lesson_today.join(", ")}</Text>
      ) : null}

      {/* K41/K46/K48: yönlendirme — kırmızı yok, yargı yok */}
      {(data.hints ?? []).map((h) => (
        <View key={h.code} className="rounded-2xl border border-cyan-200 bg-cyan-50 px-4 py-3">
          <Text className="text-sm text-cyan-950">
            <Text className="font-semibold">{h.title}. </Text>
            {h.note}
          </Text>
        </View>
      ))}

      {/* Bugünün kabı */}
      <View className="rounded-2xl border border-slate-200 bg-white p-4">
        <View className="flex-row items-center justify-between">
          <Text className="text-base font-semibold text-slate-800">Bugünün kabı</Text>
          <Pressable onPress={() => router.navigate("/(app)/student/today")} hitSlop={6}>
            <Text className="text-xs font-semibold text-brand-700">Bugün ekranında işaretle →</Text>
          </Pressable>
        </View>
        {data.cup.length === 0 ? (
          <Text className="mt-1 text-sm text-slate-500">Kabın boş. Aşağıdan bugün yapacağın kalemleri seç.</Text>
        ) : (
          <View className="mt-2 gap-1.5">
            {data.cup.map((c) => (
              <View key={c.task_id} className="flex-row items-center gap-2 rounded-xl bg-slate-50 px-3 py-2">
                <Ionicons name={c.status === "completed" ? "checkmark-circle" : "ellipse-outline"} size={18} color={c.status === "completed" ? "#059669" : "#94a3b8"} />
                <Text className="flex-1 text-sm text-slate-800" numberOfLines={3}>{c.title}</Text>
                {c.can_return ? (
                  <Pressable onPress={() => onReturn(c.task_id)} disabled={busy} hitSlop={6} accessibilityLabel="Havuza geri al">
                    <Ionicons name="arrow-undo-outline" size={18} color="#64748b" />
                  </Pressable>
                ) : null}
              </View>
            ))}
          </View>
        )}
      </View>

      {/* Öneri (K37) */}
      {suggested.length > 0 ? (
        <View className="rounded-2xl border border-brand-200 bg-brand-50 p-4">
          <Text className="text-sm font-semibold text-brand-900">Bugün için öneri</Text>
          <Text className="mt-0.5 text-xs text-brand-800">Günü belli olan ya da bugün dershanede işlenen dersin kalemleri önce.</Text>
          <View className="mt-2 gap-1.5">
            {suggested.map((it) => <ItemRow key={it.id} it={it} busy={busy} onPick={onPick} />)}
          </View>
        </View>
      ) : null}

      {/* Havuz */}
      {[...groups.entries()].map(([name, list]) => (
        <View key={name} className="gap-1.5">
          <Text className="text-xs font-semibold uppercase tracking-wide text-slate-500">{name}</Text>
          {list.map((it) => <ItemRow key={it.id} it={it} busy={busy} onPick={onPick} />)}
        </View>
      ))}

      {/* Projeksiyon (K35) */}
      <Pressable onPress={onToggleProjection} className="rounded-2xl border border-dashed border-slate-300 bg-white p-3">
        <Text className="text-sm font-medium text-slate-700">Haftaya nasıl dağılır? (öneri, zorunlu değil) {showProjection ? "▴" : "▾"}</Text>
        {showProjection ? (
          <View className="mt-2 flex-row flex-wrap gap-1.5">
            {data.projection.map((p) => (
              <View key={p.date} className="rounded-lg bg-slate-100 px-2 py-1">
                <Text className="text-[11px] text-slate-600">{fmtDate(p.date)}</Text>
                <Text className="text-sm font-semibold text-slate-800">~{p.units} birim</Text>
              </View>
            ))}
          </View>
        ) : null}
      </Pressable>
      <PreviousPeriods previous={data.previous ?? []} />
    </ScrollView>
  );
}

/** K60/K41: önceki dönemler — dokununca kalem kalem + gün gün (salt okuma, yargı yok). */
function PreviousPeriods({ previous, center }: { previous: StudentPoolResponse["previous"]; center?: boolean }) {
  const [openId, setOpenId] = React.useState<number | null>(null);
  if (previous.length === 0) return null;
  return (
    <View className={`mt-3 ${center ? "items-center" : ""}`}>
      <Text className="text-xs text-slate-500">Önceki dönemlerin (dokun → ayrıntı)</Text>
      <View className={`mt-1 flex-row flex-wrap gap-1.5 ${center ? "justify-center" : ""}`}>
        {previous.map((p) => (
          <Pressable key={p.id} onPress={() => setOpenId(p.id)} className="rounded-full border border-slate-300 bg-white px-3 py-1 active:bg-slate-100">
            <Text className="text-xs font-medium text-slate-800">{fmtDate(p.opened_on)} %{p.pct}</Text>
          </Pressable>
        ))}
      </View>
      <PeriodDetailSheet visible={openId != null} onClose={() => setOpenId(null)}
                         queryKey={poolPeriodKeys.student(openId ?? 0)} queryFn={() => getStudentPoolPeriod(openId!)} />
    </View>
  );
}

function ItemRow({ it, busy, onPick }: { it: StudentPoolItem; busy: boolean; onPick: (it: StudentPoolItem) => void }) {
  const done = it.remaining === 0;
  const pending = it.source === "ogrenci" && it.approval === "bekliyor";
  return (
    <View className={`flex-row items-center gap-2 rounded-xl border bg-white px-3 py-2 ${done ? "border-emerald-200" : "border-slate-200"}`}>
      <View className="min-w-0 flex-1">
        <Text className={`text-sm text-slate-800 ${it.teacher_homework ? "italic" : ""}`}>{it.title}</Text>
        <Text className="text-xs text-slate-500">
          {it.quantity} {UNIT_LABELS[it.unit]}{it.done > 0 ? ` · ${it.done} yapıldı` : ""}{!done ? ` · ${it.remaining} kaldı` : " · bitti"}
          {it.teacher_homework ? " · ders öğretmeni ödevi" : ""}{pending ? " · onay bekliyor" : ""}{it.day_hint ? ` · ${fmtDate(it.day_hint)}` : ""}
        </Text>
      </View>
      {done ? (
        <Ionicons name="checkmark-circle" size={22} color="#059669" />
      ) : it.in_cup_today ? (
        <Text className="text-xs font-semibold text-brand-700">kapta</Text>
      ) : (
        <Pressable onPress={() => onPick(it)} disabled={busy} className="rounded-full bg-brand-700 px-3 py-1.5 active:bg-brand-800" accessibilityLabel="Kaba al">
          <Text className="text-xs font-semibold text-white">Kaba al</Text>
        </Pressable>
      )}
    </View>
  );
}

function CountSheet({ item, busy, onClose, onPick }: { item: StudentPoolItem; busy: boolean; onClose: () => void; onPick: (n: number) => void }) {
  const opts = Array.from({ length: Math.min(item.remaining, 8) }, (_, i) => i + 1);
  return (
    <FormSheet visible title="Bugün kaç tane?" onClose={onClose}>
      <Text className="text-sm text-slate-600">{item.title} · kalan {item.remaining} {UNIT_LABELS[item.unit]}</Text>
      <View className="mt-3 flex-row flex-wrap gap-2">
        {opts.map((n) => (
          <Pressable key={n} onPress={() => onPick(n)} disabled={busy} className="size-12 items-center justify-center rounded-full border border-slate-300 bg-white active:bg-brand-50">
            <Text className="text-base font-semibold text-slate-800">{n}</Text>
          </Pressable>
        ))}
        {item.remaining > 8 ? (
          <Pressable onPress={() => onPick(item.remaining)} disabled={busy} className="h-12 items-center justify-center rounded-full border border-slate-300 bg-white px-4 active:bg-brand-50">
            <Text className="text-base font-semibold text-slate-800">hepsi ({item.remaining})</Text>
          </Pressable>
        ) : null}
      </View>
    </FormSheet>
  );
}
