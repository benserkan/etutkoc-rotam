import Link from "next/link";
import { BookOpenCheck, ChevronRight } from "lucide-react";

import { apiServer } from "@/lib/api-server";
import type { BookType, StudentBooksResponse } from "@/lib/types/student";
import { cn } from "@/lib/utils";

const BOOK_TYPE_LABEL: Record<BookType, string> = {
  soru_bankasi: "Soru bankası",
  fasikul: "Fasikül",
  konu_anlatimli: "Konu anlatımlı",
  brans_denemesi: "Branş denemesi",
  genel_deneme: "Genel deneme",
};

export const metadata = { title: "Kitaplar" };
export const dynamic = "force-dynamic";

export default async function StudentBooksPage() {
  const data = await apiServer<StudentBooksResponse>("/api/v2/student/books");
  const overallPct =
    data.total_tests > 0
      ? Math.round((data.completed_tests / data.total_tests) * 100)
      : 0;

  return (
    <div className="space-y-6">
      <header className="space-y-2">
        <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
          Kitaplarım
        </h1>
        <p className="text-sm text-muted-foreground">
          Sana atanmış tüm kitaplar — derslere göre gruplandırılmış. Her kitabın
          ilerleme detayına tıklayarak ulaşabilirsin.
        </p>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <Pill label="Toplam test" value={data.total_tests} />
          <Pill label="Tamam" value={data.completed_tests} accent="yolunda" />
          <Pill label="Rezerv" value={data.reserved_tests} accent="dikkat" />
          <Pill label="Kalan" value={data.remaining_tests} />
          <span className="ml-auto text-sm tabular-nums">
            <span className="font-medium">%{overallPct}</span> tamam
          </span>
        </div>
      </header>

      {data.subjects.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border bg-card px-4 py-10 text-center text-sm text-muted-foreground">
          Henüz size kitap atanmamış. Koçunla iletişime geçin.
        </div>
      ) : (
        <div className="space-y-6">
          {data.subjects.map((s) => (
            <section key={s.subject_id} className="space-y-3">
              <header className="flex items-baseline justify-between">
                <h2 className="font-display text-lg font-semibold tracking-tight">
                  {s.subject_name}
                </h2>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {s.completed_tests} / {s.total_tests} test ·{" "}
                  {s.reserved_tests} rezerv
                </p>
              </header>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {s.books.map((b) => {
                  const pct =
                    b.total_tests > 0
                      ? Math.round((b.completed_tests / b.total_tests) * 100)
                      : 0;
                  return (
                    <Link
                      key={b.student_book_id}
                      href={`/student/books/${b.book_id}`}
                      className="group rounded-lg border border-border bg-card p-4 transition-colors hover:bg-muted/40"
                    >
                      <div className="flex items-start gap-2.5">
                        <BookOpenCheck className="size-5 text-muted-foreground shrink-0 mt-0.5" aria-hidden />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium truncate group-hover:underline">
                            {b.book_name}
                          </p>
                          <p className="text-[11px] uppercase tracking-wide text-muted-foreground mt-0.5">
                            {BOOK_TYPE_LABEL[b.book_type]}
                          </p>
                        </div>
                        <ChevronRight className="size-4 text-muted-foreground/60 mt-0.5" aria-hidden />
                      </div>

                      <div className="mt-3 space-y-1.5">
                        <div className="h-2 rounded-full bg-muted overflow-hidden flex">
                          <span
                            className="bg-emerald-500"
                            style={{
                              width: `${(b.completed_tests / Math.max(b.total_tests, 1)) * 100}%`,
                            }}
                            aria-hidden
                          />
                          <span
                            className="bg-amber-400"
                            style={{
                              width: `${(b.reserved_tests / Math.max(b.total_tests, 1)) * 100}%`,
                            }}
                            aria-hidden
                          />
                        </div>
                        <div className="flex items-center justify-between text-xs tabular-nums">
                          <span className="text-muted-foreground">
                            Tamam {b.completed_tests} · Rezerv {b.reserved_tests} · Kalan {b.remaining_tests}
                          </span>
                          <span className="font-medium">%{pct}</span>
                        </div>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function Pill({
  label,
  value,
  accent,
}: {
  label: string;
  value: number;
  accent?: "yolunda" | "dikkat";
}) {
  const tone =
    accent === "yolunda"
      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
      : accent === "dikkat"
        ? "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
        : "bg-muted text-foreground";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs tabular-nums",
        tone,
      )}
    >
      <span className="opacity-70">{label}</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}
