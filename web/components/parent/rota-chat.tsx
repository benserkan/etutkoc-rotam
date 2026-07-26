"use client";

/**
 * Rota'ya Sor (P2+P3) — veli sohbeti (Rota kartının sekmesi).
 *
 * P2: kredisiz kural-tabanlı karşılama + hazır çipler; soru başına 3 kredi
 * (koç havuzundan, günde 10 soru). "Yorumla" çipleri P1 önbelleğine köprü.
 * P3: sesli soru (mikrofon → metin, input kutusuna dolar — otomatik
 * GÖNDERİLMEZ) + her Rota cevabında "Dinle" (ilk dinlemede ses üretilir ve
 * saklanır; tekrar dinleme kredisiz). Ses kaydı SAKLANMAZ.
 */
import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mic, Pause, RefreshCw, Send, Square, Volume2 } from "lucide-react";

import { ApiError } from "@/lib/api";
import {
  type ChatMessage,
  type CommentaryKind,
  type ParentChatResponse,
  askParentChat,
  getParentChat,
  parentChatAudioUrl,
  parentChatKeys,
  parentChatMessageVoice,
  transcribeParentChat,
} from "@/lib/api/parent";
import { GuideAvatar } from "@/components/guide/guide-avatar";
import { cn } from "@/lib/utils";

function errMessage(e: unknown): string {
  const code = e instanceof ApiError ? (e.detail?.code ?? null) : null;
  if (code === "daily_limit_reached")
    return e instanceof ApiError
      ? e.message
      : "Bugünlük soru hakkın doldu — yarın yeniden sorabilirsin.";
  if (code === "ai_credit_exhausted")
    return "Rota bu ay için dinlenmede — koçun yapay zekâ kotası doldu.";
  if (code === "ai_unavailable")
    return "Yapay zekâ servisi şu an kullanılamıyor, birkaç dakika sonra deneyin.";
  if (code === "voice_unreadable")
    return "Ses anlaşılamadı — daha net konuşup tekrar dener misin?";
  return e instanceof ApiError ? e.message : "Cevap alınamadı, tekrar deneyin.";
}

/** Tarayıcının desteklediği kayıt biçimi (codec eki backend'e GÖNDERİLMEZ). */
function pickAudioMime(): { mime: string; media: string } | null {
  if (typeof MediaRecorder === "undefined") return null;
  const candidates: Array<[string, string]> = [
    ["audio/webm", "audio/webm"],
    ["audio/mp4", "audio/mp4"],
    ["audio/ogg", "audio/ogg"],
  ];
  for (const [mime, media] of candidates) {
    if (MediaRecorder.isTypeSupported(mime)) return { mime, media };
  }
  return null;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const s = String(reader.result ?? "");
      resolve(s.includes(",") ? s.slice(s.indexOf(",") + 1) : s);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

export function RotaChat({
  studentId,
  onOpenCommentary,
}: {
  studentId: number;
  /** "Yorumla" çipi → kartın Program/Denemeler sekmesine köprü (kredisiz). */
  onOpenCommentary: (kind: CommentaryKind) => void;
}) {
  const qc = useQueryClient();
  const [text, setText] = React.useState("");
  const [err, setErr] = React.useState<string | null>(null);
  const endRef = React.useRef<HTMLDivElement | null>(null);

  // --- P3: kayıt (sesli soru) ---
  const [recording, setRecording] = React.useState(false);
  const [recSecs, setRecSecs] = React.useState(0);
  const recRef = React.useRef<MediaRecorder | null>(null);
  const chunksRef = React.useRef<Blob[]>([]);
  const streamRef = React.useRef<MediaStream | null>(null);
  const timerRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  // --- P3: dinleme (cevap balonu sesi) ---
  const audioRef = React.useRef<HTMLAudioElement | null>(null);
  const [playingId, setPlayingId] = React.useState<number | null>(null);
  const [voicePendingId, setVoicePendingId] = React.useState<number | null>(null);

  const q = useQuery({
    queryKey: parentChatKeys.thread(studentId),
    queryFn: () => getParentChat(studentId),
    staleTime: 15_000,
  });
  const data = q.data;

  // Yanıt yeni mesajları içerir → cache doğrudan güncellenir
  const askMut = useMutation({
    mutationFn: (message: string) => askParentChat(studentId, message),
    onMutate: () => setErr(null),
    onSuccess: (res) => {
      qc.setQueryData(
        parentChatKeys.thread(studentId),
        (prev: ParentChatResponse | undefined) =>
          prev
            ? {
                ...prev,
                messages: [...prev.messages, ...res.messages],
                daily_left: res.daily_left,
              }
            : prev,
      );
      setText("");
    },
    onError: (e) => {
      setErr(errMessage(e));
      // Sunucu kaydetmiş olabilir (dev proxy zaman aşımı: istemci hata görür,
      // backend geç bitirir) — anında + gecikmeli yeniden eşitle
      const inv = () =>
        void qc.invalidateQueries({ queryKey: parentChatKeys.thread(studentId) });
      inv();
      setTimeout(inv, 8000);
      setTimeout(inv, 20000);
    },
  });

  // eslint-disable-next-line lgs/missing-invalidate -- transcribe sunucu durumunu değiştirmez (metin input kutusuna dolar)
  const transcribeMut = useMutation({
    mutationFn: ({ b64, media }: { b64: string; media: string }) =>
      transcribeParentChat(studentId, b64, media),
    onMutate: () => setErr(null),
    onSuccess: (res) => {
      const t = res.text.trim();
      if (t) setText((prev) => (prev ? `${prev} ${t}` : t));
      else setErr("Ses anlaşılamadı — daha net konuşup tekrar dener misin?");
    },
    onError: (e) => setErr(errMessage(e)),
  });

  const messages: ChatMessage[] = data?.messages ?? [];

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages.length, askMut.isPending]);

  // Unmount: kayıt + çalma temizliği
  React.useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      try {
        recRef.current?.stop();
      } catch {
        /* yoksay */
      }
      streamRef.current?.getTracks().forEach((t) => t.stop());
      audioRef.current?.pause();
    };
  }, []);

  function send(message: string) {
    const m = message.trim();
    if (m.length < 2 || askMut.isPending) return;
    askMut.mutate(m);
  }

  function onChip(action: "ask" | "commentary", payload: string) {
    if (action === "commentary") {
      onOpenCommentary(payload as CommentaryKind);
      return;
    }
    send(payload);
  }

  async function startRecording() {
    const picked = pickAudioMime();
    if (!picked || !navigator.mediaDevices) {
      setErr("Tarayıcın ses kaydını desteklemiyor — soruyu yazarak sorabilirsin.");
      return;
    }
    setErr(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setErr("Mikrofona erişilemedi — tarayıcı izinlerini kontrol et.");
      return;
    }
    streamRef.current = stream;
    chunksRef.current = [];
    const rec = new MediaRecorder(stream, { mimeType: picked.mime });
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      if (timerRef.current) clearInterval(timerRef.current);
      setRecording(false);
      const blob = new Blob(chunksRef.current, { type: picked.mime });
      chunksRef.current = [];
      if (blob.size < 1000) return; // çok kısa/boş kayıt — sessiz geç
      try {
        const b64 = await blobToBase64(blob);
        transcribeMut.mutate({ b64, media: picked.media });
      } catch {
        setErr("Kayıt işlenemedi, tekrar dener misin?");
      }
    };
    recRef.current = rec;
    rec.start();
    setRecording(true);
    setRecSecs(0);
    timerRef.current = setInterval(() => setRecSecs((s) => s + 1), 1000);
  }

  function stopRecording() {
    try {
      recRef.current?.stop();
    } catch {
      setRecording(false);
    }
  }

  async function toggleListen(m: ChatMessage) {
    if (playingId === m.id) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    audioRef.current?.pause();
    setPlayingId(null);
    setVoicePendingId(m.id);
    setErr(null);
    try {
      // İlk dinlemede üretir (kredi); ses hazırsa sunucu ücretsiz döner
      await parentChatMessageVoice(studentId, m.id);
      const a = new Audio(parentChatAudioUrl(studentId, m.id));
      audioRef.current = a;
      a.onended = () => setPlayingId(null);
      a.onerror = () => {
        setPlayingId(null);
        setErr("Ses yüklenemedi, tekrar dener misin?");
      };
      await a.play();
      setPlayingId(m.id);
      // has_audio işaretini tazele (rozet/ikon durumu)
      qc.setQueryData(
        parentChatKeys.thread(studentId),
        (prev: ParentChatResponse | undefined) =>
          prev
            ? {
                ...prev,
                messages: prev.messages.map((x) =>
                  x.id === m.id ? { ...x, has_audio: true } : x,
                ),
              }
            : prev,
      );
    } catch (e) {
      setErr(errMessage(e));
    } finally {
      setVoicePendingId(null);
    }
  }

  if (q.isLoading) {
    return <p className="text-sm text-muted-foreground">Yükleniyor…</p>;
  }
  if (data && !data.ai_available) {
    return (
      <p className="text-sm text-slate-700 dark:text-slate-300">
        {data.unavailable_reason ?? "Rota sohbeti şu an kullanılamıyor."}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {/* Mesajlar + karşılama */}
      <div className="max-h-80 space-y-2.5 overflow-y-auto pr-1">
        {data?.greeting ? (
          <div className="flex items-start gap-2">
            <GuideAvatar size={28} speaking={false} />
            <div className="rounded-2xl rounded-tl-sm border border-cyan-200 bg-white px-3 py-2 text-sm text-slate-800 dark:border-cyan-500/30 dark:bg-slate-900 dark:text-slate-200">
              {data.greeting.text}
            </div>
          </div>
        ) : null}
        {messages.map((m) => (
          <div
            key={m.id}
            className={cn(
              "flex items-start gap-2",
              m.role === "veli" && "justify-end",
            )}
          >
            {m.role === "rota" ? (
              <GuideAvatar size={28} speaking={playingId === m.id} />
            ) : null}
            <div
              className={cn(
                "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm",
                m.role === "veli"
                  ? "rounded-tr-sm bg-cyan-600 text-white"
                  : "rounded-tl-sm border border-cyan-200 bg-white text-slate-800 dark:border-cyan-500/30 dark:bg-slate-900 dark:text-slate-200",
              )}
            >
              {m.body}
              {m.role === "rota" ? (
                <button
                  type="button"
                  onClick={() => void toggleListen(m)}
                  disabled={voicePendingId !== null && voicePendingId !== m.id}
                  className="mt-1.5 flex items-center gap-1 text-[11px] font-medium text-cyan-700 hover:text-cyan-900 disabled:opacity-50 dark:text-cyan-300 dark:hover:text-cyan-200"
                >
                  {voicePendingId === m.id ? (
                    <>
                      <RefreshCw className="size-3 animate-spin" aria-hidden />
                      Ses hazırlanıyor…
                    </>
                  ) : playingId === m.id ? (
                    <>
                      <Pause className="size-3" aria-hidden />
                      Duraklat
                    </>
                  ) : (
                    <>
                      <Volume2 className="size-3" aria-hidden />
                      Dinle
                    </>
                  )}
                </button>
              ) : null}
            </div>
          </div>
        ))}
        {askMut.isPending ? (
          <div className="flex items-start gap-2">
            <GuideAvatar size={28} speaking />
            <div className="rounded-2xl rounded-tl-sm border border-cyan-200 bg-white px-3 py-2 text-sm text-slate-500 dark:border-cyan-500/30 dark:bg-slate-900">
              <RefreshCw className="mr-1.5 inline size-3.5 animate-spin" aria-hidden />
              Rota düşünüyor…
            </div>
          </div>
        ) : null}
        <div ref={endRef} />
      </div>

      {/* Hazır çipler */}
      {data?.greeting?.chips?.length ? (
        <div className="flex flex-wrap gap-1.5">
          {data.greeting.chips.map((c) => (
            <button
              key={c.id}
              type="button"
              disabled={askMut.isPending}
              onClick={() => onChip(c.action, c.payload)}
              className="rounded-full border border-cyan-300 bg-white px-3 py-1 text-xs font-medium text-cyan-800 hover:bg-cyan-50 disabled:opacity-50 dark:border-cyan-500/40 dark:bg-slate-900 dark:text-cyan-200"
            >
              {c.label}
            </button>
          ))}
        </div>
      ) : null}

      {/* Giriş */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
        className="flex items-center gap-2"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={
            recording
              ? "Dinliyorum… bitince kareye bas"
              : "Rota'ya sor… (örn. Programa uyuyor mu?)"
          }
          maxLength={500}
          disabled={askMut.isPending || (data?.daily_left ?? 0) <= 0}
          className="h-10 flex-1 rounded-xl border border-cyan-200 bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 dark:border-cyan-500/30 dark:bg-slate-900 dark:text-slate-100"
        />
        {transcribeMut.isPending ? (
            <span className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-cyan-200 bg-white px-3 text-xs font-medium text-cyan-700 dark:border-cyan-500/30 dark:bg-slate-900 dark:text-cyan-300">
              <RefreshCw className="size-4 animate-spin" aria-hidden />
              Çevriliyor…
            </span>
        ) : recording ? (
          <button
            type="button"
            onClick={stopRecording}
            className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-rose-600 px-3 text-xs font-semibold text-white hover:bg-rose-700"
          >
            <Square className="size-4" aria-hidden />
            <span className="tabular-nums">
              {Math.floor(recSecs / 60)}:{String(recSecs % 60).padStart(2, "0")}
            </span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void startRecording()}
            disabled={askMut.isPending || (data?.daily_left ?? 0) <= 0}
            title="Sesli sor — konuşman yazıya çevrilip kutuya dolar"
            className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-300 bg-white text-cyan-700 hover:bg-cyan-50 disabled:opacity-50 dark:border-cyan-500/40 dark:bg-slate-900 dark:text-cyan-300"
          >
            <Mic className="size-4" aria-hidden />
            <span className="sr-only">Sesli sor</span>
          </button>
        )}
        <button
          type="submit"
          disabled={askMut.isPending || text.trim().length < 2}
          className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-cyan-600 px-4 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
        >
          <Send className="size-4" aria-hidden />
          Sor
        </button>
      </form>

      <div className="flex items-center justify-between">
        <p className="text-[11px] text-muted-foreground">
          Rota yalnız çocuğunun verilerine dayanır; koçun özel notları görülmez.
          Ses kaydın saklanmaz.
        </p>
        <p className="text-[11px] tabular-nums text-muted-foreground">
          Bugün kalan soru: {data?.daily_left ?? 0}
        </p>
      </div>

      {err ? (
        <p className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-500/10 dark:text-rose-300">
          {err}
        </p>
      ) : null}
    </div>
  );
}
