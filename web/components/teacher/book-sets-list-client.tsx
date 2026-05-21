"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus, Users } from "lucide-react";

import { getLibraryBookSets, libraryKeys } from "@/lib/api/library";
import { useCreateBookSet } from "@/lib/hooks/use-library-mutations";
import type {
  BookSetGradeBucket,
  BookSetListItem,
  BookSetListResponse,
} from "@/lib/types/library";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  INITIAL_TARGET_GRADE,
  TargetGradePicker,
  targetGradeBody,
  type TargetGradeValue,
} from "@/components/target-grade-picker";

interface Props {
  initial: BookSetListResponse;
}

export function BookSetsListClient({ initial }: Props) {
  const q = useQuery<BookSetListResponse>({
    queryKey: libraryKeys.bookSets(),
    queryFn: () => getLibraryBookSets(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const [open, setOpen] = React.useState(false);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight font-display">
            Kitap setleri
          </h1>
          <p className="text-sm text-muted-foreground">
            Birden çok kitabı bir grupta toplamak için kullan (örn. &quot;LGS 8. sınıf paketi&quot;).
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>
          <Plus className="size-4" aria-hidden />
          Yeni set
        </Button>
      </header>

      {data.items.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Henüz setiniz yok.
          </CardContent>
        </Card>
      ) : (
        <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.items.map((s) => (
            <li key={s.id}>
              <BookSetCard set={s} />
            </li>
          ))}
        </ul>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Yeni kitap seti</DialogTitle>
          </DialogHeader>
          <NewSetForm onDone={() => setOpen(false)} />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function BookSetCard({ set: s }: { set: BookSetListItem }) {
  return (
    <Link href={`/teacher/library/book-sets/${s.id}`} className="group block">
      <Card className="hover:border-foreground/30 transition-colors h-full">
        <CardContent className="p-4 space-y-2">
          <div className="flex items-start justify-between gap-2">
            <p className="font-medium truncate group-hover:underline flex-1">
              {s.name}
            </p>
            <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted text-muted-foreground whitespace-nowrap">
              {s.target_grade_label_tr}
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>{s.book_count} kitap</span>
            <span aria-hidden>·</span>
            <span className="inline-flex items-center gap-1">
              <Users className="size-3.5" aria-hidden />
              {s.student_count} öğrenci
            </span>
          </div>
          {s.grade_distribution.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {s.grade_distribution.map((g) => (
                <GradeChip key={`${g.grade_level ?? "n"}-${g.is_graduate}`} bucket={g} />
              ))}
            </div>
          ) : null}
          {s.notes ? (
            <p className="text-xs text-muted-foreground line-clamp-2 pt-2 border-t border-border">
              {s.notes}
            </p>
          ) : null}
        </CardContent>
      </Card>
    </Link>
  );
}

function GradeChip({ bucket }: { bucket: BookSetGradeBucket }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[11px] text-foreground/80">
      <span>{bucket.label_tr}</span>
      <span className="text-muted-foreground">·</span>
      <span className="tabular-nums">{bucket.student_count}</span>
    </span>
  );
}

function NewSetForm({ onDone }: { onDone: () => void }) {
  const mut = useCreateBookSet();
  const [name, setName] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const [grade, setGrade] = React.useState<TargetGradeValue>(INITIAL_TARGET_GRADE);
  const [error, setError] = React.useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Set adı zorunlu.");
      return;
    }
    const body = targetGradeBody(grade);
    if (
      body.target_grade_min !== null &&
      body.target_grade_max !== null &&
      body.target_grade_min > body.target_grade_max
    ) {
      setError("Min sınıf maks sınıftan büyük olamaz.");
      return;
    }
    mut.mutate(
      {
        body: {
          name: name.trim(),
          notes: notes.trim() || null,
          ...body,
        },
      },
      { onSuccess: () => onDone() },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1">
        <Label htmlFor="ns-name">Set adı</Label>
        <Input
          id="ns-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          required
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="ns-notes">Açıklama (opsiyonel)</Label>
        <Input
          id="ns-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>
      <TargetGradePicker
        value={grade}
        onChange={setGrade}
        idPrefix="ns-tg"
      />
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex items-center justify-end gap-2 pt-2 border-t border-border">
        <Button type="button" variant="ghost" onClick={onDone} disabled={mut.isPending}>
          İptal
        </Button>
        <Button type="submit" disabled={mut.isPending}>
          {mut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          Oluştur
        </Button>
      </div>
    </form>
  );
}
