import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQueryClient } from "@tanstack/react-query";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ArchiveWrongsButton } from "@/components/exams/archive-wrongs-button";
import { ApiError } from "@/lib/api";
import { handleCoachAiGateError } from "@/lib/upsell";
import {
  analyzeExamPdf,
  confirmExamImport,
  pickExamPdf,
  type ExamImportConfirmResult,
  type ExamImportDraft,
  type PickedPdf,
} from "@/lib/exam-import";
import { cn } from "@/lib/utils";

/**
 * Deneme PDF içe aktarma — MOBİL SADELEŞTİRİLMİŞ akış (Faz 4).
 *
 * PDF seç → Gemini çift okuma (kredi 6, koç havuzu) → ÖZET önizleme
 * (başlık/tarih/tür/oturum + ders özetleri + kontrol uyarıları) → kaydet →
 * sonuç + "yanlışları arşive ekle". Satır-düzeyi düzenleme (konu/DC/ÖC)
 * bilinçli olarak WEB panelindedir ("Satırları düzelt") — mobil ekranda
 * 120-160 satırlık tablo düzenlenebilir değildir.
 */

type Step = "pick" | "analyzing" | "preview" | "saving" | "done";

// Beyan seçicileri (BEYAN ESAS — tespit bekçiye döner; boş = otomatik)
const GRADE_CHOICES = [
  { value: "", label: "Otomatik" },
  ...[5, 6, 7, 8, 9, 10, 11, 12].map((g) => ({
    value: String(g), label: `${g}. Sınıf`,
  })),
  { value: "mezun", label: "Mezun" },
];

function sectionChoicesFor(grade: string): { value: string; label: string }[] {
  const auto = { value: "", label: "Otomatik" };
  if (!grade) return [auto];
  const g = grade === "mezun" ? 13 : Number(grade);
  if (g >= 5 && g <= 8) {
    return [auto, { value: "lgs", label: "LGS" },
            { value: "okul", label: "Okul/Yazılı" }];
  }
  if (g >= 9 && g <= 10) {
    return [auto, { value: "tyt", label: "Sınıf İzleme/TYT" },
            { value: "okul", label: "Okul/Yazılı" }];
  }
  return [
    auto,
    { value: "tyt", label: "TYT" },
    { value: "ayt_say", label: "AYT Say" },
    { value: "ayt_ea", label: "AYT EA" },
    { value: "ayt_soz", label: "AYT Söz" },
    { value: "ayt_dil", label: "AYT Dil" },
    { value: "okul", label: "Okul/Yazılı" },
  ];
}

export function ExamImportFlow({
  visible,
  onClose,
  studentId = null,
}: {
  visible: boolean;
  onClose: () => void;
  /** Koç yüzeyi: öğrenci id; öğrenci yüzeyi: null. */
  studentId?: number | null;
}) {
  const qc = useQueryClient();
  const [step, setStep] = React.useState<Step>("pick");
  const [pdf, setPdf] = React.useState<PickedPdf | null>(null);
  const [draft, setDraft] = React.useState<ExamImportDraft | null>(null);
  const [selectedPart, setSelectedPart] = React.useState<string | null>(null);
  const [title, setTitle] = React.useState("");
  const [examDate, setExamDate] = React.useState("");
  const [section, setSection] = React.useState("");
  const [needForce, setNeedForce] = React.useState(false);
  const [result, setResult] = React.useState<ExamImportConfirmResult | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [pickerMissing, setPickerMissing] = React.useState(false);
  const [declGrade, setDeclGrade] = React.useState("");
  const [declSection, setDeclSection] = React.useState("");

  function reset() {
    setStep("pick");
    setPdf(null);
    setDraft(null);
    setSelectedPart(null);
    setTitle("");
    setExamDate("");
    setSection("");
    setNeedForce(false);
    setResult(null);
    setError(null);
    setPickerMissing(false);
  }
  function close() {
    if (step === "analyzing" || step === "saving") return;
    reset();
    onClose();
  }

  const multi = (draft?.parts.length ?? 0) > 1;
  const activeRows = React.useMemo(() => {
    if (!draft) return [];
    return multi
      ? draft.rows.filter((r) => r.exam_part === selectedPart)
      : draft.rows;
  }, [draft, multi, selectedPart]);
  const missingResults = activeRows.filter((r) => r.result == null).length;
  const tally = React.useMemo(() => {
    const t = { dogru: 0, yanlis: 0, bos: 0 };
    for (const r of activeRows) {
      if (r.result === "dogru") t.dogru += 1;
      else if (r.result === "yanlis") t.yanlis += 1;
      else if (r.result === "bos") t.bos += 1;
    }
    const penalty = section === "lgs" ? 3 : 4;
    return { ...t, net: Math.round(Math.max(t.dogru - t.yanlis / penalty, 0) * 100) / 100 };
  }, [activeRows, section]);

  function autoTitle(base: string | null, d: ExamImportDraft, part: string | null): string {
    const t = base ?? "";
    if (d.parts.length <= 1) return t;
    const p = d.parts.find((x) => x.part === part);
    return p ? `${t} — ${p.section_label}` : t;
  }

  async function startPick() {
    const picked = await pickExamPdf();
    if (picked === "unavailable") {
      setStep("pick");
      setPdf(null);
      setDraft(null);
      // eski kurulum: native modül yok — analiz/arşiv çalışır, PDF seçimi çalışmaz
      setPickerMissing(true);
      return;
    }
    if (picked == null) return;
    setPdf(picked);
    setStep("analyzing");
    try {
      const d = await analyzeExamPdf(picked, studentId, {
        declaredSection: declSection || null,
        declaredGrade:
          declGrade && declGrade !== "mezun" ? Number(declGrade) : null,
      });
      const firstPart = d.parts[0]?.part ?? null;
      setDraft(d);
      setSelectedPart(firstPart);
      setTitle(autoTitle(d.title, d, firstPart));
      setExamDate(d.exam_date ?? "");
      setSection(d.parts[0]?.section ?? d.section);
      setStep("preview");
    } catch (e) {
      // Koç yüzeyinde paket/kredi kapısı → Paketim (IAP) yönlendirmesi.
      // Öğrenci yüzeyinde (studentId null) kapı koça aittir — yalnız mesaj.
      const code = e instanceof ApiError ? e.code : null;
      if (studentId != null && handleCoachAiGateError(code)) {
        setStep("pick");
        return;
      }
      setError(e instanceof ApiError ? e.message : "Belge analiz edilemedi.");
      setStep("pick");
    }
  }

  function switchPart(part: string | null) {
    if (!draft) return;
    setSelectedPart(part);
    const p = draft.parts.find((x) => x.part === part);
    if (p) setSection(p.section);
    setTitle(autoTitle(draft.title, draft, part));
  }

  async function save(force: boolean) {
    if (!draft) return;
    if (!title.trim() || !examDate) {
      setError("Deneme adı ve tarihi zorunlu.");
      return;
    }
    setError(null);
    setStep("saving");
    try {
      const res = await confirmExamImport(
        {
          title: title.trim(),
          exam_date: examDate,
          section,
          scope: draft.scope,
          grade_hint: draft.grade_hint,
          score_info: draft.score_info,
          force,
          rows: activeRows
            .filter((r) => r.result != null)
            .map((r) => ({
              subject_raw: r.subject_raw,
              question_no: r.question_no,
              topic_raw: r.topic_raw,
              topic_id: r.topic_id,
              correct_answer: r.correct_answer,
              student_answer: r.student_answer,
              result: r.result as string,
              is_suspect: r.is_suspect,
            })),
        },
        pdf,
        studentId,
      );
      setResult(res.data);
      setStep("done");
      if (studentId != null) {
        qc.invalidateQueries({ queryKey: ["teacher", "student", studentId, "exams"] });
      } else {
        qc.invalidateQueries({ queryKey: ["student", "exams"] });
      }
    } catch (e) {
      if (e instanceof ApiError && e.code === "duplicate_exam") {
        setNeedForce(true);
        setStep("preview");
        return;
      }
      setError(e instanceof ApiError ? e.message : "Kaydedilemedi.");
      setStep("preview");
    }
  }

  const failing = (draft?.checks ?? []).filter((c) => !c.ok);
  const activeSubjects = (draft?.subjects ?? []).filter(
    (s) => !multi || s.part === selectedPart,
  );

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={close}>
      <SafeAreaView className="flex-1 bg-slate-50">
        {/* Başlık çubuğu */}
        <View className="flex-row items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
          <Text className="text-base font-bold text-slate-900">
            Deneme sonucunu PDF&apos;ten aktar
          </Text>
          <Pressable onPress={close} hitSlop={10}>
            <Ionicons name="close" size={22} color="#475569" />
          </Pressable>
        </View>

        <ScrollView contentContainerClassName="p-4 gap-3">
          {error ? (
            <View className="rounded-xl border border-rose-200 bg-rose-50 p-3">
              <Text className="text-xs text-rose-800">{error}</Text>
            </View>
          ) : null}

          {step === "pick" ? (
            <View className="gap-3">
              <View className="gap-2 rounded-2xl border border-slate-200 bg-white p-3">
                <Text className="text-xs font-medium text-slate-700">
                  Denemenin sınıfı ve türünü biliyorsan seç — yanlış tür
                  ihtimali sıfırlanır. Bilmiyorsan Otomatik bırak.
                </Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View className="flex-row gap-1.5">
                    {GRADE_CHOICES.map((c) => {
                      const active = declGrade === c.value;
                      return (
                        <Pressable
                          key={c.value || "auto"}
                          onPress={() => { setDeclGrade(c.value); setDeclSection(""); }}
                          className={cn(
                            "rounded-full border px-3 py-1.5",
                            active ? "border-brand-700 bg-brand-700"
                                   : "border-slate-300 bg-white",
                          )}
                        >
                          <Text className={cn("text-xs font-semibold",
                                              active ? "text-white" : "text-slate-600")}>
                            {c.label}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </ScrollView>
                {declGrade ? (
                  <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                    <View className="flex-row gap-1.5">
                      {sectionChoicesFor(declGrade).map((c) => {
                        const active = declSection === c.value;
                        return (
                          <Pressable
                            key={c.value || "auto"}
                            onPress={() => setDeclSection(c.value)}
                            className={cn(
                              "rounded-full border px-3 py-1.5",
                              active ? "border-violet-600 bg-violet-600"
                                     : "border-slate-300 bg-white",
                            )}
                          >
                            <Text className={cn("text-xs font-semibold",
                                                active ? "text-white" : "text-slate-600")}>
                              {c.label}
                            </Text>
                          </Pressable>
                        );
                      })}
                    </View>
                  </ScrollView>
                ) : null}
              </View>
              {pickerMissing ? (
                <View className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <Text className="text-xs text-amber-900">
                    PDF seçici bu uygulama sürümünde yok — mağazadan güncelleme
                    çıkınca yükle, ya da PDF&apos;i şimdilik web panelinden aktar.
                    Konu analizi ve yanlış arşivleme bu sürümde de çalışır.
                  </Text>
                </View>
              ) : null}
              <Pressable
                onPress={() => void startPick()}
                className="items-center gap-2 rounded-2xl border-2 border-dashed border-slate-300 bg-white px-4 py-10 active:bg-slate-100"
              >
                <Ionicons name="document-attach-outline" size={40} color="#7c3aed" />
                <Text className="font-semibold text-slate-800">
                  Deneme sonuç PDF&apos;ini seç
                </Text>
                <Text className="text-center text-xs text-slate-500">
                  Yayınevi/okul sisteminden indirdiğin konu analizli sonuç
                  belgesi (≤10 MB)
                </Text>
              </Pressable>
              <View className="gap-1 px-1">
                <Text className="text-xs text-slate-500">
                  • Sınav türü otomatik tanınır — yanlışsa önizlemede değiştirirsin.
                </Text>
                <Text className="text-xs text-slate-500">
                  • Konu adları müfredatına otomatik çevrilir; analiz{" "}
                  <Text className="font-semibold">6 kredi</Text> (koç havuzundan).
                </Text>
                <Text className="text-xs text-slate-500">
                  • Soru satırı düzeltmeleri (konu/cevap) web panelinde yapılır.
                </Text>
              </View>
            </View>
          ) : null}

          {step === "analyzing" ? (
            <View className="items-center gap-3 py-16">
              <ActivityIndicator size="large" color="#7c3aed" />
              <Text className="font-semibold text-slate-800">
                Yapay zekâ belgeyi okuyor…
              </Text>
              <Text className="px-8 text-center text-xs text-slate-500">
                Uydurmayı önlemek için belge iki kez bağımsız okunur — uzun
                belgelerde 1-2 dakika sürebilir, ekranı kapatma.
              </Text>
            </View>
          ) : null}

          {(step === "preview" || step === "saving") && draft ? (
            <View className="gap-3">
              {multi ? (
                <View className="rounded-xl border border-cyan-200 bg-cyan-50 p-3">
                  <Text className="text-xs font-medium text-cyan-900">
                    Bu belgede {draft.parts.length} sınav oturumu var — hangisini
                    kaydedeceğini seç (diğerini sonra tekrar kaydedebilirsin):
                  </Text>
                  <View className="mt-2 flex-row flex-wrap gap-1.5">
                    {draft.parts.map((p) => {
                      const active = selectedPart === p.part;
                      return (
                        <Pressable
                          key={p.part ?? "tek"}
                          onPress={() => switchPart(p.part)}
                          className={cn(
                            "rounded-full border px-3 py-1.5",
                            active
                              ? "border-cyan-600 bg-cyan-600"
                              : "border-cyan-300 bg-white",
                          )}
                        >
                          <Text
                            className={cn(
                              "text-xs font-semibold",
                              active ? "text-white" : "text-cyan-800",
                            )}
                          >
                            {p.section_label} · {p.question_count} soru
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </View>
              ) : null}

              <View className="gap-2 rounded-2xl border border-slate-200 bg-white p-3">
                <Text className="text-xs font-medium text-slate-600">Deneme adı</Text>
                <TextInput
                  value={title}
                  onChangeText={setTitle}
                  placeholder="Deneme adı"
                  placeholderTextColor="#cbd5e1"
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
                />
                <View className="flex-row gap-2">
                  <View className="flex-1 gap-1">
                    <Text className="text-xs font-medium text-slate-600">
                      Tarih (YYYY-AA-GG)
                    </Text>
                    <TextInput
                      value={examDate}
                      onChangeText={setExamDate}
                      placeholder="2026-03-09"
                      placeholderTextColor="#cbd5e1"
                      className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900"
                    />
                  </View>
                </View>
                <Text className="text-xs font-medium text-slate-600">Sınav türü</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  <View className="flex-row gap-1.5">
                    {draft.section_choices.map((c) => {
                      const active = section === c.value;
                      return (
                        <Pressable
                          key={c.value}
                          onPress={() => setSection(c.value)}
                          className={cn(
                            "rounded-full border px-3 py-1.5",
                            active
                              ? "border-brand-700 bg-brand-700"
                              : "border-slate-300 bg-white",
                          )}
                        >
                          <Text
                            className={cn(
                              "text-xs font-semibold",
                              active ? "text-white" : "text-slate-600",
                            )}
                          >
                            {c.label}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </ScrollView>
                {draft.confidence !== "high" ? (
                  <Text className="text-xs text-amber-700">
                    Sınav türünden tam emin olamadım — yukarıdan kontrol et.
                  </Text>
                ) : null}
              </View>

              {needForce || draft.duplicate_exam_id ? (
                <View className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <Text className="text-xs text-amber-900">
                    Bu deneme (aynı ad + tarih) daha önce kaydedilmiş görünüyor.
                    Yeniden kaydedersen iki ayrı kayıt oluşur.
                  </Text>
                </View>
              ) : null}
              {failing.map((c) => (
                <View key={c.code} className="rounded-xl border border-rose-200 bg-rose-50 p-3">
                  <Text className="text-xs text-rose-900">
                    <Text className="font-semibold">{c.label}:</Text> {c.detail}
                  </Text>
                </View>
              ))}

              <View className="rounded-2xl border border-slate-200 bg-white p-3">
                <Text className="text-sm font-semibold text-slate-800">
                  Ders özetleri
                </Text>
                {activeSubjects.map((s) => (
                  <View
                    key={`${s.part ?? ""}-${s.name}`}
                    className="mt-2 flex-row items-center justify-between"
                  >
                    <Text className="flex-1 text-xs text-slate-700" numberOfLines={1}>
                      {s.name}
                      <Text className="text-slate-400"> · {s.questions} soru</Text>
                    </Text>
                    <Text className="text-xs text-slate-600">
                      <Text className="font-semibold text-emerald-600">{s.correct}D</Text>{" "}
                      <Text className="font-semibold text-rose-600">{s.wrong}Y</Text>{" "}
                      <Text className="text-slate-400">{s.blank}B</Text>
                      {"  "}
                      <Text className="font-bold text-slate-900">{s.net}</Text>
                      {s.doc_net != null ? (
                        <Text className="text-slate-400"> (belge {s.doc_net})</Text>
                      ) : null}
                    </Text>
                  </View>
                ))}
                <Text className="mt-2 text-[11px] text-slate-400">
                  Eşleşme: {draft.match_stats.alias + draft.match_stats.auto} otomatik ·{" "}
                  {draft.match_stats.ai} AI · {draft.match_stats.none} eşleşmedi
                  {draft.suspect_count > 0
                    ? ` · ${draft.suspect_count} şüpheli hücre`
                    : ""}
                </Text>
                <Text className="mt-1 text-[11px] text-slate-400">
                  Konu/cevap düzeltmeleri web panelindeki &quot;Satırları
                  düzelt&quot; ekranında yapılır.
                </Text>
              </View>

              {missingResults > 0 ? (
                <View className="rounded-xl border border-rose-200 bg-rose-50 p-3">
                  <Text className="text-xs text-rose-900">
                    {missingResults} sorunun sonucu belgeden okunamadı — bu belge
                    web panelinden (satır düzelterek) aktarılmalı.
                  </Text>
                </View>
              ) : null}
            </View>
          ) : null}

          {step === "done" && result ? (
            <View className="items-center gap-3 py-6">
              <Ionicons name="checkmark-circle" size={48} color="#10b981" />
              <Text className="text-lg font-bold text-slate-900">Deneme kaydedildi</Text>
              <Text className="text-center text-sm text-slate-500">
                {result.title} · {result.section_label}
              </Text>
              <View className="flex-row gap-6 py-2">
                <View className="items-center">
                  <Text className="text-2xl font-extrabold text-cyan-700">{result.net}</Text>
                  <Text className="text-[11px] text-slate-400">net</Text>
                </View>
                <View className="items-center">
                  <Text className="text-2xl font-extrabold text-emerald-600">
                    {result.total_correct}
                  </Text>
                  <Text className="text-[11px] text-slate-400">doğru</Text>
                </View>
                <View className="items-center">
                  <Text className="text-2xl font-extrabold text-rose-600">
                    {result.total_wrong}
                  </Text>
                  <Text className="text-[11px] text-slate-400">yanlış</Text>
                </View>
                <View className="items-center">
                  <Text className="text-2xl font-extrabold text-slate-500">
                    {result.total_blank}
                  </Text>
                  <Text className="text-[11px] text-slate-400">boş</Text>
                </View>
              </View>
              <Text className="px-6 text-center text-xs text-slate-500">
                {result.question_count} sorunun {result.matched_topic_count}&apos;i
                müfredat konusuna bağlandı — konu analizi güncellendi.
              </Text>
              <View className="w-full px-2 pt-2">
                <ArchiveWrongsButton
                  examId={result.exam_id}
                  studentId={studentId}
                  wrongCount={result.total_wrong}
                />
              </View>
            </View>
          ) : null}
        </ScrollView>

        {/* Sabit alt aksiyon çubuğu */}
        {step === "preview" || step === "saving" ? (
          <View className="border-t border-slate-200 bg-white px-4 py-3">
            <View className="flex-row items-center justify-between">
              <Text className="text-xs text-slate-500">
                <Text className="font-bold text-slate-900">{tally.net}</Text> net ·{" "}
                <Text className="text-emerald-600">{tally.dogru}D</Text>{" "}
                <Text className="text-rose-600">{tally.yanlis}Y</Text>{" "}
                {tally.bos}B
              </Text>
              <Pressable
                onPress={() => void save(needForce)}
                disabled={step === "saving" || missingResults > 0}
                className={cn(
                  "flex-row items-center gap-2 rounded-xl px-5 py-3",
                  missingResults > 0
                    ? "bg-slate-300"
                    : needForce
                      ? "bg-amber-600 active:bg-amber-700"
                      : "bg-brand-700 active:bg-brand-800",
                )}
              >
                {step === "saving" ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Ionicons name="checkmark" size={16} color="#fff" />
                )}
                <Text className="font-semibold text-white">
                  {needForce ? "Yine de kaydet" : "Kontrol ettim, kaydet"}
                </Text>
              </Pressable>
            </View>
          </View>
        ) : step === "done" ? (
          <View className="border-t border-slate-200 bg-white px-4 py-3">
            <Pressable
              onPress={close}
              className="items-center rounded-xl bg-brand-700 px-5 py-3 active:bg-brand-800"
            >
              <Text className="font-semibold text-white">Kapat</Text>
            </Pressable>
          </View>
        ) : null}
      </SafeAreaView>
    </Modal>
  );
}
