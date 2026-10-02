import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Alert, Pressable, Switch, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import { ApiError } from "@/lib/api";
import {
  examProgressKeys,
  fmtNet,
  fmtSigned,
  fmtTRDate,
  getDistractors,
  parseNum,
  setExamAverages,
  shareExamWithStudent,
  unshareExam,
  type ExamShareInfo,
} from "@/lib/exam-progress";
import type { ExamRow } from "@/lib/student";
import { cn } from "@/lib/utils";

/**
 * Deneme detayı (mobil, Faz 2 + 3): ders tablosu + genel ortalama farkı,
 * koçun öğrenciye notu, çeldirici analizi; koçta "Öğrenciyle paylaş" ve
 * "Genel ortalama gir". studentId null → öğrencinin kendi görünümü.
 */
export function ExamDetailSheet({
  exam,
  studentId,
  share,
  onClose,
  onChanged,
}: {
  exam: ExamRow | null;
  studentId: number | null;
  share: ExamShareInfo | null;
  onClose: () => void;
  /** koç işleminden sonra liste/paylaşımlar tazelensin */
  onChanged?: () => void;
}) {
  const [mode, setMode] = React.useState<"view" | "share" | "averages">("view");
  const close = () => {
    setMode("view");
    onClose();
  };
  return (
    <FormSheet
      visible={!!exam}
      title={mode === "share" ? "Öğrenciyle paylaş" : mode === "averages" ? "Genel ortalama" : "Deneme detayı"}
      onClose={close}
    >
      {exam ? (
        mode === "share" && studentId != null ? (
          <ShareForm exam={exam} share={share} onDone={() => { setMode("view"); onChanged?.(); }} />
        ) : mode === "averages" && studentId != null ? (
          <AveragesForm exam={exam} onDone={() => { setMode("view"); onChanged?.(); }} />
        ) : (
          <DetailBody exam={exam} studentId={studentId} share={share} onMode={setMode} />
        )
      ) : null}
    </FormSheet>
  );
}

function DetailBody({
  exam,
  studentId,
  share,
  onMode,
}: {
  exam: ExamRow;
  studentId: number | null;
  share: ExamShareInfo | null;
  onMode: (m: "share" | "averages") => void;
}) {
  const isTeacher = studentId != null;
  const av = exam.averages ?? null;
  return (
    <View className="gap-4 pb-4">
      <View>
        <Text className="text-base font-bold text-slate-900">{exam.title}</Text>
        <Text className="text-xs text-slate-500">
          {exam.section_label} · {fmtTRDate(exam.exam_date)} · {exam.total_questions} soru
        </Text>
        <View className="mt-2 flex-row items-end gap-4">
          <View>
            <Text className="text-3xl font-extrabold text-slate-900">{fmtNet(exam.net)}</Text>
            <Text className="text-[11px] text-slate-500">net</Text>
          </View>
          <Text className="pb-1 text-xs text-slate-600">
            <Text className="font-semibold text-emerald-600">D {exam.total_correct}</Text>{"  "}
            <Text className="font-semibold text-rose-600">Y {exam.total_wrong}</Text>{"  "}
            <Text className="text-slate-400">B {exam.total_blank}</Text>
          </Text>
          {av?.total != null ? (
            <Text className="pb-1 text-xs text-slate-600">
              {av.label}: {fmtNet(av.total)} ({fmtSigned(exam.net - av.total)})
            </Text>
          ) : null}
        </View>
      </View>

      {share?.note ? (
        <View className="rounded-xl border border-cyan-200 bg-cyan-50 p-3">
          <Text className="text-xs font-semibold text-cyan-900">
            {isTeacher ? "Öğrenciye yazdığın not" : "Koçunun değerlendirmesi"}
          </Text>
          <Text className="mt-1 text-sm text-cyan-950">{share.note}</Text>
        </View>
      ) : null}

      {isTeacher ? (
        <View className="flex-row gap-2">
          <Pressable
            onPress={() => onMode("share")}
            className="flex-1 flex-row items-center justify-center gap-1.5 rounded-xl border border-cyan-300 bg-cyan-50 py-2.5 active:bg-cyan-100"
          >
            <Ionicons name={share ? "person-circle" : "send-outline"} size={16} color="#0e7490" />
            <Text className="text-sm font-semibold text-cyan-800">{share ? "Paylaşım notu" : "Öğrenciyle paylaş"}</Text>
          </Pressable>
          <Pressable
            onPress={() => onMode("averages")}
            className="flex-1 flex-row items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white py-2.5 active:bg-slate-50"
          >
            <Ionicons name="people-outline" size={16} color="#475569" />
            <Text className="text-sm font-semibold text-slate-700">{av ? "Ortalamayı düzenle" : "Genel ortalama"}</Text>
          </Pressable>
        </View>
      ) : null}

      {exam.subjects.length ? (
        <View className="rounded-xl border border-slate-200">
          <View className="flex-row border-b border-slate-200 bg-slate-50 px-3 py-2">
            <Text className="flex-1 text-[11px] font-semibold text-slate-500">Ders</Text>
            <Text className="w-16 text-right text-[11px] font-semibold text-slate-500">D/Y/B</Text>
            <Text className="w-12 text-right text-[11px] font-semibold text-slate-500">Net</Text>
            {av ? <Text className="w-20 text-right text-[11px] font-semibold text-slate-500">Ort. / fark</Text> : null}
          </View>
          {exam.subjects.map((s) => {
            const a = av?.subjects[s.name];
            return (
              <View key={s.name} className="flex-row items-center border-b border-slate-100 px-3 py-2 last:border-0">
                <Text className="flex-1 pr-1 text-sm text-slate-800">{s.name}</Text>
                <Text className="w-16 text-right text-xs text-slate-500">
                  {s.correct}/{s.wrong}/{s.blank}
                </Text>
                <Text className="w-12 text-right text-sm font-semibold text-slate-900">{fmtNet(s.net)}</Text>
                {av ? (
                  <Text className={cn("w-20 text-right text-xs", a == null ? "text-slate-400" : s.net - a >= 0 ? "text-emerald-700" : "text-rose-700")}>
                    {a == null ? "—" : `${fmtNet(a)} (${fmtSigned(s.net - a)})`}
                  </Text>
                ) : null}
              </View>
            );
          })}
        </View>
      ) : null}

      {exam.import_source === "pdf_import" ? <Distractors examId={exam.id} studentId={studentId} /> : null}
    </View>
  );
}

function Distractors({ examId, studentId }: { examId: number; studentId: number | null }) {
  const q = useQuery({
    queryKey: examProgressKeys.distractors(studentId, examId),
    queryFn: () => getDistractors(studentId, examId),
  });
  if (q.isLoading) return <ActivityIndicator color="#0e7490" />;
  const d = q.data;
  if (!d || !d.answered) return null;
  const maxPct = Math.max(1, ...d.letters.map((l) => Math.max(l.chosen_pct, l.key_pct)));
  return (
    <View className="gap-3 rounded-xl border border-slate-200 p-3">
      <View className="flex-row items-center gap-1.5">
        <Ionicons name="locate-outline" size={16} color="#0e7490" />
        <Text className="text-sm font-semibold text-slate-800">Çeldirici analizi</Text>
      </View>
      <Text className="text-[11px] text-slate-500">
        {d.answered} cevap, {d.wrong_count} yanlış · koyu çubuk işaretlediği, açık çubuk anahtardaki pay
      </Text>
      <View className="gap-1.5">
        {d.letters.map((l) => (
          <View key={l.letter} className="flex-row items-center gap-2">
            <Text className="w-4 text-xs font-bold text-slate-700">{l.letter}</Text>
            <View className="flex-1 gap-0.5">
              <View className="h-2 rounded bg-brand-600" style={{ width: `${(l.chosen_pct / maxPct) * 100}%` }} />
              <View className="h-1.5 rounded bg-slate-300" style={{ width: `${(l.key_pct / maxPct) * 100}%` }} />
            </View>
            <Text className="w-24 text-right text-[11px] text-slate-500">
              %{String(l.chosen_pct).replace(".", ",")} · yanlış {l.wrong_chosen}
            </Text>
          </View>
        ))}
      </View>
      {d.notes.map((n) => (
        <View key={n} className="flex-row gap-2 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-2">
          <Ionicons name="warning-outline" size={15} color="#b45309" style={{ marginTop: 1 }} />
          <Text className="flex-1 text-xs text-amber-900">{n}</Text>
        </View>
      ))}
      {d.peer_count ? (
        <View className="gap-1.5">
          <Text className="text-xs font-semibold text-slate-600">
            Aynı denemeye giren {d.peer_count} öğrenci — yanlış/boş sorular
          </Text>
          {d.questions.slice(0, 10).map((r) => (
            <View key={`${r.subject}-${r.question_no}`} className="flex-row items-center justify-between gap-2">
              <Text className="flex-1 text-xs text-slate-700">
                {r.subject} {r.question_no} · doğru {r.correct_answer ?? "—"}, işaretlenen {r.student_answer ?? "boş"}
              </Text>
              <Text className="text-[11px] text-slate-500">%{r.peer_correct_pct} doğru</Text>
              {r.top_wrong_option ? (
                <Text
                  className={cn(
                    "overflow-hidden rounded px-1.5 py-0.5 text-[10px] font-bold",
                    r.same_as_student ? "bg-rose-600 text-white" : "bg-slate-100 text-slate-700",
                  )}
                >
                  {r.top_wrong_option} · {r.top_wrong_count}
                </Text>
              ) : null}
            </View>
          ))}
        </View>
      ) : (
        <Text className="text-[11px] text-slate-400">
          Soru bazında karşılaştırma için aynı denemeye giren en az {d.peer_min} öğrenci daha gerekir.
        </Text>
      )}
    </View>
  );
}

function ShareForm({ exam, share, onDone }: { exam: ExamRow; share: ExamShareInfo | null; onDone: () => void }) {
  const qc = useQueryClient();
  const [note, setNote] = React.useState(share?.note ?? "");
  const [notify, setNotify] = React.useState(!share);
  const mut = useMutation({
    mutationFn: () => shareExamWithStudent(exam.id, note, notify),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-progress"] });
      onDone();
    },
    onError: (e) => Alert.alert("Paylaşılamadı", e instanceof ApiError ? e.message : "Bir hata oluştu."),
  });
  const un = useMutation({
    mutationFn: () => unshareExam(exam.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-progress"] });
      onDone();
    },
  });
  return (
    <View className="gap-3 pb-2">
      <Text className="text-xs text-slate-500">
        {exam.title} · {fmtNet(exam.net)} net. Öğrenci denemeyi zaten görür; bu not ona özel değerlendirmendir.
        Koça özel notun paylaşılmaz.
      </Text>
      <TextInput
        value={note}
        onChangeText={setNote}
        maxLength={1000}
        multiline
        placeholder="Örn. Matematikte boşları azaltalım, bu hafta problemlere ağırlık veriyoruz."
        placeholderTextColor="#94a3b8"
        className="min-h-[110px] rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
      />
      <View className="flex-row items-center justify-between">
        <Text className="text-sm text-slate-700">Öğrencinin uygulamasına bildirim gönder</Text>
        <Switch value={notify} onValueChange={setNotify} />
      </View>
      <Pressable
        onPress={() => mut.mutate()}
        disabled={mut.isPending}
        className="items-center rounded-xl bg-brand-700 py-3.5 active:bg-brand-800"
      >
        <Text className="text-base font-semibold text-white">{share ? "Notu güncelle" : "Paylaş"}</Text>
      </Pressable>
      {share ? (
        <Pressable onPress={() => un.mutate()} className="items-center py-2">
          <Text className="font-semibold text-rose-600">Paylaşımı geri al</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

function AveragesForm({ exam, onDone }: { exam: ExamRow; onDone: () => void }) {
  const av = exam.averages ?? null;
  const qc = useQueryClient();
  const toStr = (v: number | null | undefined) => (v == null ? "" : String(v).replace(".", ","));
  const [total, setTotal] = React.useState(toStr(av?.total));
  const [subj, setSubj] = React.useState<Record<string, string>>(() =>
    Object.fromEntries(exam.subjects.map((s) => [s.name, toStr(av?.subjects[s.name])])),
  );
  const mut = useMutation({
    mutationFn: (body: Parameters<typeof setExamAverages>[1]) => setExamAverages(exam.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-progress"] });
      onDone();
    },
    onError: (e) => Alert.alert("Kaydedilemedi", e instanceof ApiError ? e.message : "Bir hata oluştu."),
  });
  return (
    <View className="gap-3 pb-2">
      <Text className="text-xs text-slate-500">
        Karnede katılımcıların ortalama neti yazıyorsa gir; ders tablosunda öğrencinin netiyle kıyaslanır.
      </Text>
      <View className="flex-row items-center justify-between gap-2">
        <Text className="flex-1 text-sm font-medium text-slate-700">Toplam ortalama net</Text>
        <TextInput
          value={total}
          onChangeText={setTotal}
          keyboardType="decimal-pad"
          className="w-24 rounded-lg border border-slate-300 bg-white px-2 py-2 text-center text-sm text-slate-900"
        />
      </View>
      {exam.subjects.map((s) => (
        <View key={s.name} className="flex-row items-center justify-between gap-2">
          <Text className="flex-1 text-sm text-slate-700">
            {s.name} <Text className="text-[11px] text-slate-400">(öğrenci {fmtNet(s.net)})</Text>
          </Text>
          <TextInput
            value={subj[s.name] ?? ""}
            onChangeText={(v) => setSubj((o) => ({ ...o, [s.name]: v }))}
            keyboardType="decimal-pad"
            className="w-24 rounded-lg border border-slate-300 bg-white px-2 py-2 text-center text-sm text-slate-900"
          />
        </View>
      ))}
      <Pressable
        onPress={() => {
          const subjects: Record<string, number | null> = {};
          for (const [k, v] of Object.entries(subj)) subjects[k] = parseNum(v);
          mut.mutate({ label: av?.label ?? "Genel ortalama", total: parseNum(total), subjects });
        }}
        disabled={mut.isPending}
        className="items-center rounded-xl bg-brand-700 py-3.5 active:bg-brand-800"
      >
        <Text className="text-base font-semibold text-white">Kaydet</Text>
      </Pressable>
      {av?.source === "manual" ? (
        <Pressable onPress={() => mut.mutate({})} className="items-center py-2">
          <Text className="font-semibold text-rose-600">Elle girişi kaldır</Text>
        </Pressable>
      ) : null}
    </View>
  );
}
