"use client";

import { PlayCircle } from "lucide-react";

import { cn } from "@/lib/utils";
import { demoFor, demoPlayUrl, type DemoRole } from "@/lib/demos";

/**
 * Panel-içi "▶ Nasıl kullanılır?" rozeti (başucu kaynağı).
 *
 * contextKey + role'e karşılık YAYINLANMIŞ demo varsa rozet çıkar; yeni sekmede
 * /demos?play={slug} açar (kullanıcı panelden ayrılmaz). Demo yoksa hiçbir şey
 * render etmez → slot kodda hazır kalır, video gelince otomatik belirir.
 *
 * Kullanım: <DemoHint contextKey="program" role="teacher" />
 */
export function DemoHint({
  contextKey,
  role,
  label = "Nasıl kullanılır?",
  className,
}: {
  contextKey: string;
  role: DemoRole;
  label?: string;
  className?: string;
}) {
  const demo = demoFor(contextKey, role);
  if (!demo) return null;

  return (
    <a
      href={demoPlayUrl(demo.slug)}
      target="_blank"
      rel="noopener noreferrer"
      title={`${demo.title} · ${demo.durationLabel}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-cyan-300 bg-cyan-50 px-3 py-1 text-xs font-medium text-cyan-800 transition hover:bg-cyan-100 hover:text-cyan-900",
        className,
      )}
    >
      <PlayCircle className="size-3.5" aria-hidden />
      {label}
      <span className="text-cyan-600">· {demo.durationLabel}</span>
    </a>
  );
}
