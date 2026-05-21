"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Loader2, Mail, Play, Save } from "lucide-react";

import { getTeacherSettings, settingsKeys } from "@/lib/api/settings";
import {
  usePatchCronSchedule,
  useRunCronNow,
  useTestEmail,
} from "@/lib/hooks/use-settings-mutations";
import type {
  CronScheduleItem,
  TeacherSettingsResponse,
} from "@/lib/types/settings";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordChangeCard } from "@/components/password-change-card";
import { cn } from "@/lib/utils";

type TabKey = "profile" | "security" | "email" | "cron";

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: "profile", label: "Profil" },
  { key: "security", label: "Güvenlik" },
  { key: "email", label: "E-posta" },
  { key: "cron", label: "Otomatik bildirimler" },
];

interface Props {
  initial: TeacherSettingsResponse;
}

export function SettingsClient({ initial }: Props) {
  const q = useQuery<TeacherSettingsResponse>({
    queryKey: settingsKeys.settings(),
    queryFn: () => getTeacherSettings(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;

  const [tab, setTab] = React.useState<TabKey>("profile");

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">
          Ayarlar
        </p>
        <h1 className="text-2xl font-semibold tracking-tight font-display">
          Hesap & bildirim ayarları
        </h1>
      </header>

      <div
        role="tablist"
        aria-label="Ayarlar sekmeleri"
        className="flex items-center gap-1 border-b border-border"
      >
        {TABS.map((t) => {
          const isActive = tab === t.key;
          return (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={isActive}
              onClick={() => setTab(t.key)}
              className={cn(
                "px-3 py-2 -mb-px text-sm border-b-2 transition-colors",
                isActive
                  ? "border-foreground font-medium"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "profile" ? <ProfileTab data={data} /> : null}
      {tab === "security" ? <SecurityTab /> : null}
      {tab === "email" ? <EmailTab data={data} /> : null}
      {tab === "cron" ? <CronTab data={data} /> : null}
    </div>
  );
}

function SecurityTab() {
  return (
    <div className="space-y-4">
      <PasswordChangeCard
        title="Hesap şifresi"
        description="Mevcut şifreni doğrula, ardından yeni bir şifre belirle. Yeni şifre son sızıntı veritabanlarına karşı kontrol edilir; politikayı karşılamayan şifre kabul edilmez."
      />
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Veri ve hesap işlemleri</CardTitle>
        </CardHeader>
        <CardContent className="p-4 text-sm space-y-2">
          <p className="text-muted-foreground">
            Verilerini indirme ve hesabını silme talepleri Hesabım sayfasında.
            KVKK kapsamındaki işlemler oradan yürütülür.
          </p>
          <Button asChild variant="outline" size="sm">
            <Link href="/me/account">
              <ExternalLink className="size-4" aria-hidden />
              Hesabım sayfasına git
            </Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function ProfileTab({ data }: { data: TeacherSettingsResponse }) {
  return (
    <Card>
      <CardContent className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <Field label="Ad Soyad" value={data.teacher.full_name} />
        <Field label="E-posta" value={data.teacher.email ?? "—"} />
        <Field
          label="Hesap tipi"
          value={
            data.teacher.institution_id !== null
              ? `Kurum (#${data.teacher.institution_id})`
              : "Bağımsız"
          }
        />
        <Field label="Plan" value={data.teacher.plan ?? "—"} />
      </CardContent>
    </Card>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wide">
        {label}
      </p>
      <p className="font-medium">{value}</p>
    </div>
  );
}

function EmailTab({ data }: { data: TeacherSettingsResponse }) {
  const test = useTestEmail();
  const [to, setTo] = React.useState(data.teacher.email ?? "");
  const cfg = data.email_config;

  function onSend(e: React.FormEvent) {
    e.preventDefault();
    test.mutate({ body: { to: to.trim() || undefined } });
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">SMTP yapılandırması</CardTitle>
        </CardHeader>
        <CardContent className="p-4 grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          <Field
            label="Durum"
            value={cfg.enabled ? "Etkin" : "Devre dışı (EMAIL_ENABLED=false)"}
          />
          <Field label="Sunucu" value={cfg.smtp_host ?? "Tanımsız"} />
          <Field
            label="Port"
            value={cfg.smtp_port !== null ? String(cfg.smtp_port) : "—"}
          />
          <Field label="Gönderici" value={cfg.from_address ?? "—"} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Test e-postası</CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <form onSubmit={onSend} className="flex flex-wrap items-end gap-2">
            <div className="flex-1 min-w-[220px] space-y-1">
              <Label htmlFor="test-email-to">Alıcı e-posta</Label>
              <Input
                id="test-email-to"
                type="email"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder={data.teacher.email ?? "demo@etutkoc.local"}
              />
            </div>
            <Button type="submit" disabled={test.isPending}>
              {test.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Mail className="size-4" aria-hidden />
              )}
              Test gönder
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function CronTab({ data }: { data: TeacherSettingsResponse }) {
  const runNow = useRunCronNow();
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Manuel tetikleme</CardTitle>
        </CardHeader>
        <CardContent className="p-4 flex flex-wrap items-center gap-3">
          <p className="text-sm text-muted-foreground flex-1 min-w-[200px]">
            Açık cron&apos;ları zaman kontrolünü atlayarak hemen çalıştırır.
            Bildirim mantığını (boş gün suppress, sessiz saat, vs.) test etmek
            için kullanışlıdır.
          </p>
          <Button
            onClick={() => runNow.mutate()}
            disabled={runNow.isPending}
          >
            {runNow.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Play className="size-4" aria-hidden />
            )}
            Şimdi tetikle
          </Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-3">
        {data.cron_schedules.map((c) => (
          <CronEditorCard key={c.id} schedule={c} />
        ))}
        {data.cron_schedules.length === 0 ? (
          <Card>
            <CardContent className="p-4 text-sm text-muted-foreground">
              Tanımlı cron yok.
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

const DOW_LABELS = [
  "Pazartesi",
  "Salı",
  "Çarşamba",
  "Perşembe",
  "Cuma",
  "Cumartesi",
  "Pazar",
];

function CronEditorCard({ schedule }: { schedule: CronScheduleItem }) {
  const patch = usePatchCronSchedule(schedule.id);
  const [hour, setHour] = React.useState(String(schedule.hour));
  const [minute, setMinute] = React.useState(String(schedule.minute));
  const [dow, setDow] = React.useState<string>(
    schedule.day_of_week === null ? "" : String(schedule.day_of_week),
  );
  const [enabled, setEnabled] = React.useState(schedule.enabled);

  function onSave(e: React.FormEvent) {
    e.preventDefault();
    const h = Number(hour);
    const m = Number(minute);
    if (!Number.isFinite(h) || !Number.isFinite(m)) return;
    patch.mutate({
      body: {
        hour: h,
        minute: m,
        enabled,
        day_of_week: dow === "" ? null : Number(dow),
        clear_day_of_week: dow === "",
      },
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          {schedule.info?.title ?? schedule.job_key}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 space-y-3 text-sm">
        {schedule.info ? (
          <div className="space-y-1 text-xs text-muted-foreground">
            <p>{schedule.info.what}</p>
            <p>
              <span className="font-medium">Kime uygulanır:</span>{" "}
              {schedule.info.applies}
            </p>
            <p className="italic">{schedule.info.default_hint}</p>
          </div>
        ) : null}
        <form
          onSubmit={onSave}
          className="grid grid-cols-2 sm:grid-cols-5 gap-2 items-end"
        >
          <div className="space-y-1">
            <Label htmlFor={`cron-h-${schedule.id}`}>Saat (UTC)</Label>
            <Input
              id={`cron-h-${schedule.id}`}
              type="number"
              min={0}
              max={23}
              value={hour}
              onChange={(e) => setHour(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor={`cron-m-${schedule.id}`}>Dakika</Label>
            <Input
              id={`cron-m-${schedule.id}`}
              type="number"
              min={0}
              max={59}
              value={minute}
              onChange={(e) => setMinute(e.target.value)}
            />
          </div>
          <div className="space-y-1 col-span-2">
            <Label htmlFor={`cron-d-${schedule.id}`}>Hafta günü</Label>
            <select
              id={`cron-d-${schedule.id}`}
              value={dow}
              onChange={(e) => setDow(e.target.value)}
              className={cn(
                "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            >
              <option value="">Her gün</option>
              {DOW_LABELS.map((label, i) => (
                <option key={i} value={i}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 h-9">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            Etkin
          </label>
          <Button
            type="submit"
            size="sm"
            disabled={patch.isPending}
            className="sm:col-span-5 sm:justify-self-end"
          >
            {patch.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Save className="size-4" aria-hidden />
            )}
            Kaydet
          </Button>
        </form>
        <div className="text-xs text-muted-foreground flex flex-wrap gap-3 pt-1 border-t border-border">
          <span>
            Mevcut: {schedule.time_label} UTC ≈ {schedule.tr_time_label} TR
          </span>
          <span>· {schedule.dow_label}</span>
          {schedule.last_run_at ? (
            <span>
              · son çalışma {schedule.last_run_at.slice(0, 16).replace("T", " ")}
              {schedule.last_status ? ` (${schedule.last_status})` : ""}
            </span>
          ) : null}
          {schedule.last_error ? (
            <span className="text-destructive">
              · son hata: {schedule.last_error.slice(0, 80)}
            </span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
