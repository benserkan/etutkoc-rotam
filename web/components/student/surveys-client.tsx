"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ClipboardList, Clock } from "lucide-react";

import { getStudentSurveys, surveyKeys } from "@/lib/api/surveys";
import type {
  StudentSurveysResponse,
  SurveyAssignmentRow,
} from "@/lib/types/survey";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/** Öğrenci — anket listesi (bekleyen + tamamlanan). */
export function StudentSurveysClient({
  initial,
}: {
  initial: StudentSurveysResponse;
}) {
  const q = useQuery({
    queryKey: surveyKeys.studentList(),
    queryFn: getStudentSurveys,
    initialData: initial,
  });
  const data = q.data ?? initial;

  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight font-display inline-flex items-center gap-2">
          <ClipboardList className="size-6 text-muted-foreground" aria-hidden />
          Anketlerim
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Koçunun gönderdiği tanıma anketleri. Doğru ya da yanlış cevap yok —
          seni en iyi anlatan seçeneği işaretle.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Seni bekleyenler</CardTitle>
        </CardHeader>
        <CardContent>
          {data.pending.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              Şu an bekleyen anket yok.
            </p>
          ) : (
            <ul className="space-y-2">
              {data.pending.map((a) => (
                <SurveyRow key={a.id} row={a} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {data.completed.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Tamamladıkların</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {data.completed.map((a) => (
                <SurveyRow key={a.id} row={a} done />
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function SurveyRow({ row, done }: { row: SurveyAssignmentRow; done?: boolean }) {
  const started = row.status === "in_progress";
  return (
    <li>
      <Link
        href={`/student/surveys/${row.id}`}
        className="flex items-center gap-3 rounded-lg border border-border p-3 hover:border-cyan-300 hover:bg-muted/40 transition"
      >
        {done ? (
          <CheckCircle2 className="size-5 shrink-0 text-emerald-600" aria-hidden />
        ) : (
          <Clock className="size-5 shrink-0 text-amber-600" aria-hidden />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium truncate">{row.template.title}</p>
          <p className="text-xs text-muted-foreground">
            {done
              ? `Tamamlandı${row.completed_at ? ` · ${fmtDate(row.completed_at)}` : ""} — sonucunu gör`
              : started
                ? `Devam ediyor · ${row.answered_count}/${row.template.question_count} soru cevaplandı`
                : `${row.template.question_count} soru · ~${row.template.estimated_minutes} dk`}
          </p>
          {!done && row.note ? (
            <p className="mt-1 text-xs rounded-md border border-cyan-200 bg-cyan-50 text-cyan-900 px-2 py-1">
              Koçundan not: {row.note}
            </p>
          ) : null}
        </div>
        <span className="shrink-0 text-xs font-medium text-cyan-700">
          {done ? "Sonuç →" : started ? "Devam et →" : "Başla →"}
        </span>
      </Link>
    </li>
  );
}

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "2-digit", year: "numeric" });
}
