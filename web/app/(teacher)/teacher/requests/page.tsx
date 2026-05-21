import Link from "next/link";

import { apiServer } from "@/lib/api-server";
import type {
  TeacherRequestListItem,
  TeacherRequestListResponse,
} from "@/lib/types/teacher";
import {
  REQUEST_STATUS_LABELS_TR,
  REQUEST_TYPE_LABELS_TR,
} from "@/lib/types/teacher";
import { Card, CardContent } from "@/components/ui/card";

/**
 * /teacher/requests — talep listesi (Paket 5: read-only).
 *
 * Filtreler URL search params üzerinden:
 *   ?status=pending&type=change&student_id=...&page=2
 *
 * Onaylama/Reddetme/Cevaplama akışları Paket 7'de eklenir.
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
          {data.pending_count} bekleyen · sayfada {data.items.length} · toplam{" "}
          {data.total}
        </p>
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

      <Card>
        <CardContent className="p-0">
          {data.items.length === 0 ? (
            <p className="p-6 text-sm text-muted-foreground">
              Bu filtrede talep yok.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {data.items.map((r) => (
                <RequestRow key={r.id} r={r} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <Pager
        page={data.page}
        hasNext={data.has_next}
        baseQueryString={qs.toString()}
      />
    </div>
  );
}

function RequestRow({ r }: { r: TeacherRequestListItem }) {
  return (
    <li>
      <Link
        href={`/teacher/requests/${r.id}`}
        className="grid grid-cols-12 items-center gap-3 px-4 py-3 hover:bg-muted transition-colors"
      >
        <span className="col-span-12 sm:col-span-3 text-sm font-medium truncate">
          {r.student_name}
        </span>
        <span className="col-span-6 sm:col-span-2 text-xs uppercase tracking-wide text-muted-foreground">
          {REQUEST_TYPE_LABELS_TR[r.type]}
        </span>
        <span className="col-span-6 sm:col-span-4 text-xs text-muted-foreground truncate">
          {r.task_title ?? "—"}
        </span>
        <span className="hidden sm:block sm:col-span-2 text-xs">
          {REQUEST_STATUS_LABELS_TR[r.status]}
        </span>
        <span className="hidden sm:block sm:col-span-1 text-[11px] text-muted-foreground tabular-nums text-right">
          {r.created_at.slice(0, 10)}
        </span>
      </Link>
    </li>
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
