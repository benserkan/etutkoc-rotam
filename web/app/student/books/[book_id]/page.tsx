import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { apiServer } from "@/lib/api-server";
import type { BookCell, BookGridResponse } from "@/lib/types/student";
import { cn } from "@/lib/utils";

export const metadata = { title: "Kitap detayı" };
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<Record<string, string | string[] | undefined>>;
}

export default async function StudentBookGridPage({ params }: PageProps) {
  const p = await params;
  const raw = p.book_id;
  const bookIdStr = typeof raw === "string" ? raw : "";
  const bookId = Number(bookIdStr);
  if (!Number.isFinite(bookId) || bookId < 1) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm">
        Geçersiz kitap kimliği.
      </div>
    );
  }

  const grid = await apiServer<BookGridResponse>(
    `/api/v2/student/book-grid?book_id=${bookId}`,
  );
  const overallPct =
    grid.total_tests > 0
      ? Math.round((grid.total_completed / grid.total_tests) * 100)
      : 0;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/student/books"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="size-4" aria-hidden /> Kitaplara dön
        </Link>
      </div>

      <header className="space-y-1.5">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          {grid.subject_name}
        </p>
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
          {grid.book_name}
        </h1>
        <p className="text-sm text-muted-foreground tabular-nums">
          {grid.total_completed} tamam · {grid.total_reserved} rezerv ·{" "}
          {grid.total_tests} toplam ·{" "}
          <span className="font-medium text-foreground">%{overallPct}</span>
        </p>
        <div className="h-2 max-w-md rounded-full bg-muted overflow-hidden flex">
          <span
            className="bg-emerald-500"
            style={{
              width: `${(grid.total_completed / Math.max(grid.total_tests, 1)) * 100}%`,
            }}
            aria-hidden
          />
          <span
            className="bg-amber-400"
            style={{
              width: `${(grid.total_reserved / Math.max(grid.total_tests, 1)) * 100}%`,
            }}
            aria-hidden
          />
        </div>
      </header>

      <Legend />

      <div className="space-y-6">
        {grid.sections.map((sec) => (
          <section key={sec.section_id} className="space-y-2">
            <header className="flex items-baseline justify-between gap-2">
              <h2 className="font-medium">
                {sec.label}
                {sec.topic_name ? (
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    {sec.topic_name}
                  </span>
                ) : null}
              </h2>
              <p className="text-xs text-muted-foreground tabular-nums">
                {sec.completed} tamam · {sec.reserved} rezerv · {sec.test_count} toplam
              </p>
            </header>
            <ol
              className="grid gap-1.5"
              style={{
                gridTemplateColumns: "repeat(auto-fill, minmax(2rem, 1fr))",
              }}
              aria-label={`${sec.label} hücreleri`}
            >
              {sec.cells.map((c) => (
                <Cell key={c.number} cell={c} />
              ))}
            </ol>
          </section>
        ))}
      </div>
    </div>
  );
}

function Cell({ cell }: { cell: BookCell }) {
  const cls =
    cell.state === "DONE"
      ? "bg-emerald-500/20 text-emerald-800 border-emerald-500/40 dark:text-emerald-200"
      : cell.state === "RESERVED"
        ? "bg-amber-400/20 text-amber-900 border-amber-400/40 dark:text-amber-200"
        : "bg-muted text-muted-foreground border-border";
  const stateLabel =
    cell.state === "DONE" ? "tamam" : cell.state === "RESERVED" ? "rezerv" : "boş";
  const tooltip =
    cell.task_date
      ? `Test ${cell.number} · ${stateLabel} · ${cell.task_date}`
      : `Test ${cell.number} · ${stateLabel}`;
  return (
    <li
      className={cn(
        "h-8 grid place-items-center rounded border text-[10px] font-medium tabular-nums",
        cls,
      )}
      title={tooltip}
      aria-label={tooltip}
    >
      {cell.number}
    </li>
  );
}

function Legend() {
  return (
    <ul className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
      <li className="inline-flex items-center gap-1.5">
        <span className="size-3 rounded bg-emerald-500/20 border border-emerald-500/40" aria-hidden />
        Tamam
      </li>
      <li className="inline-flex items-center gap-1.5">
        <span className="size-3 rounded bg-amber-400/20 border border-amber-400/40" aria-hidden />
        Rezerv (planlanmış görev)
      </li>
      <li className="inline-flex items-center gap-1.5">
        <span className="size-3 rounded bg-muted border border-border" aria-hidden />
        Boş
      </li>
    </ul>
  );
}
