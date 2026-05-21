import { notFound } from "next/navigation";
import Link from "next/link";

import { apiServer } from "@/lib/api-server";
import { ApiError } from "@/lib/api";
import type {
  TeacherRequestDetail,
  TeacherTaskItem,
} from "@/lib/types/teacher";
import {
  REQUEST_STATUS_LABELS_TR,
  REQUEST_TYPE_LABELS_TR,
} from "@/lib/types/teacher";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RequestActionBar } from "@/components/teacher/request-action-bar";

/**
 * /teacher/requests/[id] — talep detayı (Paket 5: read-only iskelet).
 *
 * Aksiyon butonları (Onayla/Reddet/Cevapla) disabled placeholder olarak
 * görünür; mutation hook'ları Paket 7'de eklenir.
 */
export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ id: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { id } = await params;
  return { title: `Talep #${id}` };
}

export default async function TeacherRequestDetailPage({ params }: PageProps) {
  const { id } = await params;
  const numericId = Number(id);
  if (!Number.isInteger(numericId) || numericId <= 0) notFound();

  let req: TeacherRequestDetail;
  try {
    req = await apiServer<TeacherRequestDetail>(
      `/api/v2/teacher/requests/${encodeURIComponent(String(numericId))}`,
    );
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            <Link href="/teacher/requests" className="hover:underline">
              Talepler
            </Link>
            {" · "}#{req.id}
          </p>
          <h1 className="text-2xl font-semibold tracking-tight font-display">
            {REQUEST_TYPE_LABELS_TR[req.type]}
            <span className="ml-2 text-base text-muted-foreground font-normal">
              · {REQUEST_STATUS_LABELS_TR[req.status]}
            </span>
          </h1>
          <p className="text-sm text-muted-foreground">
            <Link
              href={`/teacher/students/${req.student_id}`}
              className="hover:underline"
            >
              {req.student_name}
            </Link>
            {" · "}
            <span title={req.student_email}>{req.student_email}</span>
          </p>
        </div>
        <RequestActionBar req={req} />
      </header>

      {req.message ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Öğrencinin mesajı</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-line">{req.message}</p>
          </CardContent>
        </Card>
      ) : null}

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Mevcut görev</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {req.task_id ? (
              <>
                <p>
                  <span className="text-muted-foreground">Başlık: </span>
                  <Link
                    href={`/teacher/students/${req.student_id}/day?date=${req.task_date}`}
                    className="hover:underline font-medium"
                  >
                    {req.task_title ?? "—"}
                  </Link>
                </p>
                <p className="text-muted-foreground">Tarih: {req.task_date}</p>
                {req.current_items.length > 0 ? (
                  <ItemList items={req.current_items} />
                ) : null}
              </>
            ) : (
              <p className="text-muted-foreground">
                Bu talep bir görevle eşleşmiyor (yeni görev önerisi olabilir).
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Önerilen değişiklik</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5 text-sm">
            <ProposedRow
              label="Yeni kitap"
              value={req.proposed_book_name}
            />
            <ProposedRow
              label="Yeni bölüm"
              value={req.proposed_section_label}
            />
            <ProposedRow
              label="Yeni sayı"
              value={
                req.proposed_count !== null ? String(req.proposed_count) : null
              }
            />
            <ProposedRow label="Önerilen tarih" value={req.proposed_date} />
          </CardContent>
        </Card>
      </section>

      {req.teacher_response ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Öğretmen yanıtı</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            <p className="whitespace-pre-line">{req.teacher_response}</p>
            {req.responded_at ? (
              <p className="mt-2 text-xs text-muted-foreground">
                {req.responded_at.slice(0, 19).replace("T", " ")}
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <p className="text-xs text-muted-foreground">
        Talep tarihi: {req.created_at.slice(0, 19).replace("T", " ")}
        {req.status !== "pending" ? " · Yanıtlandı" : ""}
      </p>
    </div>
  );
}

function ProposedRow({
  label,
  value,
}: {
  label: string;
  value: string | null;
}) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="col-span-2 font-medium">{value ?? "—"}</span>
    </div>
  );
}

function ItemList({ items }: { items: TeacherTaskItem[] }) {
  return (
    <ul className="border-t border-border pt-2 mt-2 space-y-1">
      {items.map((it) => (
        <li
          key={it.id}
          className="grid grid-cols-12 items-center gap-2 text-xs"
        >
          <span className="col-span-7 truncate">
            {it.book_name}
            {it.section_label ? ` · ${it.section_label}` : ""}
          </span>
          <span className="col-span-3 tabular-nums text-muted-foreground">
            {it.completed_count}/{it.planned_count}
          </span>
          <span className="col-span-2 tabular-nums text-right text-muted-foreground">
            ünite +{it.section_remaining}
          </span>
        </li>
      ))}
    </ul>
  );
}
