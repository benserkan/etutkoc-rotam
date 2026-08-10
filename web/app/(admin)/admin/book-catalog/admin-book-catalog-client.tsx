"use client";

/**
 * Süper Admin — Ortak Kitap Kataloğu.
 *
 * Yayınevi kitaplarının GERÇEK yapısı (ünite + birebir test sayısı) burada
 * yönetilir: örnek PDF / içindekiler fotoğrafından AI okumasıyla seed +
 * koç katkılarının (pending) onayı. Yalnız "Yayında" kayıtları koçlar görür.
 */
import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  CheckCircle2,
  Eye,
  EyeOff,
  FileUp,
  Loader2,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  bookCatalogKeys,
  getAdminBookCatalog,
  getAdminBookCatalogEntry,
  getAdminCatalogSubjects,
} from "@/lib/api/book-catalog";
import {
  useAdminCatalogAction,
  useAdminCatalogCreate,
  useAdminCatalogUpdate,
  useReadStructure,
} from "@/lib/hooks/use-book-catalog-mutations";
import {
  SectionsDraftEditor,
  sectionsValid,
  type DraftSection,
} from "@/components/book-catalog/sections-draft-editor";
import {
  CATALOG_SOURCE_LABELS_TR,
  CATALOG_STATUS_LABELS_TR,
  type AdminCatalogListResponse,
  type CatalogEntryBrief,
  type CatalogEntryDetail,
} from "@/lib/types/book-catalog";
import {
  LIBRARY_BOOK_TYPE_LABELS_TR,
  type LibraryBookType,
  type SubjectRef,
} from "@/lib/types/library";
import { groupSubjectsByCurriculum } from "@/lib/utils/subjects";

const STATUS_TONE: Record<string, string> = {
  verified:
    "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-200 dark:border-emerald-500/30",
  pending:
    "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-500/10 dark:text-amber-200 dark:border-amber-500/30",
  hidden:
    "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-500/10 dark:text-slate-300 dark:border-slate-500/30",
};

const STATUS_FILTERS: { key: string; label: string }[] = [
  { key: "", label: "Tümü" },
  { key: "verified", label: "Yayında" },
  { key: "pending", label: "Onay bekleyen" },
  { key: "hidden", label: "Gizli" },
];

function Pill({ children, tone }: { children: React.ReactNode; tone: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        tone,
      )}
    >
      {children}
    </span>
  );
}

function gradeLabel(e: CatalogEntryBrief): string {
  const parts: string[] = [];
  if (e.target_grade_min != null && e.target_grade_max != null) {
    parts.push(
      e.target_grade_min === e.target_grade_max
        ? `${e.target_grade_min}. sınıf`
        : `${e.target_grade_min}-${e.target_grade_max}. sınıf`,
    );
  }
  if (e.target_graduate) parts.push("Mezun");
  return parts.join(" · ") || "Tüm seviyeler";
}

// =============================================================================
// Kayıt dialogu (oluştur + düzenle ortak)
// =============================================================================

interface EntryFormState {
  name: string;
  publisher: string;
  type: LibraryBookType;
  subject_id: number | null;
  grade_min: string;
  grade_max: string;
  graduate: boolean;
  publish: boolean;
  sections: DraftSection[];
}

const EMPTY_FORM: EntryFormState = {
  name: "",
  publisher: "",
  type: "soru_bankasi",
  subject_id: null,
  grade_min: "",
  grade_max: "",
  graduate: false,
  publish: true,
  sections: [],
};

function formFromDetail(d: CatalogEntryDetail): EntryFormState {
  return {
    name: d.name,
    publisher: d.publisher ?? "",
    type: d.type,
    subject_id: d.subject_id,
    grade_min: d.target_grade_min != null ? String(d.target_grade_min) : "",
    grade_max: d.target_grade_max != null ? String(d.target_grade_max) : "",
    graduate: d.target_graduate,
    publish: true,
    sections: d.sections.map((s) => ({
      label: s.label,
      test_count: s.test_count,
      suspect: false,
    })),
  };
}

function EntryDialog({
  mode,
  entryId,
  subjects,
  onClose,
}: {
  mode: "create" | "edit";
  entryId: number | null;
  subjects: SubjectRef[];
  onClose: () => void;
}) {
  const [form, setForm] = React.useState<EntryFormState>(EMPTY_FORM);
  const [readWarnings, setReadWarnings] = React.useState<string[]>([]);
  const fileRef = React.useRef<HTMLInputElement>(null);

  const detailQ = useQuery({
    queryKey: entryId != null ? bookCatalogKeys.coachDetail(entryId) : ["admin", "book-catalog", "new"],
    queryFn: () => getAdminBookCatalogEntry(entryId as number),
    enabled: mode === "edit" && entryId != null,
  });
  // "Prop/veri gelince render'da doldur" deseni (set-state-in-effect yerine;
  // ref render'da okunmaz — React Compiler kuralı).
  const [loadedFor, setLoadedFor] = React.useState<number | null>(null);
  if (mode === "edit" && detailQ.data && loadedFor !== entryId) {
    setLoadedFor(entryId);
    setForm(formFromDetail(detailQ.data));
  }

  const read = useReadStructure("admin");
  const create = useAdminCatalogCreate();
  const update = useAdminCatalogUpdate();
  const busy = read.isPending || create.isPending || update.isPending;

  const onRead = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    read.mutate(Array.from(files), {
      onSuccess: (res) => {
        setReadWarnings(res.warnings);
        setForm((f) => ({
          ...f,
          name: f.name || res.book_title || "",
          publisher: f.publisher || res.publisher || "",
          grade_min:
            f.grade_min || (res.grade_hint != null ? String(res.grade_hint) : ""),
          grade_max:
            f.grade_max || (res.grade_hint != null ? String(res.grade_hint) : ""),
          sections: res.sections.map((s) => ({
            label: s.label,
            test_count: s.test_count,
            suspect: s.suspect,
          })),
        }));
      },
    });
    if (fileRef.current) fileRef.current.value = "";
  };

  const canSave =
    form.name.trim().length > 0 && sectionsValid(form.sections) && !busy;

  const save = () => {
    const body = {
      name: form.name.trim(),
      publisher: form.publisher.trim() || null,
      type: form.type,
      subject_id: form.subject_id,
      target_grade_min: form.grade_min ? Number(form.grade_min) : null,
      target_grade_max: form.grade_max ? Number(form.grade_max) : null,
      target_graduate: form.graduate,
      sections: form.sections.map((s) => ({
        label: s.label.trim(),
        test_count: s.test_count ?? 0,
      })),
    };
    if (mode === "create") {
      create.mutate({ ...body, publish: form.publish }, { onSuccess: onClose });
    } else if (entryId != null) {
      update.mutate({ id: entryId, body }, { onSuccess: onClose });
    }
  };

  const groups = groupSubjectsByCurriculum(subjects);
  const totalTests = form.sections.reduce((a, s) => a + (s.test_count ?? 0), 0);

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Kataloğa kitap ekle" : "Katalog kaydını düzenle"}
          </DialogTitle>
          <DialogDescription>
            Yayınevi kitabının gerçek yapısı (ünite + birebir test sayısı).
            Yayındaki kaydı tüm koçlar tek tıkla kullanır; müfredat eşleştirmesi
            kaydederken otomatik yapılır.
          </DialogDescription>
        </DialogHeader>

        {mode === "edit" && detailQ.isLoading ? (
          <div className="flex items-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Kayıt yükleniyor…
          </div>
        ) : (
          <div className="space-y-4">
            {/* Kaynaktan oku (seed aracı) */}
            <div className="rounded-lg border border-cyan-200 bg-cyan-50 p-3 dark:bg-cyan-500/10 dark:border-cyan-500/30">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm text-cyan-900 dark:text-cyan-100">
                  <FileUp className="mr-1 inline size-4" aria-hidden />
                  <strong>İçindekiler fotoğrafı veya örnek PDF yükle</strong> — yapı
                  iki kez okunur, aşağıya dolar.
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => fileRef.current?.click()}
                >
                  {read.isPending ? (
                    <>
                      <Loader2 className="size-4 animate-spin" aria-hidden /> İki kez
                      okunuyor…
                    </>
                  ) : (
                    "Dosya seç ve oku"
                  )}
                </Button>
                <input
                  ref={fileRef}
                  type="file"
                  multiple
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  className="hidden"
                  onChange={(e) => onRead(e.target.files)}
                />
              </div>
              {readWarnings.length > 0 && (
                <ul className="mt-2 space-y-0.5 text-xs text-amber-800 dark:text-amber-200">
                  {readWarnings.map((w, i) => (
                    <li key={i}>• {w}</li>
                  ))}
                </ul>
              )}
            </div>

            {/* Kitap bilgileri */}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Kitap adı *
                </label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="örn. 4K TYT Matematik Soru Bankası"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Yayınevi
                </label>
                <Input
                  value={form.publisher}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, publisher: e.target.value }))
                  }
                  placeholder="örn. 4K Yayınları"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Kitap tipi
                </label>
                <select
                  value={form.type}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, type: e.target.value as LibraryBookType }))
                  }
                  className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                >
                  {Object.entries(LIBRARY_BOOK_TYPE_LABELS_TR).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  Ders (builtin — müfredat eşleştirmesi için)
                </label>
                <select
                  value={form.subject_id ?? ""}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      subject_id: e.target.value ? Number(e.target.value) : null,
                    }))
                  }
                  className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                >
                  <option value="">— Ders seçilmedi —</option>
                  {groups.map((g, gi) => (
                    <optgroup key={gi} label={g.label}>
                      {g.subjects.map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
              <div className="flex items-end gap-2">
                <div className="flex-1">
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">
                    Sınıf (min-maks)
                  </label>
                  <div className="flex items-center gap-1">
                    <Input
                      value={form.grade_min}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, grade_min: e.target.value }))
                      }
                      inputMode="numeric"
                      placeholder="4"
                      className="h-9 w-14 text-center"
                    />
                    <span className="text-muted-foreground">–</span>
                    <Input
                      value={form.grade_max}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, grade_max: e.target.value }))
                      }
                      inputMode="numeric"
                      placeholder="12"
                      className="h-9 w-14 text-center"
                    />
                  </div>
                </div>
                <label className="flex h-9 items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={form.graduate}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, graduate: e.target.checked }))
                    }
                  />
                  Mezun
                </label>
              </div>
            </div>

            {/* Bölümler */}
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-sm font-medium">
                  Bölümler ({form.sections.length}) · toplam {totalTests} test
                </span>
              </div>
              <SectionsDraftEditor
                sections={form.sections}
                onChange={(next) => setForm((f) => ({ ...f, sections: next }))}
                disabled={busy}
              />
            </div>

            {mode === "create" && (
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={form.publish}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, publish: e.target.checked }))
                  }
                />
                Hemen yayına al (koçlar kullanabilir)
              </label>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button onClick={save} disabled={!canSave}>
            {create.isPending || update.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            {mode === "create" ? "Kataloğa ekle" : "Kaydet"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Onay dialogu
// =============================================================================

function ConfirmDialog({
  title,
  description,
  confirmLabel,
  destructive,
  onConfirm,
  onClose,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  destructive?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Vazgeç
          </Button>
          <Button
            variant={destructive ? "destructive" : "default"}
            onClick={() => {
              onConfirm();
              onClose();
            }}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// =============================================================================
// Ana client
// =============================================================================

export function AdminBookCatalogClient({
  initial,
}: {
  initial: AdminCatalogListResponse;
}) {
  const [statusFilter, setStatusFilter] = React.useState("");
  const [search, setSearch] = React.useState("");
  const [debouncedQ, setDebouncedQ] = React.useState("");
  const [dialog, setDialog] = React.useState<
    | { kind: "create" }
    | { kind: "edit"; id: number }
    | {
        kind: "confirm";
        id: number;
        action: "verify" | "hide" | "delete";
        name: string;
      }
    | null
  >(null);

  React.useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(search.trim()), 350);
    return () => clearTimeout(t);
  }, [search]);

  const listQ = useQuery({
    queryKey: bookCatalogKeys.adminList(statusFilter || null, debouncedQ),
    queryFn: () => getAdminBookCatalog(statusFilter || null, debouncedQ),
    initialData: statusFilter === "" && debouncedQ === "" ? initial : undefined,
  });
  const subjectsQ = useQuery({
    queryKey: bookCatalogKeys.adminSubjects(),
    queryFn: getAdminCatalogSubjects,
    staleTime: 5 * 60_000,
  });

  const action = useAdminCatalogAction();
  const data = listQ.data ?? initial;

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      {/* Başlık */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex size-9 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300">
              <BookOpen className="size-5" aria-hidden />
            </span>
            <div>
              <h1 className="text-lg font-semibold">Ortak Kitap Kataloğu</h1>
              <p className="mt-0.5 max-w-2xl text-sm text-muted-foreground">
                Yayınevi kitaplarının gerçek yapısı (ünite + <strong>birebir test
                sayısı</strong>). Bir kitap bir kez tanımlanır; koçlar sihirbazda
                tek tıkla kullanır. Koç katkıları önce <strong>onay kuyruğuna</strong>{" "}
                düşer — yalnız senin onayladıkların yayına çıkar.
              </p>
            </div>
          </div>
          <Button onClick={() => setDialog({ kind: "create" })}>
            <Plus className="size-4" aria-hidden /> Kitap ekle
          </Button>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          <button
            onClick={() => setStatusFilter("verified")}
            className="rounded-lg border border-border bg-background p-3 text-left hover:bg-muted"
          >
            <div className="text-xl font-semibold text-emerald-700 dark:text-emerald-300">
              {data.verified_count}
            </div>
            <div className="text-xs text-muted-foreground">Yayında</div>
          </button>
          <button
            onClick={() => setStatusFilter("pending")}
            className="rounded-lg border border-border bg-background p-3 text-left hover:bg-muted"
          >
            <div className="text-xl font-semibold text-amber-700 dark:text-amber-300">
              {data.pending_count}
            </div>
            <div className="text-xs text-muted-foreground">Onay bekleyen</div>
          </button>
          <button
            onClick={() => setStatusFilter("hidden")}
            className="rounded-lg border border-border bg-background p-3 text-left hover:bg-muted"
          >
            <div className="text-xl font-semibold text-slate-600 dark:text-slate-300">
              {data.hidden_count}
            </div>
            <div className="text-xs text-muted-foreground">Gizli</div>
          </button>
        </div>
      </div>

      {/* Filtre + arama */}
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setStatusFilter(f.key)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm transition-colors",
              statusFilter === f.key
                ? "border-foreground bg-foreground text-background"
                : "border-border text-muted-foreground hover:bg-muted",
            )}
          >
            {f.label}
          </button>
        ))}
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Kitap adı / yayınevi ara…"
          className="ml-auto h-9 w-64"
        />
      </div>

      {/* Liste */}
      <div className="mt-4 overflow-x-auto rounded-xl border border-border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Kitap</th>
              <th className="px-3 py-2.5 font-medium">Ders · Sınıf</th>
              <th className="px-3 py-2.5 font-medium">Yapı</th>
              <th className="px-3 py-2.5 font-medium">Kaynak</th>
              <th className="px-3 py-2.5 font-medium">Kullanım</th>
              <th className="px-3 py-2.5 font-medium">Durum</th>
              <th className="px-3 py-2.5 text-right font-medium">İşlem</th>
            </tr>
          </thead>
          <tbody>
            {data.items.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-10 text-center text-muted-foreground">
                  {listQ.isFetching
                    ? "Yükleniyor…"
                    : "Kayıt yok — sağ üstten ilk kitabı ekle (örnek PDF yeter, kitabı satın alman gerekmez)."}
                </td>
              </tr>
            )}
            {data.items.map((e) => (
              <tr key={e.id} className="border-b border-border/60 last:border-0">
                <td className="px-4 py-2.5">
                  <div className="font-medium">{e.name}</div>
                  <div className="text-xs text-muted-foreground">
                    {e.publisher ?? "—"} · {LIBRARY_BOOK_TYPE_LABELS_TR[e.type]}
                  </div>
                </td>
                <td className="px-3 py-2.5 text-xs text-muted-foreground">
                  <div>{e.subject_name ?? "—"}</div>
                  <div>{gradeLabel(e)}</div>
                </td>
                <td className="px-3 py-2.5 text-xs">
                  <div>
                    {e.section_count} bölüm · <strong>{e.total_tests} test</strong>
                  </div>
                  <div className="text-muted-foreground">
                    {e.mapped_count}/{e.section_count} müfredat eşli
                  </div>
                </td>
                <td className="px-3 py-2.5 text-xs text-muted-foreground">
                  {CATALOG_SOURCE_LABELS_TR[e.source ?? ""] ?? "—"}
                </td>
                <td className="px-3 py-2.5 text-xs text-muted-foreground">
                  {e.usage_count} koç
                </td>
                <td className="px-3 py-2.5">
                  <Pill tone={STATUS_TONE[e.status] ?? STATUS_TONE.hidden}>
                    {CATALOG_STATUS_LABELS_TR[
                      e.status as keyof typeof CATALOG_STATUS_LABELS_TR
                    ] ?? e.status}
                  </Pill>
                </td>
                <td className="px-3 py-2.5">
                  <div className="flex items-center justify-end gap-1">
                    {e.status === "pending" && (
                      <Button
                        size="sm"
                        className="h-8 bg-emerald-600 text-white hover:bg-emerald-700 hover:text-white"
                        disabled={action.isPending}
                        onClick={() =>
                          setDialog({
                            kind: "confirm",
                            id: e.id,
                            action: "verify",
                            name: e.name,
                          })
                        }
                      >
                        <CheckCircle2 className="size-4" aria-hidden /> Onayla
                      </Button>
                    )}
                    {e.status === "hidden" && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8"
                        disabled={action.isPending}
                        onClick={() =>
                          setDialog({
                            kind: "confirm",
                            id: e.id,
                            action: "verify",
                            name: e.name,
                          })
                        }
                      >
                        <Eye className="size-4" aria-hidden /> Yayına al
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8"
                      onClick={() => setDialog({ kind: "edit", id: e.id })}
                      aria-label="Düzenle"
                    >
                      <Pencil className="size-4" aria-hidden />
                    </Button>
                    {e.status === "verified" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8"
                        disabled={action.isPending}
                        onClick={() =>
                          setDialog({
                            kind: "confirm",
                            id: e.id,
                            action: "hide",
                            name: e.name,
                          })
                        }
                        aria-label="Yayından kaldır"
                      >
                        <EyeOff className="size-4" aria-hidden />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 text-rose-600 hover:text-rose-700"
                      disabled={action.isPending || e.usage_count > 0}
                      title={
                        e.usage_count > 0
                          ? "Koçlar kullanmış — silinemez, yayından kaldır"
                          : "Sil"
                      }
                      onClick={() =>
                        setDialog({
                          kind: "confirm",
                          id: e.id,
                          action: "delete",
                          name: e.name,
                        })
                      }
                      aria-label="Sil"
                    >
                      <Trash2 className="size-4" aria-hidden />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {(dialog?.kind === "create" || dialog?.kind === "edit") && (
        <EntryDialog
          mode={dialog.kind}
          entryId={dialog.kind === "edit" ? dialog.id : null}
          subjects={subjectsQ.data?.items ?? []}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "confirm" && (
        <ConfirmDialog
          title={
            dialog.action === "verify"
              ? "Yayına alınsın mı?"
              : dialog.action === "hide"
                ? "Yayından kaldırılsın mı?"
                : "Kayıt silinsin mi?"
          }
          description={
            dialog.action === "verify"
              ? `"${dialog.name}" tüm koçların katalog aramasında görünür ve tek tıkla kullanılır olacak.`
              : dialog.action === "hide"
                ? `"${dialog.name}" koçların aramasından kalkar. Bu kaydı kullanmış koçların mevcut kitapları etkilenmez. Geri alınabilir.`
                : `"${dialog.name}" kalıcı olarak silinir. Bu işlem geri alınamaz.`
          }
          confirmLabel={
            dialog.action === "verify"
              ? "Yayına al"
              : dialog.action === "hide"
                ? "Yayından kaldır"
                : "Sil"
          }
          destructive={dialog.action === "delete"}
          onConfirm={() => action.mutate({ id: dialog.id, action: dialog.action })}
          onClose={() => setDialog(null)}
        />
      )}
    </div>
  );
}
