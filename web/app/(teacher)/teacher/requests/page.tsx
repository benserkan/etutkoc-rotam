import Link from "next/link";

import { apiServer } from "@/lib/api-server";
import type { TeacherRequestListResponse } from "@/lib/types/teacher";
import { RequestsInbox } from "@/components/teacher/requests-inbox-client";
import { DemoHint } from "@/components/demos/demo-hint";

/**
 * /teacher/requests — talep gelen kutusu.
 *
 * Bekleyen görünümünde iki bölüm: onay isteyen değişiklik talepleri ve
 * onay beklemeyen soru/not mesajları (Gördüm / Cevapla satır içinde).
 *
 * Filtreler URL search params üzerinden:
 *   ?status=pending&type=change&student_id=...&page=2
 */
export const dynamic = "force-dynamic";

export const metadata = {
  title: "Talepler",
};

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const STATUS_CHIPS: Array<{ value: string; label: string }> = [
  { value: "pending", label: "Bekleyen" },
  { value: "approved", label: "Onaylanan" },
  { value: "rejected", label: "Reddedilen" },
  { value: "withdrawn", label: "Geri çekilen" },
  { value: "resolved", label: "Cevaplandı" },
  { value: "all", label: "Tümü" },
];

function firstStr(v: string | string[] | undefined): string | undefined {
  if (Array.isArray(v)) return v[0];
  return v;
}

function toInt(v: string | undefined): number | undefined {
  if (!v) return undefined;
  const n = Number(v);
  return Number.isFinite(n) ? n : undefined;
}

export default async function TeacherRequestsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const status = firstStr(sp.status) ?? "pending";
  const type = firstStr(sp.type);
  const studentId = toInt(firstStr(sp.student_id));
  const page = toInt(firstStr(sp.page)) ?? 1;

  const qs = new URLSearchParams();
  qs.set("status", status);
  if (type && type !== "all") qs.set("type", type);
  if (studentId !== undefined) qs.set("student_id", String(studentId));
  if (page > 1) qs.set("page", String(page));

  const data = await apiServer<TeacherRequestListResponse>(
    `/api/v2/teacher/requests?${qs.toString()}`,
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          Talepler
        </h1>
        <p className="text-sm text-muted-foreground">
          {data.pending_count} talep onayını bekliyor ·{" "}
          {data.open_question_count ?? 0} yeni mesaj
          {status !== "pending" ? <> · bu filtrede {data.total} kayıt</> : null}
        </p>
        <DemoHint contextKey="requests" role="teacher" />
      </header>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-xs uppercase tracking-wide text-muted-foreground">
          Durum
        </span>
        {STATUS_CHIPS.map((c) => {
          const next = new URLSearchParams();
          next.set("status", c.value);
          if (type && type !== "all") next.set("type", type);
          if (studentId !== undefined) next.set("student_id", String(studentId));
          const href = "/teacher/requests?" + next.toString();
          const active = status === c.value;
          return (
            <Link
              key={c.value}
              href={href}
              className={
                "rounded-full px-3 py-1 border transition-colors " +
                (active
                  ? "border-foreground bg-foreground text-background"
                  : "border-border text-muted-foreground hover:bg-muted hover:text-foreground")
              }
            >
              {c.label}
            </Link>
          );
        })}
      </div>

      <RequestsInbox items={data.items} status={status} />

      <Pager
        page={data.page}
        hasNext={data.has_next}
        baseQueryString={qs.toString()}
      />
    </div>
  );
}

function Pager({
  page,
  hasNext,
  baseQueryString,
}: {
  page: number;
  hasNext: boolean;
  baseQueryString: string;
}) {
  function withPage(p: number): string {
    const next = new URLSearchParams(baseQueryString);
    if (p <= 1) next.delete("page");
    else next.set("page", String(p));
    return "/teacher/requests?" + next.toString();
  }
  return (
    <nav className="flex items-center justify-end gap-2 text-sm" aria-label="Sayfalama">
      {page > 1 ? (
        <Link
          href={withPage(page - 1)}
          className="rounded-md border border-border px-3 py-1.5 hover:bg-muted"
        >
          ← Önceki
        </Link>
      ) : null}
      <span className="text-muted-foreground">Sayfa {page}</span>
      {hasNext ? (
        <Link
          href={withPage(page + 1)}
          className="rounded-md border border-border px-3 py-1.5 hover:bg-muted"
        >
          Sonraki →
        </Link>
      ) : null}
    </nav>
  );
}
