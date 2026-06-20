"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2, Save, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  useCreateFeatureCard,
  useDeleteFeatureCard,
  useUpdateFeatureCard,
} from "@/lib/hooks/use-admin-mutations";
import type {
  FeatureCardBody,
  FeatureCardFormResponse,
} from "@/lib/types/admin";
import { fieldClass } from "@/components/admin/feature-catalog-ui";
import { LandingCardPreview } from "@/components/landing/card-preview";

interface Props {
  initial: FeatureCardFormResponse;
  mode: "new" | "edit";
}

function toLocalDt(iso: string | null): string {
  if (!iso) return "";
  return iso.slice(0, 16);
}

function linesToList(text: string): string[] {
  return text
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function AdminFeatureCardFormClient({ initial, mode }: Props) {
  const router = useRouter();
  const card = initial.card;
  const meta = initial.meta;
  const isEdit = mode === "edit" && card != null;

  const [slug, setSlug] = React.useState(card?.slug ?? "");
  const [title, setTitle] = React.useState(card?.title ?? "");
  const [categoryIcon, setCategoryIcon] = React.useState(card?.category_icon ?? "✨");
  const [categoryLabel, setCategoryLabel] = React.useState(card?.category_label ?? "");
  const [tagline, setTagline] = React.useState(card?.tagline ?? "");
  const [benefits, setBenefits] = React.useState((card?.benefits ?? []).join("\n"));
  const [demoSlug, setDemoSlug] = React.useState(card?.demo_slug ?? "");
  const [demoDuration, setDemoDuration] = React.useState(card?.demo_duration_label ?? "");
  const [mockupType, setMockupType] = React.useState(card?.mockup_type ?? "");
  const [descriptionMd, setDescriptionMd] = React.useState(card?.description_md ?? "");
  const [painPoints, setPainPoints] = React.useState((card?.pain_points ?? []).join("\n"));
  const [ctaLabel, setCtaLabel] = React.useState(card?.cta_label ?? "Detayları gör");
  const [ctaUrl, setCtaUrl] = React.useState(card?.cta_url ?? "");
  const [introducedAt, setIntroducedAt] = React.useState(toLocalDt(card?.introduced_at ?? null));
  const [introCommit, setIntroCommit] = React.useState(card?.introduced_in_commit ?? "");
  const [prUrl, setPrUrl] = React.useState(card?.pr_url ?? "");
  const [accentColor, setAccentColor] = React.useState(card?.accent_color ?? "#3b82f6");
  const [icon, setIcon] = React.useState(card?.icon ?? "sparkles");
  const [domain, setDomain] = React.useState(card?.domain ?? "genel");
  const [tier, setTier] = React.useState(card?.tier ?? "enhancement");
  const [status, setStatus] = React.useState(card?.status ?? "draft");
  const [roles, setRoles] = React.useState<Set<string>>(
    new Set(card?.target_roles ?? []),
  );
  const [priority, setPriority] = React.useState(card?.strategic_priority ?? 3);
  const [manualPin, setManualPin] = React.useState(card?.manual_pin ?? false);
  const [pinUntil, setPinUntil] = React.useState(toLocalDt(card?.pin_until ?? null));
  const [manualHide, setManualHide] = React.useState(card?.manual_hide ?? false);

  const createMut = useCreateFeatureCard();
  const updateMut = useUpdateFeatureCard(card?.id ?? 0);
  const deleteMut = useDeleteFeatureCard(card?.id ?? 0);
  const [delOpen, setDelOpen] = React.useState(false);
  const pending = createMut.isPending || updateMut.isPending;

  function toggleRole(value: string) {
    setRoles((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function buildBody(): FeatureCardBody {
    return {
      slug,
      title,
      tagline,
      description_md: descriptionMd,
      icon,
      accent_color: accentColor,
      category_icon: categoryIcon,
      category_label: categoryLabel,
      demo_duration_label: demoDuration,
      mockup_type: mockupType || null,
      target_roles: Array.from(roles),
      benefits: linesToList(benefits),
      pain_points: linesToList(painPoints),
      demo_slug: demoSlug,
      domain,
      tier,
      status,
      introduced_at: introducedAt || null,
      introduced_in_commit: introCommit,
      pr_url: prUrl,
      strategic_priority: priority,
      manual_pin: manualPin,
      pin_until: pinUntil || null,
      manual_hide: manualHide,
      cta_label: ctaLabel,
      cta_url: ctaUrl,
    };
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const body = buildBody();
    if (isEdit) {
      updateMut.mutate(body);
    } else {
      createMut.mutate(body, {
        onSuccess: (res) => {
          const newId = res.data.card_id;
          if (newId) router.push(`/admin/feature-catalog/${newId}`);
          else router.push("/admin/feature-catalog");
        },
      });
    }
  }

  function onDelete() {
    deleteMut.mutate(undefined, {
      onSuccess: () => router.push("/admin/feature-catalog"),
    });
  }

  return (
    <div className="space-y-5">
      <header>
        <Link
          href="/admin/feature-catalog"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Vitrin Kartları
        </Link>
        <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight">
          {isEdit ? card!.title : "Yeni Vitrin Kartı"}
        </h1>
        {isEdit ? (
          <p className="mt-1 font-mono text-xs text-muted-foreground">{card!.slug}</p>
        ) : null}
      </header>

      <form onSubmit={onSubmit} className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Sol — ana içerik */}
        <div className="space-y-4 lg:col-span-2">
          <Card className="p-5">
            <h2 className="mb-3 text-sm font-medium">1. Kimlik</h2>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field label="Slug *" hint="URL'de + programda. Sadece a-z, 0-9, '-'.">
                <input
                  type="text"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  required
                  maxLength={80}
                  placeholder="rotam"
                  className={cn(fieldClass, "font-mono")}
                />
              </Field>
              <Field label="Ana başlık *" hint="Kartın büyük başlığı. Anasayfada görünür.">
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  required
                  maxLength={160}
                  className={fieldClass}
                />
              </Field>
            </div>
          </Card>

          <Card className="border-2 border-indigo-200 bg-indigo-50/40 p-5 dark:bg-indigo-500/10 dark:border-indigo-500/30">
            <div className="mb-3 flex items-baseline justify-between">
              <h2 className="text-sm font-semibold text-indigo-900">
                🏠 2. Anasayfa Kart Görünümü
              </h2>
              <span className="text-[10px] italic text-indigo-700">
                tümü anasayfada görünür
              </span>
            </div>
            <div className="mb-4 grid grid-cols-[80px_1fr] gap-3">
              <Field label="İkon" hint="Emoji">
                <input
                  type="text"
                  value={categoryIcon}
                  onChange={(e) => setCategoryIcon(e.target.value)}
                  maxLength={16}
                  placeholder="📅"
                  className={cn(fieldClass, "bg-background text-center text-lg")}
                />
              </Field>
              <Field
                label="Kategori rozeti metni"
                hint='Örn. "Günlük Rota", "FSRS". UPPERCASE çevrilir.'
              >
                <input
                  type="text"
                  value={categoryLabel}
                  onChange={(e) => setCategoryLabel(e.target.value)}
                  maxLength={64}
                  className={cn(fieldClass, "bg-background")}
                />
              </Field>
            </div>
            <Field
              label="Açıklama paragrafı"
              hint="2-3 cümle. <strong>/<em> destekler. Maks 400 karakter."
            >
              <textarea
                value={tagline}
                onChange={(e) => setTagline(e.target.value)}
                rows={3}
                maxLength={400}
                className={cn(fieldClass, "bg-background")}
              />
            </Field>
            <div className="mt-4">
              <Field
                label="Özellik etiketleri (chipler)"
                hint="Her satıra bir chip. Emoji ile başlatın. 2-4 ideal."
              >
                <textarea
                  value={benefits}
                  onChange={(e) => setBenefits(e.target.value)}
                  rows={3}
                  placeholder={"⚡ Tek tıkla AI onayı\n🔀 Drag-and-drop sıralama"}
                  className={cn(fieldClass, "bg-background")}
                />
              </Field>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              <Field label="Demo slug (opsiyonel)" hint="Boşsa demo butonu gizlenir.">
                <input
                  type="text"
                  value={demoSlug}
                  onChange={(e) => setDemoSlug(e.target.value)}
                  maxLength={80}
                  placeholder="daily-plan"
                  className={cn(fieldClass, "bg-background font-mono")}
                />
              </Field>
              <Field label="Demo süre etiketi (opsiyonel)">
                <input
                  type="text"
                  value={demoDuration}
                  onChange={(e) => setDemoDuration(e.target.value)}
                  maxLength={64}
                  placeholder="2 dk · 8 sahne"
                  className={cn(fieldClass, "bg-background")}
                />
              </Field>
            </div>
            <div className="mt-4">
              <Field
                label="Sağ-yan görsel şablonu (opsiyonel)"
                hint="Anasayfa kartının sağındaki micro-UI mockup'ı."
              >
                <select
                  value={mockupType}
                  onChange={(e) => setMockupType(e.target.value)}
                  className={cn(fieldClass, "bg-background")}
                >
                  <option value="">— Görsel yok (geniş tek kolon) —</option>
                  {meta.mockups.map((m) => (
                    <option key={m.key} value={m.key}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
          </Card>

          <details className="rounded-lg border border-border bg-card">
            <summary className="cursor-pointer px-5 py-3 text-sm font-medium hover:bg-muted/40">
              3. Detay sayfası içeriği{" "}
              <span className="text-[10px] text-muted-foreground">(opsiyonel)</span>
            </summary>
            <div className="space-y-3 px-5 pb-5 pt-2">
              <Field label="Uzun açıklama (Markdown)">
                <textarea
                  value={descriptionMd}
                  onChange={(e) => setDescriptionMd(e.target.value)}
                  rows={5}
                  className={cn(fieldClass, "font-mono")}
                />
              </Field>
              <Field label="Hangi sorunu çözüyor" hint="Her satıra bir madde. Anasayfada görünmez.">
                <textarea
                  value={painPoints}
                  onChange={(e) => setPainPoints(e.target.value)}
                  rows={3}
                  className={fieldClass}
                />
              </Field>
            </div>
          </details>

          <details className="rounded-lg border border-border bg-card">
            <summary className="cursor-pointer px-5 py-3 text-sm font-medium hover:bg-muted/40">
              4. Detay düğmesi (CTA){" "}
              <span className="text-[10px] text-muted-foreground">(opsiyonel)</span>
            </summary>
            <div className="grid grid-cols-1 gap-3 px-5 pb-5 pt-2 md:grid-cols-2">
              <Field label="Buton metni">
                <input
                  type="text"
                  value={ctaLabel}
                  onChange={(e) => setCtaLabel(e.target.value)}
                  maxLength={80}
                  className={fieldClass}
                />
              </Field>
              <Field label="Buton bağlantısı" hint="Boşsa buton gösterilmez.">
                <input
                  type="text"
                  value={ctaUrl}
                  onChange={(e) => setCtaUrl(e.target.value)}
                  maxLength={255}
                  placeholder="/features/rotam"
                  className={fieldClass}
                />
              </Field>
            </div>
          </details>

          <details className="rounded-lg border border-border bg-card">
            <summary className="cursor-pointer px-5 py-3 text-sm font-medium hover:bg-muted/40">
              5. Kaynak{" "}
              <span className="text-[10px] text-muted-foreground">(otomatik dolar)</span>
            </summary>
            <div className="grid grid-cols-1 gap-3 px-5 pb-5 pt-2 md:grid-cols-3">
              <Field label="Eklenme tarihi">
                <input
                  type="datetime-local"
                  value={introducedAt}
                  onChange={(e) => setIntroducedAt(e.target.value)}
                  className={fieldClass}
                />
              </Field>
              <Field label="İlk commit SHA">
                <input
                  type="text"
                  value={introCommit}
                  onChange={(e) => setIntroCommit(e.target.value)}
                  maxLength={40}
                  className={cn(fieldClass, "font-mono")}
                />
              </Field>
              <Field label="PR URL">
                <input
                  type="text"
                  value={prUrl}
                  onChange={(e) => setPrUrl(e.target.value)}
                  maxLength={255}
                  className={fieldClass}
                />
              </Field>
            </div>
          </details>
        </div>

        {/* Sağ — yönetim */}
        <div className="space-y-4">
          {/* Canlı anasayfa önizlemesi — yayın öncesi "nasıl görünecek" simülasyonu */}
          <Card className="overflow-hidden border-2 border-cyan-200 bg-cyan-50/40 p-0 dark:bg-cyan-500/10 dark:border-cyan-500/30">
            <div className="flex items-baseline justify-between px-4 pb-2 pt-4">
              <h2 className="text-sm font-semibold text-cyan-900">
                🏠 Anasayfa önizlemesi
              </h2>
              <span className="text-[10px] italic text-cyan-700">canlı</span>
            </div>
            <p className="px-4 pb-3 text-[11px] text-cyan-800">
              Kart anasayfada bu şekilde görünür. Yazdıkça güncellenir.
            </p>
            <div className="bg-slate-100 p-4">
              <LandingCardPreview
                data={{
                  title,
                  tagline,
                  categoryLabel,
                  accentColor,
                  mockupType: mockupType || null,
                  benefits: linesToList(benefits),
                  demoDurationLabel: demoDuration,
                  hasDemo: Boolean(demoSlug.trim()),
                }}
              />
            </div>
            <div className="px-4 pb-4 pt-3">
              {status === "published" && !manualHide ? (
                <p className="rounded-md bg-emerald-100 px-3 py-2 text-[11px] font-medium text-emerald-900">
                  ✓ Yayında — anasayfada görünür (skor/A-B sıralamasına göre).
                </p>
              ) : status === "published" && manualHide ? (
                <p className="rounded-md bg-amber-100 px-3 py-2 text-[11px] font-medium text-amber-900">
                  Yayında ama “Manuel gizle” açık → anasayfada gösterilmiyor.
                </p>
              ) : (
                <p className="rounded-md bg-slate-200 px-3 py-2 text-[11px] font-medium text-slate-700">
                  Henüz yayında değil (durum:{" "}
                  {meta.statuses.find((s) => s.value === status)?.label ?? status}).
                  Anasayfada göstermek için sağ alttaki{" "}
                  <strong>Yayın durumu → Yayında</strong> seç.
                </p>
              )}
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="mb-3 text-sm font-medium">🎨 Görsel tema</h2>
            <Field label="Vurgu rengi">
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={accentColor}
                  onChange={(e) => setAccentColor(e.target.value)}
                  className="h-9 w-12 rounded border border-input"
                />
                <span className="font-mono text-xs text-muted-foreground">{accentColor}</span>
              </div>
            </Field>
            <div className="mt-3">
              <Field label="İkon adı (Lucide)" hint="Detay sayfası için.">
                <input
                  type="text"
                  value={icon}
                  onChange={(e) => setIcon(e.target.value)}
                  maxLength={64}
                  placeholder="compass"
                  className={cn(fieldClass, "font-mono")}
                />
              </Field>
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="mb-3 text-sm font-medium">🗂 Sınıflandırma</h2>
            <Field label="Alan">
              <select value={domain} onChange={(e) => setDomain(e.target.value)} className={fieldClass}>
                {meta.domains.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </Field>
            <div className="mt-3">
              <Field label="Düzey">
                <select value={tier} onChange={(e) => setTier(e.target.value)} className={fieldClass}>
                  {meta.tiers.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="mt-3">
              <Field label="Yayın durumu" hint='Sadece "Yayında" anasayfada görünür.'>
                <select value={status} onChange={(e) => setStatus(e.target.value)} className={fieldClass}>
                  {meta.statuses.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </Field>
            </div>
            <div className="mt-3">
              <p className="text-xs text-muted-foreground">Hedef rol(ler)</p>
              <div className="mt-1 space-y-1">
                {meta.roles.map((r) => (
                  <label key={r} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={roles.has(r)}
                      onChange={() => toggleRole(r)}
                      className="rounded border-input"
                    />
                    <span>{r}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="mt-3">
              <Field label={`Stratejik öncelik: ${priority}`}>
                <input
                  type="range"
                  value={priority}
                  onChange={(e) => setPriority(Number(e.target.value))}
                  min={1}
                  max={5}
                  step={1}
                  className="w-full"
                />
              </Field>
            </div>
          </Card>

          <Card className="p-5">
            <h2 className="mb-3 text-sm font-medium">⚙️ Görünürlük ve Sabitleme</h2>
            <label className="flex items-start gap-2">
              <input
                type="checkbox"
                checked={manualPin}
                onChange={(e) => setManualPin(e.target.checked)}
                className="mt-1 rounded border-input"
              />
              <div>
                <div className="text-sm">Manuel sabitle</div>
                <div className="text-[11px] text-muted-foreground">
                  Skorlamadan bağımsız sabit kalsın.
                </div>
              </div>
            </label>
            <div className="ml-6 mt-3">
              <Field label="Sabit süresi (opsiyonel)" hint="Boş → süresiz.">
                <input
                  type="datetime-local"
                  value={pinUntil}
                  onChange={(e) => setPinUntil(e.target.value)}
                  className={fieldClass}
                />
              </Field>
            </div>
            <label className="mt-3 flex items-start gap-2">
              <input
                type="checkbox"
                checked={manualHide}
                onChange={(e) => setManualHide(e.target.checked)}
                className="mt-1 rounded border-input"
              />
              <div>
                <div className="text-sm">Manuel gizle</div>
                <div className="text-[11px] text-muted-foreground">
                  Yayında olsa bile anasayfada gösterme.
                </div>
              </div>
            </label>
          </Card>

          <div className="flex flex-col gap-2">
            <Button
              type="submit"
              disabled={pending}
              className="w-full bg-indigo-600 text-white hover:bg-indigo-700"
            >
              {pending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Save className="size-4" aria-hidden />
              )}
              {isEdit ? "Değişiklikleri kaydet" : "Kartı oluştur"}
            </Button>
            <Link
              href="/admin/feature-catalog"
              className="w-full rounded-md border border-border bg-card px-3 py-2 text-center text-sm hover:bg-muted"
            >
              Vazgeç
            </Link>
          </div>
        </div>
      </form>

      {isEdit ? (
        <Card className="border-rose-200 bg-rose-50 p-4 dark:bg-rose-500/10 dark:border-rose-500/30">
          <h3 className="mb-2 text-sm font-medium text-rose-900">⚠ Tehlikeli Aksiyonlar</h3>
          <Button
            type="button"
            onClick={() => setDelOpen(true)}
            className="bg-rose-600 text-white hover:bg-rose-700"
          >
            <Trash2 className="size-4" aria-hidden />
            Kartı kalıcı sil
          </Button>
          <Dialog open={delOpen} onOpenChange={setDelOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Kartı sil</DialogTitle>
              </DialogHeader>
              <p className="text-sm text-muted-foreground">
                <code className="rounded bg-muted/50 px-1">{card!.slug}</code> kartı
                kalıcı olarak silinecek. Emin misin?
              </p>
              <DialogFooter className="gap-2 pt-2">
                <Button variant="ghost" onClick={() => setDelOpen(false)} disabled={deleteMut.isPending}>
                  Vazgeç
                </Button>
                <Button
                  onClick={onDelete}
                  disabled={deleteMut.isPending}
                  className="bg-rose-600 text-white hover:bg-rose-700"
                >
                  {deleteMut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                  Sil
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </Card>
      ) : null}
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-xs text-muted-foreground">{label}</span>
      <div className="mt-1">{children}</div>
      {hint ? <span className="mt-1 block text-[11px] text-muted-foreground">{hint}</span> : null}
    </label>
  );
}
