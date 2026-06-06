import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import type {
  StudentBookRow,
  StudentBookSectionRow,
  SubjectBrief,
  TaskCreateBody,
} from "@/lib/teacher";
import { cn } from "@/lib/utils";

type Step = "type" | "book" | "section" | "count" | "activity";

const ACTIVITY_TYPES = [
  { v: "video", label: "Video", placeholder: "Konu videosu izle" },
  { v: "ozet", label: "Özet", placeholder: "Konu özeti çıkar" },
  { v: "tekrar", label: "Tekrar", placeholder: "Konu tekrarı yap" },
  { v: "other", label: "Diğer", placeholder: "örn. Soru çözüm videosu" },
];

function remaining(s: StudentBookSectionRow): number {
  return Math.max(0, s.test_count - s.completed_count - s.reserved_count);
}
function bookRemaining(b: StudentBookRow): number {
  return b.sections.reduce((acc, s) => acc + remaining(s), 0);
}

export function AddTaskSheet({
  visible,
  date,
  books,
  booksLoading,
  subjects,
  busy,
  onClose,
  onSubmit,
}: {
  visible: boolean;
  date: string | null;
  books: StudentBookRow[];
  booksLoading: boolean;
  subjects: SubjectBrief[];
  busy: boolean;
  onClose: () => void;
  onSubmit: (body: TaskCreateBody) => void;
}) {
  const [step, setStep] = React.useState<Step>("type");
  const [book, setBook] = React.useState<StudentBookRow | null>(null);
  const [section, setSection] = React.useState<StudentBookSectionRow | null>(null);
  const [count, setCount] = React.useState("");
  const [actType, setActType] = React.useState("video");
  const [actSubject, setActSubject] = React.useState<SubjectBrief | null>(null);
  const [actTitle, setActTitle] = React.useState("");

  // Sheet her açıldığında baştan başla.
  const visRef = React.useRef(visible);
  if (visRef.current !== visible) {
    visRef.current = visible;
    if (visible) {
      setStep("type"); setBook(null); setSection(null); setCount("");
      setActType("video"); setActSubject(null); setActTitle("");
    }
  }

  if (!date) return null;

  // #3 — yalnız kalan kapasitesi olan kitaplar + bölümler (biten kaynaklar gizli).
  const availableBooks = books.filter((b) => bookRemaining(b) > 0);
  const availableSections = book ? book.sections.filter((s) => remaining(s) > 0) : [];

  const actPlaceholder = ACTIVITY_TYPES.find((a) => a.v === actType)?.placeholder ?? "Başlık";

  function submitTest() {
    if (!book || !section) return;
    const n = Number(count);
    if (!(n > 0)) return;
    onSubmit({
      date: date!,
      type: "test",
      title: "Görev",
      items: [{ book_id: book.book_id, section_id: section.section_id, planned_count: n }],
    });
  }
  function submitActivity() {
    const detail = actTitle.trim();
    if (!detail) return;
    // #5 — ders seçiliyse "{Ders} · {detay}" (editör/ızgara ders grubuna girer).
    const title = actSubject ? `${actSubject.name} · ${detail}` : detail;
    onSubmit({ date: date!, type: actType, title, items: [] });
  }

  return (
    <FormSheet visible={visible} title="Görev ekle" onClose={onClose}>
      <View className="gap-4 pb-2">
        {/* Adım göstergesi */}
        {step !== "type" ? (
          <Pressable onPress={() => setStep("type")} className="flex-row items-center gap-1">
            <Ionicons name="chevron-back" size={16} color="#0e7490" />
            <Text className="text-sm font-medium text-brand-700">Tip seçimine dön</Text>
          </Pressable>
        ) : null}

        {step === "type" ? (
          <View className="gap-3">
            <Text className="text-sm text-slate-600">Ne tür görev eklemek istiyorsun?</Text>
            <Pressable
              onPress={() => setStep("book")}
              className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white p-4 active:bg-slate-50"
            >
              <View className="flex-row items-center gap-3">
                <Ionicons name="book-outline" size={20} color="#0e7490" />
                <View>
                  <Text className="text-[15px] font-semibold text-slate-900">Test (kitaptan)</Text>
                  <Text className="text-xs text-slate-400">Kitap + bölüm + soru sayısı</Text>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
            </Pressable>
            <Pressable
              onPress={() => setStep("activity")}
              className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white p-4 active:bg-slate-50"
            >
              <View className="flex-row items-center gap-3">
                <Ionicons name="play-circle-outline" size={20} color="#0e7490" />
                <View>
                  <Text className="text-[15px] font-semibold text-slate-900">Etkinlik</Text>
                  <Text className="text-xs text-slate-400">Video / özet / tekrar / diğer</Text>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
            </Pressable>
          </View>
        ) : null}

        {step === "book" ? (
          booksLoading ? (
            <Text className="text-sm text-slate-400">Kitaplar yükleniyor…</Text>
          ) : availableBooks.length === 0 ? (
            <Text className="text-sm text-slate-400">
              {books.length === 0
                ? "Bu öğrenciye atanmış kitap yok. Kitap atamayı web panelinden yapabilirsin."
                : "Atanabilir (kalan kapasitesi olan) kitap yok — tüm kitapların testleri bitmiş veya dağıtılmış."}
            </Text>
          ) : (
            <View className="gap-2">
              <Text className="text-xs font-medium text-slate-600">Kitap seç</Text>
              {availableBooks.map((b) => (
                <Pressable
                  key={b.student_book_id}
                  onPress={() => { setBook(b); setSection(null); setStep("section"); }}
                  className="rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
                >
                  <Text className="text-[14px] font-semibold text-slate-900" numberOfLines={1}>{b.book_name}</Text>
                  <Text className="text-xs text-slate-400">
                    {b.subject_name} · {b.book_type_label_tr} · {bookRemaining(b)} test kaldı
                  </Text>
                </Pressable>
              ))}
            </View>
          )
        ) : null}

        {step === "section" && book ? (
          <View className="gap-2">
            <Text className="text-xs font-medium text-slate-600">{book.book_name} — bölüm seç</Text>
            {availableSections.length === 0 ? (
              <Text className="text-sm text-slate-400">Bu kitapta kalan testi olan bölüm yok.</Text>
            ) : (
              availableSections.map((s) => {
                const rem = remaining(s);
                return (
                  <Pressable
                    key={s.section_id}
                    onPress={() => { setSection(s); setCount(String(Math.min(rem, 20))); setStep("count"); }}
                    className="flex-row items-center justify-between rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
                  >
                    <View className="flex-1">
                      <Text className="text-[14px] font-medium text-slate-900" numberOfLines={1}>{s.label}</Text>
                      {s.topic_name ? <Text className="text-xs text-slate-400">{s.topic_name}</Text> : null}
                    </View>
                    <Text className="text-xs font-semibold text-emerald-600">{rem} kalan</Text>
                  </Pressable>
                );
              })
            )}
          </View>
        ) : null}

        {step === "count" && book && section ? (
          <View className="gap-2">
            <View className="rounded-xl bg-slate-50 p-3">
              <Text className="text-[13px] font-semibold text-slate-800">{book.book_name}</Text>
              <Text className="text-xs text-slate-500">{section.label} · {remaining(section)} kalan</Text>
            </View>
            <Text className="text-xs font-medium text-slate-600">Kaç test atansın?</Text>
            <TextInput
              value={count}
              onChangeText={(v) => setCount(v.replace(/[^0-9]/g, "").slice(0, 4))}
              keyboardType="number-pad"
              placeholder="örn. 20"
              placeholderTextColor="#94a3b8"
              className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-lg font-semibold text-slate-900"
            />
            <Pressable
              onPress={submitTest}
              disabled={busy || !(Number(count) > 0)}
              className={cn("items-center rounded-xl py-3.5", busy || !(Number(count) > 0) ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}
            >
              <Text className="text-base font-semibold text-white">{busy ? "Ekleniyor…" : "Programa ekle"}</Text>
            </Pressable>
          </View>
        ) : null}

        {step === "activity" ? (
          <View className="gap-4">
            <View className="gap-2">
              <Text className="text-xs font-medium text-slate-600">Etkinlik türü</Text>
              <View className="flex-row flex-wrap gap-2">
                {ACTIVITY_TYPES.map((a) => {
                  const active = a.v === actType;
                  return (
                    <Pressable
                      key={a.v}
                      onPress={() => setActType(a.v)}
                      className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}
                    >
                      <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{a.label}</Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>

            {/* #5 — ders seçimi (opsiyonel; başlık ders adıyla gruplanır) */}
            <View className="gap-2">
              <Text className="text-xs font-medium text-slate-600">Ders (opsiyonel)</Text>
              <View className="flex-row flex-wrap gap-2">
                <Pressable
                  onPress={() => setActSubject(null)}
                  className={cn("rounded-full border px-3 py-1.5", !actSubject ? "border-slate-700 bg-slate-700" : "border-slate-300 bg-white")}
                >
                  <Text className={cn("text-sm font-medium", !actSubject ? "text-white" : "text-slate-600")}>Genel</Text>
                </Pressable>
                {subjects.map((s) => {
                  const active = actSubject?.id === s.id;
                  return (
                    <Pressable
                      key={s.id}
                      onPress={() => setActSubject(s)}
                      className={cn("rounded-full border px-3 py-1.5", active ? "border-brand-600 bg-brand-50" : "border-slate-300 bg-white")}
                    >
                      <Text className={cn("text-sm font-medium", active ? "text-brand-700" : "text-slate-600")}>{s.name}</Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>

            <View className="gap-1">
              <Text className="text-xs font-medium text-slate-600">Başlık</Text>
              <TextInput
                value={actTitle}
                onChangeText={setActTitle}
                placeholder={actPlaceholder}
                placeholderTextColor="#94a3b8"
                className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
              />
              {actSubject && actTitle.trim() ? (
                <Text className="text-[11px] text-slate-400">Görev: {actSubject.name} · {actTitle.trim()}</Text>
              ) : null}
            </View>

            <Pressable
              onPress={submitActivity}
              disabled={busy || !actTitle.trim()}
              className={cn("items-center rounded-xl py-3.5", busy || !actTitle.trim() ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}
            >
              <Text className="text-base font-semibold text-white">{busy ? "Ekleniyor…" : "Programa ekle"}</Text>
            </Pressable>
          </View>
        ) : null}
      </View>
    </FormSheet>
  );
}
