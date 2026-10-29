"use client";

import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  ExternalLink,
  Loader2,
  MessageSquare,
  ShieldCheck,
  TestTube2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import {
  buildWaLink,
  getMessagingTarget,
  getMessagingTemplates,
  messagingKeys,
} from "@/lib/api/messaging";
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
import { Label } from "@/components/ui/label";
import type {
  WaTargetBrief,
  WaTemplatesListResponse,
} from "@/lib/types/messaging";

interface Props {
  /** Dialog açık mı (parent kontrolü) */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Hedef kullanıcı ID (öğrenci/veli/öğretmen) */
  targetUserId: number;
  /** Hedefin görünen adı (label için, server doğrular) */
  targetNameFallback?: string;
  /** Gönderenin ID — "kendime test" için. Yoksa test toggle gizli. */
  senderUserId?: number;
  /** Dialog başlığını özelleştir (örn. "Veliye WhatsApp Gönder") */
  title?: string;
  /** Önceden seçili kategori filtresi (örn. "veli", "ogrenci") */
  defaultCategory?: string;
}

/**
 * Tekli Click-to-WA gönderim dialog'u (P4).
 *
 * Akış:
 *  1. Hedef bilgisi yüklenir (target endpoint)
 *  2. Şablon listesi (rol filtreli) — kategori chip-bar + select
 *  3. Şablon seçilince değişken alanları gelir (otomatik example pre-fill)
 *  4. Önizleme (POST /wa-link ile gerçek render) — "Önizle" butonu
 *  5. "WhatsApp'ı Aç" → window.open(wa_url) + log atılır
 *  6. "🧪 Önce kendime test gönder" toggle (varsa sender)
 */
export function WaSendDialog({
  open,
  onOpenChange,
  targetUserId,
  targetNameFallback,
  senderUserId,
  title = "WhatsApp Mesajı Gönder",
  defaultCategory,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="inline-flex items-center gap-2">
            <MessageSquare className="size-5 text-emerald-700" aria-hidden />
            {title}
          </DialogTitle>
          <DialogDescription>
            Şablonu seçin, değişkenleri doldurun ve WhatsApp&apos;ı açın.
            Mesaj koçun kendi telefonundan gider — son gönder tuşu sizdedir.
          </DialogDescription>
        </DialogHeader>
        {open ? (
          <DialogBody
            targetUserId={targetUserId}
            targetNameFallback={targetNameFallback}
            senderUserId={senderUserId}
            defaultCategory={defaultCategory}
            onClose={() => onOpenChange(false)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function DialogBody({
  targetUserId,
  targetNameFallback,
  senderUserId,
  defaultCategory,
  onClose,
}: {
  targetUserId: number;
  targetNameFallback?: string;
  senderUserId?: number;
  defaultCategory?: string;
  onClose: () => void;
}) {
  // ===== 1. Hedef bilgisi =====
  const targetQ = useQuery<WaTargetBrief>({
    queryKey: messagingKeys.target(targetUserId),
    queryFn: () => getMessagingTarget(targetUserId),
    staleTime: 30_000,
    retry: false,
  });

  // ===== 2. Şablon listesi =====
  const [categoryFilter, setCategoryFilter] = React.useState<string | null>(
    defaultCategory ?? null,
  );
  const templatesQ = useQuery<WaTemplatesListResponse>({
    queryKey: messagingKeys.templates(categoryFilter),
    queryFn: () => getMessagingTemplates(categoryFilter),
    staleTime: 60_000,
  });

  // ===== 3. Seçili şablon + değişken alanları =====
  const [selectedTemplateId, setSelectedTemplateId] = React.useState<
    number | null
  >(null);
  const [variableValues, setVariableValues] = React.useState<
    Record<string, string>
  >({});
  const [freeformNote, setFreeformNote] = React.useState("");
  const [testMode, setTestMode] = React.useState(false);

  const templates = templatesQ.data?.items ?? [];
  const selectedTemplate = templates.find((t) => t.id === selectedTemplateId);

  // Şablon seçimi değişince değişken alanlarını example ile pre-fill (event-driven,
  // useEffect değil — React önerisi: derived state'i handler içinde set et).
  function selectTemplate(id: number | null) {
    setSelectedTemplateId(id);
    if (id) {
      const tmpl = templates.find((t) => t.id === id);
      if (tmpl) {
        const next: Record<string, string> = {};
        for (const v of tmpl.variables) {
          next[v.key] = v.example || "";
        }
        setVariableValues(next);
      }
    } else {
      setVariableValues({});
    }
  }

  // ===== 4. Build link mutation (önizleme + gönderim her ikisi) =====
  // eslint-disable-next-line lgs/missing-invalidate -- dispatch saf yan etkili tek seferlik, sonuç local state
  const linkMut = useMutation({
    mutationFn: () =>
      buildWaLink({
        template_id: selectedTemplateId!,
        target_user_id: testMode && senderUserId ? senderUserId : targetUserId,
        variables: variableValues,
        freeform_note: freeformNote.trim() || undefined,
      }),
    onError: (e: unknown) => {
      if (e instanceof ApiError) {
        const code = e.detail?.code as string | undefined;
        const labels: Record<string, string> = {
          target_not_found: "Bu kullanıcıya mesaj gönderme yetkiniz yok.",
          template_not_found: "Şablon bulunamadı (silinmiş veya pasif).",
          target_phone_not_verified:
            "Hedefin telefonu doğrulanmamış. WhatsApp gönderimi yapılamaz.",
          target_phone_missing:
            "Hedefin kayıtlı telefon numarası yok. WhatsApp gönderimi yapılamaz.",
          freeform_not_allowed:
            "Bu şablon ek not yazımına izin vermiyor — ek not alanını boşaltın.",
          role_not_allowed: "Bu özellik hesabınızda yok.",
        };
        toast.error(
          (code && labels[code]) ?? e.detail?.message ?? "Bağlantı üretilemedi",
        );
      } else {
        toast.error("Beklenmedik bir hata oluştu");
      }
    },
  });

  // ===== UI: yükleme + hata durumları =====
  if (targetQ.isLoading) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground inline-flex items-center gap-2 justify-center w-full">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        Hedef bilgileri yükleniyor…
      </div>
    );
  }

  if (targetQ.isError) {
    return (
      <ErrorState
        title="Hedef bulunamadı"
        message={
          targetNameFallback
            ? `"${targetNameFallback}" için mesaj gönderme yetkiniz yok ya da kullanıcı bulunamadı.`
            : "Bu kullanıcı için mesaj gönderme yetkiniz yok."
        }
        onClose={onClose}
      />
    );
  }

  const target = targetQ.data!;
  // Soft mod: numara varsa gönderilebilir (SMS doğrulama henüz canlı değilse
  // kimse doğrulayamaz). can_message yoksa eski phone_verified'e düş.
  const canMessage = target.can_message ?? target.phone_verified;
  const verificationPending =
    canMessage && !target.phone_verified && target.sms_verification_live === false;

  if (!canMessage) {
    return (
      <>
        <TargetHeader target={target} />
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-900 inline-flex items-start gap-2">
          <AlertTriangle className="size-4 shrink-0 mt-0.5" aria-hidden />
          <div>
            {target.sms_verification_live ? (
              <>
                <strong>Telefon doğrulanmamış.</strong> WhatsApp mesajı
                gönderebilmek için hedef kullanıcının cep telefonunu kendi
                hesabından SMS ile doğrulaması gerekir.
              </>
            ) : (
              <>
                <strong>Telefon numarası yok.</strong> WhatsApp mesajı
                gönderebilmek için hedef kullanıcının kayıtlı bir cep telefonu
                numarası olmalı.
              </>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Kapat
          </Button>
        </DialogFooter>
      </>
    );
  }

  return (
    <div className="space-y-4">
      {/* Hedef header */}
      <TargetHeader target={target} />

      {/* Soft mod: numara var ama SMS doğrulama henüz açık değil */}
      {verificationPending ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 inline-flex items-start gap-2">
          <AlertTriangle className="size-3.5 shrink-0 mt-0.5" aria-hidden />
          <span>
            Numara henüz SMS ile doğrulanmadı (SMS doğrulama yakında açılacak).
            Mesajı yine de hazırlayıp WhatsApp&apos;tan gönderebilirsiniz.
          </span>
        </div>
      ) : null}

      {/* Test modu toggle (yalnız sender verildiyse) */}
      {senderUserId ? (
        <label className="flex items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={testMode}
            onChange={(e) => setTestMode(e.target.checked)}
            className="accent-emerald-600"
          />
          <TestTube2 className="size-3.5 text-emerald-700" aria-hidden />
          <span>
            <strong>Önce kendime test gönder</strong> — hedefe değil, kendi
            telefonuma git
          </span>
        </label>
      ) : null}

      {/* Şablon kategori filter chip-bar */}
      <CategoryChips
        categories={templatesQ.data?.categories ?? {}}
        activeKey={categoryFilter}
        onChange={(k) => {
          setCategoryFilter(k);
          selectTemplate(null);
        }}
      />

      {/* Şablon select */}
      <div>
        <Label htmlFor="wa_tmpl">Şablon</Label>
        {templatesQ.isLoading ? (
          <div className="text-xs text-muted-foreground py-2 inline-flex items-center gap-2">
            <Loader2 className="size-3 animate-spin" aria-hidden />
            Şablonlar yükleniyor…
          </div>
        ) : templates.length === 0 ? (
          <div className="text-xs text-muted-foreground py-2 italic">
            Bu kategoride aktif şablon yok.
          </div>
        ) : (
          <select
            id="wa_tmpl"
            value={selectedTemplateId ?? ""}
            onChange={(e) =>
              selectTemplate(parseInt(e.target.value) || null)
            }
            className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="">— Şablon seçin —</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name_tr}
              </option>
            ))}
          </select>
        )}
        {selectedTemplate?.description ? (
          <p className="text-[11px] text-muted-foreground mt-1 italic">
            {selectedTemplate.description}
          </p>
        ) : null}
      </div>

      {/* Değişken alanları */}
      {selectedTemplate && selectedTemplate.variables.length > 0 ? (
        <div className="space-y-2 border-t border-border pt-3">
          <Label className="text-xs uppercase tracking-wider text-muted-foreground">
            Değişkenler
          </Label>
          {selectedTemplate.variables.map((v) => (
            <div key={v.key} className="grid grid-cols-[140px_1fr] items-center gap-2">
              <Label htmlFor={`vv_${v.key}`} className="text-xs font-medium">
                {v.label_tr}
              </Label>
              <Input
                id={`vv_${v.key}`}
                value={variableValues[v.key] ?? ""}
                onChange={(e) =>
                  setVariableValues((s) => ({ ...s, [v.key]: e.target.value }))
                }
                placeholder={v.example}
                className="text-sm"
              />
            </div>
          ))}
        </div>
      ) : null}

      {/* Freeform note (yalnız şablon izin veriyorsa) */}
      {selectedTemplate?.allow_freeform_note ? (
        <div className="border-t border-border pt-3">
          <Label htmlFor="wa_note">Ek not (opsiyonel)</Label>
          <textarea
            id="wa_note"
            value={freeformNote}
            onChange={(e) => setFreeformNote(e.target.value)}
            rows={2}
            placeholder="Mesajın sonuna eklenecek serbest metin"
            className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
        </div>
      ) : null}

      {/* Önizleme paneli */}
      <PreviewPanel
        result={linkMut.data}
        isPending={linkMut.isPending}
        canPreview={!!selectedTemplateId}
        onPreview={() => linkMut.mutate()}
      />

      <DialogFooter className="gap-2">
        <Button variant="ghost" onClick={onClose} disabled={linkMut.isPending}>
          Vazgeç
        </Button>
        <Button
          onClick={() => {
            if (!linkMut.data) {
              // Önce önizleme yap → sonuç linki gelince user başka tıkla açar
              linkMut.mutate(undefined, {
                onSuccess: (res) => {
                  // Otomatik aç: yeni tab
                  if (typeof window !== "undefined") {
                    window.open(res.wa_url, "_blank", "noopener,noreferrer");
                  }
                  toast.success(
                    testMode
                      ? "Test bağlantısı kendi WhatsApp'ınıza açıldı."
                      : "WhatsApp'ta mesaj hazırlandı — son gönder tuşunu siz basacaksınız.",
                  );
                },
              });
            } else {
              if (typeof window !== "undefined") {
                window.open(linkMut.data.wa_url, "_blank", "noopener,noreferrer");
              }
            }
          }}
          disabled={!selectedTemplateId || linkMut.isPending}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
        >
          {linkMut.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden />
              Hazırlanıyor…
            </>
          ) : (
            <>
              <ExternalLink className="size-4" aria-hidden />
              {testMode ? "Bana Aç" : "WhatsApp'ı Aç"}
            </>
          )}
        </Button>
      </DialogFooter>
    </div>
  );
}

// ============================================================================
// Yardımcı bileşenler
// ============================================================================

function TargetHeader({ target }: { target: WaTargetBrief }) {
  return (
    <div className="rounded-md border border-border bg-muted/30 px-3 py-2 flex items-center gap-3">
      <ShieldCheck
        className={cn(
          "size-5 shrink-0",
          target.phone_verified ? "text-emerald-700" : "text-amber-700",
        )}
        aria-hidden
      />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold truncate">{target.full_name}</div>
        <div className="text-xs text-muted-foreground">
          {target.phone_masked}
        </div>
      </div>
    </div>
  );
}

function CategoryChips({
  categories,
  activeKey,
  onChange,
}: {
  categories: Record<string, string>;
  activeKey: string | null;
  onChange: (k: string | null) => void;
}) {
  const keys = Object.keys(categories);
  if (keys.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5 text-[11px]">
      <Chip label="Hepsi" active={activeKey === null} onClick={() => onChange(null)} />
      {keys.map((k) => (
        <Chip
          key={k}
          label={categories[k]}
          active={activeKey === k}
          onClick={() => onChange(k)}
        />
      ))}
    </div>
  );
}

function Chip({
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
        "rounded-full px-2 py-0.5 border transition-colors",
        active
          ? "bg-emerald-600 text-white border-emerald-600"
          : "bg-background text-foreground border-border hover:bg-muted",
      )}
    >
      {label}
    </button>
  );
}

function PreviewPanel({
  result,
  isPending,
  canPreview,
  onPreview,
}: {
  result: import("@/lib/types/messaging").WaLinkResult | undefined;
  isPending: boolean;
  canPreview: boolean;
  onPreview: () => void;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 space-y-2 border-t border-border">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Önizleme
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onPreview}
          disabled={!canPreview || isPending}
        >
          {isPending ? (
            <Loader2 className="size-3 animate-spin" aria-hidden />
          ) : null}
          Önizle
        </Button>
      </div>
      {result ? (
        <>
          <div className="rounded border border-emerald-200 bg-emerald-50/40 px-3 py-2 text-sm whitespace-pre-wrap text-emerald-900">
            {result.rendered_text}
          </div>
          <div className="text-[10px] text-muted-foreground flex items-center gap-2">
            <span>{result.character_count} karakter</span>
            {result.long_text ? (
              <span className="text-amber-700 inline-flex items-center gap-1">
                <AlertTriangle className="size-3" aria-hidden />
                Uzun mesaj uyarısı
              </span>
            ) : null}
          </div>
          {result.warnings.length > 0 ? (
            <ul className="text-[11px] text-amber-800 list-disc pl-4 space-y-0.5">
              {result.warnings.slice(0, 3).map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : null}
        </>
      ) : (
        <p className="text-[11px] text-muted-foreground italic">
          Şablonu seçip değişkenleri doldurun, sonra &ldquo;Önizle&rdquo; ile
          metni görün.
        </p>
      )}
    </div>
  );
}

function ErrorState({
  title,
  message,
  onClose,
}: {
  title: string;
  message: string;
  onClose: () => void;
}) {
  return (
    <>
      <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-900 inline-flex items-start gap-2">
        <AlertTriangle className="size-4 shrink-0 mt-0.5" aria-hidden />
        <div>
          <strong>{title}</strong>
          <p className="mt-0.5 text-xs">{message}</p>
        </div>
      </div>
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>
          Kapat
        </Button>
      </DialogFooter>
    </>
  );
}
