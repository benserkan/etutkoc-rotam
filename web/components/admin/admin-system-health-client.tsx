"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Database,
  Inbox,
  Stethoscope,
  XCircle,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import { adminKeys, getAdminSystemHealth } from "@/lib/api/admin";
import type {
  CronStatusItem,
  DatabaseStatusInfo,
  DispatcherStatusInfo,
  HealthBand,
  SystemHealthResponse,
} from "@/lib/types/admin";

interface Props {
  initial: SystemHealthResponse;
}

/**
 * Sistem sağlığı paneli — Jinja `system_health.html` feature parity.
 *
 * 3 bölüm: cron jobs (durum + son çalışma) + dispatcher (kuyruk) + DB (boyut + tablo sayım).
 * Overall health en kötü bileşene göre (ok / warn / crit).
 */
export function AdminSystemHealthClient({ initial }: Props) {
  const q = useQuery<SystemHealthResponse>({
    queryKey: adminKeys.systemHealth(),
    queryFn: () => getAdminSystemHealth(),
    initialData: initial,
    staleTime: 15_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header>
        <Link
          href="/admin"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Panel
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 inline-flex items-center gap-2">
          <Stethoscope className="size-6 text-emerald-700" aria-hidden />
          Sistem Sağlığı
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Otomatik görevler, veliye bildirim kuyruğu ve veritabanı — anlık tablo.
        </p>
      </header>

      <OverallStatus
        health={data.overall_health}
        cronCount={data.crons.length}
      />

      <CronJobsTable crons={data.crons} />

      {data.dispatcher && <DispatcherCard dispatcher={data.dispatcher} />}

      {data.database && <DatabaseCard database={data.database} />}
    </div>
  );
}

function OverallStatus({
  health,
  cronCount,
}: {
  health: "ok" | "warn" | "crit";
  cronCount: number;
}) {
  const map = {
    crit: {
      bg: "bg-rose-50 border-rose-300",
      text: "text-rose-900",
      label: "Sistem dikkat istiyor — kritik bileşen var",
      Icon: XCircle,
      iconColor: "text-rose-600",
    },
    warn: {
      bg: "bg-amber-50 border-amber-300",
      text: "text-amber-900",
      label: "Sistem genel iyi — gözlem altında bileşen var",
      Icon: AlertCircle,
      iconColor: "text-amber-600",
    },
    ok: {
      bg: "bg-emerald-50 border-emerald-300",
      text: "text-emerald-900",
      label: "Sistem sağlıklı",
      Icon: CheckCircle2,
      iconColor: "text-emerald-600",
    },
  };
  const tone = map[health];
  const Icon = tone.Icon;
  return (
    <div className={cn("rounded-lg border-2 p-4 flex items-center gap-3", tone.bg)}>
      <Icon className={cn("size-8 shrink-0", tone.iconColor)} aria-hidden />
      <div>
        <div className={cn("text-lg font-semibold", tone.text)}>
          {tone.label}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {cronCount} otomatik görev · bildirim sistemi · veritabanı
        </div>
      </div>
    </div>
  );
}

function CronJobsTable({ crons }: { crons: CronStatusItem[] }) {
  return (
    <Card>
      <div className="px-4 py-3 border-b border-border bg-muted/40">
        <h2 className="text-sm font-medium inline-flex items-center gap-1.5">
          <Clock className="size-4 text-muted-foreground" aria-hidden />
          Otomatik Görevler ({crons.length})
        </h2>
      </div>
      {crons.length === 0 ? (
        <p className="p-6 text-center text-sm text-muted-foreground italic">
          Tanımlı otomatik görev yok.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/30 text-muted-foreground text-xs">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Görev</th>
                <th className="text-left px-4 py-2 font-medium">
                  Ne Zaman Çalışır
                </th>
                <th className="text-left px-4 py-2 font-medium">
                  Son Çalıştırma
                </th>
                <th className="text-left px-4 py-2 font-medium">Sonuç</th>
                <th className="text-left px-4 py-2 font-medium">Durum</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {crons.map((c) => (
                <CronRow key={c.job_key} cron={c} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function CronRow({ cron }: { cron: CronStatusItem }) {
  return (
    <tr>
      <td className="px-4 py-2">
        <div className="font-mono text-xs font-medium">{cron.job_key}</div>
        {cron.description && (
          <div className="text-[11px] text-muted-foreground mt-0.5">
            {cron.description}
          </div>
        )}
      </td>
      <td className="px-4 py-2 text-xs text-muted-foreground">
        {cron.dow_label} {cron.time_label} UTC
      </td>
      <td className="px-4 py-2 text-xs text-muted-foreground">
        {cron.last_run_at ? (
          <>
            {formatDateTime(cron.last_run_at)}
            {cron.hours_since_run != null && (
              <span className="text-muted-foreground/70 ml-1">
                ({cron.hours_since_run.toFixed(1)}h önce)
              </span>
            )}
          </>
        ) : (
          <span className="italic text-muted-foreground/60">hiç</span>
        )}
      </td>
      <td className="px-4 py-2 text-xs">
        {cron.last_status === "success" ? (
          <span className="text-emerald-700 inline-flex items-center gap-0.5">
            <CheckCircle2 className="size-3" aria-hidden />
            {cron.last_status}
          </span>
        ) : cron.last_status === "failed" ? (
          <span className="text-rose-700 inline-flex items-center gap-0.5">
            <XCircle className="size-3" aria-hidden />
            {cron.last_status}
          </span>
        ) : cron.last_status ? (
          <span>{cron.last_status}</span>
        ) : (
          <span className="text-muted-foreground/70">—</span>
        )}
        {cron.last_error && (
          <details className="mt-1">
            <summary className="cursor-pointer text-[10px] text-rose-600 list-none">
              hata detay ▾
            </summary>
            <pre className="mt-1 text-[10px] text-rose-800 whitespace-pre-wrap font-mono">
              {cron.last_error.slice(0, 300)}
            </pre>
          </details>
        )}
      </td>
      <td className="px-4 py-2">
        <HealthBadge band={cron.health} />
      </td>
    </tr>
  );
}

function HealthBadge({ band }: { band: HealthBand }) {
  const map: Record<HealthBand, { cls: string; label: string }> = {
    crit: {
      cls: "bg-rose-50 text-rose-700 border-rose-200",
      label: "🔴 Kritik gecikme",
    },
    warn: {
      cls: "bg-amber-50 text-amber-700 border-amber-200",
      label: "🟡 Gecikmiş",
    },
    never: {
      cls: "bg-slate-100 text-slate-600 border-slate-200",
      label: "⚪ Hiç çalışmadı",
    },
    disabled: {
      cls: "bg-slate-100 text-slate-500 border-slate-200",
      label: "⏸ Kapalı",
    },
    ok: {
      cls: "bg-emerald-50 text-emerald-700 border-emerald-200",
      label: "🟢 Sağlıklı",
    },
  };
  const m = map[band];
  return (
    <span
      className={cn(
        "text-xs px-2 py-0.5 rounded border font-medium whitespace-nowrap",
        m.cls,
      )}
    >
      {m.label}
    </span>
  );
}

function DispatcherCard({
  dispatcher,
}: {
  dispatcher: DispatcherStatusInfo;
}) {
  const healthMap = {
    crit: "text-rose-700",
    warn: "text-amber-700",
    ok: "text-emerald-700",
  };
  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="text-sm font-medium mb-3 inline-flex items-center gap-1.5">
          <Inbox className="size-4 text-muted-foreground" aria-hidden />
          Veliye Bildirim Kuyruğu
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Şu An Sırada
            </div>
            <div
              className={cn(
                "text-2xl font-semibold mt-0.5 tabular-nums",
                healthMap[dispatcher.health],
              )}
            >
              {dispatcher.queued_count}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Başarısız Toplam
            </div>
            <div className="text-2xl font-semibold mt-0.5 tabular-nums">
              {dispatcher.failed_count}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              En Eski Bekleyen
            </div>
            <div className="text-sm font-semibold mt-1">
              {dispatcher.oldest_queued_at ? (
                <>
                  {formatDateTime(dispatcher.oldest_queued_at)}
                  {dispatcher.oldest_queued_age_hours != null && (
                    <div className="text-[11px] text-muted-foreground">
                      {dispatcher.oldest_queued_age_hours.toFixed(1)} saat önce
                    </div>
                  )}
                </>
              ) : (
                <span className="text-muted-foreground/60">—</span>
              )}
            </div>
          </div>
          <div>
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
              Durum
            </div>
            <div className="mt-1">
              {dispatcher.health === "crit" ? (
                <span className="text-xs px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200 font-medium">
                  🔴 Acil bakın
                </span>
              ) : dispatcher.health === "warn" ? (
                <span className="text-xs px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 font-medium">
                  🟡 Yığılma var
                </span>
              ) : (
                <span className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                  🟢 Akıcı
                </span>
              )}
            </div>
          </div>
        </div>
        <p className="mt-3 text-[11px] text-muted-foreground italic">
          💡 100+ bekleyen veya 6 saatten eski mesaj → sarı; 500+ veya 24+ saat
          → kırmızı. Bekleyenler genellikle WhatsApp/e-posta servis darboğazı
          demektir.
        </p>
      </CardContent>
    </Card>
  );
}

function DatabaseCard({ database }: { database: DatabaseStatusInfo }) {
  const healthMap = {
    crit: "text-rose-700",
    warn: "text-amber-700",
    ok: "text-emerald-700",
  };
  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="text-sm font-medium mb-3 inline-flex items-center gap-1.5">
          <Database className="size-4 text-muted-foreground" aria-hidden />
          Veritabanı
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          <div>
            <div className="text-xs text-muted-foreground mb-2">
              Veritabanı dosyası
            </div>
            {database.file_path ? (
              <>
                <div
                  className="text-xs font-mono mb-2 truncate"
                  title={database.file_path}
                >
                  {database.file_path}
                </div>
                <div className="flex items-baseline gap-2">
                  <span
                    className={cn(
                      "text-3xl font-bold tabular-nums",
                      healthMap[database.health],
                    )}
                  >
                    {database.file_size_mb ?? "—"}
                  </span>
                  <span className="text-sm text-muted-foreground">MB</span>
                </div>
                <div className="text-[11px] text-muted-foreground mt-2">
                  500 MB üzerinde sarı, 1 GB üzerinde kırmızı uyarı.
                </div>
              </>
            ) : (
              <div className="text-sm text-muted-foreground italic">
                Dosya tabanlı veritabanı kullanılmıyor.
              </div>
            )}
          </div>
          <div>
            <div className="text-xs text-muted-foreground mb-2">
              Kayıt sayıları
            </div>
            <table className="w-full text-xs">
              <tbody className="divide-y divide-border">
                {Object.entries(database.table_counts).map(([tbl, cnt]) => (
                  <tr key={tbl}>
                    <td className="py-1 font-mono text-foreground/80">
                      {tbl}
                    </td>
                    <td className="py-1 text-right font-semibold tabular-nums">
                      {cnt < 0 ? (
                        <span className="text-rose-600">hata</span>
                      ) : (
                        new Intl.NumberFormat("tr-TR").format(cnt)
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}`;
}
