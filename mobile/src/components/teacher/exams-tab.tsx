import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import {
  createTeacherExam,
  deleteTeacherExam,
  getTeacherStudentExams,
  teacherDetailKeys,
  type ExamSectionOption,
  type TeacherExamCreateBody,
  type TeacherExamsResponse,
} from "@/lib/teacher";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const TR_MONTHS_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"];
function shortDate(iso: string): string {
  const [, m, d] = iso.split("-").map(Number);
  if (!m || !d) return iso;
  return `${d} ${TR_MONTHS_SHORT[m - 1]}`;
}
function todayISO(): string {
  const d = new Date();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

const SECTION_TONE: Record<string, { bg: string; text: string }> = {
  lgs: { bg: "bg-cyan-50", text: "text-cyan-700" },
  tyt: { bg: "bg-violet-50", text: "text-violet-700" },
  ayt_say: { bg: "bg-emerald-50", text: "text-emerald-700" },
  ayt_ea: { bg: "bg-amber-50", text: "text-amber-700" },
  ayt_soz: { bg: "bg-rose-50", text: "text-rose-700" },
  ayt_dil: { bg: "bg-sky-50", text: "text-sky-700" },
};
function tone(section: string) {
  return SECTION_TONE[section] ?? { bg: "bg-slate-100", text: "text-slate-600" };
}

function NumField({ label, value, onChangeText }: { label: string; value: string; onChangeText: (v: string) => void }) {
  return (
    <View className="flex-1 gap-1">
      <Text className="text-xs font-medium text-slate-600">{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/[^0-9]/g, "").slice(0, 3))}
        keyboardType="number-pad"
        placeholder="0"
        placeholderTextColor="#cbd5e1"
        className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-center text-lg font-semibold text-slate-900"
      />
    </View>
  );
}

// --- Ekleme formu ---
function ExamForm({
  sections,
  busy,
  error,
  onSubmit,
}: {
  sections: ExamSectionOption[];
  busy: boolean;
  error: string | null;
  onSubmit: (body: TeacherExamCreateBody) => void;
}) {
  const [title, setTitle] = React.useState("");
  const [date, setDate] = React.useState(todayISO());
  const [section, setSection] = React.useState(sections[0]?.value ?? "lgs");
  const [correct, setCorrect] = React.useState("");
  const [wrong, setWrong] = React.useState("");
  const [blank, setBlank] = React.useState("");

  const c = Number(correct) || 0;
  const w = Number(wrong) || 0;
  const b = Number(blank) || 0;
  const isLgs = section === "lgs";
  const net = Math.max(0, c - w / (isLgs ? 3 : 4));
  const canSave = title.trim().length > 0 && c + w + b > 0 && !busy;

  return (
    <View className="gap-4 pb-2">
      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Deneme adı</Text>
        <TextInput
          value={title}
          onChangeText={setTitle}
          placeholder="örn. TYT Genel Deneme 4"
          placeholderTextColor="#94a3b8"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>

      <View className="gap-1">
        <Text className="text-xs font-medium text-slate-600">Tarih</Text>
        <TextInput
          value={date}
          onChangeText={(v) => setDate(v.replace(/[^0-9-]/g, "").slice(0, 10))}
          placeholder="YYYY-AA-GG"
          placeholderTextColor="#94a3b8"
          keyboardType="numbers-and-punctuation"
          className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
        />
      </View>

      <View className="gap-1.5">
        <Text className="text-xs font-medium text-slate-600">Sınav türü</Text>
        <View className="flex-row flex-wrap gap-2">
          {sections.map((s) => {
            const active = s.value === section;
            const t = tone(s.value);
            return (
              <Pressable
                key={s.value}
                onPress={() => setSection(s.value)}
                className={cn(
                  "rounded-full border px-3 py-1.5",
                  active ? cn(t.bg, "border-transparent") : "border-slate-300 bg-white",
                )}
              >
                <Text className={cn("text-sm font-medium", active ? t.text : "text-slate-600")}>{s.label}</Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      <View className="flex-row gap-3">
        <NumField label="Doğru" value={correct} onChangeText={setCorrect} />
        <NumField label="Yanlış" value={wrong} onChangeText={setWrong} />
        <NumField label="Boş" value={blank} onChangeText={setBlank} />
      </View>

      <View className="flex-row items-center justify-between rounded-xl bg-brand-50 px-4 py-3">
        <Text className="text-sm font-medium text-brand-700">Hesaplanan net</Text>
        <Text className="text-2xl font-extrabold text-brand-800">{net.toFixed(2).replace(/\.00$/, "")}</Text>
      </View>

      {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}

      <Pressable
        onPress={() =>
          onSubmit({
            title: title.trim(),
            exam_date: date,
            section,
            total_correct: c,
            total_wrong: w,
            total_blank: b,
          })
        }
        disabled={!canSave}
        className={cn("items-center rounded-xl py-3.5", canSave ? "bg-brand-700 active:bg-brand-800" : "bg-brand-700/40")}
      >
        <Text className="text-base font-semibold text-white">{busy ? "Kaydediliyor…" : "Deneme sonucu kaydet"}</Text>
      </Pressable>
    </View>
  );
}

// --- Presentational görünüm ---
export function ExamsTabView({
  data,
  addBusy,
  addError,
  onAdd,
  onDelete,
}: {
  data: TeacherExamsResponse;
  addBusy: boolean;
  addError: string | null;
  onAdd: (body: TeacherExamCreateBody) => void;
  onDelete?: (examId: number) => void;
}) {
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const s = data.summary;

  function handleAdd(body: TeacherExamCreateBody) {
    onAdd(body);
  }

  return (
    <View className="gap-4 px-4 py-4">
      {/* Özet + ekle */}
      <View className="rounded-2xl bg-brand-700 p-5">
        <Text className="text-xs font-semibold uppercase tracking-wider text-brand-100">
          Denemeler · {s.count} sonuç
        </Text>
        <View className="mt-3 flex-row">
          <View className="flex-1 items-center">
            <Text className="text-2xl font-extrabold text-white">{s.avg_net}</Text>
            <Text className="text-[11px] text-brand-100">Ortalama</Text>
          </View>
          <View className="flex-1 items-center">
            <Text className="text-2xl font-extrabold text-white">{s.best_net}</Text>
            <Text className="text-[11px] text-brand-100">En iyi</Text>
          </View>
          <View className="flex-1 items-center">
            <Text className="text-2xl font-extrabold text-white">{s.last_net != null ? s.last_net : "—"}</Text>
            <Text className="text-[11px] text-brand-100">Son net</Text>
          </View>
        </View>
      </View>

      <Pressable
        onPress={() => setSheetOpen(true)}
        className="flex-row items-center justify-center gap-2 rounded-2xl border border-brand-200 bg-brand-50 py-3.5 active:bg-brand-100"
      >
        <Ionicons name="add-circle-outline" size={20} color="#0e7490" />
        <Text className="text-base font-semibold text-brand-700">Deneme sonucu gir</Text>
      </Pressable>

      {data.rows.length === 0 ? (
        <View className="mt-6 items-center gap-2 px-6">
          <Ionicons name="bar-chart-outline" size={40} color="#94a3b8" />
          <Text className="text-center text-sm text-slate-500">
            Henüz deneme yok. İlk sonucu girince netler ve gelişim burada görünür.
          </Text>
        </View>
      ) : (
        <View className="gap-2.5">
          {data.rows.map((e) => {
            const t = tone(e.section);
            return (
              <Pressable
                key={e.id}
                onLongPress={
                  onDelete
                    ? () =>
                        Alert.alert("Denemeyi sil", `"${e.title}" silinsin mi?`, [
                          { text: "Vazgeç", style: "cancel" },
                          { text: "Sil", style: "destructive", onPress: () => onDelete(e.id) },
                        ])
                    : undefined
                }
                className="rounded-2xl border border-slate-200 bg-white p-4 active:bg-slate-50"
              >
                <View className="flex-row items-start justify-between gap-2">
                  <Text className="flex-1 text-[15px] font-semibold text-slate-900" numberOfLines={2}>
                    {e.title}
                  </Text>
                  <View className={cn("rounded-full px-2 py-0.5", t.bg)}>
                    <Text className={cn("text-[11px] font-semibold", t.text)}>{e.section_label}</Text>
                  </View>
                </View>
                <Text className="mt-0.5 text-xs text-slate-400">{shortDate(e.exam_date)}</Text>
                <View className="mt-3 flex-row items-end justify-between">
                  <View>
                    <Text className="text-3xl font-extrabold text-slate-900">{e.net}</Text>
                    <Text className="text-[11px] text-slate-400">net</Text>
                  </View>
                  <Text className="text-xs text-slate-500">
                    <Text className="font-semibold text-emerald-600">D {e.total_correct}</Text>
                    {"  "}
                    <Text className="font-semibold text-rose-600">Y {e.total_wrong}</Text>
                    {"  "}
                    <Text className="text-slate-400">B {e.total_blank}</Text>
                  </Text>
                </View>
              </Pressable>
            );
          })}
          {onDelete ? (
            <Text className="px-1 text-[11px] text-slate-400">Bir denemeyi silmek için basılı tut.</Text>
          ) : null}
        </View>
      )}

      <FormSheet visible={sheetOpen} title="Deneme sonucu gir" onClose={() => setSheetOpen(false)}>
        <ExamForm
          sections={data.section_options}
          busy={addBusy}
          error={addError}
          onSubmit={(body) => {
            handleAdd(body);
            setSheetOpen(false);
          }}
        />
      </FormSheet>
    </View>
  );
}

// --- Container ---
export function ExamsTab({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const [addError, setAddError] = React.useState<string | null>(null);

  const q = useQuery({
    queryKey: teacherDetailKeys.exams(studentId),
    queryFn: () => getTeacherStudentExams(studentId),
    enabled: studentId > 0,
  });

  const addMut = useMutation({
    mutationFn: (body: TeacherExamCreateBody) => createTeacherExam(studentId, body),
    onMutate: () => setAddError(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: teacherDetailKeys.exams(studentId) });
    },
    onError: (e) => setAddError(e instanceof ApiError ? e.message : "Kaydedilemedi"),
  });

  const delMut = useMutation({
    mutationFn: (examId: number) => deleteTeacherExam(examId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: teacherDetailKeys.exams(studentId) });
    },
  });

  if (q.isLoading) {
    return (
      <View className="items-center justify-center py-16">
        <ActivityIndicator size="large" color="#0e7490" />
      </View>
    );
  }
  if (q.isError || !q.data) {
    return (
      <View className="items-center gap-3 py-16 px-8">
        <Text className="text-center text-base font-semibold text-slate-700">Yüklenemedi</Text>
        <Pressable onPress={() => q.refetch()} className="rounded-xl bg-brand-700 px-5 py-2.5 active:bg-brand-800">
          <Text className="font-semibold text-white">Tekrar dene</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <ExamsTabView
      data={q.data}
      addBusy={addMut.isPending}
      addError={addError}
      onAdd={(body) => addMut.mutate(body)}
      onDelete={(id) => delMut.mutate(id)}
    />
  );
}
