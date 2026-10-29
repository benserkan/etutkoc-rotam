/**
 * Konu Performansı — koç / öğrenci / veli ortak (web `shared/topic-performance-panel` ile aynı içerik).
 *
 * 2026-10-15 yeniden tasarım:
 *   1. Özet: çözülen test · doğruluk · SONUÇ GİRİLEN test · zayıf/dikkat konu (her sayı açıklamalı)
 *   2. Sonuç girilmemiş uyarısı (role göre yönlendirme)
 *   3. "Nerede puan kaybediyor?" — zayıf/dikkat konular kayıp sırasıyla (yalnız denemede olanlar dahil)
 *   4. Ders kartları: D/Y/B çubuğu, konular seviyeye göre (zayıf önce)
 */
import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { subjectColors } from "@/lib/subject-colors";
import {
  getTopicPerformance,
  topicPerfKeys,
  type SubjectPerfRow,
  type TopicPerfRow,
  type TopicPerfSource,
  type TopicPerformanceResponse,
} from "@/lib/topic-performance";
import { cn } from "@/lib/utils";

type Level = NonNullable<TopicPerfRow["level"]>;
const LEVEL: Record<Level, { label: string; bg: string; text: string; rank: number }> = {
  zayif: { label: "Zayıf", bg: "bg-rose-700", text: "text-white", rank: 0 },
  dikkat: { label: "Dikkat", bg: "bg-amber-500", text: "text-amber-950", rank: 1 },
  iyi: { label: "İyi", bg: "bg-emerald-700", text: "text-white", rank: 2 },
  veri_yok: { label: "Sonuç yok", bg: "bg-slate-600", text: "text-white", rank: 3 },
};

function accText(pct: number | null | undefined): string {
  if (pct == null) return "text-slate-400";
  if (pct >= 70) return "text-emerald-700";
  if (pct >= 50) return "text-amber-700";
  return "text-rose-700";
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `${d.getDate()}.${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function LevelBadge({ level }: { level: TopicPerfRow["level"] }) {
  const m = LEVEL[level ?? "veri_yok"];
  return (
    <View className={cn("rounded px-1.5 py-0.5", m.bg)}>
      <Text className={cn("text-[10.5px] font-bold", m.text)}>{m.label}</Text>
    </View>
  );
}

function DybBar({ c, w, b }: { c: number; w: number; b: number }) {
  const total = c + w + b;
  return (
    <View className="h-2 flex-row overflow-hidden rounded-full bg-slate-100">
      {total > 0 ? (
        <>
          <View className="bg-emerald-500" style={{ width: `${(100 * c) / total}%` }} />
          <View className="bg-rose-500" style={{ width: `${(100 * w) / total}%` }} />
          <View className="bg-slate-400" style={{ width: `${(100 * b) / total}%` }} />
        </>
      ) : null}
    </View>
  );
}

function Stat({ icon, label, value, unit, note, valueCls }: {
  icon: React.ComponentProps<typeof Ionicons>["name"]; label: string; value: string; unit?: string; note: string; valueCls?: string;
}) {
  return (
    <View className="min-w-[46%] flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5">
      <View className="flex-row items-center gap-1">
        <Ionicons name={icon} size={13} color="#64748b" />
        <Text className="text-[11.5px] font-medium text-slate-500">{label}</Text>
      </View>
      <Text className={cn("mt-0.5 text-xl font-extrabold", valueCls ?? "text-slate-900")}>
        {value}
        {unit ? <Text className="text-xs font-medium text-slate-500"> {unit}</Text> : null}
      </Text>
      <Text className="text-[11px] leading-snug text-slate-500">{note}</Text>
    </View>
  );
}

function SubjectCard({ s }: { s: SubjectPerfRow }) {
  const [open, setOpen] = React.useState(false);
  const c = subjectColors(s.subject_name);
  const session = s.session_tests ?? 0;
  const enterable = Math.max(0, s.tests_solved - session);
  const weak = s.weak_topics ?? 0;
  const topics = [...s.topics].sort(
    (a, b) => LEVEL[a.level ?? "veri_yok"].rank - LEVEL[b.level ?? "veri_yok"].rank || b.tests_solved - a.tests_solved,
  );
  return (
    <View className="overflow-hidden rounded-2xl border border-slate-200 bg-white" style={{ borderLeftWidth: 4, borderLeftColor: c.rail }}>
      <Pressable onPress={() => setOpen((v) => !v)} className="gap-2 px-4 py-3 active:bg-slate-50" accessibilityRole="button">
        <View className="flex-row items-start gap-2">
          <Ionicons name={open ? "chevron-down" : "chevron-forward"} size={16} color="#737782" style={{ marginTop: 2 }} />
          <View className="min-w-0 flex-1">
            <Text className="text-sm font-semibold text-slate-900">{s.subject_name}</Text>
            <Text className="text-[11.5px] text-slate-500">
              {s.tests_solved} test · {s.topics.length} konu · sonucu girilen {s.tests_with_result ?? 0}/{enterable}
              {session > 0 ? ` · ${session} seansta` : ""}
            </Text>
          </View>
          <Text className={cn("text-lg font-extrabold", accText(s.accuracy_pct))}>
            {s.accuracy_pct == null ? "—" : `%${s.accuracy_pct}`}
          </Text>
        </View>
        <DybBar c={s.correct} w={s.wrong} b={s.blank ?? 0} />
        <View className="flex-row items-center justify-between">
          <Text className="text-[11.5px] text-slate-500">
            <Text className="text-emerald-700">{s.correct} D</Text> · <Text className="text-rose-700">{s.wrong} Y</Text> · {s.blank ?? 0} B
          </Text>
          {weak > 0 ? (
            <View className="rounded bg-rose-700 px-1.5 py-0.5">
              <Text className="text-[10.5px] font-bold text-white">{weak} zayıf/dikkat</Text>
            </View>
          ) : null}
        </View>
      </Pressable>
      {open ? (
        <View className="border-t border-slate-100">
          {topics.map((tp) => {
            const sess = tp.session_tests ?? 0;
            const hasRes = tp.answered + (tp.blank ?? 0) > 0;
            return (
              <View key={`${tp.topic_id ?? "l"}-${tp.topic_name}`} className="gap-1.5 border-b border-slate-100 px-4 py-2.5">
                <View className="flex-row items-start gap-2">
                  <View className="min-w-0 flex-1 flex-row flex-wrap items-center gap-1.5">
                    <Text className="text-[13px] font-medium text-slate-800">{tp.topic_name}</Text>
                    <LevelBadge level={tp.level} />
                  </View>
                  <Text className={cn("text-sm font-bold", accText(tp.accuracy_pct))}>
                    {tp.accuracy_pct == null ? "—" : `%${tp.accuracy_pct}`}
                  </Text>
                </View>
                <Text className="text-[11px] text-slate-500">
                  {tp.tests_solved} test{sess > 0 ? ` (${sess} tanesi seansta)` : ""}
                  {tp.last_solved_at ? ` · son: ${fmtDate(tp.last_solved_at)}` : ""}
                  {(tp.exam_answered ?? 0) > 0 ? ` · denemede %${tp.exam_accuracy_pct} (${tp.exam_answered} soru)` : ""}
                </Text>
                <DybBar c={tp.correct} w={tp.wrong} b={tp.blank ?? 0} />
                <Text className="text-[11px] text-slate-500">
                  {hasRes ? `${tp.correct} D · ${tp.wrong} Y · ${tp.blank ?? 0} B` : "sonuç girilmemiş"}
                </Text>
              </View>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

export default function TopicPerformanceRoute() {
  const params = useLocalSearchParams<{ source?: string; id?: string }>();
  const source = (params.source ?? "student") as TopicPerfSource;
  const sid = params.id ? Number(params.id) : undefined;

  const key = source === "student" ? topicPerfKeys.student() : source === "parent" ? topicPerfKeys.parent(sid ?? 0) : topicPerfKeys.teacher(sid ?? 0);
  const q = useQuery<TopicPerformanceResponse>({ queryKey: key, queryFn: () => getTopicPerformance(source, sid) });

  const who = source === "parent" ? "Çocuğunuzun" : source === "student" ? "Senin" : "Öğrencinin";

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable onPress={() => router.back()} hitSlop={8} className="size-10 items-center justify-center rounded-full active:bg-slate-200" accessibilityLabel="Geri">
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="text-base font-semibold text-slate-800">Konu Performansı</Text>
      </View>

      {q.isLoading ? (
        <View className="items-center py-16"><ActivityIndicator size="large" color="#0e7490" /></View>
      ) : q.isError || !q.data ? (
        <View className="items-center gap-3 px-8 py-16">
          <Text className="text-center text-sm font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : q.data.subjects.length === 0 && (q.data.focus ?? []).length === 0 ? (
        <View className="items-center gap-2 px-8 py-16">
          <Ionicons name="locate-outline" size={36} color="#737782" />
          <Text className="text-center text-sm font-medium text-slate-700">Henüz konu performansı yok</Text>
          <Text className="text-center text-xs text-slate-500">
            {source === "student"
              ? "Test çözüp doğru/yanlış/boş sayını girdikçe her dersin konularındaki performansın burada birikir."
              : `${who} çözdüğü testlerde doğru/yanlış/boş girildikçe ders ve konu bazında performans burada görünür.`}
          </Text>
        </View>
      ) : (
        <Body data={q.data} source={source} />
      )}
    </SafeAreaView>
  );
}

function Body({ data, source }: { data: TopicPerformanceResponse; source: TopicPerfSource }) {
  const o = data.overall;
  const session = o.session_tests ?? 0;
  const enterable = Math.max(0, o.tests_solved - session);
  const withRes = o.tests_with_result ?? 0;
  const cov = o.result_coverage_pct ?? null;
  const focus = data.focus ?? [];
  const weakN = Math.max(o.weak_topics ?? 0, focus.length);
  const showGap = cov != null && enterable >= 3 && cov < 70;
  const action =
    source === "teacher"
      ? "Öğrenciden testi işaretlerken doğru / yanlış / boş sayısını da girmesini iste. Sonuç girilmeden zayıf konu tespiti yapılamaz."
      : source === "student"
        ? "Testi işaretlerken doğru / yanlış / boş sayını da gir; böylece hangi konuda zorlandığın burada görünür."
        : "Doğru / yanlış sayıları girildikçe hangi konularda zorlandığı burada görünür.";

  return (
    <ScrollView className="flex-1" contentContainerClassName="gap-3 px-4 py-3">
      <View className="flex-row flex-wrap gap-2">
        <Stat icon="locate-outline" label="Çözülen test" value={String(o.tests_solved)} unit="test"
              note={session > 0 ? `${session} tanesi koçun seansta işaretlediği (sonuçsuz)` : "görevlerde, deneme hariç"} />
        <Stat icon="analytics-outline" label="Doğruluk" value={o.accuracy_pct == null ? "—" : `%${o.accuracy_pct}`}
              valueCls={accText(o.accuracy_pct)}
              note={o.answered > 0 ? `${o.correct} D · ${o.wrong} Y · ${o.blank ?? 0} B soru` : "sonuç girilmediği için hesaplanamıyor"} />
        <Stat icon="clipboard-outline" label="Sonucu girilen" value={`${withRes}/${enterable}`} unit="test"
              valueCls={cov == null ? undefined : cov >= 70 ? "text-emerald-700" : cov >= 30 ? "text-amber-700" : "text-rose-700"}
              note={cov == null ? "henüz test yok" : `sonuç girilen test oranı: %${cov}`} />
        <Stat icon="warning-outline" label="Zayıf / dikkat" value={String(weakN)} unit="konu"
              valueCls={weakN > 0 ? "text-rose-700" : undefined}
              note={source === "parent" ? "çalışılması gereken konular" : "aşağıda kayıp sırasıyla"} />
      </View>

      {showGap ? (
        <View className="flex-row gap-2 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2.5">
          <Ionicons name="warning" size={16} color="#92400e" style={{ marginTop: 1 }} />
          <Text className="flex-1 text-[12.5px] leading-snug text-amber-950">
            <Text className="font-bold">{enterable} testin {enterable - withRes} tanesinde sonuç girilmemiş</Text> (sonuç girilen test oranı: %{cov}). {action}
          </Text>
        </View>
      ) : null}

      <View className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
        <View className="border-b border-slate-100 px-4 py-3">
          <Text className="text-sm font-semibold text-slate-900">
            {source === "student" ? "Nerede puan kaybediyorsun?" : "Nerede puan kaybediyor?"}
          </Text>
          <Text className="text-[11.5px] text-slate-500">Görevlerde ve son 90 gün denemelerde doğruluğu düşük konular — en çok soru kaybettiren önde.</Text>
        </View>
        {focus.length === 0 ? (
          <Text className="px-4 py-3 text-[12.5px] text-slate-500">
            {cov != null && cov < 30 ? "Sonuç girilmediği için zayıf konu tespiti yapılamıyor." : "Şu an zayıf görünen konu yok."}
          </Text>
        ) : (
          focus.map((t, i) => (
            <View key={`${t.topic_id ?? "l"}-${i}`} className="gap-1 border-b border-slate-100 px-4 py-2.5">
              <View className="flex-row flex-wrap items-center gap-1.5">
                <Text className="text-[13.5px] font-semibold text-slate-900">{t.topic_name}</Text>
                <LevelBadge level={t.level} />
                {t.exam_only ? (
                  <View className="rounded bg-violet-700 px-1.5 py-0.5">
                    <Text className="text-[10.5px] font-bold text-white">yalnız denemede</Text>
                  </View>
                ) : null}
              </View>
              <Text className="text-[11.5px] text-slate-500">{t.subject_name ?? "—"}</Text>
              <View className="flex-row flex-wrap gap-x-3">
                {t.answered > 0 ? (
                  <Text className="text-[11.5px] text-slate-600">
                    görevde <Text className={cn("font-bold", accText(t.accuracy_pct))}>%{t.accuracy_pct}</Text> ({t.answered} soru)
                  </Text>
                ) : null}
                {(t.exam_answered ?? 0) > 0 ? (
                  <Text className="text-[11.5px] text-slate-600">
                    denemede <Text className={cn("font-bold", accText(t.exam_accuracy_pct))}>%{t.exam_accuracy_pct}</Text> ({t.exam_answered} soru)
                  </Text>
                ) : null}
                <Text className="text-[11.5px] text-slate-600">
                  kaybedilen <Text className="font-bold text-slate-900">{t.loss_score ?? 0}</Text> soru
                </Text>
              </View>
            </View>
          ))
        )}
      </View>

      <Text className="px-1 pt-1 text-sm font-semibold text-slate-800">Derslere göre</Text>
      {data.subjects.map((s) => <SubjectCard key={s.subject_id} s={s} />)}

      <View className="rounded-xl bg-slate-100 px-3 py-2.5">
        <Text className="text-[11px] leading-relaxed text-slate-600">
          Doğruluk = doğru ÷ (doğru + yanlış); boş ayrıca gösterilir. Seviye: en az 8 soruda sonuç girilmişse %50 altı zayıf,
          %50–69 dikkat. Denemede en az 3 soruda %40 altı olan konu en az “dikkat” olur. Kaybedilen soru = görevde yanlış + boş
          + denemede yanlışın iki katı.
        </Text>
      </View>
      <View className="h-6" />
    </ScrollView>
  );
}
