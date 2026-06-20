"use client";

import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  CircleSlash,
  Eye,
  MessageSquare,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import {
  adminKeys,
  getAdminWhatsAppTemplates,
  previewAdminWhatsAppTemplate,
} from "@/lib/api/admin";
import {
  useCreateWaTemplate,
  useDeleteWaTemplate,
  useToggleWaTemplate,
  useUpdateWaTemplate,
} from "@/lib/hooks/use-admin-mutations";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  WaTemplateCreateBody,
  WaTemplateItem,
  WaTemplateListResponse,
  WaTemplateVar,
} from "@/lib/types/whatsapp-template";

interface Props {
  initial: WaTemplateListResponse;
}

const CATEGORY_TONE: Record<string, string> = {
  veli: "bg-sky-50 text-sky-900 border-sky-200 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200",
  ogrenci: "bg-emerald-50 text-emerald-900 border-emerald-200 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  kurum_ogretmen: "bg-violet-50 text-violet-900 border-violet-200 dark:bg-violet-500/10 dark:border-violet-500/30 dark:text-violet-200",
  kurum_veli: "bg-amber-50 text-amber-900 border-amber-200 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  kurum_ogrenci: "bg-rose-50 text-rose-900 border-rose-200 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
  admin_yonetici: "bg-fuchsia-50 text-fuchsia-900 border-fuchsia-200 dark:bg-fuchsia-500/10 dark:border-fuchsia-500/30 dark:text-fuchsia-200",
  admin_sistem: "bg-slate-100 text-slate-900 border-slate-300",
};

export function WhatsAppTemplatesClient({ initial }: Props) {
  const [categoryFilter, setCategoryFilter] = React.useState<string | null>(null);
  const [showInactive, setShowInactive] = React.useState(true);

  const q = useQuery<WaTemplateListResponse>({
    queryKey: adminKeys.whatsappTemplates(categoryFilter, null, showInactive),
    queryFn: () =>
      getAdminWhatsAppTemplates(categoryFilter, null, showInactive),
    initialData:
      categoryFilter == null && showInactive ? initial : undefined,
    staleTime: 30_000,
  });

  const data = q.data ?? initial;
  const categories = data.categories;

  // Açık dialog: yeni veya düzenle
  const [editing, setEditing] = React.useState<WaTemplateItem | null>(null);
  const [creating, setCreating] = React.useState(false);

  // Aktif şablon sayım
  const activeCount = data.items.filter((t) => t.is_active).length;
  const inactiveCount = data.items.length - activeCount;

  // Kategori chip listesi
  const categoryKeys = Object.keys(categories);

  return (
    <div className="space-y-5">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-[#117A86] font-semibold">
            <MessageSquare className="inline size-3.5 mr-1" aria-hidden />
            Manuel WhatsApp şablonları
          </p>
          <h1 className="font-display text-2xl font-semibold tracking-tight mt-1">
            Şablon Kütüphanesi
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
            Koç ve kurum yöneticilerinin tek-tıkla WhatsApp gönderiminde
            kullanacağı şablonlar. Değişken sözdizimi: <code className="bg-muted px-1 rounded font-mono text-xs">{`{{degisken_adi}}`}</code>.
          </p>
        </div>
        <Button
          onClick={() => setCreating(true)}
          className="bg-[#117A86] hover:bg-[#0E5F69] text-white"
        >
          <Plus className="size-4" aria-hidden />
          Yeni Şablon
        </Button>
      </header>

      {/* KPI + filtreler */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <Stat label="Toplam şablon" value={data.total} />
            <Stat label="Aktif" value={activeCount} tone="emerald" />
            <Stat label="Pasif" value={inactiveCount} tone="slate" />
          </div>

          {/* Kategori filter */}
          <div className="flex flex-wrap gap-2 items-center pt-2 border-t border-border">
            <span className="text-xs text-muted-foreground">Kategori:</span>
            <FilterChip
              label="Hepsi"
              active={categoryFilter === null}
              onClick={() => setCategoryFilter(null)}
            />
            {categoryKeys.map((c) => (
              <FilterChip
                key={c}
                label={categories[c]}
                active={categoryFilter === c}
                onClick={() => setCategoryFilter(c)}
              />
            ))}
            <span className="text-muted-foreground/40 mx-1">·</span>
            <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="accent-[#117A86]"
              />
              Pasifleri göster
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Liste — kategori bazlı gruplandırma */}
      {data.total === 0 ? (
        <Card>
          <CardContent className="p-10 text-center text-sm text-muted-foreground">
            Filtreye uyan şablon bulunamadı.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {groupByCategory(data.items, categories).map(([catKey, items]) => (
            <Card key={catKey} className="overflow-hidden">
              <div
                className={cn(
                  "px-4 py-2 border-b text-xs font-semibold inline-flex items-center gap-2",
                  CATEGORY_TONE[catKey] ?? "bg-muted",
                )}
              >
                <span>{categories[catKey] ?? catKey}</span>
                <span className="text-[10px] opacity-70">
                  ({items.length})
                </span>
              </div>
              <div className="divide-y divide-border">
                {items.map((t) => (
                  <TemplateRow
                    key={t.id}
                    template={t}
                    onEdit={() => setEditing(t)}
                  />
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Yeni şablon dialog */}
      {creating ? (
        <TemplateFormDialog
          categories={categories}
          targetRoles={data.target_roles}
          mode="create"
          onClose={() => setCreating(false)}
        />
      ) : null}

      {/* Düzenleme dialog */}
      {editing ? (
        <TemplateFormDialog
          categories={categories}
          targetRoles={data.target_roles}
          mode="edit"
          template={editing}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </div>
  );
}

// ============================================================================
// Stat
// ============================================================================

function Stat({
  label,
  value,
  tone = "slate",
}: {
  label: string;
  value: number;
  tone?: "slate" | "emerald";
}) {
  const cls =
    tone === "emerald"
      ? "text-emerald-700"
      : "text-foreground";
  return (
    <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className={cn("text-2xl font-semibold tabular-nums mt-0.5", cls)}>
        {value}
      </div>
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full px-2.5 py-1 text-[11px] border transition-colors",
        active
          ? "bg-[#117A86] text-white border-[#117A86]"
          : "bg-background text-foreground border-border hover:bg-muted",
      )}
    >
      {label}
    </button>
  );
}

// ============================================================================
// Liste satırı
// ============================================================================

function TemplateRow({
  template,
  onEdit,
}: {
  template: WaTemplateItem;
  onEdit: () => void;
}) {
  const toggleMut = useToggleWaTemplate();
  const deleteMut = useDeleteWaTemplate();
  const [confirmDelete, setConfirmDelete] = React.useState(false);

  return (
    <div
      className={cn(
        "px-4 py-3 flex items-start gap-3",
        !template.is_active && "opacity-60",
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium">{template.name_tr}</span>
          <span className="text-[10px] font-mono text-muted-foreground">
            {template.key}
          </span>
          {!template.is_active && (
            <span className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider bg-slate-100 text-slate-600 border border-slate-200 px-1.5 py-0.5 rounded">
              <CircleSlash className="size-3" aria-hidden />
              Pasif
            </span>
          )}
          {template.allow_bulk && (
            <span className="text-[10px] uppercase tracking-wider bg-amber-50 text-amber-800 border border-amber-200 px-1.5 py-0.5 rounded dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200">
              Toplu
            </span>
          )}
          {template.requires_date && (
            <span className="text-[10px] uppercase tracking-wider bg-sky-50 text-sky-800 border border-sky-200 px-1.5 py-0.5 rounded dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200">
              Tarihli
            </span>
          )}
          {template.allow_freeform_note && (
            <span className="text-[10px] uppercase tracking-wider bg-emerald-50 text-emerald-800 border border-emerald-200 px-1.5 py-0.5 rounded dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200">
              Serbest not
            </span>
          )}
        </div>
        {template.description ? (
          <p className="text-xs text-muted-foreground mt-0.5">
            {template.description}
          </p>
        ) : null}
        <p className="text-xs text-muted-foreground/80 mt-1 italic line-clamp-2">
          {template.content_template}
        </p>
        <div className="text-[10px] text-muted-foreground mt-1.5 flex items-center gap-2 flex-wrap">
          <span>Hedef: {template.target_role_label_tr}</span>
          <span>·</span>
          <span>{template.variables.length} değişken</span>
        </div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <Button size="sm" variant="ghost" onClick={onEdit} aria-label="Düzenle">
          <Pencil className="size-3.5" aria-hidden />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => toggleMut.mutate({ id: template.id })}
          disabled={toggleMut.isPending}
          aria-label={template.is_active ? "Pasife al" : "Aktif et"}
          title={template.is_active ? "Pasife al" : "Aktif et"}
          className={template.is_active ? "text-amber-700" : "text-emerald-700"}
        >
          {template.is_active ? (
            <CircleSlash className="size-3.5" aria-hidden />
          ) : (
            <CheckCircle2 className="size-3.5" aria-hidden />
          )}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setConfirmDelete(true)}
          disabled={template.is_active}
          title={template.is_active ? "Önce pasife alın" : "Sil"}
          aria-label="Sil"
          className="text-rose-700 disabled:opacity-30"
        >
          <Trash2 className="size-3.5" aria-hidden />
        </Button>
      </div>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Şablonu sil</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            <strong>{template.name_tr}</strong> ({template.key}) kalıcı olarak
            silinecek. Bu işlem geri alınamaz.
          </p>
          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              onClick={() => setConfirmDelete(false)}
              disabled={deleteMut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={() =>
                deleteMut.mutate(
                  { id: template.id },
                  { onSettled: () => setConfirmDelete(false) },
                )
              }
              disabled={deleteMut.isPending}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              Sil
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ============================================================================
// Form dialog (create + edit)
// ============================================================================

interface FormDialogProps {
  categories: Record<string, string>;
  targetRoles: Record<string, string>;
  mode: "create" | "edit";
  template?: WaTemplateItem;
  onClose: () => void;
}

function TemplateFormDialog({
  categories,
  targetRoles,
  mode,
  template,
  onClose,
}: FormDialogProps) {
  const createMut = useCreateWaTemplate();
  const updateMut = useUpdateWaTemplate(template?.id ?? 0);

  const [body, setBody] = React.useState<WaTemplateCreateBody>(() => ({
    key: template?.key ?? "",
    category: template?.category ?? Object.keys(categories)[0] ?? "veli",
    target_role: template?.target_role ?? "any",
    name_tr: template?.name_tr ?? "",
    description: template?.description ?? "",
    content_template: template?.content_template ?? "",
    variables: template?.variables ?? [],
    requires_date: template?.requires_date ?? false,
    allow_bulk: template?.allow_bulk ?? false,
    allow_freeform_note: template?.allow_freeform_note ?? false,
    sort_order: template?.sort_order ?? 100,
    is_active: template?.is_active ?? true,
  }));

  function set<K extends keyof WaTemplateCreateBody>(
    key: K,
    value: WaTemplateCreateBody[K],
  ) {
    setBody((s) => ({ ...s, [key]: value }));
  }

  function setVar(i: number, patch: Partial<WaTemplateVar>) {
    setBody((s) => {
      const vars = [...s.variables];
      vars[i] = { ...vars[i], ...patch };
      return { ...s, variables: vars };
    });
  }

  function addVar() {
    setBody((s) => ({
      ...s,
      variables: [...s.variables, { key: "", label_tr: "", example: "" }],
    }));
  }

  function removeVar(i: number) {
    setBody((s) => ({
      ...s,
      variables: s.variables.filter((_, idx) => idx !== i),
    }));
  }

  function onSubmit() {
    if (mode === "create") {
      createMut.mutate(body, { onSuccess: () => onClose() });
    } else if (template) {
      const { ...rest } = body;
      // Update body key alanını içermez — Omit'lendi backend tarafında
      // Spread'i kullanmadan tek atama:
      const updateBody = {
        category: rest.category,
        target_role: rest.target_role,
        name_tr: rest.name_tr,
        description: rest.description,
        content_template: rest.content_template,
        variables: rest.variables,
        requires_date: rest.requires_date,
        allow_bulk: rest.allow_bulk,
        allow_freeform_note: rest.allow_freeform_note,
        sort_order: rest.sort_order,
        is_active: rest.is_active,
      };
      updateMut.mutate(updateBody, { onSuccess: () => onClose() });
    }
  }

  const isPending = createMut.isPending || updateMut.isPending;

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-3xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {mode === "create" ? "Yeni Şablon" : "Şablonu Düzenle"}
          </DialogTitle>
          <DialogDescription>
            Değişken sözdizimi: <code className="bg-muted px-1 rounded font-mono">{`{{degisken_adi}}`}</code>
            . Önizleme için aşağıda &ldquo;Önizle&rdquo; butonunu kullanın.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {/* Key (yalnız create'te) */}
          {mode === "create" ? (
            <div>
              <Label htmlFor="tpl_key">Key (kalıcı tanıtıcı)</Label>
              <Input
                id="tpl_key"
                value={body.key}
                onChange={(e) => set("key", e.target.value)}
                placeholder="veli_yeni_program"
                className="mt-1 font-mono text-sm"
              />
              <p className="text-[11px] text-muted-foreground mt-1">
                Sonradan değiştirilemez. Küçük harf + alt çizgi.
              </p>
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">
              Key: <code className="font-mono">{template?.key}</code>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="tpl_name">Şablon adı (Türkçe)</Label>
              <Input
                id="tpl_name"
                value={body.name_tr}
                onChange={(e) => set("name_tr", e.target.value)}
                placeholder="Yeni program yayınlandı"
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="tpl_sort">Sıralama</Label>
              <Input
                id="tpl_sort"
                type="number"
                value={body.sort_order}
                onChange={(e) => set("sort_order", parseInt(e.target.value || "100"))}
                className="mt-1"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="tpl_cat">Kategori</Label>
              <select
                id="tpl_cat"
                value={body.category}
                onChange={(e) => set("category", e.target.value)}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {Object.entries(categories).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="tpl_role">Hedef rol</Label>
              <select
                id="tpl_role"
                value={body.target_role}
                onChange={(e) => set("target_role", e.target.value)}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {Object.entries(targetRoles).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <Label htmlFor="tpl_desc">Açıklama (admin notu)</Label>
            <Input
              id="tpl_desc"
              value={body.description}
              onChange={(e) => set("description", e.target.value)}
              placeholder="Bu şablon nasıl kullanılır?"
              className="mt-1"
            />
          </div>

          <div>
            <Label htmlFor="tpl_content">Mesaj metni (şablon)</Label>
            <textarea
              id="tpl_content"
              value={body.content_template}
              onChange={(e) => set("content_template", e.target.value)}
              rows={5}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              placeholder={"Merhaba {{veli_adi}}, {{ogrenci_adi}} için..."}
            />
          </div>

          {/* Değişkenler */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <Label>Değişkenler</Label>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={addVar}
              >
                <Plus className="size-3.5" aria-hidden />
                Değişken ekle
              </Button>
            </div>
            {body.variables.length === 0 ? (
              <p className="text-xs text-muted-foreground italic">
                Henüz değişken yok. Şablonda <code>{`{{...}}`}</code> kullandığınız her
                anahtarı buraya ekleyin (önizleme + UI etiket için gerekli).
              </p>
            ) : (
              <div className="space-y-2">
                {body.variables.map((v, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 items-center"
                  >
                    <Input
                      placeholder="key (örn: veli_adi)"
                      value={v.key}
                      onChange={(e) => setVar(i, { key: e.target.value })}
                      className="text-xs font-mono"
                    />
                    <Input
                      placeholder="Etiket (TR)"
                      value={v.label_tr}
                      onChange={(e) => setVar(i, { label_tr: e.target.value })}
                      className="text-xs"
                    />
                    <Input
                      placeholder="Örnek değer"
                      value={v.example}
                      onChange={(e) => setVar(i, { example: e.target.value })}
                      className="text-xs"
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => removeVar(i)}
                      className="text-rose-700"
                    >
                      <Trash2 className="size-3.5" aria-hidden />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Bayraklar */}
          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border">
            <CheckboxRow
              label="Tarih seçici gerekli"
              checked={body.requires_date}
              onChange={(v) => set("requires_date", v)}
            />
            <CheckboxRow
              label="Toplu gönderim uygun"
              checked={body.allow_bulk}
              onChange={(v) => set("allow_bulk", v)}
            />
            <CheckboxRow
              label="Serbest not izni"
              checked={body.allow_freeform_note}
              onChange={(v) => set("allow_freeform_note", v)}
            />
            <CheckboxRow
              label="Aktif"
              checked={body.is_active}
              onChange={(v) => set("is_active", v)}
            />
          </div>

          {/* Önizleme */}
          <PreviewBlock
            template={body.content_template}
            variables={body.variables}
          />
        </div>

        <DialogFooter className="gap-2">
          <Button variant="ghost" onClick={onClose} disabled={isPending}>
            Vazgeç
          </Button>
          <Button
            onClick={onSubmit}
            disabled={isPending || !body.key || !body.name_tr || !body.content_template}
            className="bg-[#117A86] hover:bg-[#0E5F69] text-white"
          >
            {mode === "create" ? "Şablonu Oluştur" : "Değişiklikleri Kaydet"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CheckboxRow({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-xs cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-[#117A86]"
      />
      {label}
    </label>
  );
}

// ============================================================================
// Önizleme blok
// ============================================================================

function PreviewBlock({
  template,
  variables,
}: {
  template: string;
  variables: WaTemplateVar[];
}) {
  // eslint-disable-next-line lgs/missing-invalidate -- preview saf okuma; sonuç local state, hiçbir cache bayatlamaz
  const previewMut = useMutation({
    mutationFn: () =>
      previewAdminWhatsAppTemplate({
        content_template: template,
        variables: {},
        variable_defs: variables,
      }),
  });
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold inline-flex items-center gap-1">
          <Eye className="size-3.5" aria-hidden />
          Önizleme
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => previewMut.mutate()}
          disabled={!template || previewMut.isPending}
        >
          Önizle
        </Button>
      </div>
      {previewMut.data ? (
        <>
          <div className="rounded border border-emerald-200 bg-emerald-50/40 px-3 py-2 text-sm whitespace-pre-wrap text-emerald-900 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200">
            {previewMut.data.rendered}
          </div>
          {previewMut.data.warnings.length > 0 ? (
            <ul className="text-[11px] text-amber-800 list-disc pl-4 space-y-0.5">
              {previewMut.data.warnings.slice(0, 5).map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : null}
        </>
      ) : (
        <p className="text-[11px] text-muted-foreground italic">
          Şablonu örnek değerlerle nasıl görüneceğini test etmek için
          &ldquo;Önizle&rdquo; deyin.
        </p>
      )}
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function groupByCategory(
  items: WaTemplateItem[],
  categories: Record<string, string>,
): [string, WaTemplateItem[]][] {
  const groups: Record<string, WaTemplateItem[]> = {};
  for (const k of Object.keys(categories)) groups[k] = [];
  for (const it of items) {
    if (!groups[it.category]) groups[it.category] = [];
    groups[it.category].push(it);
  }
  return Object.entries(groups).filter(([, list]) => list.length > 0);
}
