import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation } from "@tanstack/react-query";
import { Alert, Pressable, Text, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import { ApiError } from "@/lib/api";
import type { AnalysisEvidenceExam, AnalysisTrendTopic } from "@/lib/exam-import";
import { addAgendaItems } from "@/lib/exam-progress";
import { cn } from "@/lib/utils";

/**
 * Unutulan / gelişen konular (2026-10-03) — web ExamTrendTopics paritesi.
 * Kart: ilk ↔ son denemeler SAYIYLA + deneme deneme nokta şeridi; dokun →
 * alttan sayfada kanıt (hangi denemede hangi soru, öğrenci cevabı, doğru
 * cevap). Koç (studentId) "Seansa ekle" görür.
 */

type Kind = "forgotten" | "improved";

const pct = (v: number) => `%${Math.round(v * 100)}`;

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return d && m ? `${d}.${m}.${y}` : iso;
}

const LEVEL = {
  zayif: { label: "az veri", cls: "bg-amber-500" },
  orta: { label: "orta güven", cls: "bg-slate-500" },
  guclu: { label: "güçlü kanıt", cls: "bg-cyan-700" },
} as const;

function dotCls(e: AnalysisEvidenceExam): string {
  if (!e.asked) return "border border-dashed border-slate-400";
  const acc = e.total ? e.correct / e.total : 0;
  if (acc >= 0.999) return "bg-emerald-500";
  if (acc > 0) return "bg-amber-400";
  return "bg-rose-500";
}

function Dots({ evidence }: { evidence: AnalysisEvidenceExam[] }) {
  const first = evidence.filter((e) => e.half === "first");
  const last = evidence.filter((e) => e.half === "last");
  return (
    <View className="flex-row flex-wrap items-center gap-1">
      {first.map((e) => (
        <View key={e.exam_id} className={cn("h-3 w-3 rounded-full", dotCls(e))} />
      ))}
      <View className="mx-1 h-4 w-px bg-slate-300" />
      {last.map((e) => (
        <View key={e.exam_id} className={cn("h-3 w-3 rounded-full", dotCls(e))} />
      ))}
    </View>
  );
}

function Side({ label, c, n, acc, tone }: { label: string; c: number; n: number; acc: number; tone: string }) {
  return (
    <View className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5">
      <Text className="text-[11px] text-slate-500">{label}</Text>
      <View className="flex-row items-baseline gap-1.5">
        <Text className={cn("text-lg font-bold", tone)}>{pct(acc)}</Text>
        <Text className="text-xs text-slate-500">
          {c}/{n} doğru
        </Text>
      </View>
    </View>
  );
}

function Card({
  t,
  kind,
  onOpen,
  studentId,
}: {
  t: AnalysisTrendTopic;
  kind: Kind;
  onOpen: () => void;
  studentId: number | null;
}) {
  const [queued, setQueued] = React.useState(false);
  const mut = useMutation({
    mutationFn: () =>
      addAgendaItems(studentId ?? 0, [
        {
          text:
            `${t.topic_name} tekrar edilmeli — ${t.subject_name} · ilk denemelerde ` +
            `${t.first_correct ?? 0}/${t.first_total ?? 0}, son denemelerde ` +
            `${t.last_correct ?? 0}/${t.last_total ?? 0} doğru (unutulma işareti).`,
          key: `forgot:${t.topic_id}`,
          source: "exam",
        },
      ]),
    onSuccess: (res) => {
      setQueued(true);
      Alert.alert("Seans gündemi", res.added > 0 ? "Sıradaki seansın gündemine eklendi." : "Bu konu zaten gündemde.");
    },
    onError: (e) => Alert.alert("Eklenemedi", e instanceof ApiError ? e.message : "Bir hata oluştu."),
  });
  const hasEvidence = (t.evidence?.length ?? 0) > 0;
  const lv = LEVEL[t.evidence_level ?? "zayif"];
  const isF = kind === "forgotten";
  return (
    <Pressable
      onPress={hasEvidence ? onOpen : undefined}
      className={cn(
        "rounded-xl border border-l-4 border-slate-200 bg-white p-3 active:bg-slate-50",
        isF ? "border-l-rose-500" : "border-l-emerald-500",
      )}
    >
      <View className="flex-row items-start justify-between gap-2">
        <View className="flex-1">
          <Text className="text-sm font-semibold text-slate-900">{t.topic_name}</Text>
          <Text className="text-xs text-slate-500">{t.subject_name}</Text>
        </View>
        {t.first_total != null ? (
          <View className={cn("rounded-full px-2 py-0.5", lv.cls)}>
            <Text className="text-[10px] font-semibold text-white">
              {lv.label} · {(t.first_total ?? 0) + (t.last_total ?? 0)} soru
            </Text>
          </View>
        ) : null}
      </View>
      <View className="mt-2 flex-row items-center gap-1.5">
        <Side
          label={`İlk ${t.first_exam_count ?? ""} deneme`}
          c={t.first_correct ?? 0}
          n={t.first_total ?? 0}
          acc={t.first_accuracy}
          tone={isF ? "text-emerald-700" : "text-slate-900"}
        />
        <Ionicons name="arrow-forward" size={16} color="#94a3b8" />
        <Side
          label={`Son ${t.last_exam_count ?? ""} deneme`}
          c={t.last_correct ?? 0}
          n={t.last_total ?? 0}
          acc={t.last_accuracy}
          tone={isF ? "text-rose-700" : "text-emerald-700"}
        />
      </View>
      {hasEvidence ? (
        <View className="mt-2 flex-row items-center justify-between gap-2">
          <Dots evidence={t.evidence ?? []} />
          <Text className="text-xs font-semibold text-cyan-700">Kanıtı gör ›</Text>
        </View>
      ) : null}
      {studentId != null && isF ? (
        <Pressable
          onPress={() => mut.mutate()}
          disabled={queued || mut.isPending}
          className={cn(
            "mt-2 flex-row items-center justify-center gap-1.5 rounded-lg border px-3 py-2",
            queued ? "border-emerald-300 bg-emerald-50" : "border-slate-300 bg-white active:bg-slate-100",
          )}
        >
          <Ionicons name={queued ? "checkmark" : "calendar-outline"} size={15} color={queued ? "#047857" : "#334155"} />
          <Text className={cn("text-xs font-semibold", queued ? "text-emerald-800" : "text-slate-700")}>
            {queued ? "Seans gündeminde" : "Seansa ekle"}
          </Text>
        </Pressable>
      ) : null}
    </Pressable>
  );
}

const RESULT = {
  dogru: { label: "Doğru", cls: "bg-emerald-600" },
  yanlis: { label: "Yanlış", cls: "bg-rose-600" },
  bos: { label: "Boş", cls: "bg-slate-500" },
} as const;

function ExamBlock({ e }: { e: AnalysisEvidenceExam }) {
  return (
    <View className="mb-2 rounded-lg border border-slate-200 bg-white px-3 py-2">
      <Text className="text-sm font-medium text-slate-900">{e.title}</Text>
      <Text className="text-xs text-slate-500">
        {fmtDate(e.exam_date)}
        {e.asked ? ` · ${e.correct}/${e.total} doğru` : ""}
      </Text>
      {e.asked ? (
        e.questions.map((q) => {
          const r = RESULT[q.result as keyof typeof RESULT] ?? RESULT.bos;
          return (
            <View key={q.question_id} className="mt-1.5 border-t border-slate-100 pt-1.5">
              <View className="flex-row flex-wrap items-center gap-2">
                <Text className="text-sm font-medium text-slate-800">
                  {q.question_no != null ? `Soru ${q.question_no}` : "Soru"}
                </Text>
                <View className={cn("rounded px-1.5 py-0.5", r.cls)}>
                  <Text className="text-[11px] font-semibold text-white">{r.label}</Text>
                </View>
                {q.student_answer || q.correct_answer ? (
                  <Text className="text-xs text-slate-600">
                    Öğrenci {q.student_answer || "—"} · Doğru {q.correct_answer || "—"}
                  </Text>
                ) : null}
              </View>
              {q.label_raw ? <Text className="mt-0.5 text-[11px] text-slate-500">karnede: {q.label_raw}</Text> : null}
            </View>
          );
        })
      ) : (
        <Text className="mt-1 text-xs text-slate-500">Bu denemede bu konudan soru gelmedi.</Text>
      )}
    </View>
  );
}

export function TrendTopics({
  forgotten,
  improved,
  studentId,
}: {
  forgotten: AnalysisTrendTopic[];
  improved: AnalysisTrendTopic[];
  studentId: number | null;
}) {
  const [sel, setSel] = React.useState<{ t: AnalysisTrendTopic; kind: Kind } | null>(null);
  if (!forgotten.length && !improved.length) return null;

  const group = (kind: Kind, items: AnalysisTrendTopic[]) => {
    if (!items.length) return null;
    const isF = kind === "forgotten";
    return (
      <View className="mt-3 gap-2">
        <View className="flex-row items-center gap-2">
          <View className={cn("h-6 w-6 items-center justify-center rounded-md", isF ? "bg-rose-600" : "bg-emerald-600")}>
            <Ionicons name={isF ? "trending-down" : "trending-up"} size={14} color="#fff" />
          </View>
          <View className="flex-1">
            <Text className="text-sm font-semibold text-slate-900">
              {isF ? "Unutulan konular" : "Gelişen konular"} ({items.length})
            </Text>
            <Text className="text-[11px] text-slate-500">
              {isF ? "İlk denemelerde biliyordu, son denemelerde düştü." : "İlk denemelere göre belirgin arttı."}
            </Text>
          </View>
        </View>
        {items.map((t) => (
          <Card key={t.topic_id} t={t} kind={kind} studentId={studentId} onOpen={() => setSel({ t, kind })} />
        ))}
      </View>
    );
  };

  const t = sel?.t;
  return (
    <View>
      {group("forgotten", forgotten)}
      {group("improved", improved)}
      <FormSheet visible={sel != null} title={t?.topic_name ?? ""} onClose={() => setSel(null)}>
        {t ? (
          <View className="pb-4">
            <Text className="text-xs text-slate-500">{t.subject_name}</Text>
            <Text className="mt-1 text-sm text-slate-800">
              İlk {t.first_exam_count} denemede {t.first_total} sorunun {t.first_correct}&apos;i doğru ({pct(t.first_accuracy)}) →
              son {t.last_exam_count} denemede {t.last_total} sorunun {t.last_correct}&apos;i doğru ({pct(t.last_accuracy)}).
            </Text>
            <Text className="mt-2 rounded-lg bg-slate-100 px-3 py-2 text-[11px] leading-4 text-slate-600">
              Denemeler tarih sırasıyla ikiye bölünür; ilk yarıdaki doğruluk son yarıyla kıyaslanır. Fark en az 34 puan
              ve her yarıda en az 2 soru varsa konu işaretlenir. Boş bırakılan soru doğru sayılmaz.
            </Text>
            {t.evidence_level === "zayif" ? (
              <Text className="mt-2 rounded-lg bg-amber-500 px-3 py-2 text-xs font-medium text-white">
                Kıyas yalnız {(t.first_total ?? 0) + (t.last_total ?? 0)} soruya dayanıyor — tek soru sonucu değiştirebilir.
              </Text>
            ) : null}
            <Text className="mb-1.5 mt-3 text-xs font-semibold uppercase text-slate-500">İlk denemeler</Text>
            {(t.evidence ?? []).filter((e) => e.half === "first").map((e) => <ExamBlock key={e.exam_id} e={e} />)}
            <Text className="mb-1.5 mt-2 text-xs font-semibold uppercase text-slate-500">Son denemeler</Text>
            {(t.evidence ?? []).filter((e) => e.half === "last").map((e) => <ExamBlock key={e.exam_id} e={e} />)}
          </View>
        ) : null}
      </FormSheet>
    </View>
  );
}
