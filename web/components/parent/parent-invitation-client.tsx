"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Clock,
  HeartHandshake,
  Loader2,
  Mail,
  MessageCircle,
  ShieldCheck,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { useAcceptParentInvitation } from "@/lib/hooks/use-parent-mutations";
import type { ParentInvitationInfo } from "@/lib/types/parent";

interface Props {
  invitation: ParentInvitationInfo;
}

/**
 * Davet kabul form — Jinja `invitation_accept.html` feature parity + P0 iletişim
 * tercih matrisi.
 *
 * Veri yapısı backend ile birebir: full_name, password, password_confirm,
 * kvkk_accept. P0 ek alanlar: notification_preferences (7 e-posta + 7 WA
 * toggle), quiet_start/quiet_end, child_whatsapp_consent.
 *
 * Hata kodları: name_required / password_too_short / password_mismatch /
 * kvkk_not_accepted / email_in_use_other_role.
 */
export function ParentInvitationClient({ invitation }: Props) {
  const router = useRouter();
  const mut = useAcceptParentInvitation(invitation.token);
  const [fullName, setFullName] = React.useState("");
  const [phone, setPhone] = React.useState(""); // P1 — zorunlu, SMS ile doğrulanır
  const [password, setPassword] = React.useState("");
  const [passwordConfirm, setPasswordConfirm] = React.useState("");
  const [kvkkAccept, setKvkkAccept] = React.useState(false);
  const [localError, setLocalError] = React.useState<string | null>(null);

  // P0 — iletişim tercih matrisi (7 e-posta + 7 WA toggle)
  // E-posta default AÇIK (opt-out), WhatsApp default KAPALI (opt-in)
  const [prefs, setPrefs] = React.useState<Record<string, boolean>>({
    daily_summary_email: true,
    weekly_report_email: true,
    empty_day_email: true,
    drop_alert_email: true,
    new_program_email: true,
    teacher_note_email: true,
    exam_approaching_email: true,
    daily_summary_wa: false,
    weekly_report_wa: false,
    empty_day_wa: false,
    drop_alert_wa: false,
    new_program_wa: false,
    teacher_note_wa: false,
    exam_approaching_wa: false,
  });
  const [quietStart, setQuietStart] = React.useState("22:00");
  const [quietEnd, setQuietEnd] = React.useState("07:00");
  const [childWaConsent, setChildWaConsent] = React.useState(false);

  function togglePref(key: string) {
    setPrefs((p) => ({ ...p, [key]: !p[key] }));
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLocalError(null);

    // Client-side validasyon — server zaten doğrular ama UX için
    if (fullName.trim().length < 3) {
      setLocalError("Ad-soyad en az 3 karakter olmalıdır.");
      return;
    }
    if (phone.replace(/\D/g, "").length < 10) {
      setLocalError(
        "Cep telefonunuzu girin (örn: 0532 123 45 67). Davet kabulünden sonra SMS ile doğrulanır.",
      );
      return;
    }
    if (password.length < 8) {
      setLocalError("Şifre en az 8 karakter olmalıdır.");
      return;
    }
    if (password !== passwordConfirm) {
      setLocalError("Şifreler eşleşmiyor.");
      return;
    }
    if (!kvkkAccept) {
      setLocalError(
        "Hesap oluşturmak için aydınlatma metnini onaylamanız gereklidir.",
      );
      return;
    }

    mut.mutate(
      {
        full_name: fullName.trim(),
        phone: phone.trim(),
        password,
        password_confirm: passwordConfirm,
        kvkk_accept: kvkkAccept,
        notification_preferences: prefs,
        quiet_start: quietStart,
        quiet_end: quietEnd,
        child_whatsapp_consent: childWaConsent,
      },
      {
        onSuccess: (data) => {
          router.push(data.redirect_url || "/parent");
          router.refresh();
        },
        onError: (e) => {
          if (e instanceof ApiError) {
            setLocalError(e.detail?.message ?? "Hesap oluşturulamadı.");
          } else {
            setLocalError("Beklenmeyen bir hata oluştu.");
          }
        },
      },
    );
  }

  return (
    <div className="min-h-screen bg-muted/20 flex items-center justify-center p-4 py-8">
      <div className="w-full max-w-2xl">
        <div className="flex flex-col items-center mb-5">
          <div className="rounded-full bg-[#117A86]/10 text-[#117A86] p-3 mb-2">
            <HeartHandshake className="size-8" aria-hidden />
          </div>
          <p className="font-display text-xl font-bold tracking-tight">
            ETÜTKOÇ
          </p>
          <p className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground mt-1">
            Veli Daveti
          </p>
        </div>

        <Card className="border-border shadow-sm">
          <CardContent className="p-7 space-y-5">
            <div>
              <h1 className="text-lg font-semibold mb-1">Hoş geldiniz</h1>
              <p className="text-sm text-muted-foreground leading-relaxed">
                <strong className="text-foreground">
                  {invitation.invited_by_full_name}
                </strong>
                , velisi olduğunuz{" "}
                <strong className="text-foreground">
                  {invitation.student_full_name}
                </strong>{" "}
                adlı öğrencinin sınav hazırlık sürecini birlikte takip edebilmek
                için sizi davet etti. Hesabınızı oluşturmak için aşağıdaki
                bilgileri doldurun.
              </p>
            </div>

            <div className="rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground space-y-0.5">
              <div>
                <strong className="text-foreground">Davet edilen:</strong>{" "}
                <span className="font-mono">{invitation.invited_email}</span>
              </div>
              <div>
                <strong className="text-foreground">İlişki:</strong>{" "}
                {invitation.relation_label}
                {invitation.is_primary && (
                  <span className="ml-1 inline-block bg-[#117A86]/10 text-[#117A86] px-1.5 py-0.5 rounded text-[10px] uppercase tracking-wider font-semibold">
                    Birincil veli
                  </span>
                )}
              </div>
            </div>

            {localError && (
              <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2.5 text-sm text-rose-800">
                {localError}
              </div>
            )}

            <form onSubmit={onSubmit} method="post" className="space-y-5">
              {/* 1. Hesap bilgileri */}
              <section className="space-y-4">
                <h2 className="text-sm font-semibold text-foreground inline-flex items-center gap-1.5">
                  <span className="inline-flex items-center justify-center size-5 rounded-full bg-[#117A86] text-white text-[10px] font-bold">
                    1
                  </span>
                  Hesap bilgileri
                </h2>
                <div>
                  <Label htmlFor="full_name">Ad-Soyad</Label>
                  <Input
                    id="full_name"
                    type="text"
                    required
                    minLength={3}
                    maxLength={120}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    autoComplete="name"
                    className="mt-1"
                  />
                </div>

                <div>
                  <Label htmlFor="phone">Cep telefonu</Label>
                  <Input
                    id="phone"
                    type="tel"
                    required
                    placeholder="0532 123 45 67"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    autoComplete="tel"
                    className="mt-1"
                  />
                  <p className="text-[11px] text-muted-foreground mt-1">
                    Davet kabulünden sonra SMS ile gönderilecek 6 haneli kodla
                    doğrulayacaksınız. Bildirimler ve şifre sıfırlama için
                    kullanılır.
                  </p>
                </div>

                <div>
                  <Label htmlFor="password">Şifre</Label>
                  <Input
                    id="password"
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                    className="mt-1"
                  />
                  <p className="text-[11px] text-muted-foreground mt-1">
                    En az 8 karakter.
                  </p>
                </div>

                <div>
                  <Label htmlFor="password_confirm">Şifre (tekrar)</Label>
                  <Input
                    id="password_confirm"
                    type="password"
                    required
                    minLength={8}
                    value={passwordConfirm}
                    onChange={(e) => setPasswordConfirm(e.target.value)}
                    autoComplete="new-password"
                    className="mt-1"
                  />
                </div>
              </section>

              {/* 2. İletişim tercihleri */}
              <section className="space-y-3 border-t border-border pt-5">
                <h2 className="text-sm font-semibold text-foreground inline-flex items-center gap-1.5">
                  <span className="inline-flex items-center justify-center size-5 rounded-full bg-[#117A86] text-white text-[10px] font-bold">
                    2
                  </span>
                  İletişim tercihleriniz
                </h2>
                <p className="text-xs text-muted-foreground">
                  Çocuğunuzun ilerlemesi için size hangi kanaldan ulaşalım?
                  Her bildirim türünü ayrı ayrı seçin. Bu seçimleri istediğiniz
                  zaman Bildirim Tercihleri sayfasından değiştirebilirsiniz.
                </p>

                <PrefMatrix prefs={prefs} onToggle={togglePref} />

                <div className="rounded-md border border-amber-200 bg-amber-50/60 px-3 py-2 text-[11px] text-amber-900 leading-relaxed">
                  <strong>WhatsApp bildirimleri</strong> almak için davet
                  kabulünden sonra Bildirim Tercihleri sayfasından telefon
                  numaranızı doğrulamanız gerekir. Telefonunuz doğrulanana
                  kadar yalnızca e-posta bildirimleri gönderilir.
                </div>

                <div className="rounded-md border border-border bg-muted/30 p-3 space-y-2">
                  <h3 className="text-xs font-semibold text-foreground inline-flex items-center gap-1.5">
                    <Clock className="size-3.5 text-[#117A86]" aria-hidden />
                    Sessiz saatler
                  </h3>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Input
                      type="time"
                      value={quietStart}
                      onChange={(e) => setQuietStart(e.target.value)}
                      className="w-28"
                    />
                    <span className="text-xs text-muted-foreground">→</span>
                    <Input
                      type="time"
                      value={quietEnd}
                      onChange={(e) => setQuietEnd(e.target.value)}
                      className="w-28"
                    />
                  </div>
                  <p className="text-[10px] text-muted-foreground italic">
                    Bu saatlerde tetiklenen bildirimler sessiz saat bitimine
                    ertelenir.
                  </p>
                </div>

                <label className="flex items-start gap-2 rounded-md border border-border p-3 text-xs cursor-pointer hover:bg-muted/40 transition-colors">
                  <input
                    type="checkbox"
                    checked={childWaConsent}
                    onChange={(e) => setChildWaConsent(e.target.checked)}
                    className="mt-0.5 accent-[#117A86]"
                  />
                  <div className="flex-1">
                    <div className="font-semibold text-foreground mb-0.5">
                      Çocuğum WhatsApp mesajı alabilir
                    </div>
                    <p className="text-muted-foreground leading-relaxed">
                      18 yaş altı çocuğunuzun WhatsApp üzerinden doğrudan
                      bildirim almasına izin veriyorsanız işaretleyin. Onay
                      vermezseniz çocuğunuzla iletişim panel ve e-posta
                      üzerinden devam eder.
                    </p>
                  </div>
                </label>
              </section>

              {/* 3. KVKK */}
              <section className="space-y-3 border-t border-border pt-5">
                <h2 className="text-sm font-semibold text-foreground inline-flex items-center gap-1.5">
                  <span className="inline-flex items-center justify-center size-5 rounded-full bg-[#117A86] text-white text-[10px] font-bold">
                    3
                  </span>
                  Aydınlatma metni onayı
                </h2>
                <label className="flex items-start gap-2 text-xs text-muted-foreground cursor-pointer">
                  <input
                    type="checkbox"
                    required
                    checked={kvkkAccept}
                    onChange={(e) => setKvkkAccept(e.target.checked)}
                    className="mt-0.5 accent-[#117A86]"
                  />
                  <span>
                    <Link
                      href="/legal/kvkk-veli"
                      target="_blank"
                      className="text-[#117A86] hover:underline inline-flex items-center gap-0.5"
                    >
                      <ShieldCheck className="size-3" aria-hidden />
                      Veli Aydınlatma Metni
                    </Link>
                    &apos;ni okudum, anladım ve kişisel verilerimin belirtilen
                    amaçlarla — bildirim kanalı seçimlerim dahil — işlenmesini
                    kabul ediyorum.
                  </span>
                </label>
              </section>

              <Button
                type="submit"
                className="w-full bg-[#117A86] hover:bg-[#0E5F69] text-white"
                disabled={mut.isPending}
              >
                {mut.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                    Hesap oluşturuluyor…
                  </>
                ) : (
                  "Hesabımı Oluştur"
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-[11px] text-muted-foreground mt-6">
          © ETÜTKOÇ Rotam · Veli paneli
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// Bildirim tercih matrisi — 7 satır × 2 sütun (E-posta / WhatsApp)
// ============================================================================

const PREF_ROWS: Array<{
  emailKey: string;
  waKey: string;
  title: string;
  desc: string;
}> = [
  {
    emailKey: "daily_summary_email",
    waKey: "daily_summary_wa",
    title: "Günlük özet",
    desc: "Çocuğun bugünkü tamamlama özeti",
  },
  {
    emailKey: "weekly_report_email",
    waKey: "weekly_report_wa",
    title: "Haftalık rapor",
    desc: "Her 7 günlük döngünün sonunda",
  },
  {
    emailKey: "empty_day_email",
    waKey: "empty_day_wa",
    title: "Boş gün uyarısı",
    desc: "Hiç görev tamamlanmadığında",
  },
  {
    emailKey: "drop_alert_email",
    waKey: "drop_alert_wa",
    title: "Düşüş alarmı",
    desc: "Önceki haftaya göre belirgin düşüş",
  },
  {
    emailKey: "new_program_email",
    waKey: "new_program_wa",
    title: "Yeni program",
    desc: "Öğretmen haftalık programı yayınladığında",
  },
  {
    emailKey: "teacher_note_email",
    waKey: "teacher_note_wa",
    title: "Öğretmen notu",
    desc: "Size özel not gönderildiğinde",
  },
  {
    emailKey: "exam_approaching_email",
    waKey: "exam_approaching_wa",
    title: "Sınav yaklaşıyor",
    desc: "Sınava 30 / 7 / 1 gün kala",
  },
];

function PrefMatrix({
  prefs,
  onToggle,
}: {
  prefs: Record<string, boolean>;
  onToggle: (key: string) => void;
}) {
  return (
    <div className="rounded-md border border-border overflow-hidden">
      <div className="grid grid-cols-[1fr_auto_auto] items-center gap-1 bg-muted/60 px-3 py-2 text-[10px] uppercase tracking-wider font-semibold text-muted-foreground">
        <div>Bildirim türü</div>
        <div className="px-3 inline-flex items-center gap-1">
          <Mail className="size-3" aria-hidden />
          E-posta
        </div>
        <div className="px-3 inline-flex items-center gap-1">
          <MessageCircle className="size-3" aria-hidden />
          WhatsApp
        </div>
      </div>
      <div className="divide-y divide-border">
        {PREF_ROWS.map((row) => (
          <div
            key={row.emailKey}
            className="grid grid-cols-[1fr_auto_auto] items-center gap-1 px-3 py-2 hover:bg-muted/40 transition-colors"
          >
            <div className="min-w-0">
              <div className="text-xs font-medium truncate">{row.title}</div>
              <div className="text-[10px] text-muted-foreground truncate">
                {row.desc}
              </div>
            </div>
            <ChannelCheck
              checked={prefs[row.emailKey]}
              onChange={() => onToggle(row.emailKey)}
              label={`${row.title} — E-posta`}
            />
            <ChannelCheck
              checked={prefs[row.waKey]}
              onChange={() => onToggle(row.waKey)}
              label={`${row.title} — WhatsApp`}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

function ChannelCheck({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <label
      className={cn(
        "inline-flex items-center justify-center px-3 py-1.5 cursor-pointer rounded transition-colors",
        checked ? "text-[#117A86]" : "text-muted-foreground hover:text-foreground",
      )}
      aria-label={label}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="size-4 accent-[#117A86] cursor-pointer"
      />
    </label>
  );
}
