import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import {
  getTeacherStudentCurriculum,
  teacherDetailKeys,
  type CurriculumProjectionItem,
  type CurriculumSubjectItem,
  type CurriculumTopicItem,
} from "@/lib/teacher";
import { cn } from "@/lib/utils";

const STATUS: Record<
  CurriculumTopicItem["status"],
  { label: string; dot: string; text: string }
> = {
  tamamlandi: { label: "Tamamlandı", dot: "bg-emerald-500", text: "text-emerald-700" },
  devam: { label: "Devam", dot: "bg-amber-500", text: "text-amber-700" },
  planlandi: { label: "Planlandı", dot: "bg-sky-500", text: "text-sky-700" },
  baslanmadi: { label: "Başlanmadı", dot: "bg-slate-300", text: "text-slate-500" },
  kaynak_yok: { label: "Kaynak yok", dot: "bg-slate-200", text: "text-slate-400" },
};

const VERDICT: Record<
  CurriculumProjectionItem["verdict"],
  { label: string; bg: string; border: string; text: string; bar: string }
> = {
  yetisir: { label: "Yetişir", bg: "bg-emerald-50", border: "border-emerald-200", text: "text-emerald-800", bar: "bg-emerald-500" },
  risk: { label: "Riskli — tempo artmalı", bg: "bg-amber-50", border: "border-amber-200", text: "text-amber-800", bar: "bg-amber-500" },
  yetismez: { label: "Yetişmez — acil hızlanma", bg: "bg-rose-50", border: "border-rose-200", text: "text-rose-800", bar: "bg-rose-500" },
  sinav_yok: { label: "Sınav tarihi yok", bg: "bg-slate-50", border: "border-slate-200", text: "text-slate-600", bar: "bg-slate-400" },
  veri_yok: { label: "Veri yetersiz", bg: "bg-slate-50", border: "border-slate-200", text: "text-slate-600", bar: "bg-slate-400" },
};

export function CurriculumTab({ studentId }: { studentId: number }) {
  const q = useQuery({
    queryKey: teacherDetailKeys.curriculum(studentId),
    queryFn: () => getTeacherStudentCurriculum(studentId),
    enabled: studentId > 0,
    staleTime: 30_000,
  });

  if (q.isLoading) {
    return (
      <View className="flex-1 items-center justify-center py-12">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }
  const data = q.data;
  if (!data || data.subjects.length === 0) {
    return (
      <View className="m-3 rounded-xl border border-slate-200 bg-white p-4">
        <Text className="text-sm text-slate-600">
          Bu öğrenci için müfredat haritası oluşturulamadı. Önce web panelinde
          kütüphanede kitap ünitelerini “Müfredata eşleştir” ile resmi konulara bağlayın.
        </Text>
      </View>
    );
  }

  return (
    <ScrollView className="flex-1 bg-slate-50" contentContainerStyle={{ padding: 12, gap: 12 }}>
      {/* Genel kapsama */}
      <View className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-4">
        <View className="flex-row items-center justify-between">
          <View className="flex-1 pr-2">
            <Text className="text-sm font-semibold text-indigo-900">Müfredat işlenme oranı</Text>
            <Text className="mt-0.5 text-xs text-indigo-700">
              {data.overall_started_topics}/{data.overall_total_topics} konuya girildi
              {data.curriculum_model ? ` · ${data.curriculum_model.toUpperCase()}` : ""}
              {data.grade_level ? ` · ${data.grade_level}. sınıf` : ""}
            </Text>
          </View>
          <Text className="text-2xl font-bold text-indigo-700">%{data.overall_coverage_pct}</Text>
        </View>
        <Bar pct={data.overall_coverage_pct} track="bg-indigo-100" fill="bg-indigo-500" />
        <Text className="mt-2 text-[11px] leading-4 text-indigo-700">
          “İşlenme” = en az bir test çözülen konu / toplam resmi konu.
        </Text>
      </View>

      {data.projection ? <ProjectionCard p={data.projection} /> : null}

      {data.subjects.map((s) => (
        <SubjectBlock key={s.subject_id} subject={s} />
      ))}

      {data.extras.length > 0 ? (
        <View className="rounded-xl border border-amber-200 bg-amber-50/60 p-3">
          <Text className="text-sm font-semibold text-amber-900">
            Müfredata eşleşmemiş üniteler ({data.extras.length})
          </Text>
          <Text className="mb-2 text-[11px] text-amber-700">
            Resmi konuya bağlanmamış; haritada görünmez. Web’de “Müfredata eşleştir” ile bağlayın.
          </Text>
          {data.extras.slice(0, 12).map((e) => (
            <Text key={e.section_id} className="text-xs text-amber-800">
              • {e.book_name} · {e.label}
              {e.completed > 0 ? ` · ${e.completed} test çözülmüş` : ""}
            </Text>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

function Bar({ pct, track, fill }: { pct: number; track: string; fill: string }) {
  return (
    <View className={cn("mt-2 h-2 w-full overflow-hidden rounded-full", track)}>
      <View className={cn("h-full rounded-full", fill)} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
    </View>
  );
}

function ProjectionCard({ p }: { p: CurriculumProjectionItem }) {
  const v = VERDICT[p.verdict];
  return (
    <View className={cn("rounded-xl border p-4", v.bg, v.border)}>
      <View className="flex-row items-center justify-between">
        <Text className={cn("text-sm font-semibold", v.text)}>Sınava yetişme projeksiyonu</Text>
        <View className={cn("rounded-full border px-2 py-0.5", v.border)}>
          <Text className={cn("text-xs font-semibold", v.text)}>{v.label}</Text>
        </View>
      </View>
      {p.has_exam ? (
        <>
          <View className="mt-3 flex-row">
            <Stat value={String(p.days_to_exam ?? "—")} label="gün kaldı" text={v.text} />
            <Stat value={String(p.remaining_topics)} label="kalan konu" text={v.text} />
            <Stat value={String(p.pace_per_week)} label="konu/hafta" text={v.text} />
          </View>
          <View className="mt-3">
            <View className="flex-row items-center justify-between">
              <Text className={cn("text-[11px]", v.text)}>Bu tempoyla ulaşılacak kapsama</Text>
              <Text className={cn("text-[11px] font-semibold", v.text)}>%{p.projected_coverage_pct}</Text>
            </View>
            <Bar pct={p.projected_coverage_pct} track="bg-black/10" fill={v.bar} />
          </View>
        </>
      ) : (
        <Text className={cn("mt-2 text-xs", v.text)}>
          {p.verdict === "sinav_yok"
            ? "Öğrencinin sınav tarihi girilince, mevcut çalışma temposuna göre müfredatın yetişip yetişmeyeceği burada hesaplanır."
            : "Projeksiyon için yeterli müfredat verisi yok."}
        </Text>
      )}
    </View>
  );
}

function Stat({ value, label, text }: { value: string; label: string; text: string }) {
  return (
    <View className="flex-1 items-center">
      <Text className={cn("text-lg font-bold", text)}>{value}</Text>
      <Text className={cn("text-[10px]", text)}>{label}</Text>
    </View>
  );
}

function SubjectBlock({ subject: s }: { subject: CurriculumSubjectItem }) {
  const [open, setOpen] = React.useState(false);
  return (
    <View className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <Pressable onPress={() => setOpen((v) => !v)} className="flex-row items-center gap-2 p-3 active:bg-slate-50">
        <View className="flex-1">
          <Text className="font-semibold text-slate-800">{s.name}</Text>
          <Text className="mt-0.5 text-xs text-slate-500">
            {s.started_topics}/{s.total_topics} konu · %{s.coverage_pct}
          </Text>
          {s.next_topic_name ? (
            <Text className="mt-0.5 text-[11px] text-indigo-700" numberOfLines={1}>
              → sıradaki: {s.next_topic_name}
            </Text>
          ) : s.last_topic_name ? (
            <Text className="mt-0.5 text-[11px] text-emerald-700" numberOfLines={1}>
              son işlenen: {s.last_topic_name}
            </Text>
          ) : null}
        </View>
        <View className="w-16 items-end">
          <Text className="text-sm font-semibold text-slate-700">%{s.coverage_pct}</Text>
          <Bar pct={s.coverage_pct} track="bg-slate-100" fill="bg-indigo-500" />
        </View>
        <Ionicons name={open ? "chevron-up" : "chevron-down"} size={18} color="#94a3b8" />
      </Pressable>

      {open ? (
        <View className="border-t border-slate-100">
          {s.topics.map((t, i) => {
            const meta = STATUS[t.status];
            const isNext = t.name === s.next_topic_name;
            const prev = i > 0 ? s.topics[i - 1] : null;
            const showGrade = t.grade_level != null && (!prev || prev.grade_level !== t.grade_level);
            const showUnit = !!t.unit_name && (!prev || prev.unit_name !== t.unit_name || showGrade);
            return (
              <View key={t.topic_id}>
                {showGrade ? (
                  <View className="bg-indigo-100 px-3 py-1.5">
                    <Text className="text-xs font-bold text-indigo-800">{t.grade_level}. Sınıf</Text>
                  </View>
                ) : null}
                {showUnit ? (
                  <View className="bg-slate-100 px-3 py-1.5">
                    <Text className="text-[11px] font-semibold uppercase tracking-wide text-slate-600">
                      {t.unit_name}
                    </Text>
                  </View>
                ) : null}
                <View
                  className={cn(
                    "flex-row items-center gap-2 py-2 pr-3",
                    t.unit_name ? "pl-6" : "pl-3",
                    isNext && "bg-indigo-50/60",
                  )}
                >
                  <View className={cn("size-2 rounded-full", meta.dot)} />
                  <View className="flex-1">
                    <Text className={cn("text-sm", t.status === "kaynak_yok" ? "text-slate-400" : "text-slate-700")}>
                      {t.name}
                      {isNext ? "  • sıradaki" : ""}
                    </Text>
                    {t.has_resource && t.test_total > 0 ? (
                      <Text className="text-[11px] text-slate-400">{t.completed}/{t.test_total} test</Text>
                    ) : null}
                  </View>
                  <Text className={cn("text-[10px] font-medium", meta.text)}>{meta.label}</Text>
                </View>
              </View>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}
