"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  GitBranch,
  ExternalLink,
  Eye,
  Maximize,
  Minimize,
  MousePointer2,
  Pause,
  Play,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Volume2,
  VolumeX,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { GuideAvatar } from "@/components/guide/guide-avatar";
import {
  audioSrc,
  BRANCH_LABELS,
  boxFor,
  inferBranch,
  estimateDurationMs,
  shotSrc,
  type CoachGuideContent,
  type GuideBranch,
  type GuideChapterDef,
} from "@/components/guide/coach-guide-data";
import type { GuideProgressBody, GuideResponse } from "@/lib/types/guide";

/**
 * Rehber oynatıcısı — Rota'nın sesli, tıklamalı ekran anlatımı.
 *
 * - Her bölüm adım adım oynar: gerçek ekran görüntüsü + vurgu kutusu +
 *   imleç animasyonu + altyazı + Türkçe seslendirme (MP3; yoksa süre tahmini).
 * - Gezinme SERBESTTİR: bölüm kilidi yok; izlemek zorunlu değil. Bölüm sonu
 *   kartları yol gösterir (yaptın/zaten yapmışsın/henüz değil) ama ENGELLEMEZ.
 * - İzlenen adımlar SUNUCUYA yazılır (action=watch) — oturum düşse ya da cihaz
 *   değişse de rehber kaldığı adımdan devam eder.
 */

type Mode = "idle" | "playing" | "paused" | "end" | "choice";

interface Props {
  guide: GuideResponse;
  /** Oynatılacak rehber içeriği (GUIDES[guideKey]) — rol bazlı. */
  content: CoachGuideContent;
  busy: boolean;
  refreshing: boolean;
  onProgress: (body: GuideProgressBody) => Promise<unknown>;
  onRefresh: () => void;
  /** Sayfadaki "Nasıl kullanılır" bağlantısından gelen bölüm (?bolum=) — varsa onunla açılır. */
  initialChapter?: string | null;
}

export function GuidePlayer({
  guide,
  content,
  busy,
  refreshing,
  onProgress,
  onRefresh,
  initialChapter,
}: Props) {
  const chapters = content.chapters;
  const doneSet = useMemo(
    () => new Set(guide.state.chapters_done),
    [guide.state.chapters_done],
  );
  const firstOpenIdx = useMemo(() => {
    const idx = chapters.findIndex((c) => !doneSet.has(c.key));
    return idx === -1 ? chapters.length - 1 : idx;
  }, [chapters, doneSet]);

  const [selectedKey, setSelectedKey] = useState<string>(() => {
    if (initialChapter && chapters.some((c) => c.key === initialChapter)) return initialChapter;
    const cur = guide.state.current_chapter;
    if (cur && chapters.some((c) => c.key === cur)) return cur;
    return chapters[Math.max(0, Math.min(firstOpenIdx, chapters.length - 1))].key;
  });
  const chapterIdx = Math.max(0, chapters.findIndex((c) => c.key === selectedKey));
  const chapter = chapters[chapterIdx];

  // İzlenen adımlar: sunucudan tohumlanır (kaldığı yerden devam), yerelde
  // güncellenir + her adım bitişinde sunucuya yazılır (action=watch).
  const [played, setPlayed] = useState<Record<string, number[]>>(() => ({
    ...(guide.state.steps_watched ?? {}),
  }));

  // Dallanan rehber: koçun seçtiği yol (gün gün / havuz). Açık seçim yoksa
  // izlediği bölümlerden çıkarılır; sayfadan bir yolun bölümüyle gelindiyse o yol.
  const [branch, setBranch] = useState<GuideBranch | null>(() =>
    inferBranch(
      chapters,
      initialChapter ?? guide.state.current_chapter,
      (k) => doneSet.has(k) || (guide.state.steps_watched?.[k]?.length ?? 0) > 0,
    ),
  );
  const [showOtherBranch, setShowOtherBranch] = useState(false);
  const hasBranches = chapters.some((c) => c.branch);
  // Bölüm, seçilen yolda mı (ortak bölümler her zaman)?
  const inPath = useCallback(
    (c: GuideChapterDef) => !c.branch || !branch || c.branch === branch,
    [branch],
  );

  const firstUnwatched = useCallback(
    (key: string) => {
      const ch = chapters.find((c) => c.key === key);
      if (!ch) return 0;
      const seen = new Set(played[key] ?? []);
      const idx = ch.steps.findIndex((_, i) => !seen.has(i));
      return idx === -1 ? 0 : idx;
    },
    [chapters, played],
  );

  const [stepIdx, setStepIdx] = useState(() => firstUnwatched(selectedKey));
  const [mode, setMode] = useState<Mode>("idle");
  const [muted, setMuted] = useState(false);
  // İmleç varışı adım kimliğine bağlı saklanır — yeni adımın kimliği farklı
  // olduğundan "sıfırlama" türetilir (effect içinde senkron setState gerekmez).
  const [cursorArrivedFor, setCursorArrivedFor] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fsRef = useRef<HTMLDivElement | null>(null);
  // Kararlılık refleri: ses efekti YALNIZ (bölüm, adım, oynuyor) değişince
  // kurulmalı. Callback kimlikleri (onProgress her render'da değişebilir)
  // efekti tetiklememeli — aksi halde izleme kaydının yanıtı geldiğinde çalan
  // ses baştan başlıyordu (2026-07-24 saha bulgusu: "tekrar + takılma").
  const stepIdxRef = useRef(0);
  const playedRef = useRef<Record<string, number[]>>({});
  const onProgressRef = useRef(onProgress);
  const mutedRef = useRef(muted);

  const step = chapter.steps[Math.min(stepIdx, chapter.steps.length - 1)];
  const highlight = boxFor(step.shot, step.target);
  const playing = mode === "playing";
  const stepId = `${chapter.key}:${stepIdx}`;
  const cursorAtTarget = cursorArrivedFor === stepId;

  const stopAudio = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    const a = audioRef.current;
    if (a) {
      a.onended = null;
      a.onerror = null;
      a.pause();
    }
  }, []);

  const markPlayed = useCallback((ck: string, idx: number) => {
    // Yan etki updater DIŞINDA (StrictMode updater'ı iki kez koşturabilir);
    // mükerrer koruması ref üzerinden.
    if ((playedRef.current[ck] ?? []).includes(idx)) return;
    // Sunucuya konum kaydı — sessiz, en-iyi-çaba (oturum düşse bile sonraki
    // girişte kaldığı adımdan devam edebilsin diye).
    void onProgressRef.current({ action: "watch", chapter: ck, step: idx }).catch(
      () => undefined,
    );
    setPlayed((prev) => {
      const cur = prev[ck] ?? [];
      if (cur.includes(idx)) return prev;
      return { ...prev, [ck]: [...cur, idx] };
    });
  }, []);

  const advance = useCallback(() => {
    const idx = stepIdxRef.current;
    markPlayed(chapter.key, idx);
    if (idx + 1 < chapter.steps.length) {
      setStepIdx(idx + 1);
    } else {
      setMode("end");
    }
  }, [chapter.steps.length, chapter.key, markPlayed]);
  const advanceRef = useRef(advance);

  // Ref senkronizasyonu — render'da değil, commit SONRASI (React Compiler kuralı).
  // Ses olay işleyicileri asenkron tetiklendiğinden değerler daima taze olur.
  useEffect(() => {
    onProgressRef.current = onProgress;
    playedRef.current = played;
    stepIdxRef.current = stepIdx;
    mutedRef.current = muted;
    advanceRef.current = advance;
  });

  // Tam ekran takibi (Esc ile çıkışları da yakalar)
  useEffect(() => {
    const onFs = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onFs);
    return () => document.removeEventListener("fullscreenchange", onFs);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) {
      void document.exitFullscreen();
    } else if (fsRef.current) {
      void fsRef.current.requestFullscreen().catch(() => undefined);
    }
  }, []);

  // Adım oynatma: ses varsa ses biter bitmez, yoksa tahmini süre sonunda ilerler.
  // Bağımlılıklar BİLİNÇLİ dar: yalnız (oynuyor, bölüm anahtarı, adım). Callback
  // kimlikleri ref'ten okunur — herhangi bir üst render sesi baştan BAŞLATMAZ.
  useEffect(() => {
    if (!playing) return;
    const current = chapter.steps[stepIdx];
    if (!current) return;

    let cancelled = false;
    const fallback = () => {
      if (cancelled) return;
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(
        () => advanceRef.current(),
        estimateDurationMs(current.caption),
      );
    };

    if (!audioRef.current) audioRef.current = new Audio();
    const a = audioRef.current;
    a.muted = mutedRef.current;
    a.onended = () => advanceRef.current();
    a.onerror = fallback;
    a.src = audioSrc(chapter.key, stepIdx);
    a.currentTime = 0;
    a.play().catch(fallback);

    return () => {
      cancelled = true;
      stopAudio();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- advance/muted ref'ten; chapter nesnesi yerine key
  }, [playing, chapter.key, stepIdx, stopAudio]);

  // Sessize alma çalan sesi KESMEDEN uygulanır (adımı baştan başlatmaz).
  useEffect(() => {
    if (audioRef.current) audioRef.current.muted = muted;
  }, [muted]);

  // İmleç koreografisi: adım başında köşede bekler, kısa gecikmeyle hedefe süzülür.
  const hasCursor = Boolean(step.click && highlight);
  useEffect(() => {
    if (!playing || !hasCursor) return;
    const t = setTimeout(() => setCursorArrivedFor(stepId), 700);
    return () => clearTimeout(t);
  }, [playing, hasCursor, stepId]);

  const begin = useCallback(() => {
    if (guide.state.status === "not_started" || guide.state.status === "dismissed") {
      void onProgress({ action: "start", chapter: chapter.key });
    }
    setMode("playing");
  }, [guide.state.status, onProgress, chapter.key]);

  const selectChapter = useCallback(
    (key: string) => {
      stopAudio();
      const target = chapters.find((c) => c.key === key);
      if (target?.branch) setBranch(target.branch);
      setSelectedKey(key);
      setStepIdx(firstUnwatched(key));
      setMode("idle");
    },
    [stopAudio, firstUnwatched, chapters],
  );

  const completeChapter = useCallback(async () => {
    await onProgress({ action: "chapter_done", chapter: chapter.key });
    // Yol seçimi olan bölüm: "sonraki" yok — koç kartta yolunu seçer.
    if (chapter.choice) {
      setMode("choice");
      return;
    }
    // Bir yoldaki bölümden sonra öbür yolun bölümleri atlanır.
    const mine = chapter.branch ?? branch;
    const next = chapters
      .slice(chapterIdx + 1)
      .find((c) => !c.branch || !mine || c.branch === mine);
    if (next) {
      selectChapter(next.key);
    } else {
      setMode("end");
    }
  }, [onProgress, chapter, chapters, chapterIdx, selectChapter, branch]);

  const chooseBranch = useCallback(
    (b: GuideBranch) => {
      setBranch(b);
      setShowOtherBranch(false);
      const first = chapters.find((c) => c.branch === b);
      if (first) {
        void onProgress({ action: "start", chapter: first.key });
        selectChapter(first.key);
      }
    },
    [chapters, onProgress, selectChapter],
  );

  const goStep = useCallback(
    (delta: number) => {
      setStepIdx((idx) => {
        const next = Math.max(0, Math.min(chapter.steps.length - 1, idx + delta));
        return next;
      });
      setMode((m) => (m === "end" || m === "choice" ? "playing" : m));
    },
    [chapter.steps.length],
  );

  // Rehber bitti mi: ortak bölümler + seçilen yolun bölümleri (yol seçilmediyse
  // herhangi bir yolun tamamı).
  const pathChapters = chapters.filter(inPath);
  const branchDone = (b: GuideBranch) =>
    chapters.filter((c) => c.branch === b).every((c) => doneSet.has(c.key));
  const allDone =
    chapters.filter((c) => !c.branch).every((c) => doneSet.has(c.key)) &&
    (!hasBranches || (branch ? branchDone(branch) : branchDone("gun-gun") || branchDone("havuz")));
  const isLastInPath = pathChapters[pathChapters.length - 1]?.key === chapter.key;
  const otherBranch: GuideBranch | null = branch ? (branch === "havuz" ? "gun-gun" : "havuz") : null;
  const visibleChapters = chapters.filter(
    (c) => !c.branch || !branch || c.branch === branch || showOtherBranch,
  );
  // Üç bilgi durumu (ENGEL DEĞİL): fresh = rehber başladıktan sonra gerçekten
  // yapıldı (yeşil) · already = rehberden önce zaten vardı (mavi) · hiçbiri =
  // henüz yapılmadı (amber öneri). Devam her durumda serbest.
  const requiredAction = chapter.action && !chapter.action.optional ? chapter.action : null;
  const fresh = requiredAction ? Boolean(guide.checklist[requiredAction.checkKey]) : true;
  const already =
    requiredAction && !fresh
      ? Boolean(guide.preexisting?.[requiredAction.checkKey])
      : false;
  const watchedCount = (played[chapter.key] ?? []).length;
  const watchedAll = watchedCount >= chapter.steps.length;

  const resumeUnwatched = useCallback(() => {
    setStepIdx(firstUnwatched(chapter.key));
    setMode("playing");
  }, [firstUnwatched, chapter.key]);

  return (
    <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
      {/* Bölüm listesi */}
      <aside className="order-2 lg:order-1">
        <div className="rounded-xl border bg-card p-2">
          <p className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Bölümler
          </p>
          <ul className="space-y-1">
            {visibleChapters.map((c, i) => {
              const done = doneSet.has(c.key);
              const active = c.key === selectedKey;
              const prev = visibleChapters[i - 1];
              const showModule = Boolean(c.module) && c.module !== prev?.module;
              const modChapters = showModule
                ? visibleChapters.filter((x) => x.module === c.module)
                : [];
              const showBranch = Boolean(c.branch) && c.branch !== prev?.branch;
              const isOther = Boolean(c.branch && branch && c.branch !== branch);
              // Öbür yolun katlanmış satırı: seçilen yolun son bölümünden sonra
              const lastOfMine =
                Boolean(branch) && c.branch === branch && visibleChapters[i + 1]?.branch !== branch;
              const modDone = modChapters.filter((x) => doneSet.has(x.key)).length;
              const modMinutes = showModule
                ? Math.max(
                    1,
                    Math.round(
                      modChapters.reduce(
                        (sum, x) =>
                          sum + x.steps.reduce((t, st) => t + estimateDurationMs(st.caption), 0),
                        0,
                      ) / 60000,
                    ),
                  )
                : 0;
              return (
                <li key={c.key}>
                  {showModule ? (
                    <div className="mt-2 flex items-baseline justify-between gap-2 border-t px-2 pb-1 pt-3 first:mt-0 first:border-t-0 first:pt-1">
                      <span className="text-xs font-semibold uppercase tracking-wide text-slate-700">
                        {c.module}
                      </span>
                      <span className="shrink-0 text-[11px] text-muted-foreground">
                        {modDone}/{modChapters.length} · ~{modMinutes} dk
                      </span>
                    </div>
                  ) : null}
                  {showBranch && c.branch ? (
                    <div
                      className={cn(
                        "mx-2 mb-1 mt-2 flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-semibold",
                        isOther
                          ? "bg-slate-500/10 text-slate-700"
                          : "bg-cyan-700 text-white",
                      )}
                    >
                      <GitBranch className="h-3.5 w-3.5 shrink-0" />
                      <span className="min-w-0 break-words">
                        Yol: {BRANCH_LABELS[c.branch]}
                        {isOther ? " (öbür yol)" : branch ? " — senin yolun" : ""}
                      </span>
                    </div>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => selectChapter(c.key)}
                    data-chapter={c.key}
                    className={cn(
                      "flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition",
                      active ? "bg-cyan-600 text-white" : "hover:bg-muted",
                      isOther && !active && "opacity-70",
                    )}
                  >
                    <span
                      className={cn(
                        "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold",
                        done
                          ? "border-emerald-500 bg-emerald-500 text-white"
                          : active
                            ? "border-white/70 text-white"
                            : "border-slate-300 text-slate-500",
                      )}
                    >
                      {done ? <Check className="h-3.5 w-3.5" /> : chapters.indexOf(c) + 1}
                    </span>
                    <span className="min-w-0">
                      <span className="block break-words font-medium">{c.title}</span>
                      <span
                        className={cn(
                          "block break-words text-[11px]",
                          active ? "text-cyan-100" : "text-muted-foreground",
                        )}
                      >
                        {c.subtitle}
                      </span>
                    </span>
                  </button>
                  {lastOfMine && otherBranch && !showOtherBranch ? (
                    <button
                      type="button"
                      onClick={() => setShowOtherBranch(true)}
                      data-section="guide-other-branch"
                      className="mx-2 mt-1 flex w-[calc(100%-1rem)] items-center gap-1.5 rounded-md border border-dashed border-slate-300 px-2 py-1.5 text-left text-[11px] text-muted-foreground hover:bg-muted"
                    >
                      <ChevronDown className="h-3.5 w-3.5 shrink-0" />
                      <span className="min-w-0 break-words">
                        Öbür yol: {BRANCH_LABELS[otherBranch]} (
                        {chapters.filter((x) => x.branch === otherBranch).length} bölüm) — göz at
                      </span>
                    </button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </div>
      </aside>

      {/* Sahne + kontroller (tam ekranda birlikte büyür) */}
      <div ref={fsRef} className="guide-fs order-1 min-w-0 lg:order-2">
        <div className="guide-stage relative aspect-[1440/900] w-full overflow-hidden rounded-xl border bg-slate-100">
          <Stage
            chapter={chapter}
            stepIdx={stepIdx}
            playing={playing}
            cursorAtTarget={cursorAtTarget}
          />

          {/* Tam ekran */}
          <button
            type="button"
            onClick={toggleFullscreen}
            aria-label={isFullscreen ? "Tam ekrandan çık" : "Tam ekran izle"}
            title={isFullscreen ? "Tam ekrandan çık" : "Tam ekran izle"}
            className="absolute right-2 top-2 z-30 rounded-lg bg-slate-950/60 p-2 text-white backdrop-blur-sm transition hover:bg-slate-950/80"
          >
            {isFullscreen ? <Minimize className="h-4 w-4" /> : <Maximize className="h-4 w-4" />}
          </button>

          {/* Başlat / devam overlay */}
          {mode === "idle" ? (
            <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-4 bg-slate-950/80 p-6 text-center backdrop-blur-sm">
              <GuideAvatar size={104} speaking={false} />
              <div>
                <p className="text-lg font-semibold text-white">
                  Bölüm {chapterIdx + 1}: {chapter.title}
                </p>
                <p className="mt-0.5 text-sm text-slate-200">{chapter.subtitle}</p>
              </div>
              <Button size="lg" className="bg-cyan-600 hover:bg-cyan-700" onClick={begin}>
                <Play className="mr-2 h-5 w-5" />
                {doneSet.has(chapter.key) || watchedAll
                  ? "Yeniden izle"
                  : watchedCount > 0
                    ? `Kaldığın yerden devam et (Adım ${stepIdx + 1})`
                    : "Bölümü başlat"}
              </Button>
            </div>
          ) : null}

          {/* Yol seçimi — programı gün gün mü havuzla mı kuracaksın */}
          {mode === "choice" && chapter.choice ? (
            <div
              className="absolute inset-0 z-20 flex items-center justify-center overflow-y-auto bg-slate-950/70 p-4"
              data-section="guide-branch-choice"
            >
              <div className="w-full max-w-2xl rounded-xl border bg-card p-5 shadow-2xl">
                <div className="flex items-start gap-3">
                  <GuideAvatar size={56} speaking={false} />
                  <div className="min-w-0">
                    <p className="font-semibold">{chapter.choice.prompt}</p>
                    <p className="text-sm text-muted-foreground">
                      Seçtiğin yolla devam ederiz. Öbür yolu bölüm listesinden istediğin zaman açabilirsin.
                    </p>
                  </div>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {chapter.choice.options.map((o) => {
                    const n = chapters.filter((c) => c.branch === o.branch).length;
                    return (
                      <button
                        key={o.branch}
                        type="button"
                        onClick={() => chooseBranch(o.branch)}
                        data-branch={o.branch}
                        className={cn(
                          "rounded-xl border-2 p-4 text-left transition hover:border-cyan-600 hover:bg-cyan-500/10",
                          branch === o.branch ? "border-cyan-600" : "border-border",
                        )}
                      >
                        <span className="flex items-center gap-2 font-semibold">
                          <GitBranch className="h-4 w-4 shrink-0 text-cyan-700" />
                          {o.label}
                        </span>
                        <span className="mt-1.5 block text-sm leading-snug text-muted-foreground">
                          {o.description}
                        </span>
                        <span className="mt-2 block text-xs font-medium text-cyan-800">
                          {n} bölüm →
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : null}

          {/* Bölüm sonu kartı */}
          {mode === "end" ? (
            <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/60 p-4">
              <div className="w-full max-w-md rounded-xl border bg-card p-5 shadow-2xl">
                {allDone && isLastInPath ? (
                  <CompletionCard
                    busy={busy}
                    onReset={() => onProgress({ action: "reset" })}
                  />
                ) : (
                  <>
                    <div className="flex items-start gap-3">
                      <GuideAvatar size={56} speaking={false} />
                      <div className="min-w-0">
                        <p className="font-semibold">
                          {requiredAction ? "Şimdi sıra sende!" : "Bölüm bitti"}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {requiredAction
                            ? "Aşağıdaki adımı gerçekten yap — ben kontrol edeceğim."
                            : "Hazır olduğunda bir sonraki bölüme geçelim."}
                        </p>
                      </div>
                    </div>

                    {!watchedAll && !doneSet.has(chapter.key) ? (
                      <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2.5">
                        <Eye className="h-4 w-4 shrink-0 text-slate-500" />
                        <p className="min-w-0 flex-1 text-xs text-slate-700">
                          Bu bölümde izlemediğin {chapter.steps.length - watchedCount} adım
                          var — istersen sonra dönüp izleyebilirsin.
                        </p>
                        <Button size="sm" variant="outline" onClick={resumeUnwatched}>
                          <Play className="mr-1.5 h-3.5 w-3.5" />
                          Kaldığım yerden izle
                        </Button>
                      </div>
                    ) : null}

                    {chapter.action?.optional ? (
                      <div className="mt-4 rounded-lg border border-sky-200 bg-sky-50 p-3">
                        <p className="text-sm font-medium text-sky-900">
                          İstersen şimdi dene (zorunlu değil): {chapter.action.label}
                        </p>
                        <p className="mt-1.5 text-xs leading-relaxed text-sky-800">
                          {chapter.action.hint}
                        </p>
                        <Button
                          size="sm"
                          variant="outline"
                          className="mt-2.5"
                          onClick={() => window.open(chapter.action!.href, "_blank")}
                        >
                          <ExternalLink className="mr-1.5 h-4 w-4" />
                          Sayfayı yeni sekmede aç
                        </Button>
                      </div>
                    ) : null}

                    {requiredAction ? (
                      <div
                        className={cn(
                          "mt-4 rounded-lg border p-3",
                          fresh
                            ? "border-emerald-200 bg-emerald-50"
                            : already
                              ? "border-sky-200 bg-sky-50"
                              : "border-amber-200 bg-amber-50",
                        )}
                      >
                        <div className="flex items-center gap-2">
                          {fresh ? (
                            <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600" />
                          ) : already ? (
                            <CheckCircle2 className="h-5 w-5 shrink-0 text-sky-600" />
                          ) : (
                            <RefreshCw
                              className={cn(
                                "h-5 w-5 shrink-0 text-amber-600",
                                refreshing && "animate-spin",
                              )}
                            />
                          )}
                          <p
                            className={cn(
                              "text-sm font-medium",
                              fresh
                                ? "text-emerald-900"
                                : already
                                  ? "text-sky-900"
                                  : "text-amber-900",
                            )}
                          >
                            {fresh
                              ? `${requiredAction.doneLabel} — harika!`
                              : already
                                ? "Bunu daha önce zaten yapmışsın."
                                : requiredAction.label}
                          </p>
                        </div>
                        {!fresh ? (
                          <>
                            <p
                              className={cn(
                                "mt-2 text-xs leading-relaxed",
                                already
                                  ? "text-sky-800"
                                  : "text-amber-800",
                              )}
                            >
                              {already
                                ? `Hesabında bu adımın izi var (${requiredAction.doneLabel.toLocaleLowerCase("tr")}). İstersen rehberle birlikte bir yenisini yaparak pekiştir, istersen doğrudan devam et. ${requiredAction.hint}`
                                : requiredAction.hint}
                            </p>
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                className="bg-cyan-600 hover:bg-cyan-700"
                                onClick={() => window.open(requiredAction.href, "_blank")}
                              >
                                <ExternalLink className="mr-1.5 h-4 w-4" />
                                Sayfayı yeni sekmede aç
                              </Button>
                              <Button size="sm" variant="outline" onClick={onRefresh} disabled={refreshing}>
                                <RefreshCw className={cn("mr-1.5 h-4 w-4", refreshing && "animate-spin")} />
                                Kontrol et
                              </Button>
                            </div>
                            <p className="mt-2 text-[11px] text-muted-foreground">
                              Yaptıktan sonra bu sekmeye dön — ben kendiliğimden fark ederim;
                              gerekirse &quot;Kontrol et&quot;e bas.
                            </p>
                          </>
                        ) : null}
                      </div>
                    ) : null}

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <Button
                        className="bg-emerald-600 hover:bg-emerald-700"
                        disabled={busy}
                        onClick={() => void completeChapter()}
                      >
                        <Check className="mr-1.5 h-4 w-4" />
                        {already && !fresh
                          ? "Zaten yapmışım — devam et"
                          : "Bölümü tamamla ve devam et"}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setStepIdx(0);
                          setMode("playing");
                        }}
                      >
                        <RotateCcw className="mr-1.5 h-4 w-4" />
                        Yeniden izle
                      </Button>
                    </div>
                  </>
                )}
              </div>
            </div>
          ) : null}
        </div>

        {/* Kontrol çubuğu */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => (playing ? setMode("paused") : mode === "end" || mode === "choice" ? begin() : setMode("playing"))}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </Button>
          <Button size="sm" variant="outline" disabled={stepIdx === 0} onClick={() => goStep(-1)}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={stepIdx >= chapter.steps.length - 1}
            onClick={() => goStep(1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button size="sm" variant="outline" onClick={() => setMuted((m) => !m)}>
            {muted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </Button>
          <div className="ml-1 flex items-center gap-1.5">
            {chapter.steps.map((s, i) => (
              <button
                key={i}
                type="button"
                aria-label={`Adım ${i + 1}`}
                onClick={() => {
                  setStepIdx(i);
                  if (mode === "end" || mode === "choice" || mode === "idle") setMode("playing");
                }}
                className={cn(
                  "h-2 rounded-full transition-all",
                  i === stepIdx ? "w-6 bg-cyan-600" : "w-2 bg-slate-300 hover:bg-slate-400",
                )}
              />
            ))}
          </div>
          <span className="ml-auto text-xs text-muted-foreground">
            Adım {Math.min(stepIdx + 1, chapter.steps.length)} / {chapter.steps.length}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Zoom dönüşümü: vurgu kutusunu sahne merkezine taşıyıp yakınlaştırır.
 * translate(%, kendi boyutuna göre) SONRA scale(origin=kutu merkezi) uygulanır;
 * çeviri, ölçekli görüntünün sahneyi terk etmemesi için kenarlara kırpılır.
 */
function zoomTransform(box: { x: number; y: number; w: number; h: number }): {
  transform: string;
  transformOrigin: string;
} {
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  const scale = Math.min(2.2, Math.max(1.25, Math.min(55 / box.w, 55 / box.h)));
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
  const tx = clamp(50 - cx, (100 - cx) * (1 - scale), cx * (scale - 1));
  const ty = clamp(50 - cy, (100 - cy) * (1 - scale), cy * (scale - 1));
  return {
    transform: `translate(${tx}%, ${ty}%) scale(${scale})`,
    transformOrigin: `${cx}% ${cy}%`,
  };
}

/** Sahne: ekran görüntüsü + vurgu + imleç + zoom + altyazı, ya da avatar sahnesi. */
function Stage({
  chapter,
  stepIdx,
  playing,
  cursorAtTarget,
}: {
  chapter: GuideChapterDef;
  stepIdx: number;
  playing: boolean;
  cursorAtTarget: boolean;
}) {
  const step = chapter.steps[Math.min(stepIdx, chapter.steps.length - 1)];
  const highlight = boxFor(step.shot, step.target);
  const cursorTarget =
    highlight != null
      ? { left: `${highlight.x + highlight.w / 2}%`, top: `${highlight.y + highlight.h / 2}%` }
      : null;
  const zoomStyle = step.zoom && highlight ? zoomTransform(highlight) : null;

  return (
    <>
      {step.shot ? (
        <div
          className="absolute inset-0 transition-transform duration-[1100ms] ease-[cubic-bezier(0.3,0.8,0.3,1)] will-change-transform"
          style={zoomStyle ?? { transform: "none" }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- /static (FastAPI) ekran görüntüsü */}
          <img
            src={shotSrc(step.shot)}
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
            draggable={false}
          />
          {highlight ? (
            <div
              className="absolute z-10 rounded-md ring-4 ring-amber-400/90 shadow-[0_0_0_9999px_rgba(15,23,42,0.30)] transition-all duration-500"
              style={{
                left: `${highlight.x}%`,
                top: `${highlight.y}%`,
                width: `${highlight.w}%`,
                height: `${highlight.h}%`,
              }}
            />
          ) : null}
          {step.click && cursorTarget ? (
            <div
              className="guide-cursor absolute z-10"
              style={
                cursorAtTarget
                  ? cursorTarget
                  : { left: "86%", top: "84%" }
              }
            >
              {cursorAtTarget ? (
                <span className="guide-click-ripple absolute -left-3 -top-3 h-9 w-9 rounded-full bg-cyan-400/50" />
              ) : null}
              <MousePointer2 className="relative h-7 w-7 fill-white text-slate-900 drop-shadow-lg" />
            </div>
          ) : null}
        </div>
      ) : (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-5 bg-gradient-to-br from-cyan-700 via-cyan-800 to-slate-900 p-6">
          <GuideAvatar size={140} speaking={playing} />
          <p className="max-w-xl text-center text-base font-medium leading-relaxed text-white sm:text-lg">
            {step.caption}
          </p>
        </div>
      )}

      {/* Altyazı + konuşan avatar (ekran görüntülü adımlar) */}
      {step.shot ? (
        <div className="absolute inset-x-0 bottom-0 z-10 flex items-end gap-3 bg-gradient-to-t from-slate-950/85 via-slate-950/50 to-transparent p-3 sm:p-4">
          <GuideAvatar size={64} speaking={playing} className="mb-0.5" />
          <p className="mb-1 min-w-0 flex-1 rounded-lg bg-slate-950/60 px-3 py-2 text-[13px] font-medium leading-snug text-white backdrop-blur-sm sm:text-sm">
            {step.caption}
          </p>
        </div>
      ) : null}
    </>
  );
}

function CompletionCard({ busy, onReset }: { busy: boolean; onReset: () => void }) {
  return (
    <div className="text-center">
      <div className="mx-auto flex justify-center">
        <GuideAvatar size={80} speaking={false} />
      </div>
      <p className="mt-3 flex items-center justify-center gap-1.5 text-lg font-semibold">
        <Sparkles className="h-5 w-5 text-amber-500" />
        Rehberi tamamladın!
      </p>
      <p className="mt-1 text-sm text-muted-foreground">
        Artık temel akışın tamamını biliyorsun: kitap, atama, program, yayın, takip
        ve deneme. Bölümleri istediğin zaman yeniden izleyebilirsin.
      </p>
      <p className="mt-2 text-xs text-muted-foreground">
        Yakında: Rota&apos;ya buradan soru da sorabileceksin.
      </p>
      <Button
        variant="outline"
        size="sm"
        className="mt-4"
        disabled={busy}
        onClick={onReset}
      >
        <RotateCcw className="mr-1.5 h-4 w-4" />
        Rehberi baştan başlat
      </Button>
    </div>
  );
}
