"use client";

/**
 * Öğrenci "Havuza kalem ekle" (2026-10-22) — koçun ekleme akışının aynısı:
 *   1 Ders → 2 Nereden? [Kitabımdan: kitabın bölümleri · Müfredat konusundan: resmi konu] → 3 Ne kadar?
 * Kalem müfredata (konu) ya da kitaba (bölüm) BAĞLI eklenir; koç seansta onaylayınca yüzdeye ve
 * müfredat/kitap ilerlemesine işlenir. Konusuz kalem yalnız sayfa/etkinlik (video, özet, serbest ödev).
 * Kitap ve konu seçicileri koç panelinden (`pool-add-panel`) — iki ekran aynı görünür.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Check, Minus, NotebookPen, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { subjectColors } from "@/components/shared/subject-tag";
import { BookList, SourceOption, TopicPicker } from "@/components/teacher/pool/pool-add-panel";
import { cn } from "@/lib/utils";
import type { PoolBookOut, PoolBookSectionOut, PoolTopicOut } from "@/lib/api/pool";
import {
  getStudentPoolBooks, getStudentPoolTopics, studentPoolBooksKey, studentPoolTopicsKey, UNIT_LABELS,
  useAddStudentPoolItem, type PoolUnit, type StudentPoolItemBody, type StudentPoolResponse,
} from "@/lib/api/pool-student";

type Choice =
  | { kind: "book"; book: PoolBookOut; section: PoolBookSectionOut }
  | { kind: "topic"; topic: PoolTopicOut }
  | { kind: "none" };

const QUICK_QTY = [1, 2, 3, 4, 5];

export function StudentPoolAddDialog({ open, onOpenChange, data, studentId, studentGrade }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  data: StudentPoolResponse;
  studentId: number;
  studentGrade: number | null;
}) {
  // Pencere her açılışta temiz başlasın: içerik yalnız açıkken mount edilir.
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Havuza kalem ekle</DialogTitle>
          <DialogDescription>
            Ders öğretmeninin verdiği ödev ya da kendi ek çalışman. Kitabından ya da müfredat konusundan seç;
            koçun onaylayınca ilerlemene ve müfredat haritana işlenir.
          </DialogDescription>
        </DialogHeader>
        {open && <AddFlow data={data} studentId={studentId} studentGrade={studentGrade} onDone={() => onOpenChange(false)}
                          onCancel={() => onOpenChange(false)} />}
      </DialogContent>
    </Dialog>
  );
}

function AddFlow({ data, studentId, studentGrade, onDone, onCancel }: {
  data: StudentPoolResponse; studentId: number; studentGrade: number | null; onDone: () => void; onCancel: () => void;
}) {
  const add = useAddStudentPoolItem();
  const [subjectId, setSubjectId] = React.useState<number | null>(null);
  const [tab, setTab] = React.useState<"books" | "topics">("topics");
  const [choice, setChoice] = React.useState<Choice | null>(null);
  const [qty, setQty] = React.useState("");
  const [unit, setUnit] = React.useState<PoolUnit>("test");
  const [pageFrom, setPageFrom] = React.useState("");
  const [pageTo, setPageTo] = React.useState("");
  const [label, setLabel] = React.useState("");
  const [homework, setHomework] = React.useState(false);

  const subj = data.subjects.find((x) => x.id === subjectId) ?? null;
  const booksQ = useQuery({
    queryKey: studentPoolBooksKey(subjectId ?? 0),
    queryFn: () => getStudentPoolBooks(subjectId!),
    enabled: subjectId != null,
  });
  const books = booksQ.data?.books ?? [];

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

  // Birim seçenekleri: kitapta kitabın birimi sabit; konuda test/soru/sayfa; konusuzda sayfa/etkinlik.
  const units: PoolUnit[] = !choice ? []
    : choice.kind === "book" ? [choice.book.is_deneme ? "deneme" : "test"]
    : choice.kind === "topic" ? ["test", "soru", "sayfa"]
    : ["sayfa", "etkinlik"];
  const isActivity = unit === "etkinlik";
  const pf = Number(pageFrom);
  const pt = Number(pageTo);
  const hasRange = unit === "sayfa" && pageFrom !== "" && pageTo !== "";
  const rangeOk = !hasRange || (pf >= 1 && pt >= pf);
  const n = hasRange && rangeOk ? pt - pf + 1 : Number(qty);
  const qtyOk = isActivity || (Number.isInteger(n) && n > 0);
  const labelOk = choice?.kind !== "none" || label.trim().length > 0;
  const available = choice?.kind === "book" ? choice.section.available : null;
  const over = available != null && qtyOk && n > available;
  const ok = subj != null && choice != null && qtyOk && labelOk && rangeOk;

  function submit() {
    if (!ok || !subj || !choice) return;
    const body: StudentPoolItemBody = {
      subject_id: subj.id,
      unit,
      quantity: isActivity ? 1 : n,
      label: label.trim() || null,
      teacher_homework: homework,
      topic_id: choice.kind === "topic" ? choice.topic.topic_id : null,
      book_id: choice.kind === "book" ? choice.book.book_id : null,
      section_id: choice.kind === "book" ? choice.section.section_id : null,
      page_from: hasRange ? pf : null,
      page_to: hasRange ? pt : null,
    };
    add.mutate(body, { onSuccess: onDone });
  }

  const choiceTitle = !choice ? null
    : choice.kind === "book" ? `${choice.book.name} › ${choice.section.label}`
    : choice.kind === "topic" ? choice.topic.name
    : "Konusuz kalem";

  return (
    <>
      <ol className="space-y-4 text-sm">
        {/* 1 — Ders */}
        <Step n={1} title="Hangi ders?" done={!!subj} summary={subj?.name} onEdit={subj ? () => { setSubjectId(null); setChoice(null); } : undefined}>
          <SubjectChips data={data} onPick={pickSubject} />
        </Step>

        {/* 2 — Nereden? */}
        <Step n={2} title="Nereden çalışacaksın?" disabled={!subj} done={choice != null} summary={choiceTitle}
              onEdit={choice ? () => setChoice(null) : undefined}>
          {subj && (
            <div className="space-y-3">
              <div className="grid gap-2 sm:grid-cols-2" role="tablist" aria-label="Kalem nereden">
                <SourceOption active={tab === "books"} onClick={() => setTab("books")}
                              icon={<BookOpen className="size-4" aria-hidden />}
                              title={`Kitabımdan${subj.book_count ? ` (${subj.book_count})` : ""}`}
                              hint={subj.book_count ? "Kitabının bölümünü seç — kitap ilerlemen de işlenir" : "Bu derste sistemde kitabın yok"} />
                <SourceOption active={tab === "topics"} onClick={() => setTab("topics")}
                              icon={<NotebookPen className="size-4" aria-hidden />}
                              title="Müfredat konusundan"
                              hint="Kitabın sistemde yoksa: konuyu seç, sayıyı sen yaz" />
              </div>
              {tab === "books" ? (
                subj.book_count ? (
                  <BookList books={books} loading={booksQ.isLoading} anchorBook={null} anchorSection={null}
                            onPick={(book, section) => pickChoice({ kind: "book", book, section })} />
                ) : (
                  <div className="rounded-lg border border-dashed px-3 py-4 text-center text-xs text-muted-foreground">
                    Bu derste sistemde kayıtlı kitabın yok.
                    <button type="button" onClick={() => setTab("topics")}
                            className="ml-1 font-medium text-cyan-700 underline-offset-2 hover:underline dark:text-cyan-300">
                      Müfredat konusundan seç
                    </button>.
                  </div>
                )
              ) : (
                <TopicPicker
                  studentId={studentId} subjectId={subj.id} subjectName={subj.name}
                  studentGrade={studentGrade} examSubject={subj.group === "sinav"} audience="student"
                  topicsQuery={{ key: studentPoolTopicsKey(subj.id), fn: () => getStudentPoolTopics(subj.id) }}
                  onPick={(t) => pickChoice(t === "none" ? { kind: "none" } : { kind: "topic", topic: t })}
                />
              )}
            </div>
          )}
        </Step>

        {/* 3 — Ne kadar? */}
        <Step n={3} title="Ne kadar?" disabled={!choice} done={false}>
          {choice && (
            <div className="space-y-3">
              {units.length > 1 && (
                <div className="flex w-full flex-wrap rounded-lg bg-muted p-0.5 text-xs font-medium" role="radiogroup" aria-label="Birim">
                  {units.map((u) => (
                    <button key={u} type="button" role="radio" aria-checked={unit === u} onClick={() => setUnit(u)}
                            className={cn("flex-1 rounded-md px-2.5 py-1.5 transition",
                              unit === u ? "bg-cyan-700 text-white shadow-sm" : "text-muted-foreground hover:text-foreground")}>
                      {UNIT_LABELS[u]}
                    </button>
                  ))}
                </div>
              )}
              {choice.kind === "topic" && unit === "soru" && (
                <p className="text-xs text-muted-foreground">Soru: dağınık soruları say (örn. 20 soru); doğru/yanlış yine girersin.</p>
              )}
              {isActivity ? (
                <p className="text-xs text-muted-foreground">Etkinlik (video, özet, tekrar) tek birim sayılır; miktar gerekmez.</p>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <QtyStepper value={hasRange && rangeOk ? String(n) : qty} disabled={hasRange}
                                onChange={setQty} />
                    {!hasRange && QUICK_QTY.map((v) => (
                      <button key={v} type="button" onClick={() => setQty(String(v))} aria-pressed={n === v}
                              className={cn("min-w-9 rounded-md border px-2.5 py-1.5 text-xs font-semibold tabular-nums",
                                n === v ? "border-transparent bg-cyan-700 text-white" : "bg-background text-foreground hover:bg-muted")}>
                        {v}
                      </button>
                    ))}
                    <span className="text-xs text-muted-foreground">{UNIT_LABELS[unit]}</span>
                  </div>
                  {available != null && (
                    <p className={cn("text-xs", over ? "font-medium text-amber-700 dark:text-amber-300" : "text-muted-foreground")}>
                      Bu bölümde {available} {UNIT_LABELS[unit]} kaldı{over ? " — daha fazlasını yazdın; koçun seansta kontrol eder." : "."}
                    </p>
                  )}
                  {unit === "sayfa" && (
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="text-muted-foreground">Sayfa aralığı (isteğe bağlı):</span>
                      <Input value={pageFrom} onChange={(e) => setPageFrom(e.target.value.replace(/\D/g, ""))} inputMode="numeric"
                             placeholder="45" aria-label="Başlangıç sayfası" className="h-8 w-20" />
                      <span>–</span>
                      <Input value={pageTo} onChange={(e) => setPageTo(e.target.value.replace(/\D/g, ""))} inputMode="numeric"
                             placeholder="50" aria-label="Bitiş sayfası" className="h-8 w-20" />
                      {!rangeOk && <span className="font-medium text-rose-700 dark:text-rose-300">Başlangıç bitişten büyük olamaz.</span>}
                    </div>
                  )}
                </>
              )}
              <label className="block text-xs">
                <span className="mb-1 block font-medium text-foreground">
                  {choice.kind === "none" ? "Ne çalışacaksın? (zorunlu)" : choice.kind === "topic" ? "Kaynak notu (isteğe bağlı)" : "Not (isteğe bağlı)"}
                </span>
                <Input value={label} onChange={(e) => setLabel(e.target.value)} className="h-9"
                       placeholder={choice.kind === "none" ? "örn. Optik konu anlatım videosu" : choice.kind === "topic" ? "örn. Palme yaprak test" : ""}
                       aria-label="Not" />
              </label>
              <label className="flex items-center gap-2 text-xs text-foreground">
                <input type="checkbox" checked={homework} onChange={(e) => setHomework(e.target.checked)} />
                Ders / özel ders öğretmenimin verdiği ödev
              </label>
            </div>
          )}
        </Step>
      </ol>

      <div className="mt-4 rounded-lg border border-dashed bg-muted/40 p-3 text-xs" data-section="student:pool:add-preview">
        <div className="mb-1 font-semibold text-foreground">Havuzuna eklenecek</div>
        {ok && subj && choice ? (
          <div className="flex flex-wrap items-center gap-1.5 text-foreground">
            <span className="inline-flex shrink-0 items-center rounded-md px-1.5 py-px text-[10px] font-semibold text-white"
                  style={{ backgroundColor: subjectColors(subj.name).chipStrong }}>{subj.name}</span>
            <span className="font-medium">{choiceTitle}</span>
            {choice.kind !== "none" && (
              <span className="rounded bg-emerald-700 px-1.5 py-0.5 font-semibold text-white">
                {choice.kind === "book" ? "kitaba bağlı" : "müfredata bağlı"}
              </span>
            )}
            <span className="rounded bg-muted px-1.5 py-0.5 font-semibold">
              {isActivity ? "1 etkinlik" : hasRange ? `s. ${pf}–${pt} (${n} sayfa)` : `${n} ${UNIT_LABELS[unit]}`}
            </span>
            {homework && <span className="rounded bg-violet-700 px-1.5 py-0.5 font-semibold text-white">öğretmen ödevi</span>}
          </div>
        ) : (
          <p className="text-muted-foreground">Ders, nereden çalışacağın ve miktarı seç.</p>
        )}
        <p className="mt-1 text-muted-foreground">Koçun seansta görüp onaylayınca yüzdeye ve ilerlemene girer.</p>
      </div>

      <DialogFooter className="mt-4">
        <Button variant="ghost" onClick={onCancel}>Vazgeç</Button>
        <Button disabled={!ok || add.isPending} onClick={submit} data-testid="student-pool-add-submit"
                className="bg-cyan-700 text-white hover:bg-cyan-800 hover:text-white">
          Havuza ekle
        </Button>
      </DialogFooter>
    </>
  );
}

function Step({ n, title, done, disabled, summary, onEdit, children }: {
  n: number; title: string; done: boolean; disabled?: boolean; summary?: string | null; onEdit?: () => void;
  children?: React.ReactNode;
}) {
  const collapsed = done && !!summary;
  return (
    <li className={cn(disabled && "opacity-60")} data-step={n}>
      <div className="flex items-center gap-2">
        <span className={cn("grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-bold",
          done ? "bg-emerald-700 text-white" : disabled ? "bg-muted text-muted-foreground" : "bg-cyan-700 text-white")} aria-hidden>
          {done ? <Check className="size-3" /> : n}
        </span>
        <span className="font-semibold text-foreground">{title}</span>
        {collapsed && <span className="min-w-0 flex-1 break-words text-muted-foreground">{summary}</span>}
        {collapsed && onEdit && (
          <button type="button" onClick={onEdit} className="ml-auto shrink-0 text-xs font-medium text-cyan-700 hover:underline dark:text-cyan-300">
            Değiştir
          </button>
        )}
      </div>
      {!collapsed && !disabled && children && <div className="mt-2">{children}</div>}
    </li>
  );
}

function SubjectChips({ data, onPick }: { data: StudentPoolResponse; onPick: (id: number) => void }) {
  const groups: Array<[string, StudentPoolResponse["subjects"]]> = [];
  const okul = data.subjects.filter((x) => x.group !== "sinav");
  const tyt = data.subjects.filter((x) => x.group === "sinav" && !x.is_ayt);
  const ayt = data.subjects.filter((x) => x.group === "sinav" && x.is_ayt);
  if (okul.length) groups.push(["Okul dersleri", okul]);
  if (tyt.length) groups.push(["TYT", tyt]);
  if (ayt.length) groups.push(["AYT", ayt]);
  if (!groups.length) return <p className="text-xs text-muted-foreground">Ders bulunamadı.</p>;
  return (
    <div className="space-y-2">
      {groups.map(([title, list]) => (
        <div key={title}>
          {groups.length > 1 && <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</div>}
          <div className="flex flex-wrap gap-1.5">
            {list.map((x) => {
              const c = subjectColors(x.name);
              return (
                <button key={x.id} type="button" onClick={() => onPick(x.id)}
                        className="inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1 text-xs font-medium text-foreground transition hover:bg-muted">
                  <span className="size-2 rounded-full" style={{ backgroundColor: c.rail }} aria-hidden />
                  {x.name}
                  {(x.book_count ?? 0) > 0 && (
                    <span className="rounded bg-cyan-700 px-1.5 text-[10px] font-semibold text-white">{x.book_count} kitap</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function QtyStepper({ value, onChange, disabled }: { value: string; onChange: (v: string) => void; disabled?: boolean }) {
  const n = Number(value);
  const step = (d: number) => onChange(String(Math.max(1, (Number.isInteger(n) && n > 0 ? n : 0) + d)));
  return (
    <div className={cn("flex items-center rounded-lg border", disabled && "opacity-60")}>
      <button type="button" disabled={disabled} onClick={() => step(-1)} className="grid size-9 place-items-center text-foreground hover:bg-muted" aria-label="Bir azalt">
        <Minus className="size-4" aria-hidden />
      </button>
      <Input value={value} disabled={disabled} onChange={(e) => onChange(e.target.value.replace(/\D/g, ""))} inputMode="numeric" placeholder="0"
             className="h-9 w-16 rounded-none border-0 text-center text-base font-semibold" aria-label="Miktar" />
      <button type="button" disabled={disabled} onClick={() => step(1)} className="grid size-9 place-items-center text-foreground hover:bg-muted" aria-label="Bir arttır">
        <Plus className="size-4" aria-hidden />
      </button>
    </div>
  );
}
