"use client";

import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCopy,
  ExternalLink,
  Loader2,
  MessageSquare,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import {
  buildBulkWaLink,
  getMessagingBulkTargets,
  getMessagingTemplates,
  messagingKeys,
} from "@/lib/api/messaging";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SpamGuardBanner } from "@/components/messaging/spam-guard-banner";
import type {
  BulkSendResponse,
  BulkTargetCandidate,
  BulkTargetsResponse,
  WaTemplateBrief,
  WaTemplatesListResponse,
} from "@/lib/types/messaging";

// ≤20 hedef → sıralı sihirbaz; 20+ → broadcast modu önerilir
const BROADCAST_THRESHOLD = 20;

const SKIP_REASON_LABELS: Record<string, string> = {
  phone_not_verified: "Telefon doğrulanmamış",
  no_permission: "Yetki yok",
  not_found: "Bulunamadı",
};

type WizardStep = 1 | 2 | 3 | 4;

export function BulkSendWizard() {
  const [step, setStep] = React.useState<WizardStep>(1);
  const [selectedTemplate, setSelectedTemplate] =
    React.useState<WaTemplateBrief | null>(null);
  const [variables, setVariables] = React.useState<Record<string, string>>({});
  const [freeformNote, setFreeformNote] = React.useState("");
  const [groupKey, setGroupKey] = React.useState<string | null>(null);
  const [selectedTargetIds, setSelectedTargetIds] = React.useState<Set<number>>(
    new Set(),
  );

  return (
    <div className="space-y-6">
      <header>
        <p className="text-[11px] uppercase tracking-wider text-emerald-700 font-semibold">
          <MessageSquare className="inline size-3.5 mr-1" aria-hidden />
          Toplu WhatsApp Gönderim Sihirbazı
        </p>
        <h1 className="font-display text-2xl font-semibold tracking-tight mt-1">
          {STEP_TITLES[step]}
        </h1>
      </header>

      {/* P6 — Spam guard uyarı banner */}
      <SpamGuardBanner />

      <StepIndicator current={step} />

      {step === 1 ? (
        <Step1TemplatePicker
          onPick={(t) => {
            setSelectedTemplate(t);
            const next: Record<string, string> = {};
            for (const v of t.variables) next[v.key] = v.example || "";
            setVariables(next);
            setStep(2);
          }}
        />
      ) : null}

      {step === 2 && selectedTemplate ? (
        <Step2Variables
          template={selectedTemplate}
          variables={variables}
          setVariables={setVariables}
          freeformNote={freeformNote}
          setFreeformNote={setFreeformNote}
          onBack={() => setStep(1)}
          onNext={() => setStep(3)}
        />
      ) : null}

      {step === 3 ? (
        <Step3TargetGroup
          groupKey={groupKey}
          onPickGroup={setGroupKey}
          selectedTargetIds={selectedTargetIds}
          setSelectedTargetIds={setSelectedTargetIds}
          onBack={() => setStep(2)}
          onNext={() => setStep(4)}
        />
      ) : null}

      {step === 4 && selectedTemplate ? (
        <Step4SendMode
          template={selectedTemplate}
          variables={variables}
          freeformNote={freeformNote}
          selectedTargetIds={Array.from(selectedTargetIds)}
          onBack={() => setStep(3)}
          onRestart={() => {
            setStep(1);
            setSelectedTemplate(null);
            setVariables({});
            setFreeformNote("");
            setGroupKey(null);
            setSelectedTargetIds(new Set());
          }}
        />
      ) : null}
    </div>
  );
}

// ============================================================================
// Step indicator
// ============================================================================

const STEP_TITLES: Record<WizardStep, string> = {
  1: "1. Şablon Seç",
  2: "2. Değişkenleri Doldur",
  3: "3. Hedef Grubu Seç",
  4: "4. Gönderim Modu",
};

function StepIndicator({ current }: { current: WizardStep }) {
  const steps: WizardStep[] = [1, 2, 3, 4];
  return (
    <div className="flex items-center gap-2 text-xs">
      {steps.map((s, i) => (
        <React.Fragment key={s}>
          <div
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 border",
              s === current
                ? "bg-emerald-600 text-white border-emerald-600"
                : s < current
                ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                : "bg-muted text-muted-foreground border-border",
            )}
          >
            <span className="font-semibold">{s}</span>
            {s < current ? <CheckCircle2 className="size-3" aria-hidden /> : null}
            <span className="hidden sm:inline">{STEP_TITLES[s]}</span>
          </div>
          {i < steps.length - 1 ? (
            <ChevronRight
              className="size-3 text-muted-foreground"
              aria-hidden
            />
          ) : null}
        </React.Fragment>
      ))}
    </div>
  );
}

// ============================================================================
// Step 1 — Şablon seçici (yalnız allow_bulk=True)
// ============================================================================

function Step1TemplatePicker({
  onPick,
}: {
  onPick: (t: WaTemplateBrief) => void;
}) {
  const q = useQuery<WaTemplatesListResponse>({
    queryKey: messagingKeys.templates(null),
    queryFn: () => getMessagingTemplates(null),
    staleTime: 60_000,
  });
  const items = (q.data?.items ?? []).filter((t) => t.allow_bulk);

  if (q.isLoading) {
    return (
      <div className="text-sm text-muted-foreground inline-flex items-center gap-2 py-6">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Şablonlar yükleniyor…
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-sm text-muted-foreground">
          Toplu gönderim için uygun şablon yok. Süper admin panelinden
          şablonlarda &ldquo;Toplu gönderim uygun&rdquo; seçeneğini açın.
        </CardContent>
      </Card>
    );
  }

  // Kategori gruplandırma
  const groups: Record<string, WaTemplateBrief[]> = {};
  for (const t of items) {
    if (!groups[t.category_label_tr]) groups[t.category_label_tr] = [];
    groups[t.category_label_tr].push(t);
  }

  return (
    <div className="space-y-4">
      {Object.entries(groups).map(([catLabel, list]) => (
        <Card key={catLabel}>
          <div className="px-4 py-2 border-b border-border bg-muted/40">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {catLabel}
            </h3>
          </div>
          <ul className="divide-y divide-border">
            {list.map((t) => (
              <li
                key={t.id}
                className="px-4 py-3 hover:bg-muted/30 transition-colors cursor-pointer"
                onClick={() => onPick(t)}
              >
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{t.name_tr}</div>
                    {t.description ? (
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {t.description}
                      </div>
                    ) : null}
                    <div className="text-[11px] text-muted-foreground italic mt-1 line-clamp-2">
                      {t.content_template}
                    </div>
                  </div>
                  <ChevronRight
                    className="size-4 text-muted-foreground"
                    aria-hidden
                  />
                </div>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  );
}

// ============================================================================
// Step 2 — Değişkenleri doldur
// ============================================================================

function Step2Variables({
  template,
  variables,
  setVariables,
  freeformNote,
  setFreeformNote,
  onBack,
  onNext,
}: {
  template: WaTemplateBrief;
  variables: Record<string, string>;
  setVariables: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  freeformNote: string;
  setFreeformNote: (v: string) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-5 space-y-4">
          <div>
            <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
              Seçilen şablon
            </div>
            <div className="text-base font-medium">{template.name_tr}</div>
          </div>

          {template.variables.length > 0 ? (
            <div className="space-y-2 border-t border-border pt-3">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Değişkenler (tüm hedeflere aynı değer)
              </Label>
              {template.variables.map((v) => (
                <div key={v.key} className="grid grid-cols-[140px_1fr] items-center gap-2">
                  <Label htmlFor={`bv_${v.key}`} className="text-xs font-medium">
                    {v.label_tr}
                  </Label>
                  <Input
                    id={`bv_${v.key}`}
                    value={variables[v.key] ?? ""}
                    onChange={(e) =>
                      setVariables((s) => ({ ...s, [v.key]: e.target.value }))
                    }
                    placeholder={v.example}
                    className="text-sm"
                  />
                </div>
              ))}
            </div>
          ) : null}

          {template.allow_freeform_note ? (
            <div className="border-t border-border pt-3">
              <Label htmlFor="bulk_note">Ek not (opsiyonel)</Label>
              <textarea
                id="bulk_note"
                value={freeformNote}
                onChange={(e) => setFreeformNote(e.target.value)}
                rows={2}
                placeholder="Mesajın sonuna eklenecek serbest metin"
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>
          ) : null}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          <ChevronLeft className="size-4" aria-hidden />
          Geri
        </Button>
        <Button
          onClick={onNext}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
        >
          İleri
          <ChevronRight className="size-4" aria-hidden />
        </Button>
      </div>
    </div>
  );
}

// ============================================================================
// Step 3 — Hedef grubu seç + kişi seçimi
// ============================================================================

function Step3TargetGroup({
  groupKey,
  onPickGroup,
  selectedTargetIds,
  setSelectedTargetIds,
  onBack,
  onNext,
}: {
  groupKey: string | null;
  onPickGroup: (k: string) => void;
  selectedTargetIds: Set<number>;
  setSelectedTargetIds: React.Dispatch<React.SetStateAction<Set<number>>>;
  onBack: () => void;
  onNext: () => void;
}) {
  // Hangi grupları sender kullanabilir (initial fetch ile alacağız — boş grup ile)
  const initialQ = useQuery<BulkTargetsResponse>({
    queryKey: messagingKeys.bulkTargets("__init__"),
    queryFn: () => getMessagingBulkTargets("__init__"),
    staleTime: 60_000,
  });
  const availableGroups = initialQ.data?.available_groups ?? [];

  // Aktif group için hedef listesi
  const targetQ = useQuery<BulkTargetsResponse>({
    queryKey: messagingKeys.bulkTargets(groupKey ?? ""),
    queryFn: () => getMessagingBulkTargets(groupKey!),
    enabled: !!groupKey,
    staleTime: 30_000,
  });

  function toggleTarget(id: number) {
    setSelectedTargetIds((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll(eligible: BulkTargetCandidate[]) {
    setSelectedTargetIds(new Set(eligible.map((c) => c.user_id)));
  }

  function clearAll() {
    setSelectedTargetIds(new Set());
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-5 space-y-4">
          {/* Grup picker */}
          <div>
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">
              Hedef grubu
            </Label>
            <div className="flex flex-wrap gap-2 mt-2">
              {availableGroups.length === 0 && initialQ.isLoading ? (
                <span className="text-xs text-muted-foreground">
                  Gruplar yükleniyor…
                </span>
              ) : null}
              {availableGroups.map((g) => (
                <button
                  key={g.key}
                  type="button"
                  onClick={() => {
                    onPickGroup(g.key);
                    setSelectedTargetIds(new Set());
                  }}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-xs border transition-colors",
                    groupKey === g.key
                      ? "bg-emerald-600 text-white border-emerald-600"
                      : "bg-background hover:bg-muted",
                  )}
                >
                  {g.label_tr}
                </button>
              ))}
            </div>
          </div>

          {groupKey && targetQ.data ? (
            <TargetList
              data={targetQ.data}
              selectedIds={selectedTargetIds}
              onToggle={toggleTarget}
              onSelectAll={selectAll}
              onClearAll={clearAll}
            />
          ) : null}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          <ChevronLeft className="size-4" aria-hidden />
          Geri
        </Button>
        <Button
          onClick={onNext}
          disabled={selectedTargetIds.size === 0}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
        >
          {selectedTargetIds.size} hedefe ilerle
          <ChevronRight className="size-4" aria-hidden />
        </Button>
      </div>
    </div>
  );
}

function TargetList({
  data,
  selectedIds,
  onToggle,
  onSelectAll,
  onClearAll,
}: {
  data: BulkTargetsResponse;
  selectedIds: Set<number>;
  onToggle: (id: number) => void;
  onSelectAll: (eligible: BulkTargetCandidate[]) => void;
  onClearAll: () => void;
}) {
  return (
    <div className="space-y-3 border-t border-border pt-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-xs text-muted-foreground inline-flex items-center gap-1">
          <Users className="size-3.5" aria-hidden />
          {data.total} kişi · <strong>{data.eligible.length}</strong> gönderilebilir
          {data.no_phone.length > 0 ? (
            <span className="text-amber-700 ml-1">
              · {data.no_phone.length} telefon yok
            </span>
          ) : null}
        </div>
        <div className="flex gap-1.5">
          <Button
            size="sm"
            variant="outline"
            onClick={() => onSelectAll(data.eligible)}
          >
            Tümünü seç
          </Button>
          <Button size="sm" variant="ghost" onClick={onClearAll}>
            Temizle
          </Button>
        </div>
      </div>

      {data.eligible.length === 0 ? (
        <p className="text-xs text-muted-foreground italic">
          Telefon doğrulu hedef yok.
        </p>
      ) : (
        <ul className="max-h-72 overflow-y-auto divide-y divide-border border border-border rounded-md">
          {data.eligible.map((c) => (
            <li
              key={c.user_id}
              className={cn(
                "flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted/40 cursor-pointer",
                selectedIds.has(c.user_id) && "bg-emerald-50",
              )}
              onClick={() => onToggle(c.user_id)}
            >
              <input
                type="checkbox"
                checked={selectedIds.has(c.user_id)}
                onChange={() => onToggle(c.user_id)}
                className="accent-emerald-600"
              />
              <span className="flex-1 min-w-0">
                <span className="font-medium truncate block">
                  {c.full_name}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {c.phone_masked}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}

      {data.no_phone.length > 0 ? (
        <details className="text-xs">
          <summary className="cursor-pointer text-amber-800">
            ⚠ {data.no_phone.length} kişinin telefonu doğrulanmamış (görüntüle)
          </summary>
          <ul className="mt-1 ml-4 list-disc text-muted-foreground">
            {data.no_phone.slice(0, 10).map((c) => (
              <li key={c.user_id}>{c.full_name}</li>
            ))}
            {data.no_phone.length > 10 ? (
              <li>+{data.no_phone.length - 10} daha</li>
            ) : null}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

// ============================================================================
// Step 4 — Mod seçimi + gönderim
// ============================================================================

function Step4SendMode({
  template,
  variables,
  freeformNote,
  selectedTargetIds,
  onBack,
  onRestart,
}: {
  template: WaTemplateBrief;
  variables: Record<string, string>;
  freeformNote: string;
  selectedTargetIds: number[];
  onBack: () => void;
  onRestart: () => void;
}) {
  const targetCount = selectedTargetIds.length;
  const defaultMode: "sequential" | "broadcast" =
    targetCount >= BROADCAST_THRESHOLD ? "broadcast" : "sequential";
  const [mode, setMode] = React.useState<"sequential" | "broadcast">(defaultMode);

  // eslint-disable-next-line lgs/missing-invalidate -- bulk dispatch saf URL üretici, dispatch log otomatik atılır; cache invalidate gereği yok
  const bulkMut = useMutation({
    mutationFn: () =>
      buildBulkWaLink({
        template_id: template.id,
        target_user_ids: selectedTargetIds,
        variables,
        mode,
        freeform_note: freeformNote.trim() || undefined,
      }),
    onError: (e: unknown) => {
      if (e instanceof ApiError) {
        toast.error(e.detail?.message ?? "Gönderim başlatılamadı");
      } else {
        toast.error("Beklenmedik bir hata oluştu");
      }
    },
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-5 space-y-4">
          {/* Mod seçici */}
          <div>
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">
              Gönderim modu
            </Label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
              <ModeOption
                title="Sıralı sihirbaz"
                description={`${targetCount} kişiye tek tek wa.me linki — koç her adımda 'Aç' butonuyla gönderir.`}
                active={mode === "sequential"}
                disabled={targetCount > BROADCAST_THRESHOLD * 5}
                recommended={targetCount < BROADCAST_THRESHOLD}
                onClick={() => setMode("sequential")}
              />
              <ModeOption
                title="Broadcast (kopyala-yapıştır)"
                description="Mesajı panoya kopyala, WA Business'ta broadcast list'e yapıştır."
                active={mode === "broadcast"}
                recommended={targetCount >= BROADCAST_THRESHOLD}
                onClick={() => setMode("broadcast")}
              />
            </div>
          </div>

          {!bulkMut.data ? (
            <div className="border-t border-border pt-3">
              <Button
                onClick={() => bulkMut.mutate()}
                disabled={bulkMut.isPending}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {bulkMut.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                    Hazırlanıyor…
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="size-4" aria-hidden />
                    Gönderim Linklerini Üret
                  </>
                )}
              </Button>
            </div>
          ) : (
            <DispatchResult result={bulkMut.data} onRestart={onRestart} />
          )}
        </CardContent>
      </Card>

      {!bulkMut.data ? (
        <Button variant="ghost" onClick={onBack}>
          <ChevronLeft className="size-4" aria-hidden />
          Geri
        </Button>
      ) : null}
    </div>
  );
}

function ModeOption({
  title,
  description,
  active,
  disabled = false,
  recommended = false,
  onClick,
}: {
  title: string;
  description: string;
  active: boolean;
  disabled?: boolean;
  recommended?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={cn(
        "text-left rounded-md border px-4 py-3 transition-colors",
        active
          ? "border-emerald-600 bg-emerald-50"
          : "border-border hover:bg-muted/40",
        disabled && "opacity-50 cursor-not-allowed",
      )}
    >
      <div className="flex items-center justify-between">
        <div className="font-medium text-sm">{title}</div>
        {recommended ? (
          <span className="text-[10px] uppercase tracking-wider bg-emerald-600 text-white px-1.5 py-0.5 rounded">
            Önerilen
          </span>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground mt-1">{description}</p>
    </button>
  );
}

// ============================================================================
// Sonuç (sıralı + broadcast)
// ============================================================================

function DispatchResult({
  result,
  onRestart,
}: {
  result: BulkSendResponse;
  onRestart: () => void;
}) {
  return (
    <div className="space-y-3 border-t border-border pt-3">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs">
        <Stat label="Gönderilecek" value={result.total_dispatched} tone="emerald" />
        <Stat label="Atlandı" value={result.total_skipped} tone="amber" />
        <Stat label="Karakter" value={result.rendered_text.length} />
      </div>

      {result.warnings.length > 0 ? (
        <ul className="text-[11px] text-amber-800 list-disc pl-4 space-y-0.5">
          {result.warnings.slice(0, 3).map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      ) : null}

      {result.mode === "broadcast" ? (
        <BroadcastView result={result} />
      ) : (
        <SequentialView result={result} />
      )}

      {result.skipped.length > 0 ? (
        <details className="text-xs">
          <summary className="cursor-pointer text-amber-800">
            ⚠ {result.skipped.length} kişi atlandı (görüntüle)
          </summary>
          <ul className="mt-1 ml-4 list-disc text-muted-foreground">
            {result.skipped.slice(0, 10).map((s, i) => (
              <li key={i}>
                {s.target_name}{" "}
                <span className="text-[10px] italic">
                  ({SKIP_REASON_LABELS[s.reason] ?? s.reason})
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <div className="pt-2 border-t border-border">
        <Button variant="outline" size="sm" onClick={onRestart}>
          Sihirbazı yeniden başlat
        </Button>
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  tone = "slate",
}: {
  label: string;
  value: number;
  tone?: "emerald" | "amber" | "slate";
}) {
  const cls =
    tone === "emerald"
      ? "text-emerald-700"
      : tone === "amber"
      ? "text-amber-700"
      : "text-foreground";
  return (
    <div className="rounded-md border border-border bg-muted/30 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className={cn("text-xl font-semibold tabular-nums mt-0.5", cls)}>
        {value}
      </div>
    </div>
  );
}

// ============================================================================
// Sıralı görünüm (her item için sırayla "WhatsApp'ı Aç")
// ============================================================================

function SequentialView({ result }: { result: BulkSendResponse }) {
  const [currentIdx, setCurrentIdx] = React.useState(0);
  const [completed, setCompleted] = React.useState<Set<number>>(new Set());
  const items = result.items;

  if (items.length === 0) return null;

  const current = items[currentIdx];
  const isLast = currentIdx >= items.length - 1;

  function openCurrent() {
    if (typeof window !== "undefined") {
      window.open(current.wa_url, "_blank", "noopener,noreferrer");
    }
    setCompleted((s) => new Set(s).add(currentIdx));
  }

  function next() {
    if (!isLast) setCurrentIdx((i) => i + 1);
  }

  function prev() {
    if (currentIdx > 0) setCurrentIdx((i) => i - 1);
  }

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-xs text-muted-foreground">
            Sıralı gönderim — <strong>{currentIdx + 1}</strong> / {items.length}
            {completed.size > 0 ? (
              <span className="text-emerald-700 ml-2">
                ({completed.size} tıklandı)
              </span>
            ) : null}
          </div>
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={prev} disabled={currentIdx === 0}>
              <ChevronLeft className="size-3.5" aria-hidden />
            </Button>
            <Button size="sm" variant="ghost" onClick={next} disabled={isLast}>
              <ChevronRight className="size-3.5" aria-hidden />
            </Button>
          </div>
        </div>

        <div
          className={cn(
            "rounded-md border-2 px-3 py-2",
            completed.has(currentIdx)
              ? "border-emerald-300 bg-emerald-50"
              : "border-border bg-background",
          )}
        >
          <div className="text-sm font-semibold">{current.target_name}</div>
          <div className="text-xs text-muted-foreground">
            {current.phone_masked}
          </div>
        </div>

        <Button
          onClick={openCurrent}
          className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
        >
          <ExternalLink className="size-4" aria-hidden />
          WhatsApp&apos;ı Aç
        </Button>
      </CardContent>
    </Card>
  );
}

// ============================================================================
// Broadcast görünüm (mesaj + telefon listesi panoya kopyala)
// ============================================================================

function BroadcastView({ result }: { result: BulkSendResponse }) {
  const [textCopied, setTextCopied] = React.useState(false);
  const [phonesCopied, setPhonesCopied] = React.useState(false);

  const phoneList = result.items.map((it) => it.phone_masked).join("\n");

  async function copyText() {
    try {
      await navigator.clipboard.writeText(result.rendered_text);
      setTextCopied(true);
      toast.success("Mesaj panoya kopyalandı");
      setTimeout(() => setTextCopied(false), 2000);
    } catch {
      toast.error("Kopyalama başarısız — manuel seçip kopyalayın");
    }
  }

  async function copyPhones() {
    try {
      await navigator.clipboard.writeText(phoneList);
      setPhonesCopied(true);
      toast.success("Telefon listesi panoya kopyalandı");
      setTimeout(() => setPhonesCopied(false), 2000);
    } catch {
      toast.error("Kopyalama başarısız");
    }
  }

  return (
    <Card>
      <CardContent className="p-4 space-y-4">
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 inline-flex items-start gap-2">
          <AlertTriangle className="size-4 shrink-0 mt-0.5" aria-hidden />
          <div>
            <strong>Broadcast list talimatı:</strong> WhatsApp Business
            uygulamanızda &quot;Broadcast lists&quot; → &quot;New list&quot; →
            kişileri ekle (aşağıda listeli) → mesajı yapıştır → gönder.
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">
              Mesaj metni
            </Label>
            <Button size="sm" variant="outline" onClick={copyText}>
              {textCopied ? (
                <CheckCircle2 className="size-3.5" aria-hidden />
              ) : (
                <ClipboardCopy className="size-3.5" aria-hidden />
              )}
              Kopyala
            </Button>
          </div>
          <div className="rounded border border-emerald-200 bg-emerald-50/40 px-3 py-2 text-sm whitespace-pre-wrap text-emerald-900">
            {result.rendered_text}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <Label className="text-xs uppercase tracking-wider text-muted-foreground">
              Telefon listesi ({result.items.length})
            </Label>
            <Button size="sm" variant="outline" onClick={copyPhones}>
              {phonesCopied ? (
                <CheckCircle2 className="size-3.5" aria-hidden />
              ) : (
                <ClipboardCopy className="size-3.5" aria-hidden />
              )}
              Kopyala
            </Button>
          </div>
          <div className="rounded border border-border bg-muted/30 px-3 py-2 text-xs font-mono whitespace-pre-wrap max-h-48 overflow-y-auto">
            {phoneList}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
