"use client";

/**
 * Rota'nın Yorumu — veli asistanı P1 (tek kapı).
 *
 * İki sekme: Program | Denemeler. Rota (rehberdeki avatar) çocuğun durumunu
 * velinin dilinde anlatır: bölümlü metin + istenirse SESLİ anlatım.
 * - Okuma/tekrar dinleme ücretsiz (önbellek); üretim + ilk seslendirme koçun
 *   kredisinden düşer (günlük veli limiti backend'de).
 * - Yeni veri gelince (görev/deneme) "güncel değil" bandı + Yenile.
 * Eski "AI Durum Analizi" kartı bu karta gömüldü (kullanıcı kararı 2026-07-26).
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Pause, Play, RefreshCw, Sparkles, Volume2 } from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  type CommentaryKind,
  type ParentCommentaryResponse,
  generateParentCommentary,
  generateParentCommentaryVoice,
  getParentCommentary,
  parentCommentaryAudioUrl,
  parentP2Keys,
} from "@/lib/api/parent";
import { GuideAvatar } from "@/components/guide/guide-avatar";
import { RotaChat } from "@/components/parent/rota-chat";
import { cn } from "@/lib/utils";

type CardTab = CommentaryKind | "sohbet";

const KIND_TABS: { tab: CardTab; label: string }[] = [
  { tab: "program", label: "Program" },
  { tab: "deneme", label: "Denemeler" },
  { tab: "sohbet", label: "Rota'ya Sor" },
];

function errMessage(e: unknown): string {
  const code = e instanceof ApiError ? (e.detail?.code ?? null) : null;
  if (code === "daily_limit_reached")
    return "Bugünlük yorum hakkın doldu — yarın yeniden deneyebilirsin.";
  if (code === "ai_credit_exhausted")
    return "Rota bu ay için dinlenmede — koçun yapay zekâ kotası doldu. Yorumlar yeni dönemde devam eder.";
  if (code === "not_enough_data")
    return "Rota'nın yorumlayacağı veri henüz yok. Program yayınlandıkça ve denemeler eklendikçe burada anlatacak.";
  if (code === "ai_unavailable")
    return "Yapay zekâ servisi şu an kullanılamıyor, birkaç dakika sonra deneyin.";
  if (code === "commentary_changed")
    return "Yorum bu sırada yenilendi — Dinle'ye tekrar basın.";
  return e instanceof ApiError ? e.message : "Yorum oluşturulamadı, tekrar deneyin.";
}

export function RotaCommentaryCard({ studentId }: { studentId: number }) {
  const qc = useQueryClient();
  const [tab, setTab] = React.useState<CardTab>("program");
  const kind: CommentaryKind = tab === "sohbet" ? "program" : tab;
  const [err, setErr] = React.useState<string | null>(null);
  const [playing, setPlaying] = React.useState(false);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);

  const q = useQuery({
    queryKey: parentP2Keys.commentary(studentId, kind),
    queryFn: () => getParentCommentary(studentId, kind),
    enabled: tab !== "sohbet",
    staleTime: 30_000,
  });

  // setQueryData ile cache doğrudan güncellenir (yanıt yeni yorumu içerir)
  const genMut = useMutation({
    mutationFn: () => generateParentCommentary(studentId, kind),
    onMutate: () => {
      setErr(null);
      stopAudio();
    },
    onSuccess: (data) =>
      qc.setQueryData(parentP2Keys.commentary(studentId, kind), data),
    onError: (e) => {
      setErr(errMessage(e));
      // Sunucu tarafı kaydetmiş olabilir (dev proxy zaman aşımı) — anında +
      // gecikmeli yeniden eşitle
      const inv = () =>
        void qc.invalidateQueries({ queryKey: parentP2Keys.commentary(studentId, kind) });
      inv();
      setTimeout(inv, 8000);
      setTimeout(inv, 20000);
    },
  });

  // Ses üretimi yalnız commentary cache'ini tazeler (has_audio)
  const voiceMut = useMutation({
    mutationFn: () => generateParentCommentaryVoice(studentId, kind),
    onMutate: () => setErr(null),
    onSuccess: (res) => {
      qc.setQueryData(
        parentP2Keys.commentary(studentId, kind),
        (prev: ParentCommentaryResponse | undefined) =>
          prev?.commentary
            ? {
                ...prev,
                commentary: {
                  ...prev.commentary,
                  has_audio: res.has_audio,
                  audio_content_type: res.audio_content_type,
                },
              }
            : prev,
      );
      playAudio();
    },
    onError: (e) => {
      setErr(errMessage(e));
      void qc.invalidateQueries({ queryKey: parentP2Keys.commentary(studentId, kind) });
    },
  });

  const data = q.data;
  const commentary = data?.commentary ?? null;

  function stopAudio() {
    const a = audioRef.current;
    if (a) {
      a.pause();
      a.currentTime = 0;
    }
    setPlaying(false);
  }

  function playAudio() {
    const c = qc.getQueryData<ParentCommentaryResponse>(
      parentP2Keys.commentary(studentId, kind),
    )?.commentary;
    const bust = c?.generated_at ?? String(Date.now());
    const url = parentCommentaryAudioUrl(studentId, kind, bust);
    let a = audioRef.current;
    if (!a) {
      a = new Audio();
      a.onended = () => setPlaying(false);
      a.onpause = () => setPlaying(false);
      a.onplay = () => setPlaying(true);
      audioRef.current = a;
    }
    if (!a.src.includes(encodeURIComponent(bust))) a.src = url;
    void a.play().catch(() => setPlaying(false));
  }

  function onListen() {
    if (playing) {
      audioRef.current?.pause();
      return;
    }
    if (commentary?.has_audio) playAudio();
    else voiceMut.mutate();
  }

  // Sekme/yorum değişince çalan sesi durdur (yanlış sesi çalma)
  React.useEffect(() => {
    stopAudio();
    if (audioRef.current) audioRef.current.src = "";
  }, [tab, kind, commentary?.generated_at]);

  return (
    <section className="rounded-2xl border border-cyan-200 bg-cyan-50/40 p-5 dark:border-cyan-500/30 dark:bg-cyan-500/10">
      <div className="flex flex-wrap items-center gap-3">
        <GuideAvatar size={56} speaking={playing} />
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold text-cyan-950 dark:text-cyan-100">
            Rota&apos;nın Yorumu
          </h2>
          <p className="text-xs text-cyan-900/70 dark:text-cyan-200/70">
            Çocuğunun durumunu sizin dilinizde anlatır — okuyun ya da dinleyin.
          </p>
        </div>
        <div className="flex rounded-lg border border-cyan-200 bg-white p-0.5 dark:border-cyan-500/30 dark:bg-slate-900">
          {KIND_TABS.map((t) => (
            <button
              key={t.tab}
              type="button"
              onClick={() => setTab(t.tab)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-semibold transition",
                tab === t.tab
                  ? "bg-cyan-600 text-white"
                  : "text-slate-600 hover:text-slate-900 dark:text-slate-300",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4">
        {tab === "sohbet" ? (
          <RotaChat studentId={studentId} onOpenCommentary={(k) => setTab(k)} />
        ) : q.isLoading ? (
          <p className="text-sm text-muted-foreground">Yükleniyor…</p>
        ) : data && !data.ai_available ? (
          <p className="text-sm text-slate-700 dark:text-slate-300">
            {data.unavailable_reason ?? "Rota yorumu şu an kullanılamıyor."}
          </p>
        ) : commentary ? (
          <div className="space-y-4">
            {data?.is_stale ? (
              <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
                <AlertCircle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                Bu yorumdan sonra yeni gelişmeler oldu — güncel anlatım için
                yenileyin.
              </div>
            ) : null}

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onListen}
                disabled={voiceMut.isPending}
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-60"
              >
                {voiceMut.isPending ? (
                  <RefreshCw className="size-4 animate-spin" aria-hidden />
                ) : playing ? (
                  <Pause className="size-4" aria-hidden />
                ) : commentary.has_audio ? (
                  <Play className="size-4" aria-hidden />
                ) : (
                  <Volume2 className="size-4" aria-hidden />
                )}
                {voiceMut.isPending
                  ? "Rota hazırlanıyor…"
                  : playing
                    ? "Duraklat"
                    : commentary.has_audio
                      ? "Dinle"
                      : "Rota seslendirsin"}
              </button>
              <button
                type="button"
                onClick={() => genMut.mutate()}
                disabled={genMut.isPending}
                className="inline-flex items-center gap-1.5 rounded-xl border border-cyan-300 px-3 py-2 text-sm font-semibold text-cyan-800 hover:bg-cyan-100/60 disabled:opacity-60 dark:border-cyan-500/40 dark:text-cyan-200"
              >
                <RefreshCw
                  className={cn("size-3.5", genMut.isPending && "animate-spin")}
                  aria-hidden
                />
                {genMut.isPending ? "Yenileniyor…" : "Yenile"}
              </button>
            </div>

            <div className="space-y-3">
              {commentary.sections.map((s, i) => (
                <div key={i}>
                  <h3 className="text-sm font-semibold text-cyan-950 dark:text-cyan-100">
                    {s.title}
                  </h3>
                  <p className="mt-0.5 text-sm leading-relaxed text-slate-800 dark:text-slate-200">
                    {s.body}
                  </p>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-muted-foreground">
              Öneri amaçlıdır; kesin değerlendirme değildir. Sonucu yalnız siz
              görürsünüz.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-slate-700 dark:text-slate-300">
              {kind === "program"
                ? "Rota, çocuğunuzun haftalık program ilerlemesini — neyin yapıldığını, neyin aksadığını, evde nasıl destek olabileceğinizi — sizin dilinizde anlatır."
                : "Rota, deneme sonuçlarını ve konu analizini grafiklere boğulmadan anlamanız için derleyip anlatır."}
            </p>
            <button
              type="button"
              onClick={() => genMut.mutate()}
              disabled={genMut.isPending}
              className="inline-flex items-center gap-2 rounded-xl bg-cyan-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-60"
            >
              <Sparkles className="size-4" aria-hidden />
              {genMut.isPending ? "Rota hazırlıyor…" : "Rota yorumlasın"}
            </button>
          </div>
        )}

        {err ? (
          <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
            {err}
          </p>
        ) : null}
      </div>
    </section>
  );
}
