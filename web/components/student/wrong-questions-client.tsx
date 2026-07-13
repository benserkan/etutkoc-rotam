"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpen,
  Camera,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Eye,
  ImageIcon,
  Loader2,
  Plus,
  RotateCcw,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  getStudentBooks,
  getStudentBookSections,
  studentKeys,
} from "@/lib/api/student";
import {
  getStudentWrongQuestions,
  studentWrongImageUrl,
  wrongQuestionKeys,
} from "@/lib/api/wrong-questions";
import {
  useAddWrongImage,
  useAiTagWrongQuestion,
  useAttemptWrongQuestion,
  useCreateWrongQuestion,
  useDeleteWrongQuestion,
  useUpdateWrongQuestion,
} from "@/lib/hooks/use-wrong-question-mutations";
import type {
  WrongQuestionItem,
  WrongQuestionListResponse,
} from "@/lib/types/wrong-question";
import { cn } from "@/lib/utils";

/**
 * Öğrenci "Yanlışlarım" — yanlış soru arşivi.
 *
 * Döngü: fotoğrafla ekle → sistem yarın yeniden sorar (FSRS) → aralıklı 2
 * doğru çözüm soruyu KAPATIR; "yine yanlış" kapalıyı yeniden açar.
 * Veli bu alanı görmez; yalnız öğrenci + koç.
 */

const SOURCE_LABELS: Record<string, string> = {
  gorev: "Görevden",
  deneme: "Denemeden",
  diger: "Diğer",
};

interface UrlPrefill {
  open: boolean;
  taskId?: number;
  bookId?: number;
  sectionId?: number;
}

function readPrefill(): UrlPrefill {
  if (typeof window === "undefined") return { open: false };
  const sp = new URLSearchParams(window.location.search);
  if (sp.get("add") !== "1") return { open: false };
  const num = (k: string) => {
    const v = Number(sp.get(k));
    return Number.isFinite(v) && v > 0 ? v : undefined;
  };
  return {
    open: true,
    taskId: num("task_id"),
    bookId: num("book_id"),
    sectionId: num("section_id"),
  };
}

export function StudentWrongQuestionsClient({
  initial,
}: {
  initial: WrongQuestionListResponse;
}) {
  const [statusFilter, setStatusFilter] = React.useState<"" | "acik" | "kapandi">("");
  const [subjectFilter, setSubjectFilter] = React.useState<string>("");
  const [errorFilter, setErrorFilter] = React.useState<string>("");
  const [prefill] = React.useState<UrlPrefill>(readPrefill);
  const [captureOpen, setCaptureOpen] = React.useState(prefill.open);
  const [detailId, setDetailId] = React.useState<number | null>(null);
  const [resolveOpen, setResolveOpen] = React.useState(false);

  const q = useQuery({
    queryKey: wrongQuestionKeys.studentList(),
    queryFn: () => getStudentWrongQuestions(),
    initialData: initial,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;

  // Filtreler istemci tarafında (liste zaten öğrencinin tamamı, ≤500)
  const items = data.items.filter((it) => {
    if (statusFilter && it.status !== statusFilter) return false;
    if (subjectFilter && String(it.subject_id ?? "") !== subjectFilter) return false;
    if (errorFilter && it.error_type !== errorFilter) return false;
    return true;
  });
  const openItems = data.items.filter((it) => it.status === "acik");
  const dueItems = data.items.filter((it) => it.is_due);
  // Çözme kuyruğu: vadesi gelenler önce; hiçbiri yoksa açık sorularla
  // alıştırma yapılabilir (özellik hiçbir zaman "ölü" görünmez).
  const practiceQueue = dueItems.length > 0 ? dueItems : openItems;
  const subjects = Array.from(
    new Map(
      data.items
        .filter((it) => it.subject_id != null && it.subject_name)
        .map((it) => [it.subject_id as number, it.subject_name as string]),
    ).entries(),
  );

  // Detay kaydı listeden TÜRETİLİR — liste tazelenince dialog güncel kalır,
  // kayıt silinirse dialog kendiliğinden kapanır (state kopyası yok)
  const detail =
    (detailId != null && data.items.find((it) => it.id === detailId)) || null;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Yanlışlarım</h1>
          <p className="text-sm text-muted-foreground max-w-xl mt-1">
            Yanlış yaptığın soruyu fotoğrafla arşive at. Sistem doğru zamanda
            yeniden sorar; <b>aralıklı iki doğru çözüm</b> soruyu kapatır.
          </p>
        </div>
        <Button onClick={() => setCaptureOpen(true)} className="gap-1.5">
          <Camera className="size-4" aria-hidden /> Yanlış ekle
        </Button>
      </header>

      {/* Yeniden çözme kuyruğu — vadesi gelenler; yoksa açıklarla alıştırma */}
      {practiceQueue.length > 0 ? (
        <div
          className={cn(
            "flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3",
            dueItems.length > 0
              ? "border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10"
              : "border-cyan-200 bg-cyan-50 dark:border-cyan-500/30 dark:bg-cyan-500/10",
          )}
        >
          <RotateCcw
            className={cn(
              "size-5",
              dueItems.length > 0
                ? "text-amber-700 dark:text-amber-300"
                : "text-cyan-700 dark:text-cyan-300",
            )}
            aria-hidden
          />
          <div className="flex-1 min-w-48">
            {dueItems.length > 0 ? (
              <>
                <div className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                  Yeniden çözme zamanı: {dueItems.length} soru seni bekliyor
                </div>
                <div className="text-xs text-amber-800/80 dark:text-amber-200/70">
                  Bir yanlışı kapatmanın yolu, aradan zaman geçince yeniden çözmek.
                </div>
              </>
            ) : (
              <>
                <div className="text-sm font-semibold text-cyan-900 dark:text-cyan-200">
                  Alıştırma: {openItems.length} açık soru
                </div>
                <div className="text-xs text-cyan-800/80 dark:text-cyan-200/70">
                  Sıradakilerin vadesi henüz gelmedi — istersen şimdi de kendini
                  deneyebilirsin.
                </div>
              </>
            )}
          </div>
          <Button
            size="sm"
            className={cn(
              "text-white hover:text-white",
              dueItems.length > 0
                ? "bg-amber-600 hover:bg-amber-700"
                : "bg-cyan-600 hover:bg-cyan-700",
            )}
            onClick={() => setResolveOpen(true)}
          >
            {dueItems.length > 0 ? "Çözmeye başla" : "Kendini dene"}{" "}
            <ChevronRight className="size-4" aria-hidden />
          </Button>
        </div>
      ) : null}

      {/* Sayaçlar + filtreler */}
      <div className="flex flex-wrap items-center gap-2">
        {(
          [
            ["", `Tümü (${data.counts.total})`],
            ["acik", `Açık (${data.counts.open})`],
            ["kapandi", `Kapanan (${data.counts.closed})`],
          ] as const
        ).map(([val, label]) => (
          <button
            key={val || "all"}
            type="button"
            onClick={() => setStatusFilter(val)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs font-medium transition",
              statusFilter === val
                ? "border-cyan-600 bg-cyan-600 text-white"
                : "border-border bg-card text-muted-foreground hover:text-foreground",
            )}
          >
            {label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {subjects.length > 1 ? (
            <select
              value={subjectFilter}
              onChange={(e) => setSubjectFilter(e.target.value)}
              className="h-8 rounded-md border border-border bg-card px-2 text-xs text-foreground"
              aria-label="Ders filtresi"
            >
              <option value="">Tüm dersler</option>
              {subjects.map(([id, name]) => (
                <option key={id} value={String(id)}>{name}</option>
              ))}
            </select>
          ) : null}
          <select
            value={errorFilter}
            onChange={(e) => setErrorFilter(e.target.value)}
            className="h-8 rounded-md border border-border bg-card px-2 text-xs text-foreground"
            aria-label="Hata türü filtresi"
          >
            <option value="">Tüm hata türleri</option>
            {Object.entries(data.error_type_labels).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Liste */}
      {items.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-card px-6 py-12 text-center">
          <ImageIcon className="mx-auto size-8 text-muted-foreground/50" aria-hidden />
          <p className="mt-3 text-sm text-muted-foreground">
            {data.counts.total === 0
              ? "Henüz arşivde soru yok. İlk yanlışını fotoğrafla ekle — gerisini sistem takip eder."
              : "Bu filtreyle eşleşen kayıt yok."}
          </p>
          {data.counts.total === 0 ? (
            <Button className="mt-4 gap-1.5" onClick={() => setCaptureOpen(true)}>
              <Plus className="size-4" aria-hidden /> İlk yanlışını ekle
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((it) => (
            <WrongCard key={it.id} item={it} onOpen={() => setDetailId(it.id)} />
          ))}
        </div>
      )}

      <CaptureDialog
        open={captureOpen}
        onOpenChange={setCaptureOpen}
        errorLabels={data.error_type_labels}
        prefill={prefill}
      />
      <DetailDialog
        item={detail}
        onClose={() => setDetailId(null)}
        errorLabels={data.error_type_labels}
      />
      {resolveOpen ? (
        <ResolveDialog
          onClose={() => setResolveOpen(false)}
          items={practiceQueue}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Kart
// ---------------------------------------------------------------------------

function WrongCard({
  item,
  onOpen,
}: {
  item: WrongQuestionItem;
  onOpen: () => void;
}) {
  const qImg = item.images.find((im) => im.kind === "question");
  const closed = item.status === "kapandi";
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "group flex flex-col overflow-hidden rounded-lg border bg-card text-left shadow-sm transition hover:shadow-md",
        closed ? "border-emerald-200 dark:border-emerald-500/30 opacity-80" : "border-border",
        item.is_due && "border-amber-300 dark:border-amber-500/40",
      )}
    >
      <div className="relative h-32 w-full bg-muted">
        {qImg ? (
          // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF görüntü ucu; next/Image optimizasyonu cookie'li dinamik uca uygulanamaz
          <img
            src={studentWrongImageUrl(item.id, qImg.id)}
            alt="Soru fotoğrafı"
            className="h-full w-full object-cover object-top"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-muted-foreground/40">
            <ImageIcon className="size-8" aria-hidden />
          </div>
        )}
        <div className="absolute left-2 top-2 flex gap-1">
          {closed ? (
            <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-[10px] font-bold text-white">
              KAPANDI
            </span>
          ) : item.is_due ? (
            <span className="rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-bold text-white">
              YENİDEN ÇÖZ
            </span>
          ) : null}
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3">
        <div className="text-sm font-medium text-foreground line-clamp-1">
          {item.topic_name ?? item.section_label ?? item.subject_name ?? "Etiketsiz soru"}
        </div>
        <div className="text-xs text-muted-foreground line-clamp-1">
          {[item.subject_name, item.book_name].filter(Boolean).join(" · ") ||
            SOURCE_LABELS[item.source_kind]}
        </div>
        <div className="mt-auto flex items-center gap-2 pt-1.5">
          {item.error_type_label ? (
            <span className="rounded bg-rose-50 px-1.5 py-0.5 text-[10px] font-medium text-rose-800 dark:bg-rose-500/10 dark:text-rose-300">
              {item.error_type_label}
            </span>
          ) : null}
          {!closed ? (
            <span
              className="ml-auto inline-flex items-center gap-0.5"
              title={`Kapanışa ${Math.max(0, 2 - item.correct_streak)} doğru çözüm kaldı`}
            >
              {[0, 1].map((i) => (
                <span
                  key={i}
                  className={cn(
                    "inline-block size-2 rounded-full",
                    i < item.correct_streak
                      ? "bg-emerald-500"
                      : "bg-muted-foreground/25",
                  )}
                />
              ))}
            </span>
          ) : null}
        </div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Yakalama dialog'u
// ---------------------------------------------------------------------------

function CaptureDialog({
  open,
  onOpenChange,
  errorLabels,
  prefill,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  errorLabels: Record<string, string>;
  prefill: UrlPrefill;
}) {
  const create = useCreateWrongQuestion();
  const [files, setFiles] = React.useState<File[]>([]);
  const [source, setSource] = React.useState<"gorev" | "deneme" | "diger" | "kitap">(
    prefill.sectionId ? "gorev" : "diger",
  );
  const [bookId, setBookId] = React.useState<string>(String(prefill.bookId ?? ""));
  const [sectionId, setSectionId] = React.useState<string>(String(prefill.sectionId ?? ""));
  const [errorType, setErrorType] = React.useState<string>("");
  const [note, setNote] = React.useState("");
  const fileRef = React.useRef<HTMLInputElement>(null);

  const booksQ = useQuery({
    queryKey: studentKeys.books(),
    queryFn: getStudentBooks,
    enabled: open && source === "kitap",
    staleTime: 60_000,
  });
  const sectionsQ = useQuery({
    queryKey: studentKeys.bookSections(Number(bookId) || 0),
    queryFn: () => getStudentBookSections(Number(bookId)),
    enabled: open && source === "kitap" && !!bookId,
    staleTime: 60_000,
  });

  function reset() {
    setFiles([]);
    setErrorType("");
    setNote("");
    if (!prefill.sectionId) {
      setSource("diger");
      setBookId("");
      setSectionId("");
    }
  }

  function submit() {
    const secId =
      source === "gorev"
        ? prefill.sectionId
        : source === "kitap" && sectionId
          ? Number(sectionId)
          : undefined;
    create.mutate(
      {
        fields: {
          source_kind: source === "kitap" ? "diger" : source === "gorev" ? "gorev" : source,
          book_section_id: secId,
          task_id: source === "gorev" ? prefill.taskId : undefined,
          error_type: errorType || undefined,
          note: note.trim() || undefined,
        },
        photos: files,
      },
      {
        onSuccess: () => {
          reset();
          onOpenChange(false);
        },
      },
    );
  }

  const canSubmit =
    files.length > 0 || note.trim().length > 0 || source === "gorev" ||
    (source === "kitap" && !!sectionId);

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!create.isPending) onOpenChange(v); }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="inline-flex items-center gap-2">
            <Camera className="size-4 text-cyan-700 dark:text-cyan-300" aria-hidden />
            Yanlış soru ekle
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {/* Fotoğraf */}
          <div>
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              capture="environment"
              multiple
              className="hidden"
              onChange={(e) => {
                const list = Array.from(e.target.files ?? []);
                if (list.length) setFiles((prev) => [...prev, ...list].slice(0, 4));
                e.target.value = "";
              }}
            />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="flex w-full flex-col items-center gap-1 rounded-lg border-2 border-dashed border-border bg-muted/30 px-4 py-6 text-sm text-muted-foreground transition hover:border-cyan-400 hover:text-foreground"
            >
              <Camera className="size-6" aria-hidden />
              {files.length === 0
                ? "Sorunun fotoğrafını çek veya seç (en fazla 4)"
                : `${files.length} fotoğraf seçildi — eklemek için tekrar dokun`}
            </button>
            {files.length > 0 ? (
              <ul className="mt-2 space-y-1">
                {files.map((f, i) => (
                  <li key={`${f.name}-${i}`} className="flex items-center gap-2 text-xs text-muted-foreground">
                    <ImageIcon className="size-3.5 shrink-0" aria-hidden />
                    <span className="truncate">{f.name}</span>
                    <button
                      type="button"
                      aria-label="Fotoğrafı çıkar"
                      className="ml-auto rounded p-0.5 hover:text-rose-600"
                      onClick={() => setFiles((prev) => prev.filter((_, j) => j !== i))}
                    >
                      <X className="size-3.5" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>

          {/* Kaynak */}
          {source === "gorev" ? (
            <div className="rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs text-cyan-900 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-200">
              <BookOpen className="mr-1 inline size-3.5" aria-hidden />
              Görevden ekleniyor — ders ve konu otomatik etiketlenecek.
            </div>
          ) : (
            <div>
              <div className="mb-1.5 text-xs font-medium text-muted-foreground">
                Bu soru nereden? <span className="font-normal">(kitap seçersen konu otomatik etiketlenir)</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {(
                  [
                    ["kitap", "Kitabımdan"],
                    ["deneme", "Denemeden"],
                    ["diger", "Diğer"],
                  ] as const
                ).map(([val, label]) => (
                  <button
                    key={val}
                    type="button"
                    onClick={() => setSource(val)}
                    className={cn(
                      "rounded-full border px-3 py-1 text-xs font-medium transition",
                      source === val
                        ? "border-cyan-600 bg-cyan-600 text-white"
                        : "border-border bg-card text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {source === "kitap" ? (
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  <select
                    value={bookId}
                    onChange={(e) => { setBookId(e.target.value); setSectionId(""); }}
                    className="h-9 rounded-md border border-border bg-card px-2 text-sm text-foreground"
                    aria-label="Kitap seç"
                  >
                    <option value="">Kitap seç…</option>
                    {(booksQ.data?.subjects ?? []).map((g) =>
                      g.books.map((b) => (
                        <option key={b.book_id} value={String(b.book_id)}>
                          {g.subject_name} — {b.book_name}
                        </option>
                      )),
                    )}
                  </select>
                  <select
                    value={sectionId}
                    onChange={(e) => setSectionId(e.target.value)}
                    disabled={!bookId || sectionsQ.isLoading}
                    className="h-9 rounded-md border border-border bg-card px-2 text-sm text-foreground disabled:opacity-50"
                    aria-label="Bölüm seç"
                  >
                    <option value="">
                      {sectionsQ.isLoading ? "Yükleniyor…" : "Bölüm/ünite seç…"}
                    </option>
                    {(sectionsQ.data?.items ?? []).map((s) => (
                      <option key={s.id} value={String(s.id)}>{s.label}</option>
                    ))}
                  </select>
                </div>
              ) : null}
            </div>
          )}

          {/* Hata türü */}
          <div>
            <div className="mb-1.5 text-xs font-medium text-muted-foreground">
              Neden yanlış yaptın? <span className="font-normal">(dürüst ol — koçun buna göre yardım eder)</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(errorLabels).map(([k, v]) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setErrorType(errorType === k ? "" : k)}
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-medium transition",
                    errorType === k
                      ? "border-rose-500 bg-rose-500 text-white"
                      : "border-border bg-card text-muted-foreground hover:text-foreground",
                  )}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>

          {/* Not */}
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="Not (istersen): neyi karıştırdın, hangi adımda takıldın…"
            className="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/60"
          />

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={create.isPending}>
              Vazgeç
            </Button>
            <Button onClick={submit} disabled={!canSubmit || create.isPending} className="gap-1.5">
              {create.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Plus className="size-4" aria-hidden />
              )}
              Arşive ekle
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Detay dialog'u
// ---------------------------------------------------------------------------

function DetailDialog({
  item,
  onClose,
  errorLabels,
}: {
  item: WrongQuestionItem | null;
  onClose: () => void;
  errorLabels: Record<string, string>;
}) {
  const update = useUpdateWrongQuestion();
  const del = useDeleteWrongQuestion();
  const addImage = useAddWrongImage();
  const aiTag = useAiTagWrongQuestion("student");
  const solutionRef = React.useRef<HTMLInputElement>(null);

  if (!item) return null;
  const qImgs = item.images.filter((im) => im.kind === "question");
  const sImgs = item.images.filter((im) => im.kind === "solution");
  const closed = item.status === "kapandi";

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose(); }}>
      {/* Kaydırılabilir gövde + SABİT alt aksiyon çubuğu: uzun soru fotoğrafı
          değerlendirme butonlarını ekran dışına itmesin (kullanıcı geri bildirimi) */}
      <DialogContent className="flex max-h-[88vh] max-w-2xl flex-col overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4">
          <DialogTitle className="flex flex-wrap items-center gap-2 text-base">
            {closed ? (
              <CheckCircle2 className="size-4 text-emerald-600" aria-hidden />
            ) : (
              <CircleDashed className="size-4 text-amber-600" aria-hidden />
            )}
            {item.topic_name ?? item.section_label ?? "Etiketsiz soru"}
            <span className="text-xs font-normal text-muted-foreground">
              {[item.subject_name, item.book_name].filter(Boolean).join(" · ")}
            </span>
          </DialogTitle>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {/* Durum bandı */}
          <div
            className={cn(
              "rounded-md px-3 py-2 text-xs",
              closed
                ? "bg-emerald-50 text-emerald-900 dark:bg-emerald-500/10 dark:text-emerald-200"
                : "bg-amber-50 text-amber-900 dark:bg-amber-500/10 dark:text-amber-200",
            )}
          >
            {closed
              ? `Kapandı — ${item.attempts_count} denemede aralıklı iki doğru çözüm.`
              : item.is_due
                ? "Yeniden çözme zamanı geldi — aşağıdan sonucu işaretle."
                : `Açık · doğru serisi ${item.correct_streak}/2 · sistem vakti gelince yeniden soracak.`}
          </div>

          {/* Soru fotoğrafları — yükseklik sınırlı (aksiyon çubuğu hep görünür) */}
          {qImgs.length > 0 ? (
            <div className="space-y-2">
              {qImgs.map((im) => (
                // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF görüntü ucu
                <img
                  key={im.id}
                  src={studentWrongImageUrl(item.id, im.id)}
                  alt="Soru fotoğrafı"
                  className="max-h-[52vh] w-full rounded-md border border-border bg-muted object-contain"
                />
              ))}
            </div>
          ) : (
            <p className="text-sm italic text-muted-foreground">
              Fotoğraf yok{item.note ? " — not üzerinden takip ediliyor" : ""}.
            </p>
          )}

          {/* AI etiketleme (Faz 3) — konu eşleme + zorluk + yaklaşım ipucu */}
          {qImgs.length > 0 ? (
            item.ai_hint || item.ai_tagged_at || item.ai_question_text ? null : (
              <Button
                variant="outline"
                size="sm"
                className="w-full gap-1.5 border-violet-300 text-violet-700 hover:bg-violet-500/10 hover:text-violet-800 dark:border-violet-500/40 dark:text-violet-300"
                disabled={aiTag.isPending}
                onClick={() => aiTag.mutate({ id: item.id })}
              >
                {aiTag.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Sparkles className="size-4" aria-hidden />
                )}
                Yapay zekâ okusun — konuyu etiketle + yaklaşım ipucu ver
              </Button>
            )
          ) : null}

          {item.ai_hint ? (
            <div className="rounded-md border border-violet-200 bg-violet-50 px-3 py-2 dark:border-violet-500/30 dark:bg-violet-500/10">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-violet-800 dark:text-violet-300">
                <Sparkles className="size-3" aria-hidden />
                Yaklaşım ipucu
                {item.difficulty_guess ? (
                  <span className="ml-auto rounded bg-violet-200/60 px-1.5 py-0.5 text-[10px] font-medium normal-case text-violet-900 dark:bg-violet-500/20 dark:text-violet-200">
                    {item.difficulty_guess}
                  </span>
                ) : null}
              </div>
              <p className="mt-0.5 whitespace-pre-wrap text-sm text-violet-950 dark:text-violet-100">
                {item.ai_hint}
              </p>
              <p className="mt-1 text-[10px] text-violet-800/70 dark:text-violet-300/70">
                Yapay zekâ çözümü vermez — yolu gösterir. Çözümü sen bul.
              </p>
            </div>
          ) : null}

          {/* Koç açıklaması */}
          {item.coach_note ? (
            <div className="rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 dark:border-cyan-500/30 dark:bg-cyan-500/10">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-cyan-800 dark:text-cyan-300">
                Koçunun açıklaması
              </div>
              <p className="mt-0.5 whitespace-pre-wrap text-sm text-cyan-950 dark:text-cyan-100">
                {item.coach_note}
              </p>
            </div>
          ) : null}

          {/* Çözüm fotoğrafları */}
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Çözüm
              </span>
              <input
                ref={solutionRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                capture="environment"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) addImage.mutate({ id: item.id, file: f, kind: "solution" });
                  e.target.value = "";
                }}
              />
              <Button
                variant="outline"
                size="sm"
                className="h-7 gap-1 text-xs"
                disabled={addImage.isPending}
                onClick={() => solutionRef.current?.click()}
              >
                {addImage.isPending ? (
                  <Loader2 className="size-3 animate-spin" aria-hidden />
                ) : (
                  <Plus className="size-3" aria-hidden />
                )}
                Çözüm fotoğrafı ekle
              </Button>
            </div>
            {sImgs.length > 0 ? (
              <div className="space-y-2">
                {sImgs.map((im) => (
                  // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF görüntü ucu
                  <img
                    key={im.id}
                    src={studentWrongImageUrl(item.id, im.id)}
                    alt="Çözüm fotoğrafı"
                    className="max-h-[45vh] w-full rounded-md border border-border bg-muted object-contain"
                  />
                ))}
              </div>
            ) : (
              <p className="text-xs italic text-muted-foreground">
                Henüz çözüm fotoğrafı yok — doğru çözümü bulunca buraya ekle.
              </p>
            )}
          </div>

          {/* Etiketler */}
          <div>
            <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Hata türü
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(errorLabels).map(([k, v]) => (
                <button
                  key={k}
                  type="button"
                  disabled={update.isPending}
                  onClick={() =>
                    update.mutate({
                      id: item.id,
                      body: { error_type: k },
                    })
                  }
                  className={cn(
                    "rounded-full border px-3 py-1 text-xs font-medium transition",
                    item.error_type === k
                      ? "border-rose-500 bg-rose-500 text-white"
                      : "border-border bg-card text-muted-foreground hover:text-foreground",
                  )}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>

          {item.note ? (
            <p className="text-sm text-muted-foreground">
              <b className="text-foreground">Notun:</b> {item.note}
            </p>
          ) : null}

          <div className="flex items-center justify-between border-t border-border pt-3">
            <span className="text-[11px] text-muted-foreground">
              {SOURCE_LABELS[item.source_kind]} ·{" "}
              {new Date(item.created_at).toLocaleDateString("tr-TR")}
              {" · "}yalnız sen ve koçun görür
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 gap-1 text-xs text-rose-600 hover:bg-rose-500/10 hover:text-rose-700"
              disabled={del.isPending}
              onClick={() => {
                if (window.confirm("Bu soru arşivden silinsin mi? Geri alınamaz.")) {
                  del.mutate({ id: item.id }, { onSuccess: onClose });
                }
              }}
            >
              <Trash2 className="size-3" aria-hidden /> Sil
            </Button>
          </div>
        </div>

        {/* SABİT aksiyon çubuğu — açık soruda her zaman görünür/erişilebilir */}
        {!closed ? (
          <div className="shrink-0 border-t border-border bg-card px-5 py-3">
            <AttemptButtons id={item.id} isDue={item.is_due} />
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "emerald" | "rose" | "cyan";
}) {
  const cls = {
    emerald: "text-emerald-700 dark:text-emerald-300",
    rose: "text-rose-700 dark:text-rose-300",
    cyan: "text-cyan-700 dark:text-cyan-300",
  }[tone];
  return (
    <div className="rounded-md border border-border bg-card px-2 py-2">
      <div className={cn("text-xl font-semibold tabular-nums", cls)}>{value}</div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}

function AttemptButtons({ id, isDue }: { id: number; isDue: boolean }) {
  const attempt = useAttemptWrongQuestion();
  const opts: Array<{ rating: 1 | 2 | 3 | 4; label: string; cls: string }> = [
    { rating: 1, label: "Yine yanlış", cls: "bg-rose-600 hover:bg-rose-700" },
    { rating: 2, label: "Zor çözdüm", cls: "bg-amber-600 hover:bg-amber-700" },
    { rating: 3, label: "Çözdüm", cls: "bg-emerald-600 hover:bg-emerald-700" },
    { rating: 4, label: "Kolayca çözdüm", cls: "bg-cyan-600 hover:bg-cyan-700" },
  ];
  return (
    <div>
      <div className="mb-2 text-xs font-medium text-foreground">
        Soruyu yeniden çözmeyi dene — sonra sonucu işaretle:
        {!isDue ? (
          <span className="ml-1 font-normal text-muted-foreground">
            (vadesi gelmedi ama şimdi de deneyebilirsin)
          </span>
        ) : null}
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {opts.map((o) => (
          <Button
            key={o.rating}
            size="sm"
            disabled={attempt.isPending}
            className={cn("text-white hover:text-white", o.cls)}
            onClick={() => attempt.mutate({ id, body: { rating: o.rating } })}
          >
            {attempt.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              o.label
            )}
          </Button>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Yeniden çözme modu (due kuyruğu, kart kart)
// ---------------------------------------------------------------------------

function ResolveDialog({
  onClose,
  items,
}: {
  onClose: () => void;
  items: WrongQuestionItem[];
}) {
  const attempt = useAttemptWrongQuestion();
  const qc = useQueryClient();
  const [idx, setIdx] = React.useState(0);
  const [reveal, setReveal] = React.useState(false);
  // Kuyruk mount anında dondurulur (dialog yalnız açıkken mount edilir) —
  // attempt sonrası liste değişse de sıra şaşmaz.
  const [queue] = React.useState<WrongQuestionItem[]>(() => items);
  // Oturum sonucu — kuyruk bitince ÖZET gösterilir. (Eskiden dialog sessizce
  // kapanıyordu; tek soruluk kuyrukta "hiçbir şey olmadı" hissi veriyordu.)
  const [done, setDone] = React.useState(false);
  const [tally, setTally] = React.useState({ solved: 0, wrong: 0, closed: 0 });

  const current = queue[idx];

  function advance() {
    setReveal(false);
    if (idx + 1 >= queue.length) {
      setDone(true);
      qc.invalidateQueries({ queryKey: ["student", "wrong-questions"] });
    } else {
      setIdx(idx + 1);
    }
  }

  function rate(rating: 1 | 2 | 3 | 4) {
    if (!current) return;
    attempt.mutate(
      { id: current.id, body: { rating } },
      {
        onSuccess: (res) => {
          setTally((t) => ({
            solved: t.solved + (rating >= 3 ? 1 : 0),
            wrong: t.wrong + (rating === 1 ? 1 : 0),
            closed: t.closed + (res.data.status === "kapandi" ? 1 : 0),
          }));
          advance();
        },
      },
    );
  }

  function finish() {
    onClose();
    qc.invalidateQueries({ queryKey: ["student", "wrong-questions"] });
  }

  const rateOpts: Array<{ rating: 1 | 2 | 3 | 4; label: string; cls: string }> = [
    { rating: 1, label: "Yine yanlış", cls: "bg-rose-600 hover:bg-rose-700" },
    { rating: 2, label: "Zor çözdüm", cls: "bg-amber-600 hover:bg-amber-700" },
    { rating: 3, label: "Çözdüm", cls: "bg-emerald-600 hover:bg-emerald-700" },
    { rating: 4, label: "Kolayca çözdüm", cls: "bg-cyan-600 hover:bg-cyan-700" },
  ];

  return (
    <Dialog open onOpenChange={(v) => { if (!v) onClose(); }}>
      {/* Kaydırılabilir gövde + SABİT değerlendirme çubuğu — uzun soru fotoğrafı
          butonları ekran dışına itmesin (kullanıcı geri bildirimi 14.07) */}
      <DialogContent className="flex max-h-[90vh] max-w-2xl flex-col overflow-hidden p-0">
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4">
          <DialogTitle className="flex items-center gap-2 text-base">
            <RotateCcw className="size-4 text-amber-600" aria-hidden />
            Yeniden çözme · {Math.min(idx + 1, queue.length)}/{queue.length}
          </DialogTitle>
        </DialogHeader>
        {done || !current ? (
          /* Oturum özeti — ne yaptığın açıkça görünür */
          <div className="px-6 py-8 text-center">
            <CheckCircle2 className="mx-auto size-10 text-emerald-500" aria-hidden />
            <h3 className="mt-3 text-base font-semibold text-foreground">
              Tur bitti
            </h3>
            <div className="mx-auto mt-4 grid max-w-sm grid-cols-3 gap-3">
              <SummaryStat label="çözdün" value={tally.solved} tone="emerald" />
              <SummaryStat label="yine yanlış" value={tally.wrong} tone="rose" />
              <SummaryStat label="kapandı" value={tally.closed} tone="cyan" />
            </div>
            <p className="mx-auto mt-4 max-w-sm text-xs text-muted-foreground">
              {tally.closed > 0
                ? "Kapanan sorular arşivde “Kapanan” filtresinde. Diğerleri, aradan zaman geçince tekrar karşına gelecek."
                : tally.solved > 0
                  ? "Bir doğru çözüm daha yaptın. Kapanması için aradan zaman geçmiş ikinci bir doğru çözüm gerekiyor — sistem seni çağıracak."
                  : "Sorun değil. Sistem bu soruları daha sık karşına getirecek; takıldığın yerde koçunun açıklamasına bakabilirsin."}
            </p>
            <Button className="mt-5" onClick={finish}>
              Tamam
            </Button>
          </div>
        ) : (
          <>
            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-4">
              <div className="text-sm text-muted-foreground">
                {[current.subject_name, current.topic_name ?? current.section_label]
                  .filter(Boolean)
                  .join(" · ") || "Etiketsiz soru"}
              </div>
              {current.images.filter((im) => im.kind === "question").map((im) => (
                // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF görüntü ucu
                <img
                  key={im.id}
                  src={studentWrongImageUrl(current.id, im.id)}
                  alt="Soru fotoğrafı"
                  className="max-h-[55vh] w-full rounded-md border border-border bg-muted object-contain"
                />
              ))}
              {current.images.filter((im) => im.kind === "question").length === 0 ? (
                <div className="rounded-md border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
                  Bu kaydın fotoğrafı yok — {current.note ? `notun: "${current.note}"` : "kaynağından bulup çöz"}.
                </div>
              ) : null}

              {/* İpucu / çözüm katmanı */}
              {(current.coach_note || current.ai_hint ||
                current.images.some((im) => im.kind === "solution")) ? (
                !reveal ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-1.5"
                    onClick={() => setReveal(true)}
                  >
                    <Eye className="size-4" aria-hidden /> Takıldım — ipucu/çözümü göster
                  </Button>
                ) : (
                  <div className="space-y-2">
                    {current.ai_hint ? (
                      <div className="rounded-md border border-violet-200 bg-violet-50 px-3 py-2 text-sm text-violet-950 dark:border-violet-500/30 dark:bg-violet-500/10 dark:text-violet-100">
                        <b>Yaklaşım ipucu:</b> {current.ai_hint}
                      </div>
                    ) : null}
                    {current.coach_note ? (
                      <div className="rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm text-cyan-950 dark:border-cyan-500/30 dark:bg-cyan-500/10 dark:text-cyan-100">
                        <b>Koçun:</b> {current.coach_note}
                      </div>
                    ) : null}
                    {current.images.filter((im) => im.kind === "solution").map((im) => (
                      // eslint-disable-next-line @next/next/no-img-element -- auth'lu BFF görüntü ucu
                      <img
                        key={im.id}
                        src={studentWrongImageUrl(current.id, im.id)}
                        alt="Çözüm fotoğrafı"
                        className="max-h-[45vh] w-full rounded-md border border-border bg-muted object-contain"
                      />
                    ))}
                  </div>
                )
              ) : null}
            </div>

            {/* SABİT değerlendirme çubuğu */}
            <div className="shrink-0 border-t border-border bg-card px-5 py-3">
              <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-foreground">
                <AlertTriangle className="size-3.5 text-amber-600" aria-hidden />
                Önce KENDİN çöz, sonra işaretle — sistem sana göre plan yapıyor.
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {rateOpts.map((o) => (
                  <Button
                    key={o.rating}
                    size="sm"
                    disabled={attempt.isPending}
                    className={cn("text-white hover:text-white", o.cls)}
                    onClick={() => rate(o.rating)}
                  >
                    {attempt.isPending ? (
                      <Loader2 className="size-3.5 animate-spin" aria-hidden />
                    ) : (
                      o.label
                    )}
                  </Button>
                ))}
              </div>
              <button
                type="button"
                className="mt-2 text-xs text-muted-foreground underline-offset-2 hover:underline"
                onClick={advance}
              >
                Şimdilik atla →
              </button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
