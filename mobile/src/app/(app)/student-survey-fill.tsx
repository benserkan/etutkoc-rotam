import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import * as React from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { SurveyResultView } from "@/components/student/survey-result-view";
import {
  getStudentSurveyFill,
  saveSurveyAnswers,
  surveyKeys,
  type SurveyQuestionModel,
} from "@/lib/surveys";
import { cn } from "@/lib/utils";

/**
 * Öğrenci — anket doldurma ekranı (büyük dokunma hedefleri).
 * likert5 → 5 buton · slider10 → 1-10 şerit · open → çok satırlı metin.
 * "Kaydet" kısmi ilerleme saklar; "Tamamla" doğrular (eksikte ilk eksiğe
 * kaydırır). Tamamlanınca sonuç görünümü.
 */

const LIKERT_LABELS = ["Hiç", "Az", "Orta", "Uygun", "Tam"];
const LIKERT_FULL = [
  "Hiç uygun değil",
  "Pek uygun değil",
  "Kararsızım",
  "Uygun",
  "Tamamen uygun",
];

export default function StudentSurveyFillRoute() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const assignmentId = Number(id ?? 0);
  const qc = useQueryClient();

  const q = useQuery({
    queryKey: surveyKeys.studentFill(assignmentId),
    queryFn: () => getStudentSurveyFill(assignmentId),
    enabled: assignmentId > 0,
  });

  const [answers, setAnswers] = React.useState<Record<string, number | string>>({});
  const [missing, setMissing] = React.useState<Set<number>>(new Set());
  const seededRef = React.useRef(false);
  const scrollRef = React.useRef<ScrollView | null>(null);
  const qPositions = React.useRef<Record<number, number>>({});

  // Sunucudaki kayıtlı cevaplar bir kez local state'e alınır (devam et akışı)
  if (q.data && !seededRef.current) {
    seededRef.current = true;
    if (Object.keys(q.data.answers).length > 0) {
      setAnswers({ ...q.data.answers });
    }
  }

  const saveMut = useMutation({
    mutationFn: (vars: { complete: boolean }) =>
      saveSurveyAnswers(assignmentId, answers, vars.complete),
    onSuccess: (res, vars) => {
      void qc.invalidateQueries({ queryKey: ["student", "surveys"] });
      const d = res.data;
      if (vars.complete && !d.completed && d.missing_question_ids.length > 0) {
        const ids = new Set(d.missing_question_ids);
        setMissing(ids);
        const first = q.data?.questions.find((qq) => ids.has(qq.id));
        const y = first ? qPositions.current[first.id] : undefined;
        if (y != null) scrollRef.current?.scrollTo({ y: Math.max(0, y - 80), animated: true });
        Alert.alert(
          "Eksik sorular var",
          `${d.missing_question_ids.length} soru cevapsız — kırmızı işaretli soruları doldurup tekrar dene.`,
        );
      } else if (vars.complete && d.completed) {
        void q.refetch();
      } else {
        Alert.alert("Kaydedildi", "Cevapların saklandı — istediğin zaman devam edebilirsin.");
      }
    },
    onError: () => Alert.alert("Hata", "Cevaplar kaydedilemedi. Tekrar dene."),
  });

  function setAnswer(qid: number, value: number | string) {
    setAnswers((prev) => ({ ...prev, [String(qid)]: value }));
    setMissing((prev) => {
      if (!prev.has(qid)) return prev;
      const next = new Set(prev);
      next.delete(qid);
      return next;
    });
  }

  const data = q.data;
  const completed = data?.assignment.status === "completed";
  const requiredQs = (data?.questions ?? []).filter((qq) => qq.qtype !== "open");
  const answeredRequired = requiredQs.filter((qq) => {
    const v = answers[String(qq.id)];
    return v !== undefined && v !== null && String(v).trim() !== "";
  }).length;

  return (
    <SafeAreaView edges={["top"]} className="flex-1 bg-slate-50">
      <View className="flex-row items-center gap-1 px-2 py-2">
        <Pressable
          onPress={() => router.back()}
          hitSlop={8}
          className="size-10 items-center justify-center rounded-full active:bg-slate-200"
          accessibilityLabel="Geri"
        >
          <Ionicons name="chevron-back" size={26} color="#334155" />
        </Pressable>
        <Text className="flex-1 text-base font-semibold text-slate-800" numberOfLines={1}>
          {data?.assignment.template.title ?? "Anket"}
        </Text>
      </View>

      {q.isLoading ? (
        <View className="flex-1 items-center justify-center">
          <ActivityIndicator size="large" color="#0e7490" />
        </View>
      ) : !data ? (
        <View className="flex-1 items-center justify-center gap-3 px-8">
          <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
          <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
            <Text className="font-semibold text-white">Tekrar dene</Text>
          </Pressable>
        </View>
      ) : completed && data.result ? (
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-3 gap-3">
          <View className="flex-row items-center gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 p-3">
            <Ionicons name="checkmark-circle" size={20} color="#059669" />
            <Text className="flex-1 text-[13px] text-emerald-900">
              Bu anketi tamamladın — işte sonucun. Koçun da görüyor; birlikte
              değerlendireceksiniz.
            </Text>
          </View>
          <SurveyResultView result={data.result} />
        </ScrollView>
      ) : (
        <>
          <ScrollView
            ref={scrollRef}
            className="flex-1"
            contentContainerClassName="px-4 py-2 gap-3 pb-6"
            keyboardShouldPersistTaps="handled"
          >
            <Text className="text-xs leading-5 text-slate-500">
              Doğru ya da yanlış cevap yok — seni en iyi anlatan seçeneği
              işaretle. İstediğin an kaydedip sonra devam edebilirsin.
            </Text>
            {data.assignment.note ? (
              <View className="rounded-xl border border-cyan-200 bg-cyan-50 px-3 py-2">
                <Text className="text-xs text-cyan-900">Koçundan not: {data.assignment.note}</Text>
              </View>
            ) : null}

            {data.questions.map((qq, idx) => (
              <View
                key={qq.id}
                onLayout={(e) => {
                  qPositions.current[qq.id] = e.nativeEvent.layout.y;
                }}
              >
                <QuestionCard
                  index={idx + 1}
                  total={data.questions.length}
                  question={qq}
                  value={answers[String(qq.id)]}
                  missing={missing.has(qq.id)}
                  onChange={(v) => setAnswer(qq.id, v)}
                />
              </View>
            ))}
            <Text className="text-[10px] leading-4 text-slate-400">{data.disclaimer}</Text>
          </ScrollView>

          {/* Alt eylem çubuğu */}
          <View className="border-t border-slate-200 bg-white px-4 pb-2 pt-2">
            <View className="mb-2 flex-row items-center gap-2">
              <View className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                <View
                  className="h-full rounded-full bg-brand-700"
                  style={{
                    width: `${requiredQs.length > 0 ? Math.round((answeredRequired / requiredQs.length) * 100) : 100}%`,
                  }}
                />
              </View>
              <Text className="text-[11px] text-slate-500">
                {answeredRequired}/{requiredQs.length}
              </Text>
            </View>
            <View className="flex-row gap-2">
              <Pressable
                onPress={() => saveMut.mutate({ complete: false })}
                disabled={saveMut.isPending}
                className="flex-row items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-3 active:bg-slate-100"
              >
                <Ionicons name="save-outline" size={16} color="#334155" />
                <Text className="text-[14px] font-semibold text-slate-700">Kaydet</Text>
              </Pressable>
              <Pressable
                onPress={() => saveMut.mutate({ complete: true })}
                disabled={saveMut.isPending}
                className={cn(
                  "flex-1 flex-row items-center justify-center gap-2 rounded-xl py-3",
                  saveMut.isPending ? "bg-brand-700/60" : "bg-brand-700 active:bg-brand-800",
                )}
              >
                {saveMut.isPending ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Ionicons name="checkmark-circle-outline" size={18} color="#fff" />
                )}
                <Text className="text-[15px] font-semibold text-white">Anketi Tamamla</Text>
              </Pressable>
            </View>
          </View>
        </>
      )}
    </SafeAreaView>
  );
}

function QuestionCard({
  index,
  total,
  question,
  value,
  missing,
  onChange,
}: {
  index: number;
  total: number;
  question: SurveyQuestionModel;
  value: number | string | undefined;
  missing: boolean;
  onChange: (v: number | string) => void;
}) {
  return (
    <View
      className={cn(
        "rounded-2xl border p-3.5",
        missing ? "border-rose-400 bg-rose-50" : "border-slate-200 bg-white",
      )}
    >
      <Text className="text-[14px] leading-6 text-slate-900">
        <Text className="text-slate-400">
          {index}/{total}{"  "}
        </Text>
        {question.text}
      </Text>

      {question.qtype === "likert5" ? (
        <View className="mt-3">
          <View className="flex-row gap-1.5">
            {LIKERT_LABELS.map((label, i) => {
              const v = i + 1;
              const active = value === v;
              return (
                <Pressable
                  key={v}
                  onPress={() => onChange(v)}
                  accessibilityLabel={LIKERT_FULL[i]}
                  className={cn(
                    "flex-1 items-center rounded-xl border px-1 py-2.5",
                    active ? "border-brand-700 bg-brand-700" : "border-slate-200 bg-slate-50 active:bg-slate-100",
                  )}
                >
                  <Text className={cn("text-base font-bold", active ? "text-white" : "text-slate-700")}>
                    {v}
                  </Text>
                  <Text className={cn("mt-0.5 text-[9px]", active ? "text-cyan-100" : "text-slate-500")}>
                    {label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          {typeof value === "number" ? (
            <Text className="mt-1.5 text-center text-[11px] text-brand-700">
              {LIKERT_FULL[value - 1]}
            </Text>
          ) : null}
        </View>
      ) : null}

      {question.qtype === "slider10" ? (
        <View className="mt-3 flex-row flex-wrap gap-1.5">
          {Array.from({ length: 10 }, (_, i) => i + 1).map((v) => {
            const active = value === v;
            return (
              <Pressable
                key={v}
                onPress={() => onChange(v)}
                className={cn(
                  "h-11 w-[8.5%] min-w-9 flex-1 items-center justify-center rounded-xl border",
                  active ? "border-brand-700 bg-brand-700" : "border-slate-200 bg-slate-50 active:bg-slate-100",
                )}
              >
                <Text className={cn("text-[14px] font-bold", active ? "text-white" : "text-slate-700")}>
                  {v}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}

      {question.qtype === "open" ? (
        <TextInput
          value={typeof value === "string" ? value : ""}
          onChangeText={(t) => onChange(t)}
          multiline
          numberOfLines={3}
          placeholder="Kendi cümlelerinle yaz… (boş bırakabilirsin)"
          placeholderTextColor="#94a3b8"
          className="mt-3 min-h-20 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[14px] text-slate-900"
          textAlignVertical="top"
        />
      ) : null}

      {question.qtype === "choice" && question.options.length > 0 ? (
        <View className="mt-3 flex-row flex-wrap gap-1.5">
          {question.options.map((o) => {
            const active = value === o.value;
            return (
              <Pressable
                key={o.value}
                onPress={() => onChange(o.value)}
                className={cn(
                  "rounded-xl border px-3 py-2",
                  active ? "border-brand-700 bg-brand-700" : "border-slate-200 bg-slate-50 active:bg-slate-100",
                )}
              >
                <Text className={cn("text-[13px]", active ? "text-white" : "text-slate-700")}>
                  {o.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}
