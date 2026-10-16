import * as React from "react";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { ActivityIndicator, Pressable, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import {
  getTeacherSubjectTopics,
  getTeacherTaskPicker,
  type PickerSource,
  type PickerTopic,
  type StudentBookRow,
  type StudentBookSectionRow,
  type SubjectBrief,
  type TaskCreateBody,
} from "@/lib/teacher";
import { cn } from "@/lib/utils";

const TR_MAP: Record<string, string> = {
  ı: "i", İ: "i", ş: "s", Ş: "s", ğ: "g", Ğ: "g", ü: "u", Ü: "u", ö: "o", Ö: "o", ç: "c", Ç: "c", â: "a", î: "i", û: "u",
};
function normTr(s: string): string {
  return s
    .replace(/[ıİşŞğĞüÜöÖçÇâîû]/g, (c) => TR_MAP[c] ?? c)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}
/** Web topic-picker-panel ile aynı kural: her sözcük ad/tema/ders sözcüklerinden birinin başında. */
function topicMatches(
  t: { name: string; parent_name: string | null; subject_name: string | null },
  query: string,
): boolean {
  const q = normTr(query);
  if (!q) return true;
  const hay = normTr([t.name, t.parent_name ?? "", t.subject_name ?? ""].join(" ")).split(" ");
  return q.split(" ").every((w) => hay.some((h) => h.startsWith(w)));
}

/**
 * Mobil koç görev ekleme (2026-10-16 — web görev kutusuyla aynı mantık).
 *
 *  · "Ne çalışsın?" konu araması (sözcük bazlı, yazım hatasına dayanıklı — task-picker ucu)
 *  · konu seçilince: kitabından ya da KAYNAKSIZ (müfredat konusuna bağlı) test
 *  · kitabı olmayan öğrenciye de test verilir: ders → konu listesi (kaynaksız)
 *  · adet kutusu TEST sayısıdır; 15'ten büyükse "soru sayısı mı yazdın" uyarısı
 */
type Step = "type" | "source" | "book" | "section" | "subject" | "subjectTopic" | "count" | "activity";

const ACTIVITY_TYPES = [
  { v: "video", label: "Video", placeholder: "Konu videosu izle" },
  { v: "ozet", label: "Özet", placeholder: "Konu özeti çıkar" },
  { v: "tekrar", label: "Tekrar", placeholder: "Konu tekrarı yap" },
  { v: "other", label: "Diğer", placeholder: "örn. Soru çözüm videosu" },
];

/** Adet adımına giden seçim — kitaptan ya da kaynaksız */
interface Pick {
  title: string;
  subtitle: string;
  book_id: number | null;
  section_id: number | null;
  topic_id: number | null;
  /** Kitapta kalan test (kaynaksızda null) */
  remaining: number | null;
  /** Önceki adım — "geri" bununla döner */
  back: Step;
}

function remaining(s: StudentBookSectionRow): number {
  return Math.max(0, s.test_count - s.completed_count - s.reserved_count);
}
function bookRemaining(b: StudentBookRow): number {
  return b.sections.reduce((acc, s) => acc + remaining(s), 0);
}

function topicMeta(t: PickerTopic): string {
  const parts = [t.subject_name];
  if (t.grade_level) parts.push(`${t.grade_level}. sınıf`);
  if (t.theme_name) parts.push(t.theme_name);
  return parts.join(" · ");
}

function useDebounced(value: string, ms: number): string {
  const [v, setV] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

export function AddTaskSheet({
  studentId,
  visible,
  date,
  books,
  booksLoading,
  subjects,
  busy,
  onClose,
  onSubmit,
}: {
  studentId: number;
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
  const [query, setQuery] = React.useState("");
  const [topic, setTopic] = React.useState<PickerTopic | null>(null);
  const [book, setBook] = React.useState<StudentBookRow | null>(null);
  const [subject, setSubject] = React.useState<SubjectBrief | null>(null);
  const [pick, setPick] = React.useState<Pick | null>(null);
  const [count, setCount] = React.useState("");
  const [actType, setActType] = React.useState("video");
  const [actSubject, setActSubject] = React.useState<SubjectBrief | null>(null);
  const [actTitle, setActTitle] = React.useState("");
  // Video bağlantısı — öğrenci "Videoyu izle" ile doğrudan açar (video tipinde zorunlu)
  const [actLink, setActLink] = React.useState("");

  // Sheet her açıldığında baştan başla.
  const visRef = React.useRef(visible);
  if (visRef.current !== visible) {
    visRef.current = visible;
    if (visible) {
      setStep("type"); setQuery(""); setTopic(null); setBook(null); setSubject(null);
      setPick(null); setCount("");
      setActType("video"); setActSubject(null); setActTitle(""); setActLink("");
    }
  }

  const [topicQuery, setTopicQuery] = React.useState("");
  const debounced = useDebounced(query, 300);
  const pickerQ = useQuery({
    queryKey: ["teacher", "student", studentId, "task-picker", debounced],
    queryFn: () => getTeacherTaskPicker(studentId, debounced),
    enabled: visible && step === "type" && studentId > 0,
    staleTime: 30_000,
  });
  const subjectTopicsQ = useQuery({
    queryKey: ["teacher", "student", studentId, "subject-topics", subject?.id ?? 0],
    queryFn: () => getTeacherSubjectTopics(studentId, subject!.id),
    enabled: visible && step === "subjectTopic" && subject != null,
    staleTime: 5 * 60_000,
  });

  const shownTopics = (subjectTopicsQ.data?.topics ?? []).filter((t) => topicMatches(t, topicQuery));

  if (!date) return null;

  // Yalnız kalan kapasitesi olan kitaplar + bölümler (biten kaynaklar gizli).
  const availableBooks = books.filter((b) => bookRemaining(b) > 0);
  const availableSections = book ? book.sections.filter((s) => remaining(s) > 0) : [];
  const groups = pickerQ.data?.groups ?? [];
  const actPlaceholder = ACTIVITY_TYPES.find((a) => a.v === actType)?.placeholder ?? "Başlık";
  const n = Number(count);
  const looksLikeQuestions = n > 15;

  function goCount(p: Pick, defaultCount: number) {
    setPick(p);
    setCount(String(Math.max(1, defaultCount)));
    setStep("count");
  }

  function chooseTopic(t: PickerTopic) {
    setTopic(t);
    setStep("source");
  }

  function chooseSource(t: PickerTopic, src: PickerSource | null) {
    goCount(
      src
        ? {
            title: t.topic_name,
            subtitle: `${src.book_name} — ${src.section_label}`,
            book_id: src.book_id,
            section_id: src.section_id,
            topic_id: null,
            remaining: src.remaining,
            back: "source",
          }
        : {
            title: t.topic_name,
            subtitle: `${t.subject_name} · kaynaksız (müfredata bağlı)`,
            book_id: null,
            section_id: null,
            topic_id: t.topic_id,
            remaining: null,
            back: "source",
          },
      t.quantity || 3,
    );
  }

  function submitTest() {
    if (!pick || !(n > 0)) return;
    const over = pick.remaining != null && n > pick.remaining;
    onSubmit({
      date: date!,
      type: "test",
      title: "Görev",
      items: [
        pick.book_id != null
          ? {
              book_id: pick.book_id,
              section_id: pick.section_id,
              planned_count: n,
              // Kapasite yetmiyorsa engel değil — koç uyarıyı görüyor
              allow_over_capacity: over,
            }
          : {
              // Kaynaksız görev: kitap yok, müfredat konusu var
              book_id: null,
              section_id: null,
              topic_id: pick.topic_id,
              label: pick.title,
              planned_count: n,
            },
      ],
    });
  }

  const isVideoAct = actType === "video";
  const activityReady = !!actTitle.trim() && (!isVideoAct || !!actLink.trim());

  function submitActivity() {
    const detail = actTitle.trim();
    if (!activityReady) return;
    // Ders seçiliyse "{Ders} · {detay}" (editör/ızgara ders grubuna girer).
    const title = actSubject ? `${actSubject.name} · ${detail}` : detail;
    const link = actLink.trim();
    onSubmit({ date: date!, type: actType, title, items: [], link_url: link || undefined });
  }

  const backTarget: Step | null =
    step === "type"
      ? null
      : step === "count"
        ? pick?.back ?? "type"
        : step === "section"
          ? "book"
          : step === "subjectTopic"
            ? "subject"
            : "type";

  return (
    <FormSheet visible={visible} title="Görev ekle" onClose={onClose}>
      <View className="gap-4 pb-2">
        {backTarget ? (
          <Pressable onPress={() => setStep(backTarget)} className="flex-row items-center gap-1">
            <Ionicons name="chevron-back" size={16} color="#0e7490" />
            <Text className="text-sm font-medium text-brand-700">Geri</Text>
          </Pressable>
        ) : null}

        {step === "type" ? (
          <View className="gap-3">
            <Text className="text-xs font-medium text-slate-600">Ne çalışsın?</Text>
            <View className="flex-row items-center gap-2 rounded-xl border border-slate-300 bg-white px-3">
              <Ionicons name="search" size={16} color="#94a3b8" />
              <TextInput
                value={query}
                onChangeText={setQuery}
                placeholder="konu adı yaz · örn. milli destan"
                placeholderTextColor="#94a3b8"
                autoCorrect={false}
                accessibilityLabel="Görev ara"
                className="flex-1 py-2.5 text-base text-slate-900"
              />
              {query ? (
                <Pressable onPress={() => setQuery("")} hitSlop={8}>
                  <Ionicons name="close-circle" size={18} color="#94a3b8" />
                </Pressable>
              ) : null}
            </View>

            {pickerQ.isLoading ? (
              <ActivityIndicator color="#0e7490" />
            ) : groups.length === 0 ? (
              <Text className="text-sm text-slate-400">
                {query.trim()
                  ? "Eşleşen konu yok. Konunun bir kelimesini ya da baş harflerini yaz (örn. trigo, destan)."
                  : "Konu adı yazarak ara."}
              </Text>
            ) : (
              <View className="gap-3">
                {groups.map((g) => (
                  <View key={g.key} className="gap-1.5">
                    <Text className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{g.label}</Text>
                    {g.items.slice(0, 8).map((t) => (
                      <Pressable
                        key={`${g.key}-${t.topic_id}`}
                        onPress={() => chooseTopic(t)}
                        className="rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
                      >
                        <Text className="text-[14px] font-semibold text-slate-900">{t.topic_name}</Text>
                        <Text className="text-xs text-slate-500">{topicMeta(t)}</Text>
                        <Text className="mt-0.5 text-[11px] text-slate-400">
                          {t.sources.some((s) => !s.full)
                            ? `Kitabı var · ${t.sources.length} kaynak`
                            : "Kitabı yok — kaynaksız verilir"}
                          {t.match === "kısmi" ? " · kısmi eşleşme" : ""}
                        </Text>
                      </Pressable>
                    ))}
                  </View>
                ))}
              </View>
            )}

            <View className="mt-1 gap-2 border-t border-slate-100 pt-3">
              <Text className="text-xs text-slate-500">Ya da listeden seç:</Text>
              <EntryRow
                icon="book-outline"
                title="Kitaptan test"
                sub="Kitap + bölüm + test sayısı"
                onPress={() => setStep("book")}
              />
              <EntryRow
                icon="list-outline"
                title="Dersin konusundan test (kaynaksız)"
                sub="Kitap gerekmez — müfredat konusuna bağlanır"
                onPress={() => setStep("subject")}
              />
              <EntryRow
                icon="play-circle-outline"
                title="Etkinlik"
                sub="Video / özet / tekrar / diğer"
                onPress={() => setStep("activity")}
              />
            </View>
          </View>
        ) : null}

        {step === "source" && topic ? (
          <View className="gap-2">
            <View className="rounded-xl bg-slate-50 p-3">
              <Text className="text-[14px] font-semibold text-slate-900">{topic.topic_name}</Text>
              <Text className="text-xs text-slate-500">{topicMeta(topic)}</Text>
            </View>
            <Text className="text-xs font-medium text-slate-600">Nereden verilsin?</Text>
            {topic.sources.map((s) => (
              <Pressable
                key={s.section_id}
                onPress={() => chooseSource(topic, s)}
                className="flex-row items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
              >
                <View className="flex-1">
                  <Text className="text-[14px] font-medium text-slate-900">{s.book_name}</Text>
                  <Text className="text-xs text-slate-400">{s.section_label}</Text>
                </View>
                <Text className={cn("text-xs font-semibold", s.full ? "text-amber-700" : "text-emerald-600")}>
                  {s.full ? "kapasite doldu" : `${s.remaining} kalan`}
                </Text>
              </Pressable>
            ))}
            <Pressable
              onPress={() => chooseSource(topic, null)}
              className="rounded-xl border border-brand-600 bg-brand-50 p-3 active:bg-brand-100"
            >
              <Text className="text-[14px] font-semibold text-brand-700">Kaynaksız (müfredat konusuna bağlı)</Text>
              <Text className="text-xs text-slate-600">
                Kitap gerekmez; müfredat ilerlemesine ve kurum tablolarına yansır.
              </Text>
            </Pressable>
          </View>
        ) : null}

        {step === "book" ? (
          booksLoading ? (
            <Text className="text-sm text-slate-400">Kitaplar yükleniyor…</Text>
          ) : availableBooks.length === 0 ? (
            <View className="gap-3">
              <Text className="text-sm text-slate-500">
                {books.length === 0
                  ? "Bu öğrenciye atanmış kitap yok."
                  : "Atanabilir (kalan kapasitesi olan) kitap yok — tüm testler bitmiş veya dağıtılmış."}{" "}
                Kitap olmadan da test verebilirsin: konu seç, görev müfredata bağlanır.
              </Text>
              <EntryRow
                icon="list-outline"
                title="Dersin konusundan test (kaynaksız)"
                sub="Ders → konu → test sayısı"
                onPress={() => setStep("subject")}
              />
            </View>
          ) : (
            <View className="gap-2">
              <Text className="text-xs font-medium text-slate-600">Kitap seç</Text>
              {availableBooks.map((b) => (
                <Pressable
                  key={b.student_book_id}
                  onPress={() => { setBook(b); setStep("section"); }}
                  className="rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
                >
                  <Text className="text-[14px] font-semibold text-slate-900">{b.book_name}</Text>
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
                    onPress={() =>
                      goCount(
                        {
                          title: s.label,
                          subtitle: book.book_name,
                          book_id: book.book_id,
                          section_id: s.section_id,
                          topic_id: null,
                          remaining: rem,
                          back: "section",
                        },
                        Math.min(rem, 3),
                      )
                    }
                    className="flex-row items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
                  >
                    <View className="flex-1">
                      <Text className="text-[14px] font-medium text-slate-900">{s.label}</Text>
                      {s.topic_name ? <Text className="text-xs text-slate-400">{s.topic_name}</Text> : null}
                    </View>
                    <Text className="text-xs font-semibold text-emerald-600">{rem} kalan</Text>
                  </Pressable>
                );
              })
            )}
          </View>
        ) : null}

        {step === "subject" ? (
          <View className="gap-2">
            <Text className="text-xs font-medium text-slate-600">Ders seç</Text>
            <View className="flex-row flex-wrap gap-2">
              {subjects.map((s) => (
                <Pressable
                  key={s.id}
                  onPress={() => { setSubject(s); setTopicQuery(""); setStep("subjectTopic"); }}
                  className="rounded-full border border-slate-300 bg-white px-3 py-1.5 active:bg-slate-50"
                >
                  <Text className="text-sm font-medium text-slate-700">{s.name}</Text>
                </Pressable>
              ))}
            </View>
          </View>
        ) : null}

        {step === "subjectTopic" && subject ? (
          <View className="gap-2">
            <Text className="text-xs font-medium text-slate-600">{subject.name} — konu seç</Text>
            <View className="flex-row items-center gap-2 rounded-xl border border-slate-300 bg-white px-3">
              <Ionicons name="search" size={16} color="#64748b" />
              <TextInput
                value={topicQuery}
                onChangeText={setTopicQuery}
                placeholder="Konu ya da ünite ara"
                placeholderTextColor="#94a3b8"
                aria-label="Konu ara"
                className="flex-1 py-2.5 text-[15px] text-slate-900"
              />
              <Text className="text-xs text-slate-400">{shownTopics.length}</Text>
            </View>
            {subjectTopicsQ.isLoading ? (
              <ActivityIndicator color="#0e7490" />
            ) : shownTopics.length === 0 ? (
              <Text className="text-sm text-slate-400">
                {topicQuery ? "Eşleşen konu yok — daha kısa yaz." : "Bu derste müfredat konusu bulunamadı."}
              </Text>
            ) : (
              shownTopics.map((t) => (
                <Pressable
                  key={t.topic_id}
                  onPress={() =>
                    goCount(
                      {
                        title: t.name,
                        subtitle: `${t.subject_name ?? subject.name} · kaynaksız (müfredata bağlı)`,
                        book_id: null,
                        section_id: null,
                        topic_id: t.topic_id,
                        remaining: null,
                        back: "subjectTopic",
                      },
                      3,
                    )
                  }
                  className="rounded-xl border border-slate-200 bg-white p-3 active:bg-slate-50"
                >
                  <Text className="text-[14px] font-medium text-slate-900">{t.name}</Text>
                  <Text className="text-xs text-slate-400">
                    {[t.grade_level ? `${t.grade_level}. sınıf` : null, t.parent_name, t.subject_name]
                      .filter(Boolean)
                      .join(" · ")}
                  </Text>
                </Pressable>
              ))
            )}
          </View>
        ) : null}

        {step === "count" && pick ? (
          <View className="gap-2">
            <View className="rounded-xl bg-slate-50 p-3">
              <Text className="text-[14px] font-semibold text-slate-900">{pick.title}</Text>
              <Text className="text-xs text-slate-500">
                {pick.subtitle}
                {pick.remaining != null ? ` · ${pick.remaining} test kaldı` : ""}
              </Text>
            </View>
            {pick.book_id == null ? (
              <Text className="text-[11.5px] text-slate-500">
                Görev bu müfredat konusuna bağlı test olarak eklenir; müfredat ilerlemesine ve kurum
                tablolarına yansır.
              </Text>
            ) : null}
            <Text className="text-xs font-medium text-slate-600">Kaç test?</Text>
            <View className="flex-row items-center gap-2">
              <TextInput
                value={count}
                onChangeText={(v) => setCount(v.replace(/[^0-9]/g, "").slice(0, 3))}
                keyboardType="number-pad"
                placeholder="örn. 3"
                placeholderTextColor="#94a3b8"
                accessibilityLabel="Test sayısı"
                className="w-24 rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-lg font-semibold text-slate-900"
              />
              <Text className="text-base text-slate-600">test</Text>
            </View>
            {looksLikeQuestions ? (
              <View className="flex-row gap-2 rounded-xl border border-amber-300 bg-amber-50 p-3">
                <Ionicons name="warning-outline" size={16} color="#b45309" />
                <Text className="flex-1 text-[12.5px] text-amber-900">
                  Bu kutu <Text className="font-bold">test sayısıdır</Text> — {n} test yazdın. Soru
                  sayısı yazdıysan test sayısına çevir (bir test genelde 10–15 soru).
                </Text>
              </View>
            ) : null}
            {pick.remaining != null && n > pick.remaining ? (
              <Text className="text-[12px] text-amber-800">
                Kayıtlı kapasite {pick.remaining} test — {n - pick.remaining} test aşılacak. Görev yine de
                oluşturulur.
              </Text>
            ) : null}
            <Pressable
              onPress={submitTest}
              disabled={busy || !(n > 0)}
              className={cn("items-center rounded-xl py-3.5", busy || !(n > 0) ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}
            >
              <Text className="text-base font-semibold text-white">
                {busy ? "Ekleniyor…" : n > 0 ? `Ekle · ${n} test` : "Ekle"}
              </Text>
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

            {/* Ders seçimi (opsiyonel; başlık ders adıyla gruplanır) */}
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
              {actType === "other" && /\d+\s*(adet\s*)?test/i.test(actTitle) ? (
                <Text className="text-[11.5px] text-amber-800">
                  Test görevi mi veriyorsun? &quot;Geri&quot; → &quot;Dersin konusundan test&quot; ile ver; böylece
                  müfredata ve kurum tablolarına yansır.
                </Text>
              ) : null}
            </View>

            {isVideoAct ? (
              <View className="gap-1">
                <Text className="text-xs font-medium text-slate-600">Video bağlantısı</Text>
                <TextInput
                  value={actLink}
                  onChangeText={setActLink}
                  placeholder="https://youtube.com/watch?v=…"
                  placeholderTextColor="#94a3b8"
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-base text-slate-900"
                />
                <Text className="text-[11px] text-slate-400">Öğrenci programda &quot;Videoyu izle&quot; ile doğrudan açar.</Text>
              </View>
            ) : null}

            <Pressable
              onPress={submitActivity}
              disabled={busy || !activityReady}
              className={cn("items-center rounded-xl py-3.5", busy || !activityReady ? "bg-brand-700/40" : "bg-brand-700 active:bg-brand-800")}
            >
              <Text className="text-base font-semibold text-white">{busy ? "Ekleniyor…" : "Programa ekle"}</Text>
            </Pressable>
          </View>
        ) : null}
      </View>
    </FormSheet>
  );
}

function EntryRow({
  icon,
  title,
  sub,
  onPress,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  title: string;
  sub: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      className="flex-row items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-3.5 active:bg-slate-50"
    >
      <View className="flex-1 flex-row items-center gap-3">
        <Ionicons name={icon} size={20} color="#0e7490" />
        <View className="flex-1">
          <Text className="text-[15px] font-semibold text-slate-900">{title}</Text>
          <Text className="text-xs text-slate-400">{sub}</Text>
        </View>
      </View>
      <Ionicons name="chevron-forward" size={18} color="#cbd5e1" />
    </Pressable>
  );
}
