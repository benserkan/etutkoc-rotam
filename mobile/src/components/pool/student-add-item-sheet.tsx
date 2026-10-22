import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import * as React from "react";
import { ActivityIndicator, Pressable, Switch, Text, TextInput, View } from "react-native";

import { FormSheet } from "@/components/ui/form-sheet";
import {
  getStudentPoolBooks, getStudentPoolTopics, poolKeys, UNIT_LABELS,
  type PoolBook, type PoolBookSection, type PoolTopic, type PoolUnit, type StudentPoolItemBody, type StudentPoolResponse,
} from "@/lib/pool";

/**
 * Havuza kalem ekle — öğrenci (2026-10-22, web `pool-add-dialog` ile aynı akış):
 *   1 Ders → 2 Nereden? [Kitabım: bölümler · Müfredat konusu] → 3 Ne kadar?
 * Kalem konuya/kitaba BAĞLI eklenir; koç onaylayınca ilerlemeye ve müfredat haritasına işlenir.
 * Konusuz kalem yalnız sayfa/etkinlik (video, özet, serbest ödev).
 */
type Choice =
  | { kind: "book"; book: PoolBook; section: PoolBookSection }
  | { kind: "topic"; topic: PoolTopic }
  | { kind: "none" };

const QUICK = [1, 2, 3, 4, 5];

function trLower(s: string) {
  return s.toLocaleLowerCase("tr-TR");
}

export function StudentAddItemSheet({ visible, data, busy, onClose, onSubmit }: {
  visible: boolean; data: StudentPoolResponse; busy: boolean; onClose: () => void;
  onSubmit: (b: StudentPoolItemBody) => void;
}) {
  return (
    <FormSheet visible={visible} title="Havuza kalem ekle" onClose={onClose}>
      {visible ? <Flow data={data} busy={busy} onSubmit={onSubmit} /> : null}
    </FormSheet>
  );
}

function Flow({ data, busy, onSubmit }: { data: StudentPoolResponse; busy: boolean; onSubmit: (b: StudentPoolItemBody) => void }) {
  const [subjectId, setSubjectId] = React.useState<number | null>(null);
  const [tab, setTab] = React.useState<"books" | "topics">("topics");
  const [choice, setChoice] = React.useState<Choice | null>(null);
  const [unit, setUnit] = React.useState<PoolUnit>("test");
  const [qty, setQty] = React.useState("");
  const [pageFrom, setPageFrom] = React.useState("");
  const [pageTo, setPageTo] = React.useState("");
  const [label, setLabel] = React.useState("");
  const [homework, setHomework] = React.useState(false);
  const subj = data.subjects.find((s) => s.id === subjectId) ?? null;

  function pickSubject(id: number) {
    const s = data.subjects.find((x) => x.id === id);
    setSubjectId(id);
    setChoice(null);
    setTab((s?.book_count ?? 0) > 0 ? "books" : "topics");
  }
  function pickChoice(c: Choice) {
    setChoice(c);
    setQty("");
    setPageFrom("");
    setPageTo("");
    setLabel("");
    setUnit(c.kind === "book" ? (c.book.is_deneme ? "deneme" : "test") : c.kind === "none" ? "sayfa" : "test");
  }

  const units: PoolUnit[] = !choice ? []
    : choice.kind === "book" ? [choice.book.is_deneme ? "deneme" : "test"]
    : choice.kind === "topic" ? ["test", "soru", "sayfa"] : ["sayfa", "etkinlik"];
  const isActivity = unit === "etkinlik";
  const pf = Number(pageFrom), pt = Number(pageTo);
  const hasRange = unit === "sayfa" && pageFrom !== "" && pageTo !== "";
  const rangeOk = !hasRange || (pf >= 1 && pt >= pf);
  const n = hasRange && rangeOk ? pt - pf + 1 : Number(qty);
  const qtyOk = isActivity || (Number.isInteger(n) && n > 0);
  const ok = subj != null && choice != null && qtyOk && rangeOk && (choice.kind !== "none" || label.trim().length > 0);
  const available = choice?.kind === "book" ? choice.section.available : null;

  const choiceTitle = !choice ? null : choice.kind === "book" ? `${choice.book.name} › ${choice.section.label}`
    : choice.kind === "topic" ? choice.topic.name : "Konusuz kalem";

  function submit() {
    if (!ok || !subj || !choice) return;
    onSubmit({
      subject_id: subj.id, unit, quantity: isActivity ? 1 : n, label: label.trim() || null, teacher_homework: homework,
      topic_id: choice.kind === "topic" ? choice.topic.topic_id : null,
      book_id: choice.kind === "book" ? choice.book.book_id : null,
      section_id: choice.kind === "book" ? choice.section.section_id : null,
      page_from: hasRange ? pf : null, page_to: hasRange ? pt : null,
    });
  }

  return (
    <View className="gap-4">
      <Text className="text-xs text-slate-500">
        Ders öğretmeninin verdiği ödev ya da kendi ek çalışman. Kitabından ya da müfredat konusundan seç; koçun onaylayınca ilerlemene işlenir.
      </Text>

      {/* 1 — Ders */}
      <Step n={1} title="Hangi ders?" done={!!subj} summary={subj?.name} onEdit={() => { setSubjectId(null); setChoice(null); }}>
        <View className="flex-row flex-wrap gap-1.5">
          {data.subjects.map((s) => (
            <Pressable key={s.id} onPress={() => pickSubject(s.id)} className="flex-row items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-1.5 active:bg-slate-100">
              <Text className="text-xs font-medium text-slate-700">{s.name}</Text>
              {(s.book_count ?? 0) > 0 ? <View className="rounded bg-cyan-700 px-1.5"><Text className="text-[10px] font-semibold text-white">{s.book_count} kitap</Text></View> : null}
            </Pressable>
          ))}
        </View>
      </Step>

      {/* 2 — Nereden? */}
      <Step n={2} title="Nereden çalışacaksın?" disabled={!subj} done={choice != null} summary={choiceTitle} onEdit={() => setChoice(null)}>
        {subj ? (
          <View className="gap-2">
            <View className="flex-row gap-2">
              <SourceTab active={tab === "books"} onPress={() => setTab("books")} icon="book-outline"
                         title={`Kitabımdan${subj.book_count ? ` (${subj.book_count})` : ""}`} />
              <SourceTab active={tab === "topics"} onPress={() => setTab("topics")} icon="list-outline" title="Müfredat konusu" />
            </View>
            {tab === "books"
              ? <BookPicker subjectId={subj.id} hasBooks={(subj.book_count ?? 0) > 0} onPick={(book, section) => pickChoice({ kind: "book", book, section })}
                            onGoTopics={() => setTab("topics")} />
              : <TopicPicker subjectId={subj.id} grade={data.grade_level ?? null} examSubject={subj.group === "sinav"}
                             onPick={(t) => pickChoice(t === "none" ? { kind: "none" } : { kind: "topic", topic: t })} />}
          </View>
        ) : null}
      </Step>

      {/* 3 — Ne kadar? */}
      <Step n={3} title="Ne kadar?" disabled={!choice} done={false}>
        {choice ? (
          <View className="gap-3">
            {units.length > 1 ? (
              <View className="flex-row rounded-xl bg-slate-200 p-0.5">
                {units.map((u) => (
                  <Pressable key={u} onPress={() => setUnit(u)} className={`flex-1 items-center rounded-lg py-1.5 ${unit === u ? "bg-cyan-700" : ""}`}>
                    <Text className={`text-xs font-semibold ${unit === u ? "text-white" : "text-slate-600"}`}>{UNIT_LABELS[u]}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
            {isActivity ? (
              <Text className="text-xs text-slate-500">Etkinlik (video, özet, tekrar) tek birim sayılır.</Text>
            ) : (
              <>
                <View className="flex-row flex-wrap items-center gap-2">
                  <TextInput value={hasRange && rangeOk ? String(n) : qty} editable={!hasRange} onChangeText={(v) => setQty(v.replace(/\D/g, ""))}
                             keyboardType="number-pad" placeholder="sayı" accessibilityLabel="Miktar"
                             className="w-20 rounded-xl border border-slate-300 bg-white px-3 py-2 text-center text-base font-semibold text-slate-800" />
                  {!hasRange ? QUICK.map((v) => (
                    <Pressable key={v} onPress={() => setQty(String(v))} className={`size-10 items-center justify-center rounded-full border ${n === v ? "border-cyan-700 bg-cyan-700" : "border-slate-300 bg-white"}`}>
                      <Text className={`text-sm font-semibold ${n === v ? "text-white" : "text-slate-800"}`}>{v}</Text>
                    </Pressable>
                  )) : null}
                  <Text className="text-xs text-slate-500">{UNIT_LABELS[unit]}</Text>
                </View>
                {available != null ? (
                  <Text className={`text-xs ${qtyOk && n > available ? "font-medium text-amber-700" : "text-slate-500"}`}>
                    Bu bölümde {available} {UNIT_LABELS[unit]} kaldı{qtyOk && n > available ? " — fazlasını yazdın; koçun kontrol eder." : "."}
                  </Text>
                ) : null}
                {unit === "sayfa" ? (
                  <View className="flex-row items-center gap-2">
                    <Text className="text-xs text-slate-500">Sayfa aralığı:</Text>
                    <TextInput value={pageFrom} onChangeText={(v) => setPageFrom(v.replace(/\D/g, ""))} keyboardType="number-pad" placeholder="45"
                               accessibilityLabel="Başlangıç sayfası" className="w-16 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-center text-sm text-slate-800" />
                    <Text className="text-slate-500">–</Text>
                    <TextInput value={pageTo} onChangeText={(v) => setPageTo(v.replace(/\D/g, ""))} keyboardType="number-pad" placeholder="50"
                               accessibilityLabel="Bitiş sayfası" className="w-16 rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-center text-sm text-slate-800" />
                  </View>
                ) : null}
                {!rangeOk ? <Text className="text-xs font-medium text-rose-700">Başlangıç sayfası bitişten büyük olamaz.</Text> : null}
              </>
            )}
            <View className="gap-1">
              <Text className="text-xs font-semibold text-slate-600">
                {choice.kind === "none" ? "Ne çalışacaksın? (zorunlu)" : choice.kind === "topic" ? "Kaynak notu (isteğe bağlı)" : "Not (isteğe bağlı)"}
              </Text>
              <TextInput value={label} onChangeText={setLabel}
                         placeholder={choice.kind === "none" ? "örn. Optik konu anlatım videosu" : choice.kind === "topic" ? "örn. Palme yaprak test" : ""}
                         className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800" />
            </View>
            <View className="flex-row items-center justify-between">
              <Text className="flex-1 text-xs text-slate-700">Ders / özel ders öğretmenimin verdiği ödev</Text>
              <Switch value={homework} onValueChange={setHomework} trackColor={{ true: "#0e7490" }} />
            </View>
          </View>
        ) : null}
      </Step>

      {ok && subj && choice ? (
        <View className="rounded-xl border border-dashed border-slate-300 bg-slate-100 p-3">
          <Text className="text-xs font-semibold text-slate-700">Havuzuna eklenecek</Text>
          <Text className="mt-1 text-xs text-slate-700">
            {subj.name} · {choiceTitle} · {isActivity ? "1 etkinlik" : hasRange ? `s. ${pf}–${pt} (${n} sayfa)` : `${n} ${UNIT_LABELS[unit]}`}
            {choice.kind !== "none" ? (choice.kind === "book" ? " · kitaba bağlı" : " · müfredata bağlı") : ""}
          </Text>
          <Text className="mt-1 text-[11px] text-slate-500">Koçun onaylayınca yüzdeye ve ilerlemene girer.</Text>
        </View>
      ) : null}

      <Pressable onPress={submit} disabled={!ok || busy} accessibilityRole="button"
                 className={`items-center rounded-xl px-4 py-3 ${ok ? "bg-cyan-700 active:bg-cyan-800" : "bg-slate-300"}`}>
        <Text className="font-semibold text-white">{busy ? "Ekleniyor…" : "Havuza ekle"}</Text>
      </Pressable>
    </View>
  );
}

function Step({ n, title, done, disabled, summary, onEdit, children }: {
  n: number; title: string; done: boolean; disabled?: boolean; summary?: string | null; onEdit?: () => void; children?: React.ReactNode;
}) {
  const collapsed = done && !!summary;
  return (
    <View className={disabled ? "opacity-50" : ""}>
      <View className="flex-row items-center gap-2">
        <View className={`size-5 items-center justify-center rounded-full ${done ? "bg-emerald-700" : disabled ? "bg-slate-300" : "bg-cyan-700"}`}>
          {done ? <Ionicons name="checkmark" size={12} color="#fff" /> : <Text className="text-[11px] font-bold text-white">{n}</Text>}
        </View>
        <Text className="text-sm font-semibold text-slate-800">{title}</Text>
        {collapsed ? <Text className="flex-1 text-xs text-slate-500" numberOfLines={2}>{summary}</Text> : null}
        {collapsed && onEdit ? (
          <Pressable onPress={onEdit} hitSlop={8}><Text className="text-xs font-semibold text-cyan-700">Değiştir</Text></Pressable>
        ) : null}
      </View>
      {!collapsed && !disabled && children ? <View className="mt-2">{children}</View> : null}
    </View>
  );
}

function SourceTab({ active, onPress, icon, title }: { active: boolean; onPress: () => void; icon: keyof typeof Ionicons.glyphMap; title: string }) {
  return (
    <Pressable onPress={onPress} className={`flex-1 flex-row items-center gap-2 rounded-xl border px-3 py-2.5 ${active ? "border-cyan-700 bg-cyan-700" : "border-slate-300 bg-white"}`}>
      <Ionicons name={icon} size={16} color={active ? "#fff" : "#0e7490"} />
      <Text className={`flex-1 text-xs font-semibold ${active ? "text-white" : "text-slate-800"}`}>{title}</Text>
    </Pressable>
  );
}

function BookPicker({ subjectId, hasBooks, onPick, onGoTopics }: {
  subjectId: number; hasBooks: boolean; onPick: (b: PoolBook, s: PoolBookSection) => void; onGoTopics: () => void;
}) {
  const q = useQuery({ queryKey: poolKeys.books(subjectId), queryFn: () => getStudentPoolBooks(subjectId), enabled: hasBooks });
  const [open, setOpen] = React.useState<number | null>(null);
  if (!hasBooks) {
    return (
      <Pressable onPress={onGoTopics} className="rounded-xl border border-dashed border-slate-300 px-3 py-4">
        <Text className="text-center text-xs text-slate-500">Bu derste sistemde kitabın yok. <Text className="font-semibold text-cyan-700">Müfredat konusundan seç</Text></Text>
      </Pressable>
    );
  }
  if (q.isLoading) return <ActivityIndicator color="#0e7490" />;
  const books = q.data?.books ?? [];
  const openId = open ?? books[0]?.book_id ?? null;
  return (
    <View className="gap-2">
      {books.map((b) => {
        const isOpen = openId === b.book_id;
        return (
          <View key={b.book_id} className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <Pressable onPress={() => setOpen(isOpen ? -1 : b.book_id)} className="flex-row items-center gap-2 px-3 py-2.5 active:bg-slate-50">
              <Ionicons name="book-outline" size={16} color="#0e7490" />
              <View className="flex-1">
                <Text className="text-sm font-medium text-slate-800">{b.name}</Text>
                <Text className="text-[11px] text-slate-500">{b.type_label} · {b.completed}/{b.total_tests} {b.is_deneme ? "deneme" : "test"} çözüldü</Text>
              </View>
              <Ionicons name={isOpen ? "chevron-up" : "chevron-down"} size={16} color="#64748b" />
            </Pressable>
            {isOpen ? b.sections.map((s) => {
              const full = s.available <= 0;
              return (
                <Pressable key={s.section_id} onPress={() => onPick(b, s)} className="flex-row items-center gap-2 border-t border-slate-100 px-3 py-2 active:bg-cyan-50">
                  <View className="flex-1">
                    <Text className={`text-sm ${full ? "text-slate-400" : "text-slate-800"}`}>{s.label}</Text>
                    {s.topic_name && s.topic_name !== s.label ? <Text className="text-[11px] text-slate-500">müfredat: {s.topic_name}</Text> : null}
                  </View>
                  {s.is_last ? <View className="rounded bg-cyan-700 px-1.5 py-0.5"><Text className="text-[10px] font-semibold text-white">SON</Text></View> : null}
                  <Text className="text-xs text-slate-600">{full ? (s.remaining > 0 ? "hepsi havuzda" : "bitti") : `${s.available} kaldı`}</Text>
                </Pressable>
              );
            }) : null}
          </View>
        );
      })}
    </View>
  );
}

function TopicPicker({ subjectId, grade, examSubject, onPick }: {
  subjectId: number; grade: number | null; examSubject: boolean; onPick: (t: PoolTopic | "none") => void;
}) {
  const q = useQuery({ queryKey: poolKeys.topics(subjectId), queryFn: () => getStudentPoolTopics(subjectId) });
  const [term, setTerm] = React.useState("");
  const topics = q.data?.topics ?? [];
  const grades = [...new Set(topics.map((t) => t.grade_level))].sort((a, b) => (b ?? -1) - (a ?? -1));
  const own = !examSubject && grade != null && grades.includes(grade) ? grade : null;
  const [gradeSel, setGradeSel] = React.useState<number | "all" | null>(null);
  const active = gradeSel ?? (grades.length > 1 && own != null ? own : "all");
  const t = trLower(term.trim());
  const shown = topics.filter((x) => (t ? trLower(x.name).includes(t) || trLower(x.unit_name ?? "").includes(t) : active === "all" || x.grade_level === active));
  return (
    <View className="gap-2">
      <TextInput value={term} onChangeText={setTerm} placeholder="Konu ara…" accessibilityLabel="Konu ara"
                 className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-800" />
      {grades.length > 1 && !t ? (
        <View className="flex-row flex-wrap gap-1.5">
          {[...grades, "all" as const].map((g) => {
            const on = active === (g ?? "all");
            return (
              <Pressable key={String(g)} onPress={() => setGradeSel(g ?? "all")} className={`rounded-full border px-2.5 py-1 ${on ? "border-slate-700 bg-slate-700" : "border-slate-300 bg-white"}`}>
                <Text className={`text-[11px] font-medium ${on ? "text-white" : "text-slate-700"}`}>
                  {g === "all" ? "Tümü" : g == null ? "Sınıfsız" : `${g}. sınıf${g === own ? " · senin" : ""}`}
                </Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
      {q.isLoading ? <ActivityIndicator color="#0e7490" /> : (
        <View className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          {shown.length === 0 ? <Text className="p-3 text-xs text-slate-500">{topics.length ? "Aramayla eşleşen konu yok." : "Bu derste konu listesi yok."}</Text> : null}
          {shown.slice(0, 80).map((x, i) => (
            <Pressable key={x.topic_id} onPress={() => onPick(x)} className={`flex-row items-center gap-2 px-3 py-2 active:bg-cyan-50 ${i ? "border-t border-slate-100" : ""}`}>
              <View className="flex-1">
                <Text className="text-sm text-slate-800">{x.name}</Text>
                {x.unit_name ? <Text className="text-[11px] text-slate-500">{x.unit_name}</Text> : null}
              </View>
              {x.is_last ? <View className="rounded bg-cyan-700 px-1.5 py-0.5"><Text className="text-[10px] font-semibold text-white">SON</Text></View> : null}
              {x.status === "planlandi" ? <View className="rounded bg-sky-700 px-1.5 py-0.5"><Text className="text-[10px] font-semibold text-white">havuzda</Text></View> : null}
              {x.sources.length ? <Text className="text-[10px] text-slate-500">kitapta var</Text> : null}
            </Pressable>
          ))}
        </View>
      )}
      <Pressable onPress={() => onPick("none")} className="flex-row items-center gap-2 self-start rounded-lg border border-slate-300 bg-white px-3 py-1.5 active:bg-slate-100">
        <Ionicons name="create-outline" size={14} color="#334155" />
        <Text className="text-xs text-slate-700">Konusuz kalem (video, sayfa, serbest ödev)</Text>
      </Pressable>
    </View>
  );
}
