"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BellRing,
  CheckCircle2,
  Clock,
  Loader2,
  MessageCircle,
  Moon,
  Settings as SettingsIcon,
  ShieldCheck,
  Users,
  VolumeX,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getParentSettings, parentKeys } from "@/lib/api/parent";
import {
  useToggleChildMute,
  useUpdateParentPreferences,
  useWhatsAppDisable,
  useWhatsAppStart,
  useWhatsAppVerify,
} from "@/lib/hooks/use-parent-mutations";
import type {
  ParentChildLink,
  ParentPreferencesInfo,
  ParentSettingsResponse,
  ParentWhatsAppInfo,
} from "@/lib/types/parent";

interface Props {
  initial: ParentSettingsResponse;
}

const PREF_ROWS: Array<{
  key: keyof ParentPreferencesBody;
  title: string;
  desc: string;
}> = [
  {
    key: "daily_summary",
    title: "Günlük özet",
    desc: "Çocuğun bugünkü tamamlama özeti",
  },
  {
    key: "empty_day",
    title: "Boş gün uyarısı",
    desc: "Hiç görev tamamlamadığında bilgi verir (3 günü aşan üst üste suskunluk için sus)",
  },
  {
    key: "weekly_report",
    title: "Haftalık rapor",
    desc: "Her 7 günlük döngünün sonunda gönderilir",
  },
  {
    key: "new_program",
    title: "Yeni program duyurusu",
    desc: "Öğretmen yeni haftalık programı yayınladığında",
  },
  {
    key: "drop_alert",
    title: "Düşüş alarmı",
    desc: "Geçen haftaya göre %30+ düşüş olduğunda",
  },
  {
    key: "teacher_note",
    title: "Öğretmen notu",
    desc: "Öğretmen size özel not gönderdiğinde",
  },
  {
    key: "exam_approaching",
    title: "Sınav yaklaşıyor",
    desc: "Sınav tarihine 30, 7 ve 1 gün kala bilgilendirme (LGS / YKS)",
  },
];

type ParentPreferencesBody = {
  daily_summary: boolean;
  weekly_report: boolean;
  empty_day: boolean;
  new_program: boolean;
  drop_alert: boolean;
  teacher_note: boolean;
  exam_approaching: boolean;
  quiet_start: string;
  quiet_end: string;
};

/**
 * Veli ayarlar — Jinja `settings_skeleton.html` feature parity.
 *
 * 3 bölüm:
 *   1. Bildirim türleri (7 toggle + sessiz saatler)
 *   2. Çocuk başına mute
 *   3. WhatsApp 3 durum (kapalı / kod bekleniyor / aktif)
 */
export function ParentSettingsClient({ initial }: Props) {
  const q = useQuery<ParentSettingsResponse>({
    queryKey: parentKeys.settings(),
    queryFn: () => getParentSettings(),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight font-display inline-flex items-center gap-2">
          <SettingsIcon className="size-6 text-[#117A86]" aria-hidden />
          Bildirim Tercihleri
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Hangi bildirimleri, hangi kanaldan ve ne zaman alacağınızı buradan
          yönetin.
        </p>
      </header>

      {data.preferences.unsubscribed_at && (
        <UnsubscribedBanner unsubscribedAt={data.preferences.unsubscribed_at} />
      )}

      <PreferencesForm preferences={data.preferences} />

      {data.children.length > 0 && (
        <ChildrenMuteCard childLinks={data.children} />
      )}

      <WhatsAppCard whatsapp={data.whatsapp} />

      <div className="rounded-md border border-rose-200 bg-rose-50/50 p-4 text-xs text-rose-800 leading-relaxed">
        <strong>Tek tıkla tüm bildirimleri kapatmak için:</strong>{" "}
        e-postaların altındaki &ldquo;tek tıkla kapat&rdquo; linkini
        kullanabilirsiniz. Tüm türler kapanır; bu sayfadan tekrar aktive
        edebilirsiniz.
      </div>
    </div>
  );
}

// ============================================================================
// Unsubscribed banner
// ============================================================================

function UnsubscribedBanner({ unsubscribedAt }: { unsubscribedAt: string }) {
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 flex items-start gap-2">
      <VolumeX className="size-5 shrink-0 mt-0.5" aria-hidden />
      <div>
        <strong>Tüm bildirimler kapalı.</strong> Aşağıdan yeniden tercihlerinizi
        kaydederseniz bildirim akışı tekrar açılır (kapatma kaydınız:{" "}
        {formatTimestamp(unsubscribedAt)}).
      </div>
    </div>
  );
}

// ============================================================================
// Preferences form
// ============================================================================

function PreferencesForm({
  preferences,
}: {
  preferences: ParentPreferencesInfo;
}) {
  const mut = useUpdateParentPreferences();
  // İlk render değeri server'dan; mutate sonrası TanStack invalidate fresh
  // preferences döner ve formun parent component'i remount edilirken bu state
  // o değerlerle başlar (kullanıcı az önce save ettiği için zaten aynıdır).
  const [state, setState] = React.useState<ParentPreferencesBody>(() => ({
    daily_summary: preferences.daily_summary_enabled,
    weekly_report: preferences.weekly_report_enabled,
    empty_day: preferences.empty_day_alert_enabled,
    new_program: preferences.new_program_alert_enabled,
    drop_alert: preferences.drop_alert_enabled,
    teacher_note: preferences.teacher_note_enabled,
    exam_approaching: preferences.exam_approaching_enabled,
    quiet_start: preferences.quiet_hours_start,
    quiet_end: preferences.quiet_hours_end,
  }));

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(state);
  }

  return (
    <Card>
      <form onSubmit={onSubmit}>
        <div className="px-5 py-3 border-b border-border">
          <h2 className="font-semibold inline-flex items-center gap-1.5">
            <BellRing className="size-4 text-[#117A86]" aria-hidden />
            Bildirim Türleri
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            İstemediğiniz bildirim türlerini kapatabilirsiniz
          </p>
        </div>

        <div className="divide-y divide-border">
          {PREF_ROWS.map((row) => (
            <label
              key={row.key}
              className="flex items-start gap-3 px-5 py-3 cursor-pointer hover:bg-muted/40 transition-colors"
            >
              <input
                type="checkbox"
                checked={state[row.key] as boolean}
                onChange={(e) =>
                  setState((s) => ({ ...s, [row.key]: e.target.checked }))
                }
                className="mt-1 accent-[#117A86] size-4"
              />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">{row.title}</div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {row.desc}
                </div>
              </div>
            </label>
          ))}
        </div>

        <div className="px-5 py-4 border-t border-border bg-muted/30">
          <h3 className="text-sm font-medium mb-3 inline-flex items-center gap-1.5">
            <Moon className="size-4 text-[#117A86]" aria-hidden />
            Sessiz saatler
          </h3>
          <div className="flex items-center gap-3 flex-wrap">
            <Label htmlFor="quiet_start" className="text-xs">
              Başlangıç:
            </Label>
            <Input
              id="quiet_start"
              type="time"
              value={state.quiet_start}
              onChange={(e) =>
                setState((s) => ({ ...s, quiet_start: e.target.value }))
              }
              className="w-32"
            />
            <span className="text-xs text-muted-foreground">→</span>
            <Label htmlFor="quiet_end" className="text-xs">
              Bitiş:
            </Label>
            <Input
              id="quiet_end"
              type="time"
              value={state.quiet_end}
              onChange={(e) =>
                setState((s) => ({ ...s, quiet_end: e.target.value }))
              }
              className="w-32"
            />
          </div>
          <p className="text-[11px] text-muted-foreground italic mt-2">
            Bu saatlerde tetiklenen bildirimler sessiz saat bitimine ertelenir.
            Sistem mesajları (davet, doğrulama kodu) bu kuraldan etkilenmez.
          </p>
        </div>

        <div className="px-5 py-3 border-t border-border flex justify-end">
          <Button
            type="submit"
            className="bg-[#117A86] hover:bg-[#0E5F69] text-white"
            disabled={mut.isPending}
          >
            {mut.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Kaydediliyor…
              </>
            ) : (
              "Tercihleri Kaydet"
            )}
          </Button>
        </div>
      </form>
    </Card>
  );
}

// ============================================================================
// Çocuk başına mute
// ============================================================================

function ChildrenMuteCard({ childLinks }: { childLinks: ParentChildLink[] }) {
  return (
    <Card>
      <div className="px-5 py-3 border-b border-border">
        <h2 className="font-semibold inline-flex items-center gap-1.5">
          <Users className="size-4 text-[#117A86]" aria-hidden />
          Çocuk Başına Bildirim
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          Belirli bir çocuk için tüm bildirimleri sustur
        </p>
      </div>
      <ul className="divide-y divide-border">
        {childLinks.map((c) => (
          <ChildMuteRow key={c.student_id} child={c} />
        ))}
      </ul>
    </Card>
  );
}

function ChildMuteRow({ child }: { child: ParentChildLink }) {
  const mut = useToggleChildMute(child.student_id);
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  function toggle() {
    if (child.muted) {
      // Unmute — direct, no confirm
      mut.mutate({ muted: false });
    } else {
      setConfirmOpen(true);
    }
  }

  function doMute() {
    mut.mutate(
      { muted: true },
      { onSettled: () => setConfirmOpen(false) },
    );
  }

  return (
    <li className="px-5 py-3 flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="text-sm font-medium truncate">{child.full_name}</div>
        <div className="text-[11px] text-muted-foreground mt-0.5">
          {child.relation_label}
          {child.is_primary && " · Birincil veli"}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {child.muted ? (
          <>
            <span className="text-[10px] uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-200 px-2 py-0.5 rounded">
              Susturulmuş
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={toggle}
              disabled={mut.isPending}
              className="text-emerald-700 border-emerald-200 hover:bg-emerald-50"
            >
              {mut.isPending ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : null}
              Tekrar aç
            </Button>
          </>
        ) : (
          <>
            <span className="text-[10px] uppercase tracking-wider bg-emerald-100 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded">
              Aktif
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={toggle}
              disabled={mut.isPending}
              className="text-rose-700 border-rose-200 hover:bg-rose-50"
            >
              Sustur
            </Button>
          </>
        )}
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bildirimleri sustur</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            <strong>{child.full_name}</strong> için tüm bildirimleri kapatmak
            istediğinizden emin misiniz?
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setConfirmOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={doMute}
              disabled={mut.isPending}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              Sustur
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </li>
  );
}

// ============================================================================
// WhatsApp 3 durum
// ============================================================================

function WhatsAppCard({ whatsapp }: { whatsapp: ParentWhatsAppInfo }) {
  return (
    <Card>
      <div className="px-5 py-3 border-b border-border flex items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold inline-flex items-center gap-1.5">
            <MessageCircle className="size-4 text-[#117A86]" aria-hidden />
            WhatsApp Bildirimleri
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Telefonunuzu doğrulayarak haftalık raporları WhatsApp&apos;tan da
            alabilirsiniz
          </p>
        </div>
        <WhatsAppStatusBadge whatsapp={whatsapp} />
      </div>

      <CardContent className="p-5">
        {whatsapp.enabled ? (
          <WhatsAppActivePanel whatsapp={whatsapp} />
        ) : whatsapp.pending_verify ? (
          <WhatsAppPendingPanel whatsapp={whatsapp} />
        ) : (
          <WhatsAppStartPanel />
        )}
      </CardContent>

      <div className="px-5 py-3 border-t border-border bg-muted/30 text-[11px] text-muted-foreground italic">
        WhatsApp gönderimi yalnızca onaylanmış şablonlarla yapılır. Numaranız
        sadece bildirim için kullanılır, üçüncü taraflarla paylaşılmaz.
      </div>
    </Card>
  );
}

function WhatsAppStatusBadge({ whatsapp }: { whatsapp: ParentWhatsAppInfo }) {
  if (whatsapp.enabled) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200">
        <CheckCircle2 className="size-3" aria-hidden />
        Aktif
      </span>
    );
  }
  if (whatsapp.pending_verify) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-amber-100 text-amber-700 border border-amber-200">
        <Clock className="size-3" aria-hidden />
        Kod bekleniyor
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-600 border border-slate-200">
      Kapalı
    </span>
  );
}

function WhatsAppActivePanel({ whatsapp }: { whatsapp: ParentWhatsAppInfo }) {
  const mut = useWhatsAppDisable();
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  function doDisable() {
    mut.mutate(undefined, {
      onSettled: () => setConfirmOpen(false),
    });
  }

  return (
    <>
      <div className="text-sm mb-3">
        Doğrulanan numara:{" "}
        <code className="bg-muted px-1.5 py-0.5 rounded font-mono">
          +{whatsapp.phone}
        </code>
      </div>
      {whatsapp.verified_at && (
        <div className="text-xs text-muted-foreground mb-3">
          Doğrulama tarihi: {formatTimestamp(whatsapp.verified_at)}
        </div>
      )}
      <Button
        size="sm"
        variant="outline"
        onClick={() => setConfirmOpen(true)}
        className="text-rose-700 border-rose-200 hover:bg-rose-50"
      >
        WhatsApp&apos;ı kapat
      </Button>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>WhatsApp bildirimlerini kapat</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            WhatsApp bildirimlerini kapatmak istediğinizden emin misiniz?
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setConfirmOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={doDisable}
              disabled={mut.isPending}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              Kapat
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function WhatsAppPendingPanel({ whatsapp }: { whatsapp: ParentWhatsAppInfo }) {
  const verify = useWhatsAppVerify();
  const startMut = useWhatsAppStart();
  const [code, setCode] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    verify.mutate({ code });
  }

  function resend() {
    if (whatsapp.pending_phone) {
      startMut.mutate({ phone: whatsapp.pending_phone });
    }
  }

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        <code className="bg-white/60 px-1.5 py-0.5 rounded font-mono">
          +{whatsapp.pending_phone}
        </code>{" "}
        numarasına 6 haneli kod gönderildi. WhatsApp uygulamanızı açıp kodu
        girin (geçerlilik 10 dakika).
      </div>

      {whatsapp.dev_test_code && (
        <div className="rounded-md border border-slate-300 bg-slate-100 p-2 text-xs flex items-center gap-2">
          <ShieldCheck className="size-4 text-slate-600 shrink-0" aria-hidden />
          <span className="font-semibold">DEV:</span>
          <span>WhatsApp gönderimi devre dışı (stub). Test kodu:</span>
          <code className="bg-white px-2 py-0.5 rounded border border-slate-300 font-mono">
            {whatsapp.dev_test_code}
          </code>
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-3">
        <div>
          <Label htmlFor="code">Doğrulama kodu</Label>
          <Input
            id="code"
            type="text"
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            placeholder="6 haneli kod"
            required
            autoComplete="one-time-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-40 mt-1 text-lg tracking-widest font-mono text-center"
          />
        </div>
        <div className="flex gap-2 flex-wrap">
          <Button
            type="submit"
            className="bg-[#117A86] hover:bg-[#0E5F69] text-white"
            disabled={verify.isPending}
          >
            {verify.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Doğrulanıyor…
              </>
            ) : (
              "Kodu Doğrula"
            )}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={resend}
            disabled={startMut.isPending}
            className="text-[#117A86]"
          >
            ↻ Yeni kod gönder
          </Button>
        </div>
      </form>
    </div>
  );
}

function WhatsAppStartPanel() {
  const mut = useWhatsAppStart();
  const [phone, setPhone] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate({ phone });
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        WhatsApp ile bildirim almak için telefon numaranızı girin. Numaraya 6
        haneli bir doğrulama kodu göndereceğiz.
      </p>
      <form onSubmit={onSubmit} className="space-y-3">
        <div>
          <Label htmlFor="phone">Telefon numarası</Label>
          <Input
            id="phone"
            type="tel"
            placeholder="+90 532 ..."
            required
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full max-w-sm mt-1"
            autoComplete="tel"
          />
          <p className="text-[11px] text-muted-foreground mt-1">
            Türkiye için <code>0532...</code> veya <code>+90 532...</code>
            {" "}
            formatı kabul edilir.
          </p>
        </div>
        <Button
          type="submit"
          className="bg-[#117A86] hover:bg-[#0E5F69] text-white"
          disabled={mut.isPending}
        >
          {mut.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden />
              Gönderiliyor…
            </>
          ) : (
            "Doğrulama Kodu Gönder"
          )}
        </Button>
      </form>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm}.${yyyy} ${hh}:${mn}`;
}
