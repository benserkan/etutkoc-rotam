"use client";

/**
 * Görev ekleme kutusu — 3 tık (P4, 2026-09-07).
 *
 * KOÇ GERİ BİLDİRİMİ: eski form ders → kitap → ünite → adet → Ekle zinciriyle
 * ~9 etkileşim istiyordu; kapasitesi dolan ünite de yolu tıkıyordu.
 *
 * TASARIM: koç "türev çalışsın" diye düşünür, "345'in 12. ünitesi" diye değil.
 * Bu yüzden arama birimi KONU, kaynaklar konunun altında. Her konunun altında
 * sabit "Kaynak belirtmeden ver" seçeneği var (P2) ve kapasitesi dolu bölüm
 * gizlenmez, işaretlenir (P1). Adet koçun kendi alışkanlığından gelir (P3).
 *
 * Tık sayımı: kutu (1) → satır (2) → Ekle (3).
 */

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  ChevronRight,
  Loader2,
  Search,
  Sparkles,
  TriangleAlert,
  X,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getTaskPicker, teacherKeys } from "@/lib/api/teacher";
import { useCreateTask } from "@/lib/hooks/use-teacher-mutations";
import type {
  ItemUnit,
  PickerSourceItem,
  PickerTopicItem,
  TaskPeriod,
  TaskPickerResponse,
} from "@/lib/types/teacher";
import { cn } from "@/lib/utils";
import {
  PageSuggestionLine,
  UNIT_WORD,
  UnitSegment,
  usePageSuggestion,
  type TaskSeed,
} from "./task-seed";

/** Seçilen satır: konu + (varsa) kaynak. Kaynak yoksa kaynaksız görev. */
type Picked = {
  topic: PickerTopicItem;
  source: PickerSourceItem | null;
};

const BADGE_TONE: Record<string, string> = {
  sıradaki:
    "bg-cyan-50 text-cyan-800 border-cyan-200",
  zayıf:
    "bg-amber-50 text-amber-900 border-amber-200",
  "son çalışılan":
    "bg-slate-100 text-slate-700 border-slate-200",
};

function Badge({ label }: { label: string }) {
  return (
    <span
      className={cn(
        "rounded border px-1.5 py-px text-[10px] font-medium whitespace-nowrap",
        BADGE_TONE[label] ??
          "bg-slate-100 text-slate-700 border-slate-200",
      )}
    >
      {label}
    </span>
  );
}

export function TaskQuickAdd({
  studentId,
  dayDate,
  period,
  onAfterAdd,
  initialQuery = "",
  autoOpen = false,
  onSourcePick,
  initialSeed = null,
  onSeedChange,
  onPeriodChange,
  secondary,
}: {
  studentId: number;
  dayDate: string;
  period: TaskPeriod | null;
  onAfterAdd: () => void;
  /** Kutu açılırken arama önceden dolu gelir (iskelet hayaleti: ders adı). */
  initialQuery?: string;
  autoOpen?: boolean;
  /**
   * Verilirse kaynaklı seçim görev YAZMAZ, çağırana devredilir (iskelet
   * hayaletinin "başka konu" yolu — kabul oranı ölçümüne "other" olarak
   * girsin diye ghosts/accept ucundan yazılır). Kaynaksız seçim normal akar.
   */
  onSourcePick?: (p: { section_id: number; count: number }) => void;
  /** Ayrıntılı formdan / tip formundan dönüşte seçim kaldığı yerden gelir (2026-10-22). */
  initialSeed?: TaskSeed | null;
  /** Seçim her değiştiğinde üst bileşene bildirilir — diğer formlara taşınsın diye. */
  onSeedChange?: (seed: TaskSeed | null) => void;
  /** Kart içindeki periyot seçimi üst bileşene de yazılsın (ayrıntılı forma taşınır). */
  onPeriodChange?: (p: TaskPeriod | null) => void;
  /** Kart altbilgisinin sol tarafı (ör. "Bu konuyla: Video · Özet …"). */
  secondary?: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(autoOpen);
  const [q, setQ] = React.useState(initialQuery);
  const [debounced, setDebounced] = React.useState(initialQuery);
  const [picked, setPicked] = React.useState<Picked | null>(
    initialSeed ? { topic: initialSeed.topic, source: initialSeed.source } : null,
  );
  const [count, setCount] = React.useState(initialSeed?.count ?? "");
  // Kaynaksız konulu görevde birim + kitap notu + sayfa aralığı (2026-10-22)
  const [unit, setUnit] = React.useState<ItemUnit>(initialSeed?.unit ?? "test");
  const [note, setNote] = React.useState(initialSeed?.note ?? "");
  const [pageFrom, setPageFrom] = React.useState(initialSeed?.pageFrom ?? "");
  const [pageTo, setPageTo] = React.useState(initialSeed?.pageTo ?? "");
  const sourceless = picked !== null && picked.source === null;
  const effUnit: ItemUnit = sourceless ? unit : "test";
  const pageMode = sourceless && unit === "sayfa";
  const pf = Number(pageFrom);
  const pt = Number(pageTo);
  const rangeValid = pageMode && pageFrom !== "" && pageTo !== "" && pf >= 1 && pt >= pf;
  const pageSug = usePageSuggestion(studentId, picked?.topic.topic_id ?? null, note, pageMode);
  // Saat · periyot kartın içinde (2026-10-22) — ayrıntılı forma gitme nedeni kalktı.
  const [hour, setHour] = React.useState("");
  const [localPeriod, setLocalPeriod] = React.useState<TaskPeriod | null>(period);
  const [extrasOpen, setExtrasOpen] = React.useState(period !== null);
  const [customOpen, setCustomOpen] = React.useState(false);

  // Seçim değişince üst bileşene bildir (formlar arası taşıma).
  React.useEffect(() => {
    onSeedChange?.(
      picked
        ? { topic: picked.topic, source: picked.source, count, unit, note, pageFrom, pageTo }
        : null,
    );
  }, [picked, count, unit, note, pageFrom, pageTo, onSeedChange]);
  const create = useCreateTask(studentId);
  const boxRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const t = setTimeout(() => setDebounced(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  // Dışarı tıklama VE Escape ile kapanmalı. Escape'siz sürümde liste açık
  // kalıp altındaki kontrolleri örtüyordu (canlı tarayıcı testinde yakalandı):
  // koç klavyeyle çıkamıyordu.
  React.useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const pickerQ = useQuery<TaskPickerResponse>({
    queryKey: teacherKeys.studentTaskPicker(studentId, debounced),
    queryFn: () => getTaskPicker(studentId, debounced),
    enabled: open,
    staleTime: 30_000,
  });

  /** Konu satırına tıklama: kitabı varsa (dolu olmayan) ilk kaynak, yoksa kaynaksız. */
  function chooseDefault(topic: PickerTopicItem) {
    const src = topic.sources.find((x) => !x.full) ?? null;
    choose(topic, src);
  }

  function choose(topic: PickerTopicItem, source: PickerSourceItem | null) {
    setPicked({ topic, source });
    setCount(String(topic.quantity));
    setUnit("test");
    setNote("");
    setPageFrom("");
    setPageTo("");
    setOpen(false);
    setQ("");
  }

  const overflow =
    picked?.source && Number(count) > 0
      ? Math.max(0, Number(count) - picked.source.remaining)
      : 0;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!picked) return;
    const n = pageMode ? (rangeValid ? pt - pf + 1 : 0) : Number(count);
    if (!Number.isFinite(n) || n < 1) return;
    const { topic, source } = picked;
    if (source && onSourcePick) {
      onSourcePick({ section_id: source.section_id, count: n });
      setPicked(null);
      setCount("");
      return;
    }
    // Kaynaksız görevde başlığı sunucu kurar ("Konu (Not): s. 45–50" / "Konu — 3 test").
    const title = source ? `${source.book_name} — ${source.section_label}: ${n} test` : "Görev";
    create.mutate(
      {
        body: {
          date: dayDate,
          type: "test",
          title,
          scheduled_hour: hour === "" ? null : Number(hour),
          period: localPeriod,
          items: [
            source
              ? {
                  book_id: source.book_id,
                  section_id: source.section_id,
                  planned_count: n,
                  // Kapasite yetmiyorsa engel değil — koç uyarıyı görüyor (P1)
                  allow_over_capacity: overflow > 0,
                }
              : {
                  // Kaynaksız görev: kitap yok, konu var (P2)
                  book_id: null,
                  section_id: null,
                  topic_id: topic.topic_id,
                  label: note.trim() || topic.topic_name,
                  planned_count: n,
                  unit,
                  page_from: pageMode ? pf : null,
                  page_to: pageMode ? pt : null,
                },
          ],
        },
      },
      {
        onSuccess: () => {
          setPicked(null);
          setCount("");
          setPageFrom("");
          setPageTo("");
          setCustomOpen(false);
          onAfterAdd();
        },
      },
    );
  }

  const groups = pickerQ.data?.groups ?? [];
  const empty = !pickerQ.isLoading && groups.length === 0;
  const firstHit = groups[0]?.items[0] ?? null;
  const n = pageMode ? (rangeValid ? pt - pf + 1 : 0) : Number(count);
  // Kutu TEST sayısıdır; 15'ten büyük sayı çoğu zaman soru sayısı yazıldığını gösterir.
  const looksLikeQuestions = effUnit === "test" && Number.isFinite(n) && n > 15;
  const ctaLabel = pageMode && rangeValid ? `Ekle · s. ${pf}–${pt}` : `Ekle · ${n} ${UNIT_WORD[effUnit]}`;

  // YENİDEN TASARIM (2026-10-22, koç: "dağınık ve karışık"): boş durumda yalnız arama; konu
  // seçilince tek sütunlu görev kartı — yukarıdan aşağı karar sırası (Nasıl → Miktar →
  // Kaynak → Saat · periyot), tek sol hiza, tek vurgu rengi, birincil eylem EN ALTTA.
  const habit = picked?.topic.quantity ?? 3;
  const chipValues = Array.from(new Set([1, 2, 3, 4, 5, habit])).sort((a, b) => a - b);
  const countNum = Number(count);
  const isCustom = customOpen || (count !== "" && !chipValues.includes(countNum));
  const showComposer = picked !== null && !open;

  return (
    <div ref={boxRef} className="@container relative space-y-2">
      {!showComposer ? (
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onKeyDown={(e) => {
              // Enter = ilk sonucu seç (kitabı varsa kitaptan, yoksa kaynaksız)
              if (e.key === "Enter" && open && firstHit) {
                e.preventDefault();
                chooseDefault(firstHit);
              }
            }}
            placeholder="Ne çalışsın? Konu adı yaz"
            title="Konu adı yaz · örn. milli destan, trigo, mevsimler"
            className="pl-8"
            aria-label="Görev ara"
          />
        </div>
      ) : null}

      {showComposer && picked ? (
        <form
          onSubmit={submit}
          aria-label="Görev ekleme kutusu"
          className="overflow-hidden rounded-lg border border-border bg-background"
          data-section="quick-add:composer"
        >
          {/* Başlık: seçim — dokununca değiştir */}
          <div
            className="flex items-start gap-2 border-b border-border bg-muted/40 px-3 py-2.5"
            data-testid="quick-add-picked"
          >
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="min-w-0 flex-1 text-left"
              aria-label="Seçimi değiştir"
            >
              <span className="block text-[14px] font-semibold leading-snug text-foreground">
                {picked.topic.topic_name}
              </span>
              <span className="block text-[12px] leading-snug text-muted-foreground">
                {picked.topic.subject_name} ·{" "}
                {picked.source
                  ? `${picked.source.book_name} · ${picked.source.section_label} · ${
                      picked.source.full ? "kapasite doldu" : `${picked.source.remaining} test kaldı`
                    }`
                  : "kaynaksız (müfredata bağlı)"}
              </span>
            </button>
            <button
              type="button"
              onClick={() => {
                setPicked(null);
                setCount("");
                setOpen(true);
              }}
              className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label="Seçimi kaldır"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="space-y-3 px-3 py-3">
            {sourceless ? (
              <Row label="Nasıl?">
                <UnitSegment
                  value={unit}
                  onChange={(u) => {
                    setUnit(u);
                    if (u !== "sayfa") {
                      setPageFrom("");
                      setPageTo("");
                    }
                  }}
                  className="w-full @md:w-auto"
                />
                <p className="text-[11.5px] leading-snug text-muted-foreground">{unitHint(unit)}</p>
              </Row>
            ) : null}

            {pageMode ? (
              <Row label="Sayfa">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Input
                    type="number"
                    min={1}
                    value={pageFrom}
                    onChange={(e) => setPageFrom(e.target.value)}
                    className="h-9 w-20 text-center tabular-nums"
                    aria-label="Başlangıç sayfası"
                    placeholder="baş."
                  />
                  <span className="text-muted-foreground" aria-hidden>–</span>
                  <Input
                    type="number"
                    min={1}
                    value={pageTo}
                    onChange={(e) => setPageTo(e.target.value)}
                    className="h-9 w-20 text-center tabular-nums"
                    aria-label="Bitiş sayfası"
                    placeholder="bitiş"
                  />
                  {rangeValid ? (
                    <span className="text-[12.5px] tabular-nums text-foreground">= {pt - pf + 1} sayfa</span>
                  ) : null}
                </div>
                {pageFrom !== "" && pageTo !== "" && !rangeValid ? (
                  <p className="text-[12px] text-rose-700">
                    Bitiş sayfası başlangıçtan küçük olamaz.
                  </p>
                ) : null}
                <PageSuggestionLine data={pageSug.data} pageFrom={pageFrom} onPageFrom={setPageFrom} />
              </Row>
            ) : (
              <Row label="Miktar">
                <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Miktar">
                  {chipValues.map((v) => {
                    const on = !isCustom && countNum === v;
                    return (
                      <button
                        key={v}
                        type="button"
                        onClick={() => {
                          setCount(String(v));
                          setCustomOpen(false);
                        }}
                        aria-pressed={on}
                        title={v === habit ? "bu derste genelde verdiğin sayı" : undefined}
                        className={cn(
                          "relative h-9 min-w-9 rounded-md border px-2 text-sm font-medium tabular-nums transition",
                          on
                            ? "border-cyan-700 bg-cyan-700 text-white"
                            : "border-input bg-background text-foreground hover:border-cyan-600",
                        )}
                      >
                        {v}
                        {v === habit && !on ? (
                          <span className="absolute -right-0.5 -top-0.5 size-1.5 rounded-full bg-cyan-600" aria-hidden />
                        ) : null}
                      </button>
                    );
                  })}
                  {isCustom ? (
                    <Input
                      type="number"
                      min={1}
                      value={count}
                      autoFocus={customOpen}
                      onChange={(e) => setCount(e.target.value)}
                      className="h-9 w-20 text-center tabular-nums"
                      aria-label={effUnit === "soru" ? "Soru sayısı" : "Test sayısı"}
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setCustomOpen(true);
                        setCount("");
                      }}
                      className="h-9 rounded-md border border-dashed border-input px-2.5 text-[12.5px] text-muted-foreground hover:text-foreground"
                    >
                      başka
                    </button>
                  )}
                  <span className="text-[12.5px] text-muted-foreground">{UNIT_WORD[effUnit]}</span>
                </div>
                {effUnit === "test" ? (
                  <p className="text-[11.5px] text-muted-foreground">
                    <span className="mr-1 inline-block size-1.5 rounded-full bg-cyan-600 align-middle" aria-hidden />
                    {picked.topic.quantity_reason}
                  </p>
                ) : null}
                {looksLikeQuestions ? (
                  <p className="flex items-start gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-[12px] leading-snug text-amber-900">
                    <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>
                      Bu sayı <b>test</b> sayısıdır — {n} test yazdın. Soru sayısıysa birimi
                      &quot;soru&quot; yap.
                    </span>
                  </p>
                ) : null}
                {overflow > 0 && picked.source ? (
                  <p className="flex items-start gap-1.5 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-[12px] leading-snug text-amber-900">
                    <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                    <span>
                      Bu bölümde kayıtlı kapasite{" "}
                      {picked.source.remaining === 0 ? "kalmadı" : `${picked.source.remaining} test`} —{" "}
                      <b>{overflow} test</b> aşılacak. Görev yine de oluşturulur.
                    </span>
                  </p>
                ) : null}
              </Row>
            )}

            {sourceless ? (
              <Row label="Kaynak">
                <Input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  list="quick-add-note-suggestions"
                  maxLength={120}
                  placeholder="Kitap adı — isteğe bağlı (örn. Hız Fen)"
                  aria-label="Kitap adı notu"
                  className="h-9"
                />
                <datalist id="quick-add-note-suggestions">
                  {(pageSug.data?.notes ?? []).map((x) => (
                    <option key={x} value={x} />
                  ))}
                </datalist>
              </Row>
            ) : null}

            {/* Saat · periyot — katlı; seçiliyse açık gelir */}
            <div>
              <button
                type="button"
                onClick={() => setExtrasOpen((v) => !v)}
                aria-expanded={extrasOpen}
                className="inline-flex items-center gap-1 text-[12px] font-medium text-muted-foreground hover:text-foreground"
              >
                <ChevronRight className={cn("h-3.5 w-3.5 transition", extrasOpen && "rotate-90")} aria-hidden />
                Saat · periyot
                {localPeriod || hour !== "" ? (
                  <span className="ml-1 text-foreground">
                    ({[PERIODS.find((x) => x.key === localPeriod)?.label, hour !== "" ? `${hour}:00` : null]
                      .filter((x) => x && x !== "—")
                      .join(" · ")})
                  </span>
                ) : null}
              </button>
              {extrasOpen ? (
                <div className="mt-2 flex flex-wrap items-center gap-2" data-section="quick-add:extras">
                  <div className="inline-flex rounded-md border border-input bg-background p-0.5" role="radiogroup" aria-label="Periyot">
                    {PERIODS.map((x) => (
                      <button
                        key={x.key ?? "none"}
                        type="button"
                        role="radio"
                        aria-checked={localPeriod === x.key}
                        onClick={() => {
                          setLocalPeriod(x.key);
                          onPeriodChange?.(x.key);
                        }}
                        className={cn(
                          "rounded px-2 py-1 text-[12px] font-medium transition",
                          localPeriod === x.key ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {x.label}
                      </button>
                    ))}
                  </div>
                  <select
                    value={hour}
                    onChange={(e) => setHour(e.target.value)}
                    aria-label="Saat"
                    className="h-8 rounded-md border border-input bg-background px-2 text-[12.5px] text-foreground"
                  >
                    <option value="">saat yok</option>
                    {Array.from({ length: 24 }, (_, h) => (
                      <option key={h} value={String(h)}>
                        {String(h).padStart(2, "0")}:00
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
            </div>
          </div>

          {/* Altbilgi: ikincil eylemler solda, birincil Ekle sağda */}
          <div className="flex flex-wrap items-center gap-2 border-t border-border bg-muted/30 px-3 py-2.5">
            <div className="min-w-0 flex-1">{secondary}</div>
            <Button
              type="submit"
              disabled={(pageMode ? !rangeValid : !(countNum > 0)) || create.isPending}
              // koyu temada varsayılan primary 3,68 kontrast → cyan-700 (≥4,5) kuralı
              className="ml-auto h-9 bg-cyan-700 px-4 text-white hover:bg-cyan-800 hover:text-white"
            >
              {create.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : n > 0 ? (
                ctaLabel
              ) : (
                "Ekle"
              )}
            </Button>
          </div>
        </form>
      ) : null}

      {/* Aday listesi */}
      {open ? (
        <div
          className="absolute left-0 right-0 top-full z-30 mt-1 max-h-[22rem] overflow-y-auto rounded-lg border border-border bg-popover p-1 shadow-lg"
          data-testid="quick-add-results"
        >
          {pickerQ.isLoading ? (
            <p className="px-2 py-3 text-center text-xs text-muted-foreground">
              <Loader2 className="mr-1 inline h-3 w-3 animate-spin" />
              yükleniyor…
            </p>
          ) : empty ? (
            <p className="px-2 py-3 text-center text-xs text-muted-foreground">
              Eşleşen konu yok. Konunun bir kelimesini ya da baş harflerini yaz
              (örn. &ldquo;trigo&rdquo;, &ldquo;destan&rdquo;).
            </p>
          ) : (
            groups.map((g) => (
              <div key={g.key} className="mb-1 last:mb-0">
                <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {g.label}
                </p>
                {g.items.map((it) => (
                  <div key={it.topic_id} className="mb-0.5">
                    <button
                      type="button"
                      onClick={() => chooseDefault(it)}
                      className="flex w-full flex-wrap items-baseline gap-x-1.5 rounded px-2 py-1 text-left hover:bg-accent"
                      title={
                        it.sources.some((x) => !x.full)
                          ? "Seç — kitabından verilir"
                          : "Seç — kaynak belirtmeden (müfredata bağlı) verilir"
                      }
                    >
                      <span className="text-[13px] font-medium text-foreground">
                        {it.topic_name}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        {it.subject_name}
                        {it.grade_level ? ` · ${it.grade_level}. sınıf` : ""}
                        {it.theme_name ? ` · ${it.theme_name}` : ""}
                      </span>
                      {it.badge ? <Badge label={it.badge} /> : null}
                      {it.match === "kısmi" ? (
                        <span className="text-[10px] text-amber-700">
                          kısmi eşleşme
                        </span>
                      ) : null}
                    </button>
                    {it.sources.map((s) => (
                      <button
                        key={s.section_id}
                        type="button"
                        onClick={() => choose(it, s)}
                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 pl-5 text-left text-[12px] hover:bg-accent"
                      >
                        <BookOpen className="h-3 w-3 shrink-0 text-muted-foreground" />
                        <span className="truncate text-foreground">
                          {s.book_name}
                          <span className="text-muted-foreground">
                            {" "}
                            · {s.section_label}
                          </span>
                        </span>
                        <span
                          className={cn(
                            "ml-auto whitespace-nowrap text-[11px] tabular-nums",
                            s.full
                              ? "text-amber-700"
                              : "text-muted-foreground",
                          )}
                        >
                          {s.full ? "kapasite doldu" : `${s.remaining} test kaldı`}
                        </span>
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => choose(it, null)}
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 pl-5 text-left text-[12px] text-muted-foreground hover:bg-accent"
                    >
                      <Zap className="h-3 w-3 shrink-0" />
                      Kaynak belirtmeden ver
                    </button>
                  </div>
                ))}
              </div>
            ))
          )}
          <p className="flex items-center gap-1.5 border-t border-border px-2 py-1.5 text-[10.5px] text-muted-foreground">
            <Sparkles className="h-3 w-3" />
            Adet, bu derste genelde verdiğin sayıdan gelir — değiştirebilirsin.
          </p>
        </div>
      ) : null}
    </div>
  );
}


const PERIODS: { key: TaskPeriod | null; label: string }[] = [
  { key: null, label: "—" },
  { key: "morning", label: "Sabah" },
  { key: "noon", label: "Öğle" },
  { key: "evening", label: "Akşam" },
];

/** Kart satırı: solda etiket sütunu, sağda kontrol (dar kapta etiket üste geçer). */
function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1.5 @md:grid-cols-[5rem_1fr] @md:items-start @md:gap-3">
      <span className="pt-1.5 text-[12px] font-medium text-muted-foreground">{label}</span>
      <div className="min-w-0 space-y-1.5">{children}</div>
    </div>
  );
}

function unitHint(unit: ItemUnit): string {
  if (unit === "soru") return "Müfredata bağlanır · öğrenci doğru/yanlış/boş girer · test sayısına girmez";
  if (unit === "sayfa") return "Müfredata bağlanır · öğrenci yaptım der · test sayısına girmez";
  return "Müfredata bağlanır · konu performansına ve test sayılarına girer";
}
