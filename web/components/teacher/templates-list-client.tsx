"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Trash2 } from "lucide-react";

import { getLibraryTemplates, libraryKeys } from "@/lib/api/library";
import {
  useDeleteTemplate,
  useVerifyTemplate,
} from "@/lib/hooks/use-library-mutations";
import type {
  BookTemplateListItem,
  BookTemplateListResponse,
} from "@/lib/types/library";
import { LIBRARY_BOOK_TYPE_LABELS_TR } from "@/lib/types/library";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface Props {
  initial: BookTemplateListResponse;
}

export function TemplatesListClient({ initial }: Props) {
  const q = useQuery<BookTemplateListResponse>({
    queryKey: libraryKeys.templates(),
    queryFn: () => getLibraryTemplates(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight font-display">
            Kitap şablonları
          </h1>
          <p className="text-sm text-muted-foreground">
            Yeniden kullanılabilir bölüm şablonları. Bir şablon başka kitaplara
            uygulanabilir.
          </p>
        </div>
        <Link
          href="/teacher/library"
          className="text-sm underline-offset-4 hover:underline"
        >
          ← Kitap listesine dön
        </Link>
      </header>

      {data.items.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Henüz şablonunuz yok. Kitap detayında &quot;Şablon olarak kaydet&quot;
            ile veya AI önerisi alarak şablon biriktirebilirsiniz.
          </CardContent>
        </Card>
      ) : (
        <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {data.items.map((t) => (
            <li key={t.id}>
              <TemplateCard tpl={t} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TemplateCard({ tpl }: { tpl: BookTemplateListItem }) {
  const verifyMut = useVerifyTemplate();
  const deleteMut = useDeleteTemplate();

  function onDelete() {
    if (
      !window.confirm(
        `"${tpl.name}" şablonunu silmek istiyor musunuz?`,
      )
    ) {
      return;
    }
    deleteMut.mutate({ templateId: tpl.id });
  }

  return (
    <Card>
      <CardContent className="p-4 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {tpl.subject_name ?? "—"} ·{" "}
              {LIBRARY_BOOK_TYPE_LABELS_TR[tpl.type]}
            </p>
            <p className="font-medium leading-snug truncate">{tpl.name}</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onDelete}
            disabled={deleteMut.isPending}
            aria-label="Sil"
          >
            {deleteMut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Trash2 className="size-4" aria-hidden />
            )}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {tpl.section_count} bölüm
          {tpl.is_ai_generated ? " · AI tarafından üretildi" : ""}
        </p>
        {tpl.is_ai_generated && !tpl.is_verified ? (
          <div className="pt-2 border-t border-border flex items-center justify-between gap-2">
            <span className="text-xs text-amber-600 dark:text-amber-400">
              Henüz doğrulanmadı
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => verifyMut.mutate({ templateId: tpl.id })}
              disabled={verifyMut.isPending}
            >
              {verifyMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              Doğrula
            </Button>
          </div>
        ) : tpl.is_verified ? (
          <p className="text-xs text-emerald-600 dark:text-emerald-400 pt-2 border-t border-border">
            ✓ Doğrulanmış
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
