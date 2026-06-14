"use client";

import * as React from "react";
import { BarChart3, ExternalLink, RefreshCw, Info } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * Site Analitiği — Plausible (self-host) panosunu gömülü gösterir.
 * `PLAUSIBLE_SHARED_URL` (paylaşılabilir embed bağlantısı) tanımlıysa iframe;
 * değilse kurulum rehberi. Plausible gizlilik-dostu (çerezsiz, kişisel veri yok).
 */
export function AnalyticsView({
  sharedUrl,
  dashboardUrl,
}: {
  sharedUrl: string;
  dashboardUrl: string;
}) {
  const [reloadKey, setReloadKey] = React.useState(0);

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 inline-flex size-9 items-center justify-center rounded-lg bg-indigo-100 text-indigo-700">
              <BarChart3 className="size-5" aria-hidden />
            </span>
            <div>
              <h1 className="text-lg font-semibold">Site Analitiği</h1>
              <p className="mt-0.5 max-w-2xl text-sm text-muted-foreground">
                Ziyaretçi, sayfa görüntüleme, trafik kaynağı, cihaz ve ülke kırılımı —
                gizlilik-dostu (çerezsiz, kişisel veri saklanmaz, KVKK uyumlu) Plausible
                ile ölçülür. Veri kendi sunucumuzda kalır.
              </p>
            </div>
          </div>
          {sharedUrl ? (
            <div className="flex items-center gap-1.5">
              <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
                <RefreshCw className="size-4" aria-hidden /> Yenile
              </Button>
              {dashboardUrl ? (
                <Button variant="outline" size="sm" asChild>
                  <a href={dashboardUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="size-4" aria-hidden /> Tam panel
                  </a>
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      {sharedUrl ? (
        <div className="mt-4 overflow-hidden rounded-xl border border-border bg-card">
          <iframe
            key={reloadKey}
            src={sharedUrl}
            title="Site Analitiği — Plausible"
            loading="lazy"
            scrolling="no"
            className="w-full"
            style={{ minWidth: "100%", height: "1700px", border: "0" }}
          />
        </div>
      ) : (
        <SetupGuide />
      )}
    </div>
  );
}

function SetupGuide() {
  return (
    <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/60 p-5 dark:border-amber-900/40 dark:bg-amber-950/20">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-900 dark:text-amber-200">
        <Info className="size-4" aria-hidden /> Analitik henüz yapılandırılmadı
      </div>
      <p className="text-sm text-amber-900/90 dark:text-amber-100/80">
        Plausible (self-host) sunucuda çalışır hale gelince burada gömülü pano görünür.
        Kurulum adımları:
      </p>
      <ol className="mt-3 list-decimal space-y-1.5 pl-5 text-sm text-amber-900/90 dark:text-amber-100/80">
        <li>
          <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">docker compose up -d plausible</code>{" "}
          ile Plausible + ClickHouse ayağa kalkar (deploy/docker-compose.yml hazır).
        </li>
        <li>
          <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">analytics.etutkoc.com</code>{" "}
          DNS A kaydı sunucuya yönlendirilir; Plausible ilk kullanıcı + site
          (<code>rotam.etutkoc.com</code>) oluşturulur.
        </li>
        <li>
          Plausible → Site Ayarları → <strong>Visibility / Shared Links</strong>’ten
          paylaşılabilir bağlantı üretilir.
        </li>
        <li>
          O bağlantı <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">PLAUSIBLE_SHARED_URL</code>{" "}
          olarak <code>deploy/.env</code>’e yazılır;{" "}
          <code className="rounded bg-amber-100 px-1 dark:bg-amber-900/40">docker compose up -d next</code>.
        </li>
      </ol>
      <p className="mt-3 text-xs text-amber-800/80 dark:text-amber-200/60">
        Ayrıntı: <code>deploy/PLAUSIBLE_SETUP.md</code>
      </p>
    </div>
  );
}
