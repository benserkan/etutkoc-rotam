"use client";

import * as React from "react";
import { BookOpenCheck, ChevronDown, Layers } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ResourceSidebar as ResourceSidebarData } from "@/lib/types/student";

interface Props {
  data: ResourceSidebarData;
  /** Mobil drawer modunda padding'i farklı uygulamak için. */
  variant?: "sticky" | "drawer";
}

/**
 * Kaynak Durumu yapışkan sidebar — öğrenciye atanmış tüm kitapların
 * total / reserved / completed / remaining özetini ders bazlı accordion ile
 * gösterir.
 *
 * Sözleşme:
 *   - Yalnız OKUMA — invalidate ile gelen yeni veriyi anında yansıtır.
 *   - Accordion state'i local — sayfa yenilemelerinde sıfırlanır (kullanıcı
 *     kasıtlı tercih: hep ilk ders açılır).
 */
export function ResourceSidebar({ data, variant = "sticky" }: Props) {
  const subjects = data.subjects;
  const [openSubjectId, setOpenSubjectId] = React.useState<number | null>(
    subjects.length > 0 ? subjects[0].subject_id : null,
  );

  return (
    <aside
      className={cn(
        "w-full",
        variant === "sticky"
          ? "lg:sticky lg:top-[3.75rem] lg:self-start lg:max-h-[calc(100vh-4.5rem)] lg:overflow-y-auto"
          : "",
      )}
      aria-label="Kaynak Durumu"
    >
      <div className="rounded-lg border border-border bg-card">
        <div className="px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Layers className="size-4 text-muted-foreground" aria-hidden="true" />
            Kaynak Durumu
          </div>
          <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <Metric label="Toplam" value={data.total_tests} />
            <Metric label="Kalan" value={data.remaining_tests} accent="muted" />
            <Metric label="Rezerv" value={data.reserved_tests} accent="dikkat" />
            <Metric label="Tamam" value={data.completed_tests} accent="yolunda" />
          </div>
        </div>

        {subjects.length === 0 ? (
          <p className="px-4 py-6 text-sm text-muted-foreground">
            Henüz size kitap atanmamış.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {subjects.map((s) => {
              const isOpen = openSubjectId === s.subject_id;
              return (
                <li key={s.subject_id}>
                  <button
                    type="button"
                    onClick={() => setOpenSubjectId(isOpen ? null : s.subject_id)}
                    className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-muted/40 transition-colors"
                    aria-expanded={isOpen}
                  >
                    <ChevronDown
                      className={cn(
                        "size-4 shrink-0 text-muted-foreground transition-transform",
                        isOpen ? "" : "-rotate-90",
                      )}
                      aria-hidden="true"
                    />
                    <span className="flex-1 truncate text-sm font-medium">
                      {s.subject_name}
                    </span>
                    <span className="text-[11px] tabular-nums text-muted-foreground">
                      {s.completed_tests}/{s.total_tests}
                    </span>
                  </button>
                  {isOpen ? (
                    <div className="px-4 pb-3 space-y-2">
                      {s.books.map((b) => {
                        const pct =
                          b.total_tests > 0
                            ? Math.round((b.completed_tests / b.total_tests) * 100)
                            : 0;
                        return (
                          <div key={b.student_book_id} className="space-y-1">
                            <div className="flex items-center gap-2 text-xs">
                              <BookOpenCheck className="size-3.5 text-muted-foreground shrink-0" aria-hidden="true" />
                              <span className="flex-1 truncate font-medium">
                                {b.book_name}
                              </span>
                              <span className="tabular-nums text-muted-foreground">
                                %{pct}
                              </span>
                            </div>
                            <div className="h-1.5 rounded-full bg-muted overflow-hidden flex">
                              <span
                                className="bg-emerald-500"
                                style={{
                                  width: `${(b.completed_tests / Math.max(b.total_tests, 1)) * 100}%`,
                                }}
                                aria-hidden="true"
                              />
                              <span
                                className="bg-amber-400"
                                style={{
                                  width: `${(b.reserved_tests / Math.max(b.total_tests, 1)) * 100}%`,
                                }}
                                aria-hidden="true"
                              />
                            </div>
                            <div className="flex items-center gap-3 text-[10px] text-muted-foreground tabular-nums">
                              <span>Tamam {b.completed_tests}</span>
                              <span>Rezerv {b.reserved_tests}</span>
                              <span>Kalan {b.remaining_tests}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}

function Metric({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: "muted" | "dikkat" | "yolunda";
}) {
  const color =
    accent === "yolunda"
      ? "text-emerald-600"
      : accent === "dikkat"
        ? "text-amber-600"
        : "text-foreground";
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="opacity-70">{label}</span>
      <span className={cn("font-semibold tabular-nums", color)}>{value}</span>
    </div>
  );
}
