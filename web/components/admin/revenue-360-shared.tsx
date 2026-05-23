"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  BellRing,
  Ban,
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Gift,
  Loader2,
  Pin,
  PinOff,
  Plus,
  Save,
  Send,
  Trash2,
  TriangleAlert,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  useAddCrmAction,
  useAddCrmNote,
  useAddOwnerTag,
  useCancelInvoice,
  useCancelOffer,
  useCompleteCrmAction,
  useCreateOffer,
  useDeleteCrmAction,
  useDeleteCrmNote,
  useDeleteOwnerTag,
  useMarkInvoicePaid,
  usePinCrmNote,
  usePostponeInvoice,
  useSaveOwnerContact,
  useSendInvoiceReminder,
  useSendOffer,
  useUpdateOffer,
} from "@/lib/hooks/use-admin-mutations";
import {
  adminKeys,
  getAdminActionTemplateRender,
  getAdminActionTemplates,
} from "@/lib/api/admin";
import type {
  ActionTemplatesResponse,
  CrmActionItem,
  CrmMeta,
  CrmNoteItem,
  HealthHistoryPoint,
  HealthScoreV2Data,
  HealthTriggerItem,
  InvoiceItem,
  OfferItem,
  OwnerContactData,
  OwnerTagItem,
  OwnerType,
  PlanChangeItem,
} from "@/lib/types/admin";
import { fieldClass } from "@/components/admin/feature-catalog-ui";

// ── Statik ton map'leri (Tailwind purge güvenli) ─────────────────────────────

const BADGE: Record<string, string> = {
  emerald: "bg-emerald-100 text-emerald-800 border-emerald-200",
  lime: "bg-lime-100 text-lime-800 border-lime-200",
  amber: "bg-amber-100 text-amber-800 border-amber-200",
  orange: "bg-orange-100 text-orange-800 border-orange-200",
  rose: "bg-rose-100 text-rose-800 border-rose-200",
  indigo: "bg-indigo-100 text-indigo-800 border-indigo-200",
  slate: "bg-slate-100 text-slate-700 border-slate-200",
  blue: "bg-blue-100 text-blue-800 border-blue-200",
  purple: "bg-purple-100 text-purple-800 border-purple-200",
  pink: "bg-pink-100 text-pink-800 border-pink-200",
  sky: "bg-sky-100 text-sky-800 border-sky-200",
  yellow: "bg-yellow-100 text-yellow-800 border-yellow-200",
};
export const badge = (t: string) => BADGE[t] ?? BADGE.slate;

const BAR: Record<string, string> = {
  emerald: "bg-emerald-500",
  lime: "bg-lime-500",
  amber: "bg-amber-500",
  orange: "bg-orange-500",
  rose: "bg-rose-500",
};
function barColor(pct: number): string {
  if (pct >= 80) return BAR.emerald;
  if (pct >= 60) return BAR.lime;
  if (pct >= 40) return BAR.amber;
  if (pct >= 20) return BAR.orange;
  return BAR.rose;
}

export function tl(n: number | null | undefined): string {
  return `${Math.round(n ?? 0).toLocaleString("tr-TR")} ₺`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("tr-TR");
  } catch {
    return iso.slice(0, 10);
  }
}
function fmtDateTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("tr-TR");
  } catch {
    return iso.slice(0, 16);
  }
}

// ── Header etiket rozetleri ──────────────────────────────────────────────────

export function TagBadges({ tags }: { tags: OwnerTagItem[] }) {
  if (tags.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      {tags.map((t) => (
        <span
          key={t.id}
          title={t.description}
          className={cn("inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium", badge(t.color))}
        >
          {t.label}
        </span>
      ))}
    </div>
  );
}

// ── Sağlık Skoru 2.0 kartı ───────────────────────────────────────────────────

export function HealthV2Card({
  health,
  triggers = [],
  history = [],
}: {
  health: HealthScoreV2Data | null;
  triggers?: HealthTriggerItem[];
  history?: HealthHistoryPoint[];
}) {
  if (!health) {
    return (
      <Card className="p-4 text-sm text-muted-foreground">Sağlık skoru hesaplanamadı.</Card>
    );
  }
  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold">Sağlık Skoru 2.0 — Kullanım Bazlı</h2>
          <p className="text-xs text-muted-foreground">Ağırlıklı bileşenlerden hesaplanır. Yüksek = sağlıklı.</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn("text-3xl font-bold leading-none", `text-${health.band_color}-700`)}>
            {health.score}
          </span>
          <span
            className={cn("rounded-lg px-3 py-1.5 text-sm font-semibold", badge(health.band_color))}
          >
            {health.band_label}
          </span>
        </div>
      </div>

      {triggers.length > 0 ? (
        <div className="border-b border-rose-200 bg-rose-50 px-4 py-3">
          <div className="mb-2 inline-flex items-center gap-1 text-xs font-semibold uppercase text-rose-900">
            <TriangleAlert className="size-3.5" aria-hidden /> Erken Uyarı
          </div>
          <ul className="space-y-1.5">
            {triggers.map((t) => (
              <li key={t.code} className="text-sm">
                <span className="font-semibold text-rose-900">{t.title}</span>
                <span className="block text-xs text-rose-700">{t.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="space-y-2 px-4 py-3">
        {health.components.map((c) => (
          <div key={c.code}>
            <div className="mb-0.5 flex items-center justify-between text-xs">
              <span>{c.label}</span>
              <span className="text-muted-foreground">
                <span className="font-mono">%{c.value_pct}</span> · ağırlık %{c.weight_pct} →{" "}
                <strong className="font-mono">+{c.contribution}</strong>
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded bg-muted">
              <div className={cn("h-full", barColor(c.value_pct))} style={{ width: `${c.value_pct}%` }} />
            </div>
            {c.note ? <div className="mt-0.5 text-[10px] text-muted-foreground">{c.note}</div> : null}
          </div>
        ))}
      </div>

      {history.length >= 2 ? (
        <div className="border-t border-border bg-muted/30 px-4 py-3">
          <div className="mb-2 text-xs text-muted-foreground">Son {history.length} gün skor seyri</div>
          <div className="flex h-12 items-end gap-1">
            {history.map((s, i) => (
              <div key={i} className="flex flex-1 flex-col items-center justify-end gap-0.5"
                   title={`${fmtDate(s.snapshot_date)}: ${s.score}/100`}>
                <div className={cn("w-full rounded-t", barColor(s.score))} style={{ height: `${Math.max(2, s.score)}%` }} />
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  );
}

// ── Plan değişiklik zaman çizelgesi ──────────────────────────────────────────

export function PlanChangesTimeline({ changes }: { changes: PlanChangeItem[] }) {
  if (changes.length === 0) {
    return <div className="py-4 text-center text-sm text-muted-foreground">Plan değişikliği yok.</div>;
  }
  return (
    <ul className="space-y-2">
      {changes.map((pc) => (
        <li key={pc.id} className="flex items-baseline gap-2 text-sm">
          <span className="whitespace-nowrap text-xs text-muted-foreground">{fmtDate(pc.occurred_at)}</span>
          <span>
            {pc.from_plan ? <span className="font-mono text-muted-foreground">{pc.from_plan}</span> : null}
            {pc.from_plan ? " → " : ""}
            <span className="font-mono">{pc.to_plan ?? "—"}</span>
            <span className="ml-1.5 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">{pc.reason}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

// ── CRM Notlar paneli ────────────────────────────────────────────────────────

export function CrmNotesPanel({
  ownerType,
  ownerId,
  notes,
}: {
  ownerType: OwnerType;
  ownerId: number;
  notes: CrmNoteItem[];
}) {
  const [content, setContent] = React.useState("");
  const [pinned, setPinned] = React.useState(false);
  const addMut = useAddCrmNote(ownerType, ownerId);
  const pinMut = usePinCrmNote();
  const delMut = useDeleteCrmNote();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!content.trim()) return;
    addMut.mutate({ content: content.trim(), pinned }, {
      onSuccess: () => {
        setContent("");
        setPinned(false);
      },
    });
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div className="md:col-span-1">
        <Card className="sticky top-4 p-4">
          <h2 className="mb-2 text-sm font-semibold">Yeni Not</h2>
          <form onSubmit={submit}>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={5}
              maxLength={5000}
              required
              placeholder="Görüşme özeti, hatırlatma, niyet bilgisi…"
              className={cn(fieldClass, "mb-2")}
            />
            <label className="mb-2 flex items-center gap-1.5 text-xs text-muted-foreground">
              <input type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} className="rounded border-input" />
              Sabitle (en üstte kalsın)
            </label>
            <Button type="submit" disabled={addMut.isPending} className="w-full bg-indigo-600 text-white hover:bg-indigo-700">
              {addMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Plus className="size-4" aria-hidden />}
              Not ekle
            </Button>
          </form>
        </Card>
      </div>
      <div className="md:col-span-2">
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Notlar ({notes.length})</h2>
          </div>
          {notes.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">Henüz not yok.</div>
          ) : (
            <ul className="divide-y divide-border">
              {notes.map((n) => (
                <li key={n.id} className={cn("px-4 py-3", n.pinned && "bg-amber-50/40")}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      {n.pinned ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-700">
                          <Pin className="size-3" aria-hidden /> SABİT
                        </span>
                      ) : null}
                      <div className="mt-0.5 whitespace-pre-wrap break-words text-sm">{n.content}</div>
                      <div className="mt-1.5 text-[11px] text-muted-foreground">
                        {fmtDateTime(n.created_at)}
                        {n.created_by_name ? ` · ${n.created_by_name}` : ""}
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => pinMut.mutate(n.id)}
                        disabled={pinMut.isPending}
                        title={n.pinned ? "Sabitlemeyi kaldır" : "Sabitle"}
                        className="text-muted-foreground hover:text-amber-700"
                      >
                        {n.pinned ? <PinOff className="size-4" aria-hidden /> : <Pin className="size-4" aria-hidden />}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (confirm("Notu silmek istiyor musun?")) delMut.mutate(n.id);
                        }}
                        disabled={delMut.isPending}
                        title="Sil"
                        className="text-muted-foreground hover:text-rose-700"
                      >
                        <Trash2 className="size-4" aria-hidden />
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

// ── CRM Aksiyon paneli ───────────────────────────────────────────────────────

export function CrmActionsPanel({
  ownerType,
  ownerId,
  actions,
  meta,
}: {
  ownerType: OwnerType;
  ownerId: number;
  actions: CrmActionItem[];
  meta: CrmMeta;
}) {
  const [kind, setKind] = React.useState(meta.action_kinds[0]?.value ?? "call");
  const [summary, setSummary] = React.useState("");
  const [notes, setNotes] = React.useState("");
  const [result, setResult] = React.useState("pending");
  const [followUp, setFollowUp] = React.useState("");
  const [tplLoading, setTplLoading] = React.useState(false);
  const addMut = useAddCrmAction(ownerType, ownerId);
  const completeMut = useCompleteCrmAction();
  const delMut = useDeleteCrmAction();

  // Aksiyon şablonları (hazır script'ler) — owner placeholder'larıyla doldurulur.
  const tplQ = useQuery<ActionTemplatesResponse>({
    queryKey: adminKeys.revenueActionTemplates(),
    queryFn: getAdminActionTemplates,
    staleTime: 60_000,
  });
  const templates = tplQ.data?.templates ?? [];

  async function applyTemplate(id: string) {
    if (!id) return;
    setTplLoading(true);
    try {
      const r = await getAdminActionTemplateRender(Number(id), ownerType, ownerId);
      if (r.kind) setKind(r.kind);
      // Özet: subject varsa o, yoksa gövdenin ilk satırı.
      const firstLine = (r.body || "").split("\n").find((l) => l.trim()) ?? "";
      setSummary((r.subject || firstLine).slice(0, 500));
      setNotes(r.body || "");
    } finally {
      setTplLoading(false);
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!summary.trim()) return;
    addMut.mutate(
      { kind, summary: summary.trim(), notes: notes.trim(), result, follow_up_at: followUp || null },
      {
        onSuccess: () => {
          setSummary("");
          setNotes("");
          setResult("pending");
          setFollowUp("");
        },
      },
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div className="md:col-span-1">
        <Card className="sticky top-4 p-4">
          <h2 className="mb-2 text-sm font-semibold">Yeni Aksiyon</h2>
          {templates.length > 0 ? (
            <label className="mb-2 block rounded-md border border-indigo-200 bg-indigo-50/50 p-2">
              <span className="text-xs font-medium text-indigo-800">Şablondan doldur</span>
              <select
                defaultValue=""
                disabled={tplLoading}
                onChange={(e) => { applyTemplate(e.target.value); e.target.value = ""; }}
                className={cn(fieldClass, "mt-1")}
              >
                <option value="">{tplLoading ? "Dolduruluyor…" : "Şablon seç…"}</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.name} ({t.kind_label})</option>
                ))}
              </select>
              <span className="mt-1 block text-[10px] text-muted-foreground">
                Owner bilgileri ({"{{owner_name}}"}, {"{{plan}}"}, {"{{trial_ends_at}}"}…) otomatik dolar.
              </span>
            </label>
          ) : null}
          <form onSubmit={submit} className="space-y-2">
            <label className="block">
              <span className="text-xs text-muted-foreground">Tür</span>
              <select value={kind} onChange={(e) => setKind(e.target.value)} className={cn(fieldClass, "mt-1")}>
                {meta.action_kinds.map((k) => (
                  <option key={k.value} value={k.value}>{k.label}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Özet</span>
              <input type="text" value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={500} required
                     placeholder="Kısa açıklama…" className={cn(fieldClass, "mt-1")} />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Detay (opsiyonel)</span>
              <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className={cn(fieldClass, "mt-1")} />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Sonuç</span>
              <select value={result} onChange={(e) => setResult(e.target.value)} className={cn(fieldClass, "mt-1")}>
                {meta.action_results.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Takip tarihi (opsiyonel)</span>
              <input type="date" value={followUp} onChange={(e) => setFollowUp(e.target.value)} className={cn(fieldClass, "mt-1")} />
            </label>
            <Button type="submit" disabled={addMut.isPending} className="w-full bg-indigo-600 text-white hover:bg-indigo-700">
              {addMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Plus className="size-4" aria-hidden />}
              Aksiyon ekle
            </Button>
          </form>
        </Card>
      </div>
      <div className="md:col-span-2">
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Aksiyonlar ({actions.length})</h2>
            <p className="text-xs text-muted-foreground">Bekleyenler ve son aksiyonlar üstte.</p>
          </div>
          {actions.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">Henüz aksiyon yok.</div>
          ) : (
            <ul className="divide-y divide-border">
              {actions.map((a) => (
                <ActionRow key={a.id} a={a} meta={meta} completeMut={completeMut} delMut={delMut} />
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function ActionRow({
  a,
  meta,
  completeMut,
  delMut,
}: {
  a: CrmActionItem;
  meta: CrmMeta;
  completeMut: ReturnType<typeof useCompleteCrmAction>;
  delMut: ReturnType<typeof useDeleteCrmAction>;
}) {
  const [open, setOpen] = React.useState(false);
  const [result, setResult] = React.useState("success");
  const [notes, setNotes] = React.useState("");

  return (
    <li className={cn("px-4 py-3", !a.completed_at && "bg-indigo-50/30")}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium">{a.kind_label}</span>
            <span className={cn("rounded border px-1.5 py-0.5 text-[10px] font-semibold", badge(a.result_color))}>
              {a.result_label}
            </span>
          </div>
          <div className="mt-1 text-sm">{a.summary}</div>
          {a.notes ? <div className="mt-1 whitespace-pre-wrap break-words text-xs text-muted-foreground">{a.notes}</div> : null}
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 text-[11px] text-muted-foreground">
            <span>{fmtDateTime(a.created_at)}</span>
            {a.created_by_name ? <span>· {a.created_by_name}</span> : null}
            {a.follow_up_at ? (
              <span className="inline-flex items-center gap-0.5">
                · <Bell className="size-3" aria-hidden /> takip: <strong>{fmtDate(a.follow_up_at)}</strong>
              </span>
            ) : null}
            {a.completed_at ? (
              <span className="inline-flex items-center gap-0.5">
                · <CheckCircle2 className="size-3" aria-hidden /> {fmtDateTime(a.completed_at)}
              </span>
            ) : null}
          </div>
          {!a.completed_at ? (
            <div className="mt-2">
              {open ? (
                <div className="flex flex-wrap items-center gap-2">
                  <select value={result} onChange={(e) => setResult(e.target.value)} className={cn(fieldClass, "w-auto py-1 text-xs")}>
                    {meta.action_results.map((r) => (
                      <option key={r.value} value={r.value}>{r.label}</option>
                    ))}
                  </select>
                  <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500}
                         placeholder="Sonuç notu (opsiyonel)" className={cn(fieldClass, "min-w-[180px] flex-1 py-1 text-xs")} />
                  <Button
                    size="sm"
                    disabled={completeMut.isPending}
                    onClick={() => completeMut.mutate({ actionId: a.id, body: { result, notes } }, { onSettled: () => setOpen(false) })}
                    className="bg-emerald-600 text-white hover:bg-emerald-700"
                  >
                    Tamamla
                  </Button>
                </div>
              ) : (
                <button type="button" onClick={() => setOpen(true)} className="text-xs text-emerald-700 hover:text-emerald-900">
                  Tamamla / sonuç gir
                </button>
              )}
            </div>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => {
            if (confirm("Aksiyonu silmek istiyor musun?")) delMut.mutate(a.id);
          }}
          disabled={delMut.isPending}
          title="Sil"
          className="shrink-0 text-muted-foreground hover:text-rose-700"
        >
          <Trash2 className="size-4" aria-hidden />
        </button>
      </div>
    </li>
  );
}

// ── İletişim + Etiket paneli ─────────────────────────────────────────────────

export function ContactAndTagsPanel({
  ownerType,
  ownerId,
  contact,
  tags,
  meta,
}: {
  ownerType: OwnerType;
  ownerId: number;
  contact: OwnerContactData | null;
  tags: OwnerTagItem[];
  meta: CrmMeta;
}) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <OwnerContactForm ownerType={ownerType} ownerId={ownerId} contact={contact} />
      <OwnerTagsCard ownerType={ownerType} ownerId={ownerId} tags={tags} meta={meta} />
    </div>
  );
}

function OwnerContactForm({
  ownerType,
  ownerId,
  contact,
}: {
  ownerType: OwnerType;
  ownerId: number;
  contact: OwnerContactData | null;
}) {
  const saveMut = useSaveOwnerContact(ownerType, ownerId);
  const [form, setForm] = React.useState({
    responsible_person_name: contact?.responsible_person_name ?? "",
    responsible_person_title: contact?.responsible_person_title ?? "",
    billing_email: contact?.billing_email ?? "",
    phone: contact?.phone ?? "",
    whatsapp: contact?.whatsapp ?? "",
    linkedin_url: contact?.linkedin_url ?? "",
    website: contact?.website ?? "",
    address: contact?.address ?? "",
    note: contact?.note ?? "",
  });
  function set(k: keyof typeof form, v: string) {
    setForm((p) => ({ ...p, [k]: v }));
  }
  const fields: { key: keyof typeof form; label: string; type?: string }[] = [
    { key: "responsible_person_name", label: "Yetkili kişi" },
    { key: "responsible_person_title", label: "Unvan" },
    { key: "billing_email", label: "Fatura e-postası", type: "email" },
    { key: "phone", label: "Telefon" },
    { key: "whatsapp", label: "WhatsApp" },
    { key: "linkedin_url", label: "LinkedIn" },
    { key: "website", label: "Web sitesi" },
  ];
  return (
    <Card className="p-4">
      <h2 className="mb-3 text-sm font-semibold">İletişim Bilgileri</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          saveMut.mutate(form);
        }}
        className="space-y-2"
      >
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {fields.map((f) => (
            <label key={f.key} className="block">
              <span className="text-xs text-muted-foreground">{f.label}</span>
              <input type={f.type ?? "text"} value={form[f.key]} onChange={(e) => set(f.key, e.target.value)} className={cn(fieldClass, "mt-1")} />
            </label>
          ))}
        </div>
        <label className="block">
          <span className="text-xs text-muted-foreground">Adres</span>
          <textarea value={form.address} onChange={(e) => set("address", e.target.value)} rows={2} className={cn(fieldClass, "mt-1")} />
        </label>
        <label className="block">
          <span className="text-xs text-muted-foreground">Not (sözleşme/özel anlaşma)</span>
          <textarea value={form.note} onChange={(e) => set("note", e.target.value)} rows={2} className={cn(fieldClass, "mt-1")} />
        </label>
        <Button type="submit" disabled={saveMut.isPending} className="bg-indigo-600 text-white hover:bg-indigo-700">
          {saveMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Save className="size-4" aria-hidden />}
          Kaydet
        </Button>
        {contact?.updated_at ? (
          <p className="text-[11px] text-muted-foreground">Son güncelleme: {fmtDateTime(contact.updated_at)}</p>
        ) : null}
      </form>
    </Card>
  );
}

function OwnerTagsCard({
  ownerType,
  ownerId,
  tags,
  meta,
}: {
  ownerType: OwnerType;
  ownerId: number;
  tags: OwnerTagItem[];
  meta: CrmMeta;
}) {
  const addMut = useAddOwnerTag(ownerType, ownerId);
  const delMut = useDeleteOwnerTag();
  const existing = new Set(tags.map((t) => t.kind));
  const available = meta.tag_kinds.filter((k) => !existing.has(k.value));
  const [kindRaw, setKind] = React.useState("");
  const [note, setNote] = React.useState("");
  // Seçili tür available listesinden düşmüşse ilk uygun türe geri düş (effect'siz).
  const kind = available.some((a) => a.value === kindRaw)
    ? kindRaw
    : (available[0]?.value ?? "");

  return (
    <Card className="p-4">
      <h2 className="mb-3 text-sm font-semibold">Etiketler</h2>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {tags.length === 0 ? (
          <span className="text-sm text-muted-foreground">Henüz etiket yok.</span>
        ) : (
          tags.map((t) => (
            <span key={t.id} title={t.description}
                  className={cn("inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium", badge(t.color))}>
              {t.label}
              <button type="button" onClick={() => delMut.mutate(t.id)} disabled={delMut.isPending} className="hover:opacity-60" aria-label="Etiketi kaldır">
                <Trash2 className="size-3" aria-hidden />
              </button>
            </span>
          ))
        )}
      </div>
      {available.length > 0 ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!kind) return;
            addMut.mutate({ kind, note }, { onSuccess: () => setNote("") });
          }}
          className="flex flex-wrap items-end gap-2"
        >
          <label className="block flex-1">
            <span className="text-xs text-muted-foreground">Etiket türü</span>
            <select value={kind} onChange={(e) => setKind(e.target.value)} className={cn(fieldClass, "mt-1")}>
              {available.map((k) => (
                <option key={k.value} value={k.value}>{k.label}</option>
              ))}
            </select>
          </label>
          <label className="block flex-1">
            <span className="text-xs text-muted-foreground">Not (opsiyonel)</span>
            <input type="text" value={note} onChange={(e) => setNote(e.target.value)} maxLength={500} className={cn(fieldClass, "mt-1")} />
          </label>
          <Button type="submit" disabled={addMut.isPending} className="bg-indigo-600 text-white hover:bg-indigo-700">
            <Plus className="size-4" aria-hidden /> Ekle
          </Button>
        </form>
      ) : (
        <p className="text-xs text-muted-foreground">Tüm etiketler eklenmiş.</p>
      )}
    </Card>
  );
}

// ── Sekme barı ───────────────────────────────────────────────────────────────

export function TabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string; badge?: number }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-center gap-1 border-b border-border">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={cn(
            "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
            active === t.id
              ? "border-indigo-500 text-indigo-700"
              : "border-transparent text-muted-foreground hover:border-border hover:text-foreground",
          )}
        >
          {t.label}
          {t.badge && t.badge > 0 ? (
            <span className={cn(
              "ml-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1 text-[10px]",
              active === t.id ? "bg-indigo-100 text-indigo-800" : "bg-muted text-muted-foreground",
            )}>
              {t.badge}
            </span>
          ) : null}
        </button>
      ))}
    </div>
  );
}

// ── Teklifler paneli ─────────────────────────────────────────────────────────

export function OffersPanel({
  ownerType,
  ownerId,
  offers,
  meta,
}: {
  ownerType: OwnerType;
  ownerId: number;
  offers: OfferItem[];
  meta: CrmMeta;
}) {
  const createMut = useCreateOffer(ownerType, ownerId);
  const sendMut = useSendOffer();
  const cancelMut = useCancelOffer();
  const updateMut = useUpdateOffer();
  // DRAFT teklif düzenleme (göndermeden son rötuş)
  const [editId, setEditId] = React.useState<number | null>(null);
  const [eTitle, setETitle] = React.useState("");
  const [eMsg, setEMsg] = React.useState("");
  const [eNote, setENote] = React.useState("");

  function startEdit(o: OfferItem) {
    setEditId(o.id);
    setETitle(o.title);
    setEMsg(o.public_message ?? "");
    setENote(o.admin_note ?? "");
  }
  function saveEdit(o: OfferItem) {
    updateMut.mutate(
      {
        offerId: o.id,
        body: {
          kind: o.kind, title: eTitle.trim() || o.title,
          value: o.value, duration_months: o.duration_months,
          new_plan: o.new_plan ?? "", public_message: eMsg, admin_note: eNote,
        },
      },
      { onSuccess: () => setEditId(null) },
    );
  }

  const [kind, setKind] = React.useState(meta.offer_kinds[0]?.value ?? "discount_percent");
  const [title, setTitle] = React.useState("");
  const [value, setValue] = React.useState("");
  const [duration, setDuration] = React.useState("");
  const [newPlan, setNewPlan] = React.useState("");
  const [publicMsg, setPublicMsg] = React.useState("");
  const [adminNote, setAdminNote] = React.useState("");
  const [expires, setExpires] = React.useState("14");
  const [sendNow, setSendNow] = React.useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    createMut.mutate(
      {
        kind,
        title: title.trim(),
        value: value.trim() ? Number(value.replace(",", ".")) : null,
        duration_months: duration.trim() ? Number(duration) : null,
        new_plan: newPlan.trim(),
        public_message: publicMsg.trim(),
        admin_note: adminNote.trim(),
        expires_in_days: Number(expires) || 14,
        send_now: sendNow,
      },
      {
        onSuccess: () => {
          setTitle("");
          setValue("");
          setDuration("");
          setNewPlan("");
          setPublicMsg("");
          setAdminNote("");
          setSendNow(false);
        },
      },
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <div className="md:col-span-1">
        <Card className="sticky top-4 p-4">
          <h2 className="mb-2 inline-flex items-center gap-1.5 text-sm font-semibold">
            <Gift className="size-4 text-indigo-700" aria-hidden /> Yeni Teklif
          </h2>
          <form onSubmit={submit} className="space-y-2">
            <label className="block">
              <span className="text-xs text-muted-foreground">Tür</span>
              <select value={kind} onChange={(e) => setKind(e.target.value)} className={cn(fieldClass, "mt-1")}>
                {meta.offer_kinds.map((k) => (
                  <option key={k.value} value={k.value}>{k.label}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Başlık (owner&apos;a görünür)</span>
              <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={255} required
                     placeholder="ör. 3 ay %20 indirim" className={cn(fieldClass, "mt-1")} />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="block">
                <span className="text-xs text-muted-foreground">Değer</span>
                <input type="number" step="0.01" min="0" value={value} onChange={(e) => setValue(e.target.value)}
                       placeholder="20" className={cn(fieldClass, "mt-1")} />
              </label>
              <label className="block">
                <span className="text-xs text-muted-foreground">Süre (ay)</span>
                <input type="number" min="1" max="999" value={duration} onChange={(e) => setDuration(e.target.value)}
                       placeholder="3" className={cn(fieldClass, "mt-1")} />
              </label>
            </div>
            <label className="block">
              <span className="text-xs text-muted-foreground">Yeni plan (yükseltme için)</span>
              <input type="text" value={newPlan} onChange={(e) => setNewPlan(e.target.value)} maxLength={32}
                     placeholder="kurumsal_max" className={cn(fieldClass, "mt-1 font-mono")} />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Owner&apos;a mesaj</span>
              <textarea value={publicMsg} onChange={(e) => setPublicMsg(e.target.value)} rows={2} className={cn(fieldClass, "mt-1")} />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Admin notu (görünmez)</span>
              <textarea value={adminNote} onChange={(e) => setAdminNote(e.target.value)} rows={2} className={cn(fieldClass, "mt-1")} />
            </label>
            <label className="block">
              <span className="text-xs text-muted-foreground">Geçerlilik (gün)</span>
              <input type="number" min="0" max="365" value={expires} onChange={(e) => setExpires(e.target.value)} className={cn(fieldClass, "mt-1")} />
            </label>
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" checked={sendNow} onChange={(e) => setSendNow(e.target.checked)} className="rounded border-input" />
              Oluşturduktan sonra hemen gönder (e-posta)
            </label>
            <Button type="submit" disabled={createMut.isPending} className="w-full bg-indigo-600 text-white hover:bg-indigo-700">
              {createMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Plus className="size-4" aria-hidden />}
              Teklifi kaydet
            </Button>
          </form>
        </Card>
      </div>
      <div className="md:col-span-2">
        <Card className="overflow-hidden">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Teklifler ({offers.length})</h2>
          </div>
          {offers.length === 0 ? (
            <div className="px-4 py-10 text-center text-sm text-muted-foreground">Henüz teklif yok.</div>
          ) : (
            <ul className="divide-y divide-border">
              {offers.map((o) => (
                <li key={o.id} className={cn("px-4 py-3", o.status === "sent" && "bg-amber-50/30")}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium">{o.title}</span>
                        <span className={cn("rounded border px-1.5 py-0.5 text-[10px] font-semibold", badge(o.status_color))}>
                          {o.status_label}
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {o.kind_label}
                        {o.summary && o.summary !== o.title ? ` · ${o.summary}` : ""}
                      </div>
                      {o.public_message ? (
                        <div className="mt-1 whitespace-pre-wrap break-words text-xs italic text-muted-foreground">
                          &ldquo;{o.public_message}&rdquo;
                        </div>
                      ) : null}
                      {o.admin_note ? (
                        <div className="mt-1 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] text-amber-700">
                          <strong>Not (iç):</strong> {o.admin_note}
                        </div>
                      ) : null}
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 text-[11px] text-muted-foreground">
                        <span>Oluşturuldu: {fmtDateTime(o.created_at)}</span>
                        {o.sent_at ? <span>· Gönderildi: {fmtDateTime(o.sent_at)}</span> : null}
                        {o.viewed_at ? (
                          <span className="font-medium text-emerald-700">· Açıldı: {fmtDateTime(o.viewed_at)}</span>
                        ) : o.status === "sent" ? (
                          <span className="text-amber-700">· Henüz açılmadı</span>
                        ) : null}
                        {o.responded_at ? <span>· Yanıt: {fmtDateTime(o.responded_at)}</span> : null}
                        {o.expires_at ? <span>· Son: {fmtDate(o.expires_at)}</span> : null}
                      </div>
                      {o.decline_reason ? (
                        <div className="mt-1.5 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700">
                          <strong>Ret nedeni:</strong> {o.decline_reason}
                        </div>
                      ) : null}
                      {o.status === "draft" && editId === o.id ? (
                        <div className="mt-2 space-y-2 rounded-lg border border-indigo-200 bg-indigo-50/40 p-2">
                          <label className="block">
                            <span className="text-[11px] text-muted-foreground">Başlık</span>
                            <input type="text" value={eTitle} onChange={(e) => setETitle(e.target.value)} maxLength={255} className={cn(fieldClass, "mt-0.5")} />
                          </label>
                          <label className="block">
                            <span className="text-[11px] text-muted-foreground">Owner&apos;a mesaj</span>
                            <textarea value={eMsg} onChange={(e) => setEMsg(e.target.value)} rows={2} className={cn(fieldClass, "mt-0.5")} />
                          </label>
                          <label className="block">
                            <span className="text-[11px] text-muted-foreground">Admin notu (görünmez)</span>
                            <textarea value={eNote} onChange={(e) => setENote(e.target.value)} rows={1} className={cn(fieldClass, "mt-0.5")} />
                          </label>
                          <div className="flex gap-2">
                            <Button size="sm" disabled={updateMut.isPending} onClick={() => saveEdit(o)} className="bg-indigo-600 text-white hover:bg-indigo-700">
                              {updateMut.isPending ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : <Save className="size-3.5" aria-hidden />} Kaydet
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>Vazgeç</Button>
                          </div>
                        </div>
                      ) : null}
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {o.status === "draft" ? (
                          <>
                            <Button size="sm" disabled={sendMut.isPending} onClick={() => sendMut.mutate(o.id)} className="bg-emerald-600 text-white hover:bg-emerald-700">
                              <Send className="size-3.5" aria-hidden /> Gönder
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => (editId === o.id ? setEditId(null) : startEdit(o))}>
                              Düzenle
                            </Button>
                            <Button size="sm" variant="outline" disabled={cancelMut.isPending} onClick={() => cancelMut.mutate(o.id)}>
                              İptal
                            </Button>
                          </>
                        ) : o.status === "sent" ? (
                          <>
                            <a href={`/offers/${o.token}`} target="_blank" rel="noreferrer"
                               className="inline-flex items-center gap-1 rounded border border-indigo-300 bg-card px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50">
                              <ExternalLink className="size-3.5" aria-hidden /> Public link
                            </a>
                            <Button size="sm" variant="outline" disabled={cancelMut.isPending} onClick={() => cancelMut.mutate(o.id)}>
                              Geri çek
                            </Button>
                          </>
                        ) : (
                          <a href={`/offers/${o.token}`} target="_blank" rel="noreferrer"
                             className="inline-flex items-center gap-1 rounded border border-border bg-card px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted">
                            <ExternalLink className="size-3.5" aria-hidden /> Public link
                          </a>
                        )}
                      </div>
                    </div>
                    <span className="shrink-0 font-mono text-[10px] text-muted-foreground">#{o.id}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

// ── Fatura tablosu (tahsilat müdahaleleri) ───────────────────────────────────

export function InvoicesTable({ invoices }: { invoices: InvoiceItem[] }) {
  if (invoices.length === 0) {
    return (
      <Card className="p-8 text-center text-sm text-muted-foreground">
        Bu owner için fatura kaydı yok.
      </Card>
    );
  }
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold">Faturalar ({invoices.length})</h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th className="px-4 py-2 text-left font-medium">Durum</th>
              <th className="px-4 py-2 text-left font-medium">Vade</th>
              <th className="px-4 py-2 text-right font-medium">Tutar</th>
              <th className="px-4 py-2 text-left font-medium">Plan</th>
              <th className="px-4 py-2 text-left font-medium">Dunning</th>
              <th className="px-4 py-2 text-right font-medium">Eylem</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {invoices.map((inv) => (
              <InvoiceRow key={inv.invoice_id} inv={inv} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

const INVOICE_TONE: Record<string, string> = {
  pending: "slate",
  paid: "emerald",
  overdue: "rose",
  failed: "rose",
  refunded: "amber",
  cancelled: "slate",
};

function InvoiceRow({ inv }: { inv: InvoiceItem }) {
  const postponeMut = usePostponeInvoice();
  const markPaidMut = useMarkInvoicePaid();
  const cancelMut = useCancelInvoice();
  const reminderMut = useSendInvoiceReminder();
  const eligible = inv.status === "pending" || inv.status === "overdue";
  const tone = INVOICE_TONE[inv.status] ?? "slate";
  const busy = postponeMut.isPending || markPaidMut.isPending || cancelMut.isPending || reminderMut.isPending;

  return (
    <tr className="hover:bg-muted/40">
      <td className="px-4 py-2 whitespace-nowrap">
        <span className={cn("rounded border px-2 py-0.5 text-[10px] font-semibold", badge(tone))}>
          {inv.status_label}
        </span>
      </td>
      <td className="px-4 py-2 text-xs">
        {fmtDate(inv.due_at)}
        {inv.days_overdue > 0 ? (
          <div className="text-[10px] font-semibold text-rose-600">{inv.days_overdue}g gecikmiş</div>
        ) : inv.days_until_due != null && inv.days_until_due <= 7 && inv.status === "pending" ? (
          <div className="text-[10px] text-amber-600">{inv.days_until_due}g kaldı</div>
        ) : null}
      </td>
      <td className="px-4 py-2 text-right font-mono font-semibold whitespace-nowrap">{tl(inv.amount_try)}</td>
      <td className="px-4 py-2 text-xs text-muted-foreground">{inv.plan_label}</td>
      <td className="px-4 py-2 text-xs">
        {inv.last_reminder_kind ? (
          <span className="text-amber-700">
            {inv.last_reminder_kind}
            {inv.attempt_count ? <span className="text-muted-foreground">·{inv.attempt_count}</span> : null}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-2 text-right whitespace-nowrap">
        {eligible ? (
          <div className="inline-flex items-center gap-1">
            <button type="button" disabled={busy}
                    onClick={() => reminderMut.mutate({ invoiceId: inv.invoice_id, body: { kind: "manual" } })}
                    title="Hatırlatma gönder"
                    className="rounded border border-sky-200 bg-sky-50 px-2 py-0.5 text-[11px] text-sky-700 hover:bg-sky-100 disabled:opacity-50">
              <BellRing className="size-3.5" aria-hidden />
            </button>
            <button type="button" disabled={busy}
                    onClick={() => { const d = prompt("Kaç gün ötelensin?", "7"); if (d) postponeMut.mutate({ invoiceId: inv.invoice_id, body: { days: Number(d) } }); }}
                    title="Vadeyi ötele"
                    className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] text-amber-700 hover:bg-amber-100 disabled:opacity-50">
              <CalendarClock className="size-3.5" aria-hidden />
            </button>
            <button type="button" disabled={busy}
                    onClick={() => { if (confirm("Manuel ödendi işaretlensin mi?")) markPaidMut.mutate({ invoiceId: inv.invoice_id, body: { method: "manual" } }); }}
                    title="Manuel ödendi"
                    className="rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700 hover:bg-emerald-100 disabled:opacity-50">
              <CheckCircle2 className="size-3.5" aria-hidden />
            </button>
            <button type="button" disabled={busy}
                    onClick={() => { const n = prompt("İptal sebebi?"); if (n != null) cancelMut.mutate({ invoiceId: inv.invoice_id, body: { note: n } }); }}
                    title="İptal et"
                    className="rounded border border-rose-200 bg-rose-50 px-2 py-0.5 text-[11px] text-rose-700 hover:bg-rose-100 disabled:opacity-50">
              <Ban className="size-3.5" aria-hidden />
            </button>
          </div>
        ) : (
          <span className="text-[11px] text-muted-foreground">—</span>
        )}
      </td>
    </tr>
  );
}

export { fmtDate, fmtDateTime };
