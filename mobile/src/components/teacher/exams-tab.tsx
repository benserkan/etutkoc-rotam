import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ActivityIndicator, Alert, Pressable, Text, TextInput, View } from "react-native";

import { ArchiveWrongsButton } from "@/components/exams/archive-wrongs-button";
import { ExamDetailSheet } from "@/components/exams/exam-detail-sheet";
import { ExamAddActions } from "@/components/exams/exam-add-actions";
import { ExamImportFlow } from "@/components/exams/exam-import-flow";
import { ProgressReportCard } from "@/components/exams/progress-report-card";
import { ScoreEstimateCard } from "@/components/exams/score-estimate-card";
import { examProgressKeys, getExamShares } from "@/lib/exam-progress";
import { TopicAnalysisCard } from "@/components/exams/topic-analysis-card";
import { FormSheet } from "@/components/ui/form-sheet";
import {
  createTeacherExam,
  deleteTeacherExam,
  getTeacherStudentExams,
  teacherDetailKeys,
  type ExamSectionOption,
  type ExamSubjectInput,
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
  maarif_1: { bg: "bg-teal-50", text: "text-teal-700" },
  maarif_2: { bg: "bg-fuchsia-50", text: "text-fuchsia-700" },
  maarif_9: { bg: "bg-lime-50", text: "text-lime-800" },
  maarif_10: { bg: "bg-sky-50", text: "text-sky-700" },
  maarif_11: { bg: "bg-blue-50", text: "text-blue-700" },
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
type ExamMode = "total" | "subjects";

function netOf(c: number, w: number, isLgs: boolean): number {
  return Math.max(0, c - w / (isLgs ? 3 : 4));
}

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
  const [mode, setMode] = React.useState<ExamMode>("total");
  const [correct, setCorrect] = React.useState("");
  const [wrong, setWrong] = React.useState("");
  const [blank, setBlank] = React.useState("");
  // #6 — ders bazlı satırlar (her ders için D/Y/B)
  const [subjects, setSubjects] = React.useState<ExamSubjectInput[]>([{ name: "", correct: 0, wrong: 0, blank: 0 }]);

  const isLgs = section === "lgs";

  const c = Number(correct) || 0;
  const w = Number(wrong) || 0;
  const b = Number(blank) || 0;

  const sumC = subjects.reduce((a, s) => a + (Number(s.correct) || 0), 0);
  const sumW = subjects.reduce((a, s) => a + (Number(s.wrong) || 0), 0);
  const sumB = subjects.reduce((a, s) => a + (Number(s.blank) || 0), 0);

  const net = mode === "subjects" ? netOf(sumC, sumW, isLgs) : netOf(c, w, isLgs);

  const cleanedSubjects = subjects
    .map((s) => ({ ...s, name: s.name.trim() }))
    .filter((s) => s.name.length > 0 && (s.correct + s.wrong + s.blank) > 0);

  const canSave =
    title.trim().length > 0 &&
    !busy &&
    (mode === "total" ? c + w + b > 0 : cleanedSubjects.length > 0);

  function updateSubject(i: number, patch: Partial<ExamSubjectInput>) {
    setSubjects((prev) => prev.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  }
  function addSubjectRow() {
    setSubjects((prev) => [...prev, { name: "", correct: 0, wrong: 0, blank: 0 }]);
  }
  function removeSubjectRow(i: number) {
    setSubjects((prev) => (prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== i)));
  }

  function submit() {
    if (mode === "subjects") {
      onSubmit({
        title: title.trim(),
        exam_date: date,
        section,
        total_correct: 0,
        total_wrong: 0,
        total_blank: 0,
        subjects: cleanedSubjects,
      });
    } else {
      onSubmit({ title: title.trim(), exam_date: date, section, total_correct: c, total_wrong: w, total_blank: b });
    }
  }

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

      {/* #6 — giriş modu: Toplam veya Ders bazlı */}
      <View className="flex-row rounded-xl border border-slate-200 bg-slate-50 p-1">
        {([
          { v: "total", label: "Toplam" },
          { v: "subjects", label: "Ders bazlı" },
        ] as { v: ExamMode; label: string }[]).map((m) => {
          const active = m.v === mode;
          return (
            <Pressable
              key={m.v}
              onPress={() => setMode(m.v)}
              className={cn("flex-1 items-center rounded-lg py-2", active ? "bg-white" : "")}
            >
              <Text className={cn("text-sm font-semibold", active ? "text-brand-700" : "text-slate-500")}>{m.label}</Text>
            </Pressable>
          );
        })}
      </View>

      {mode === "total" ? (
        <View className="flex-row gap-3">
          <NumField label="Doğru" value={correct} onChangeText={setCorrect} />
          <NumField label="Yanlış" value={wrong} onChangeText={setWrong} />
          <NumField label="Boş" value={blank} onChangeText={setBlank} />
        </View>
      ) : (
        <View className="gap-2">
          <View className="flex-row gap-1.5 px-0.5">
            <Text className="flex-1 text-[10px] font-medium uppercase tracking-wide text-slate-400">Ders</Text>
            <Text className="w-11 text-center text-[10px] font-medium uppercase tracking-wide text-slate-400">D</Text>
            <Text className="w-11 text-center text-[10px] font-medium uppercase tracking-wide text-slate-400">Y</Text>
            <Text className="w-11 text-center text-[10px] font-medium uppercase tracking-wide text-slate-400">B</Text>
            <View className="w-6" />
          </View>
          {subjects.map((s, i) => (
            <View key={i} className="flex-row items-center gap-1.5">
              <TextInput
                value={s.name}
                onChangeText={(v) => updateSubject(i, { name: v })}
                placeholder="Matematik"
                placeholderTextColor="#cbd5e1"
                className="flex-1 rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900"
              />
              <TextInput
                value={s.correct ? String(s.correct) : ""}
                onChangeText={(v) => updateSubject(i, { correct: Number(v.replace(/[^0-9]/g, "")) || 0 })}
                keyboardType="number-pad"
                placeholder="0"
                placeholderTextColor="#cbd5e1"
                className="w-11 rounded-lg border border-slate-300 bg-white px-1 py-2 text-center text-sm font-semibold text-slate-900"
              />
              <TextInput
                value={s.wrong ? String(s.wrong) : ""}
                onChangeText={(v) => updateSubject(i, { wrong: Number(v.replace(/[^0-9]/g, "")) || 0 })}
                keyboardType="number-pad"
                placeholder="0"
                placeholderTextColor="#cbd5e1"
                className="w-11 rounded-lg border border-slate-300 bg-white px-1 py-2 text-center text-sm font-semibold text-slate-900"
              />
              <TextInput
                value={s.blank ? String(s.blank) : ""}
                onChangeText={(v) => updateSubject(i, { blank: Number(v.replace(/[^0-9]/g, "")) || 0 })}
                keyboardType="number-pad"
                placeholder="0"
                placeholderTextColor="#cbd5e1"
                className="w-11 rounded-lg border border-slate-300 bg-white px-1 py-2 text-center text-sm font-semibold text-slate-900"
              />
              <Pressable onPress={() => removeSubjectRow(i)} disabled={subjects.length <= 1} hitSlop={6} className="w-6 items-center">
                <Ionicons name="close-circle" size={18} color={subjects.length <= 1 ? "#e2e8f0" : "#fb7185"} />
              </Pressable>
            </View>
          ))}
          <Pressable onPress={addSubjectRow} className="flex-row items-center justify-center gap-1.5 rounded-lg border border-dashed border-slate-300 py-2.5 active:bg-slate-50">
            <Ionicons name="add" size={16} color="#0e7490" />
            <Text className="text-sm font-medium text-brand-700">Ders ekle</Text>
          </Pressable>
          <Text className="text-[11px] text-slate-400">Toplam: D {sumC} · Y {sumW} · B {sumB}</Text>
        </View>
      )}

      <View className="flex-row items-center justify-between rounded-xl bg-brand-50 px-4 py-3">
        <Text className="text-sm font-medium text-brand-700">Hesaplanan net</Text>
        <Text className="text-2xl font-extrabold text-brand-800">{net.toFixed(2).replace(/\.00$/, "")}</Text>
      </View>

      {error ? <Text className="text-sm text-rose-600">{error}</Text> : null}

      <Pressable
        onPress={submit}
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
  studentId,
}: {
  data: TeacherExamsResponse;
  addBusy: boolean;
  addError: string | null;
  onAdd: (body: TeacherExamCreateBody) => void;
  onDelete?: (examId: number) => void;
  /** Verilirse PDF içe aktarma + konu analizi + arşiv köprüsü aktifleşir. */
  studentId?: number;
}) {
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [importOpen, setImportOpen] = React.useState(false);
  const [detailId, setDetailId] = React.useState<number | null>(null);
  const qc = useQueryClient();
  const sharesQ = useQuery({
    queryKey: examProgressKeys.shares(studentId ?? -1),
    queryFn: () => getExamShares(studentId ?? -1),
    enabled: studentId != null,
  });
  const shares = sharesQ.data?.shares ?? {};
  const detail = data.rows.find((r) => r.id === detailId) ?? null;
  // tür seçici: en çok denemesi olan tür varsayılan (ölçekler karışmasın)
  const sectionCounts = React.useMemo(() => {
    const m = new Map<string, { label: string; n: number }>();
    for (const r of data.rows) {
      const k = r.series_key || r.section; // tür + genel/branş
      const e = m.get(k);
      if (e) e.n += 1;
      else m.set(k, { label: r.series_label || r.section_label, n: 1 });
    }
    return [...m.entries()].map(([value, v]) => ({ value, ...v })).sort((a, b) => b.n - a.n);
  }, [data.rows]);
  const [sel, setSel] = React.useState<string | null>(null);
  const activeSection = sel && sectionCounts.some((x) => x.value === sel) ? sel : sectionCounts[0]?.value ?? null;
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

      <ExamAddActions
        onImport={studentId != null ? () => setImportOpen(true) : undefined}
        onManual={() => setSheetOpen(true)}
      />

      {studentId != null && sectionCounts.length > 1 ? (
        <View className="flex-row flex-wrap gap-1.5">
          {sectionCounts.map((g) => {
            const active = g.value === activeSection;
            const tn = tone(g.value);
            return (
              <Pressable
                key={g.value}
                onPress={() => setSel(g.value)}
                className={cn("rounded-full border px-3 py-1.5", active ? cn(tn.bg, "border-transparent") : "border-slate-200 bg-white")}
              >
                <Text className={cn("text-xs font-medium", active ? tn.text : "text-slate-500")}>
                  {g.label} ({g.n})
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}

      {studentId != null ? <TopicAnalysisCard studentId={studentId} section={activeSection} /> : null}
      {studentId != null && data.rows.length ? (
        <>
          <ProgressReportCard studentId={studentId} section={activeSection} />
          <ScoreEstimateCard studentId={studentId} />
        </>
      ) : null}

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
                onPress={studentId != null ? () => setDetailId(e.id) : undefined}
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
                {shares[String(e.id)] ? (
                  <View className="mt-2 flex-row items-center gap-1">
                    <Ionicons name="person-circle-outline" size={14} color="#0e7490" />
                    <Text className="text-[11px] font-medium text-cyan-800">Öğrenciyle paylaşıldı</Text>
                  </View>
                ) : null}
                {studentId != null && e.import_source === "pdf_import" && e.total_wrong > 0 ? (
                  <View className="mt-2 flex-row justify-end">
                    <ArchiveWrongsButton
                      examId={e.id}
                      studentId={studentId}
                      wrongCount={e.total_wrong}
                      compact
                    />
                  </View>
                ) : null}
              </Pressable>
            );
          })}
          {onDelete ? (
            <Text className="px-1 text-[11px] text-slate-400">
              Detay, paylaşım ve çeldirici için dokun; silmek için basılı tut.
            </Text>
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
      {studentId != null ? (
        <ExamDetailSheet
          exam={detail}
          studentId={studentId}
          share={detail ? shares[String(detail.id)] ?? null : null}
          onClose={() => setDetailId(null)}
          onChanged={() => qc.invalidateQueries({ queryKey: teacherDetailKeys.exams(studentId) })}
        />
      ) : null}
      {studentId != null ? (
        <ExamImportFlow
          visible={importOpen}
          onClose={() => setImportOpen(false)}
          studentId={studentId}
        />
      ) : null}
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
      studentId={studentId}
    />
  );
}
