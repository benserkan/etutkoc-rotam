"use client";

import * as React from "react";
import { ChevronDown, ExternalLink, PlaySquare, X } from "lucide-react";

import { cn } from "@/lib/utils";

interface VideoRef {
  id: number;
  title: string;
  url: string;
  duration_min: number | null;
  role: string;
}

/**
 * Video Sepeti'nden gelen çok videolu görev — her video ayrı bağlantı.
 * Tek videolu görevde çağıran taraf mevcut "Videoyu izle" düğmesini kullanır.
 * Soru çözümü videoları farklı renkle işaretlenir (koç kararı).
 *
 * `collapsible`: liste tek satırlık özete katlanır (koç gün kartı — konu
 * eklendikçe kart uzamasın); özete tıklayınca numaralı liste açılır.
 */
export function TaskVideoLinks({
  videos,
  className,
  collapsible = false,
  onRemove,
  removingId,
}: {
  videos: VideoRef[];
  className?: string;
  collapsible?: boolean;
  /** Koç yüzeyi: videoyu görevden çıkar (sepete döner). Verilmezse düğme yok. */
  onRemove?: (v: VideoRef) => void;
  removingId?: number | null;
}) {
  const [open, setOpen] = React.useState(!collapsible);
  if (videos.length < 2) return null;
  const totalMin = videos.reduce((s, v) => s + (v.duration_min ?? 0), 0);
  const soru = videos.filter((v) => v.role === "soru").length;

  return (
    <div className={cn("mt-1", className)}>
      {collapsible ? (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="inline-flex items-center gap-1 rounded-md bg-rose-600 px-2 py-0.5 text-[11px] font-semibold text-white hover:bg-rose-700"
          title={open ? "Video listesini kapat" : "Video listesini aç"}
        >
          <PlaySquare className="size-3" aria-hidden />
          {videos.length} video
          {totalMin > 0 ? ` · ${totalMin} dk` : ""}
          {soru > 0 ? ` · ${soru} soru çözümü` : ""}
          <ChevronDown className={cn("size-3 transition-transform", open && "rotate-180")} aria-hidden />
        </button>
      ) : null}
      {open ? (
        <ol className={cn("space-y-0.5", collapsible && "mt-1")}>
          {videos.map((v, i) => (
            <li key={v.id} className="flex items-start gap-1">
              <a
                href={v.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex max-w-full items-start gap-1 text-[12px] text-cyan-800 hover:underline dark:text-cyan-300"
              >
                <ExternalLink className="mt-0.5 size-3 shrink-0" aria-hidden />
                <span className="break-words">
                  {i + 1}. {v.title}
                  {v.duration_min ? ` · ${v.duration_min} dk` : ""}
                </span>
                {v.role === "soru" ? (
                  <span className="shrink-0 rounded bg-amber-600 px-1 text-[10px] font-semibold text-white">
                    soru çözümü
                  </span>
                ) : null}
              </a>
              {onRemove ? (
                <button
                  type="button"
                  onClick={() => onRemove(v)}
                  disabled={removingId === v.id}
                  title="Bu videoyu görevden çıkar (sepete döner)"
                  aria-label={`${v.title} videosunu görevden çıkar`}
                  className="mt-0.5 shrink-0 rounded p-0.5 text-muted-foreground hover:bg-rose-600 hover:text-white disabled:opacity-50"
                >
                  <X className="size-3" aria-hidden />
                </button>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
