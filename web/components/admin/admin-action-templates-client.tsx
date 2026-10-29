"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ClipboardList, Loader2, Pencil, Plus, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminActionTemplates } from "@/lib/api/admin";
import {
  useCreateActionTemplate,
  useDeleteActionTemplate,
  useUpdateActionTemplate,
} from "@/lib/hooks/use-admin-mutations";
import type {
  ActionTemplateItem,
  ActionTemplatesResponse,
  EnumOption,
} from "@/lib/types/admin";
import { fieldClass } from "@/components/admin/feature-catalog-ui";

interface Props {
  initial: ActionTemplatesResponse;
}

const PLACEHOLDERS = ["{{owner_name}}", "{{plan}}", "{{trial_ends_at}}", "{{contact_email}}", "{{today}}"];

// Backend ile aynı: yalnız ÇİFT süslü {{ key }} render edilir.
const SAMPLE_CTX: Record<string, string> = {
  owner_name: "Ahmet Koç",
  plan: "solo_pro",
  trial_ends_at: "30.05.2026",
  contact_email: "ahmet@ornek.com",
  today: "23.05.2026",
};

function renderPreview(text: string): string {
  return (text || "").replace(/\{\{\s*([a-zA-Z_]+)\s*\}\}/g, (m, key) =>
    Object.prototype.hasOwnProperty.call(SAMPLE_CTX, key) ? SAMPLE_CTX[key] : m,
  );
}

/** Tek süslü {key} (çift değil) → render EDİLMEZ; uyar. */
function hasSingleBrace(text: string): boolean {
  const stripped = (text || "").replace(/\{\{\s*[a-zA-Z_]+\s*\}\}/g, "");
  return /\{\s*[a-zA-Z_]+\s*\}/.test(stripped);
}

export function AdminActionTemplatesClient({ initial }: Props) {
  const q = useQuery<ActionTemplatesResponse>({
    queryKey: adminKeys.revenueActionTemplates(),
    queryFn: () => getAdminActionTemplates(),
    initialData: initial,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header>
        <Link href="/admin/revenue/action-center" className="text-sm text-muted-foreground hover:text-foreground">
          ← Ticari Pano
        </Link>
        <h1 className="mt-1 inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <ClipboardList className="size-6 text-indigo-700" aria-hidden />
          Aksiyon Şablonları
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          CRM aksiyonu eklerken seçilebilen hazır e-posta/arama scriptleri.
          Yer tutucular ({PLACEHOLDERS.map((p) => (
            <code key={p} className="mx-0.5 rounded bg-muted px-1 text-[11px]">{p}</code>
          ))}) owner bağlamında otomatik dolar.
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <NewTemplateForm kinds={data.kinds} />
        </div>
        <div className="space-y-3 lg:col-span-2">
          {data.templates.length === 0 ? (
            <Card className="p-10 text-center text-sm text-muted-foreground">
              Henüz şablon yok — soldan ekleyebilirsin.
            </Card>
          ) : (
            data.templates.map((t) => <TemplateCard key={t.id} t={t} kinds={data.kinds} />)
          )}
        </div>
      </div>
    </div>
  );
}

function NewTemplateForm({ kinds }: { kinds: EnumOption[] }) {
  const createMut = useCreateActionTemplate();
  const [name, setName] = React.useState("");
  const [kind, setKind] = React.useState(kinds[0]?.value ?? "email");
  const [subject, setSubject] = React.useState("");
  const [body, setBody] = React.useState("");
  const [description, setDescription] = React.useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !body.trim()) return;
    createMut.mutate(
      { name: name.trim(), kind, subject: subject.trim(), body, description: description.trim() },
      {
        onSuccess: () => {
          setName("");
          setSubject("");
          setBody("");
          setDescription("");
        },
      },
    );
  }

  return (
    <Card className="sticky top-4 p-4">
      <h2 className="mb-3 text-sm font-semibold">Yeni Şablon</h2>
      <form onSubmit={submit} className="space-y-2">
        <label className="block">
          <span className="text-xs text-muted-foreground">Şablon adı *</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={255} required
                 placeholder="ör. Trial son uyarı (e-posta)" className={cn(fieldClass, "mt-1")} />
        </label>
        <label className="block">
          <span className="text-xs text-muted-foreground">Tür *</span>
          <select value={kind} onChange={(e) => setKind(e.target.value)} className={cn(fieldClass, "mt-1")}>
            {kinds.map((k) => (
              <option key={k.value} value={k.value}>{k.label}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-xs text-muted-foreground">Konu (e-posta için)</span>
          <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={255}
                 placeholder="ör. Deneme süreniz bitiyor" className={cn(fieldClass, "mt-1")} />
        </label>
        <label className="block">
          <span className="text-xs text-muted-foreground">Gövde *</span>
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={7} required
                    placeholder={"Merhaba {{owner_name}},\n\nPlanınız: {{plan}}…"}
                    className={cn(fieldClass, "mt-1 font-mono text-xs")} />
        </label>
        {hasSingleBrace(subject) || hasSingleBrace(body) ? (
          <p className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
            ⚠ Tek süslü {"{...}"} render edilmez. Çift süslü <strong>{"{{...}}"}</strong> kullan
            (ör. {"{{trial_ends_at}}"}).
          </p>
        ) : null}
        {body.trim() ? (
          <div className="rounded border border-border bg-muted/40 p-2">
            <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Önizleme (örnek koç verisiyle)
            </span>
            {subject.trim() ? (
              <div className="mt-1 text-xs font-medium">Konu: {renderPreview(subject)}</div>
            ) : null}
            <pre className="mt-1 whitespace-pre-wrap break-words font-sans text-xs text-foreground/90">{renderPreview(body)}</pre>
          </div>
        ) : null}
        <label className="block">
          <span className="text-xs text-muted-foreground">Açıklama (admin için)</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
                    placeholder="Ne zaman kullanılır?" className={cn(fieldClass, "mt-1")} />
        </label>
        <Button type="submit" disabled={createMut.isPending} className="w-full bg-indigo-600 text-white hover:bg-indigo-700">
          {createMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Plus className="size-4" aria-hidden />}
          Ekle
        </Button>
      </form>
    </Card>
  );
}

function TemplateCard({ t, kinds }: { t: ActionTemplateItem; kinds: EnumOption[] }) {
  const [editing, setEditing] = React.useState(false);
  const delMut = useDeleteActionTemplate();

  return (
    <Card className={cn("overflow-hidden", !t.is_active && "opacity-60")}>
      <div className="flex items-start justify-between gap-3 px-4 py-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">{t.name}</span>
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{t.kind_label}</span>
            {!t.is_active ? <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] text-rose-700">Pasif</span> : null}
          </div>
          {t.subject ? <div className="mt-1 text-xs text-muted-foreground">Konu: {t.subject}</div> : null}
          {t.description ? <div className="mt-0.5 text-xs italic text-muted-foreground">{t.description}</div> : null}
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button type="button" onClick={() => setEditing((v) => !v)} title="Düzenle"
                  className="text-muted-foreground hover:text-indigo-700">
            <Pencil className="size-4" aria-hidden />
          </button>
          <button type="button" disabled={delMut.isPending}
                  onClick={() => { if (confirm("Bu şablonu silmek istiyor musun?")) delMut.mutate(t.id); }}
                  title="Sil" className="text-muted-foreground hover:text-rose-700">
            <Trash2 className="size-4" aria-hidden />
          </button>
        </div>
      </div>
      <div className="border-t border-border bg-muted/30 px-4 py-3">
        <pre className="whitespace-pre-wrap rounded border border-border bg-card p-2 font-mono text-xs">{t.body}</pre>
      </div>
      {editing ? <EditTemplateForm t={t} kinds={kinds} onClose={() => setEditing(false)} /> : null}
    </Card>
  );
}

function EditTemplateForm({
  t,
  kinds,
  onClose,
}: {
  t: ActionTemplateItem;
  kinds: EnumOption[];
  onClose: () => void;
}) {
  const updateMut = useUpdateActionTemplate(t.id);
  const [name, setName] = React.useState(t.name);
  const [kind, setKind] = React.useState(t.kind);
  const [subject, setSubject] = React.useState(t.subject ?? "");
  const [body, setBody] = React.useState(t.body);
  const [description, setDescription] = React.useState(t.description ?? "");
  const [isActive, setIsActive] = React.useState(t.is_active);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    updateMut.mutate(
      { name, kind, subject, body, description, is_active: isActive },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-2 border-t border-border p-4">
      <input type="text" value={name} onChange={(e) => setName(e.target.value)} required maxLength={255} className={fieldClass} />
      <select value={kind} onChange={(e) => setKind(e.target.value)} className={fieldClass}>
        {kinds.map((k) => (
          <option key={k.value} value={k.value}>{k.label}</option>
        ))}
      </select>
      <input type="text" value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={255} placeholder="Konu" className={fieldClass} />
      <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={6} required className={cn(fieldClass, "font-mono text-xs")} />
      <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} placeholder="Açıklama" className={fieldClass} />
      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} className="rounded border-input" />
        Aktif
      </label>
      <div className="flex items-center gap-2">
        <Button type="submit" disabled={updateMut.isPending} className="bg-indigo-600 text-white hover:bg-indigo-700">
          {updateMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          Güncelle
        </Button>
        <Button type="button" variant="ghost" onClick={onClose}>Vazgeç</Button>
      </div>
    </form>
  );
}
