"use client";

/**
 * Anasayfa tanıtım videosu — karşılama modalı + hero altı kalıcı bölüm.
 *
 * Akış: ilk ziyarette (gecikmeli) modal açılır, video SESSİZ otomatik başlar
 * (tarayıcılar sesli otomatik oynatmayı engeller; video altyazılı olduğu için
 * sessizde de anlaşılır) — "Sesi aç" ile baştan sesli devam eder. Modal
 * kapanınca video hero'nun hemen altındaki kalıcı bölümde oynatılmaya hazır
 * durur.
 *
 * Telemetri (mevcut landing altyapısı; gizli `tanitim-videosu` kartı taşır):
 *   impression → modal/bölüm göründü · view → oynatıldı
 *   demo_click → yarısı izlendi      · cta_click → CTA'ya basıldı
 */

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { PlayCircle, Sparkles, Volume2, X } from "lucide-react";

import { sendLandingTelemetry } from "@/lib/api/landing";
import { cn } from "@/lib/utils";

const VIDEO_SRC = "/static/video/rotam-tanitim.mp4";
const POSTER_SRC = "/static/video/rotam-tanitim-poster.jpg";
const SLUG = "tanitim-videosu";
/** Kalıcı "bir daha gösterme" işareti (checkbox işaretliyken). */
const LS_KEY = "rotam_tour_video_v1";
/** Oturumluk işaret (checkbox kaldırılmışsa yalnız bu sekmede susar). */
const SS_KEY = "rotam_tour_video_session";
const OPEN_DELAY_MS = 2500;

/** Aynı olayı bir kez gönderen yardımcı (video başına). */
function useVideoTelemetry(variant: string | null) {
  const sent = React.useRef<Set<string>>(new Set());
  return React.useCallback(
    (event: string) => {
      if (sent.current.has(event)) return;
      sent.current.add(event);
      sendLandingTelemetry(SLUG, event, variant);
    },
    [variant],
  );
}

function TourVideo({
  variant,
  autoPlayMuted = false,
  className,
  videoRef,
}: {
  variant: string | null;
  autoPlayMuted?: boolean;
  className?: string;
  videoRef?: React.RefObject<HTMLVideoElement | null>;
}) {
  const innerRef = React.useRef<HTMLVideoElement | null>(null);
  const ref = videoRef ?? innerRef;
  const track = useVideoTelemetry(variant);
  const [muted, setMuted] = React.useState(autoPlayMuted);

  function onTimeUpdate(e: React.SyntheticEvent<HTMLVideoElement>) {
    const el = e.currentTarget;
    if (el.duration > 0 && el.currentTime / el.duration >= 0.5) {
      track("demo_click"); // yarısı izlendi = anlamlı izleme
    }
  }

  function unmute() {
    const el = ref.current;
    if (!el) return;
    el.muted = false;
    el.currentTime = 0;
    setMuted(false);
    void el.play().catch(() => {});
    track("view");
  }

  return (
    <div className={cn("relative w-full min-w-0 overflow-hidden rounded-2xl bg-black", className)}>
      <video
        ref={ref}
        className="block aspect-video h-auto w-full bg-black"
        src={VIDEO_SRC}
        poster={POSTER_SRC}
        controls
        playsInline
        preload="metadata"
        autoPlay={autoPlayMuted || undefined}
        muted={autoPlayMuted ? muted : undefined}
        onPlay={() => track("view")}
        onTimeUpdate={onTimeUpdate}
      />
      {autoPlayMuted && muted ? (
        <button
          type="button"
          onClick={unmute}
          className="absolute inset-x-0 top-5 mx-auto flex w-fit items-center gap-2 rounded-full bg-cyan-600 px-6 py-3 text-base font-bold text-white shadow-xl ring-2 ring-white/40 transition hover:bg-cyan-500"
        >
          <Volume2 className="size-5" aria-hidden />
          Sesi aç
        </button>
      ) : null}
    </div>
  );
}

/* ───────────────────────── Karşılama modalı ───────────────────────── */

export function WelcomeVideoModal({ variant }: { variant: string | null }) {
  const [open, setOpen] = React.useState(false);
  const [dontShow, setDontShow] = React.useState(true);
  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const track = useVideoTelemetry(variant);

  React.useEffect(() => {
    let seen = false;
    try {
      seen =
        window.localStorage.getItem(LS_KEY) === "1" ||
        window.sessionStorage.getItem(SS_KEY) === "1";
    } catch {
      seen = false; // depolama kapalıysa modal yine de bir kez gösterilir
    }
    if (seen) return;
    const t = window.setTimeout(() => setOpen(true), OPEN_DELAY_MS);
    return () => window.clearTimeout(t);
  }, []);

  const close = React.useCallback(() => {
    setOpen(false);
    videoRef.current?.pause();
    try {
      window.sessionStorage.setItem(SS_KEY, "1");
      if (dontShow) window.localStorage.setItem(LS_KEY, "1");
    } catch {
      // depolama yoksa sessizce geç
    }
  }, [dontShow]);

  React.useEffect(() => {
    if (!open) return;
    track("impression");
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, close, track]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/85 p-3 backdrop-blur-sm sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label="Tanıtım videosu"
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="flex max-h-[92vh] w-full min-w-0 max-w-5xl flex-col overflow-y-auto overscroll-contain rounded-2xl bg-slate-950 shadow-2xl ring-1 ring-white/10">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-white/10 px-4 py-3 sm:px-5">
          <div className="flex min-w-0 items-center gap-3">
            <Image
              src="/etutkoc-mark.svg"
              alt=""
              width={30}
              height={30}
              className="shrink-0"
            />
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-white">
                Hoş geldiniz — Rotam 3 dakikada
              </p>
              <p className="hidden truncate text-xs text-white/60 sm:block">
                Rota anlatıyor: ne yapar, nasıl yapar, siz ne kazanırsınız.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={close}
            aria-label="Kapat"
            className="shrink-0 rounded-full bg-white/10 p-2 text-white ring-1 ring-white/20 transition hover:bg-white/20"
          >
            <X className="size-5" aria-hidden />
          </button>
        </div>

        <TourVideo variant={variant} autoPlayMuted videoRef={videoRef} className="rounded-none" />

        <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t border-white/10 px-4 py-3 sm:px-5">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-white/70">
            <input
              type="checkbox"
              checked={dontShow}
              onChange={(e) => setDontShow(e.target.checked)}
              className="size-4 accent-cyan-500"
            />
            Bir daha gösterme
          </label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={close}
              className="rounded-full px-4 py-2 text-sm font-semibold text-white/70 transition hover:bg-white/10 hover:text-white"
            >
              Kapat
            </button>
            <Link
              href="/signup/teacher"
              onClick={() => track("cta_click")}
              className="inline-flex items-center gap-2 rounded-full bg-cyan-600 px-5 py-2.5 text-sm font-bold text-white transition hover:bg-cyan-500"
            >
              <Sparkles className="size-4 text-amber-300" aria-hidden />
              14 gün ücretsiz dene
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ──────────────────── Hero altı kalıcı video bölümü ──────────────────── */

export function TourVideoSection({ variant }: { variant: string | null }) {
  const track = useVideoTelemetry(variant);
  const secRef = React.useRef<HTMLElement | null>(null);

  React.useEffect(() => {
    const el = secRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          track("impression");
          io.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [track]);

  return (
    <section
      ref={secRef}
      id="tanitim"
      className="relative overflow-hidden bg-cyan-950 py-14 text-white lg:py-18"
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_50%_at_15%_0%,theme(colors.cyan.400/0.18),transparent_60%),radial-gradient(ellipse_50%_50%_at_100%_100%,theme(colors.amber.400/0.12),transparent_60%)]"
        aria-hidden
      />
      <div className="relative mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold text-cyan-100 backdrop-blur">
            <PlayCircle className="size-3.5 text-amber-300" aria-hidden />
            3 dakikalık tanıtım
          </span>
          <h2 className="mt-4 font-display text-3xl font-extrabold tracking-tight sm:text-4xl">
            Anlatmak yerine göstereyim
          </h2>
          <p className="mt-3 text-base leading-relaxed text-cyan-100/85 sm:text-lg">
            Rota, sistemi baştan sona anlatıyor: deneme karnesinin yapay zekâyla
            analizi, kitaba bağlı haftalık program, yanlış soru arşivi, veli
            tarafı ve kurum panosu.
          </p>
        </div>

        <div className="mx-auto mt-8 max-w-4xl">
          <TourVideo
            variant={variant}
            className="shadow-2xl shadow-black/40 ring-1 ring-white/15"
          />
        </div>

        <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/signup/teacher"
            onClick={() => track("cta_click")}
            className="inline-flex items-center gap-2 rounded-full bg-white px-6 py-3 font-bold text-cyan-900 transition hover:-translate-y-0.5 hover:bg-cyan-50"
          >
            <Sparkles className="size-4 text-amber-500" aria-hidden />
            14 gün ücretsiz dene
          </Link>
          <Link
            href="/pricing?type=kurum#kurumsal"
            onClick={() => track("cta_click")}
            className="inline-flex items-center gap-2 rounded-full border border-white/25 px-6 py-3 font-semibold text-white transition hover:-translate-y-0.5 hover:bg-white/10"
          >
            Kurumsal teklif alın
          </Link>
        </div>
      </div>
    </section>
  );
}
