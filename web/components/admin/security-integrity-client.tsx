"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Clock,
  DatabaseZap,
  FileWarning,
  GitBranch,
  HardDrive,
  ScrollText,
  Unlink,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { adminKeys, getAdminSecurityIntegrity } from "@/lib/api/admin";
import type { IntegrityResponse } from "@/lib/types/admin";
import {
  LevelBadge,
  fmtDateTime,
  humanizeAgo,
  levelBadgeClass,
} from "@/components/admin/security-ui";

interface Props {
  initial: IntegrityResponse;
}

function migrationTone(status: string): string {
  if (status === "ok") return "border-emerald-200 bg-emerald-50/40";
  if (status === "pending") return "border-amber-200 bg-amber-50/40";
  return "border-rose-200 bg-rose-50/40";
}

export function SecurityIntegrityClient({ initial }: Props) {
  const q = useQuery<IntegrityResponse>({
    queryKey: adminKeys.securityIntegrity(),
    queryFn: getAdminSecurityIntegrity,
    initialData: initial,
    staleTime: 30_000,
  });
  const d = q.data ?? initial;
  const mig = d.migration;
  const dbf = d.db_file;
  const cron = d.cron_drift;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
          <DatabaseZap className="size-6 text-slate-700" aria-hidden />
          Veri Bütünlüğü
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Veritabanı şema sürümü, dosya boyutu, kayıt tutarsızlıkları (yetim kayıtlar),
          KVKK talep süresi (30 günlük yasal süre) ve zamanlanmış görevlerin tazeliği.
        </p>
        <p className="mt-1 text-[11px] text-muted-foreground">Son tarama: {fmtDateTime(d.generated_at)}</p>
      </header>

      {/* Migration + DB dosyası */}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card className={cn("border-l-4 p-4", migrationTone(mig.status))}>
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
            <GitBranch className="size-4 text-muted-foreground" aria-hidden />
            Şema sürümü (migration)
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Kodun beklediği veritabanı sürümü ile çalışan sürüm aynı mı?
          </p>
          <dl className="mt-3 space-y-1.5 text-sm">
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Durum</dt>
              <dd>
                <LevelBadge level={mig.status === "ok" ? "ok" : mig.status === "pending" ? "pending" : "error"} />
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Beklenen (head)</dt>
              <dd className="font-mono text-[11px]">{mig.head ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Çalışan (current)</dt>
              <dd className="font-mono text-[11px]">{mig.current ?? "—"}</dd>
            </div>
            {mig.pending ? (
              <p className="rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-800">
                Bekleyen migration var — kod ile veritabanı sürümü uyuşmuyor.
              </p>
            ) : null}
            {mig.error ? (
              <p className="rounded-md bg-rose-50 px-2 py-1 font-mono text-[11px] text-rose-800">{mig.error}</p>
            ) : null}
          </dl>
        </Card>

        <Card className="p-4">
          <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
            <HardDrive className="size-4 text-muted-foreground" aria-hidden />
            Veritabanı dosyası
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">500 MB sonrası uyarı, 1 GB sonrası kritik.</p>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-semibold tabular-nums">{dbf.size_mb}</span>
            <span className="text-sm text-muted-foreground">MB</span>
            <span className="ml-auto">
              <LevelBadge level={dbf.level} />
            </span>
          </div>
          <dl className="mt-3 space-y-1.5 text-sm">
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Son değişiklik</dt>
              <dd>{fmtDateTime(dbf.modified_at)} ({humanizeAgo(dbf.age_seconds)})</dd>
            </div>
            {dbf.path ? (
              <div className="truncate font-mono text-[11px] text-muted-foreground" title={dbf.path}>
                {dbf.path}
              </div>
            ) : null}
          </dl>
        </Card>
      </section>

      {/* Orphan tarama */}
      <section>
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <Unlink className="size-4 text-muted-foreground" aria-hidden />
              Yetim kayıt taraması
            </h2>
            <span
              className={cn(
                "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
                d.orphans.total_findings > 0 ? levelBadgeClass("warn") : levelBadgeClass("ok"),
              )}
            >
              {d.orphans.total_findings} kayıt
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Bağlı olması gereken ama bağlantısı kopmuş kayıtlar (kuruma bağlı olmayan
            yönetici, çocuğu olmayan veli vb.).
          </p>
          {d.orphans.findings.length === 0 ? (
            <p className="mt-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              Tutarsızlık bulunamadı.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {d.orphans.findings.map((f) => (
                <div key={f.kind} className="rounded-md border border-amber-200 bg-amber-50/50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-amber-900">{f.label}</span>
                    <span className="rounded-full bg-amber-200 px-2 py-0.5 text-[11px] font-medium text-amber-900">
                      {f.count}
                    </span>
                  </div>
                  {f.samples.length > 0 ? (
                    <ul className="mt-1.5 space-y-0.5 font-mono text-[11px] text-amber-800">
                      {f.samples.slice(0, 5).map((s, i) => (
                        <li key={i}>{JSON.stringify(s)}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </Card>
      </section>

      {/* KVKK SLA + Cron drift */}
      <section className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <FileWarning className="size-4 text-muted-foreground" aria-hidden />
              KVKK talep süresi
            </h2>
            <span
              className={cn(
                "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
                d.kvkk_sla.overdue_count > 0 ? levelBadgeClass("critical") : levelBadgeClass("ok"),
              )}
            >
              {d.kvkk_sla.overdue_count} gecikmiş
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Veri talepleri {d.kvkk_sla.sla_days} gün içinde sonuçlandırılmalı. Açık toplam: {d.kvkk_sla.open_total}.
          </p>
          {d.kvkk_sla.overdue_samples.length === 0 ? (
            <p className="mt-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              Süresi geçmiş talep yok.
            </p>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-2 py-1 text-left">#</th>
                    <th className="px-2 py-1 text-left">Tür</th>
                    <th className="px-2 py-1 text-left">Durum</th>
                    <th className="px-2 py-1 text-right">Yaş</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.kvkk_sla.overdue_samples.map((r) => (
                    <tr key={r.id}>
                      <td className="px-2 py-1 font-mono text-[11px]">{r.id}</td>
                      <td className="px-2 py-1 text-muted-foreground">{r.kind}</td>
                      <td className="px-2 py-1 text-muted-foreground">{r.status}</td>
                      <td className="px-2 py-1 text-right tabular-nums text-rose-600">{r.age_days} gün</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <h2 className="inline-flex items-center gap-2 text-sm font-semibold">
              <Clock className="size-4 text-muted-foreground" aria-hidden />
              Zamanlanmış görev tazeliği
            </h2>
            <span className="text-xs text-muted-foreground">
              {cron.summary.ok ?? 0} sağlıklı · {cron.summary.warn ?? 0} uyarı · {cron.summary.critical ?? 0} kritik
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Her görevin son çalışma zamanı eşiği aştı mı? (25 saat uyarı, 48 saat kritik)
          </p>
          {cron.jobs.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">Kayıtlı görev yok.</p>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-2 py-1 text-left">Görev</th>
                    <th className="px-2 py-1 text-left">Son çalışma</th>
                    <th className="px-2 py-1 text-center">Durum</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {cron.jobs.map((j) => (
                    <tr key={j.job_key}>
                      <td className="px-2 py-1 font-mono text-[11px]">{j.job_key}</td>
                      <td className="px-2 py-1 text-muted-foreground">
                        {j.last_run_at ? (
                          <>
                            {fmtDateTime(j.last_run_at)}
                            {j.age_hours != null ? (
                              <span className="ml-1 text-[11px]">({j.age_hours} saat önce)</span>
                            ) : null}
                          </>
                        ) : (
                          "hiç"
                        )}
                      </td>
                      <td className="px-2 py-1 text-center">
                        <LevelBadge level={j.level} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <ScrollText className="size-3.5" aria-hidden />
        Tüm taramalar sayfa açılışında hafif sorgularla (LIMIT 100) çalışır; veritabanına yazma yapmaz.
      </p>
    </div>
  );
}
