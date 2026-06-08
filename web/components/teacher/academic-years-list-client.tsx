"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus, Trash2 } from "lucide-react";

import {
  academicKeys,
  getAcademicYearChoices,
  getAcademicYears,
} from "@/lib/api/academic";
import {
  useCreateAcademicYear,
  useDeleteAcademicYear,
} from "@/lib/hooks/use-academic-mutations";
import type {
  AcademicYearChoicesResponse,
  AcademicYearListResponse,
} from "@/lib/types/academic";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DemoHint } from "@/components/demos/demo-hint";

interface Props {
  initialList: AcademicYearListResponse;
  initialChoices: AcademicYearChoicesResponse;
}

export function AcademicYearsListClient({ initialList, initialChoices }: Props) {
  const listQ = useQuery<AcademicYearListResponse>({
    queryKey: academicKeys.years(),
    queryFn: () => getAcademicYears(),
    initialData: initialList,
    staleTime: 30_000,
  });
  const choicesQ = useQuery<AcademicYearChoicesResponse>({
    queryKey: academicKeys.yearChoices(),
    queryFn: () => getAcademicYearChoices(),
    initialData: initialChoices,
    staleTime: 30_000,
  });
  const create = useCreateAcademicYear();
  const list = listQ.data ?? initialList;
  const choices = choicesQ.data ?? initialChoices;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          Plan zaman ekseni
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          Akademik yıllar
        </h1>
        <p className="text-sm text-muted-foreground">
          Eylül-Ağustos eksenli akademik yıllar + dönem (faz) tanımları.
          Şu an: {choices.current_start_year}-{choices.current_start_year + 1}.
        </p>
        <DemoHint contextKey="academic-years" role="teacher" className="mt-1.5" />
      </header>

      <Card>
        <CardContent className="p-4 space-y-2">
          <h2 className="text-base font-medium">Hızlı yıl ekle</h2>
          <p className="text-sm text-muted-foreground">
            Aşağıdaki yıllardan birini tıklayarak hesabına ekle.
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            {choices.items.map((c) => (
              <Button
                key={c.start_year}
                variant={c.exists ? "ghost" : "outline"}
                size="sm"
                disabled={c.exists || create.isPending}
                onClick={() =>
                  create.mutate({ body: { start_year: c.start_year } })
                }
              >
                {create.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : c.exists ? null : (
                  <Plus className="size-4" aria-hidden />
                )}
                {c.label}
                {c.exists ? " · ekli" : ""}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {list.items.length === 0 ? (
            <p className="text-sm text-muted-foreground p-4">
              Henüz kayıtlı akademik yıl yok.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {list.items.map((y) => (
                <YearRow key={y.id} year={y} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function YearRow({
  year,
}: {
  year: AcademicYearListResponse["items"][number];
}) {
  const del = useDeleteAcademicYear(year.id);
  function onDelete() {
    if (
      !window.confirm(
        `"${year.name}" akademik yılını silmek istediğinize emin misiniz?`,
      )
    ) {
      return;
    }
    del.mutate();
  }
  return (
    <li className="px-4 py-3 flex items-center gap-3 text-sm">
      <Link
        href={`/teacher/academic-years/${year.id}`}
        className="flex-1 min-w-0 hover:underline"
      >
        <span className="font-medium truncate block">{year.name}</span>
        <span className="text-xs text-muted-foreground">
          {year.phase_count} dönem · {year.student_count} öğrenci
          {year.exam_label !== "—" ? ` · ${year.exam_label}` : ""}
          {year.is_active ? "" : " · pasif"}
        </span>
      </Link>
      <Button
        variant="ghost"
        size="sm"
        onClick={onDelete}
        disabled={del.isPending}
        aria-label="Yılı sil"
      >
        {del.isPending ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <Trash2 className="size-4" aria-hidden />
        )}
      </Button>
    </li>
  );
}
