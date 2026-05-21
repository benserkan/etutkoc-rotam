"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Loader2, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { adminKeys, getAdminFeatureFlags } from "@/lib/api/admin";
import { useToggleFeatureFlag } from "@/lib/hooks/use-admin-mutations";
import type {
  FeatureFlagItem,
  FeatureFlagsListResponse,
} from "@/lib/types/admin";

interface Props {
  initial: FeatureFlagsListResponse;
}

/**
 * Özellik anahtarları listesi — Jinja `feature_flags_list.html` feature parity.
 *
 * Tablo: key + açıklama + global toggle (confirm) + override sayım + detay link.
 */
export function AdminFeatureFlagsClient({ initial }: Props) {
  const q = useQuery<FeatureFlagsListResponse>({
    queryKey: adminKeys.featureFlags(),
    queryFn: () => getAdminFeatureFlags(),
    initialData: initial,
    staleTime: 30_000,
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
          <Sparkles className="size-6 text-indigo-700" aria-hidden />
          Özellik Anahtarları
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Yapay zeka önerisi, veliye e-posta, WhatsApp gibi özellikleri açıp
          kapat. &ldquo;Hepsine açık&rdquo; veya &ldquo;Sadece şu kuruma
          açık/kapalı&rdquo;. Değişiklik 1 dakikada tüm sistemde geçerli.
        </p>
      </header>

      {data.flags.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            Henüz tanımlı özellik anahtarı yok.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Özellik</th>
                  <th className="text-left px-4 py-2 font-medium">Açıklama</th>
                  <th className="text-left px-4 py-2 font-medium">
                    Genel Durum
                  </th>
                  <th className="text-left px-4 py-2 font-medium">
                    Kuruma Özel
                  </th>
                  <th className="text-right px-4 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.flags.map((f) => (
                  <FlagRow key={f.id} flag={f} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="rounded-md border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground space-y-1">
        <p>
          💡 <strong>Öncelik sırası:</strong> Önce kuruma özel ayar bakılır; o
          yoksa genel duruma. Tanımsız flag → açık (defansif).
        </p>
      </div>
    </div>
  );
}

function FlagRow({ flag }: { flag: FeatureFlagItem }) {
  return (
    <tr>
      <td className="px-4 py-3">
        <Link
          href={`/admin/feature-flags/${flag.id}`}
          className="font-mono text-sm font-medium hover:text-indigo-600"
        >
          {flag.key}
        </Link>
      </td>
      <td className="px-4 py-3 text-muted-foreground text-xs max-w-md">
        {flag.description}
      </td>
      <td className="px-4 py-3">
        <ToggleButton flag={flag} />
      </td>
      <td className="px-4 py-3 text-xs">
        {flag.override_total === 0 ? (
          <span className="text-muted-foreground/60">—</span>
        ) : (
          <>
            {flag.override_enabled_count > 0 && (
              <span className="text-emerald-700">
                {flag.override_enabled_count} açık
              </span>
            )}
            {flag.override_disabled_count > 0 && (
              <>
                {flag.override_enabled_count > 0 && (
                  <span className="text-muted-foreground/40 mx-1">·</span>
                )}
                <span className="text-rose-700">
                  {flag.override_disabled_count} kapalı
                </span>
              </>
            )}
          </>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        <Link
          href={`/admin/feature-flags/${flag.id}`}
          className="text-xs text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-0.5"
        >
          Kuruma özel ayar
          <ArrowRight className="size-3" aria-hidden />
        </Link>
      </td>
    </tr>
  );
}

function ToggleButton({ flag }: { flag: FeatureFlagItem }) {
  const mut = useToggleFeatureFlag(flag.id);
  const [open, setOpen] = React.useState(false);

  function doToggle() {
    mut.mutate(undefined, { onSettled: () => setOpen(false) });
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "text-xs px-3 py-1 rounded font-medium border",
          flag.enabled_globally
            ? "bg-emerald-100 text-emerald-700 border-emerald-300 hover:bg-emerald-200"
            : "bg-rose-100 text-rose-700 border-rose-300 hover:bg-rose-200",
        )}
      >
        {flag.enabled_globally ? "● Açık" : "○ Kapalı"}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Genel Durumu Değiştir</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            <code className="bg-muted/50 px-1 rounded">{flag.key}</code>{" "}
            özelliği herkese{" "}
            <strong>{flag.enabled_globally ? "KAPATILSIN" : "AÇILSIN"}</strong>{" "}
            mı? Tüm kurumları etkiler (kuruma özel ayar varsa o korunur).
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={doToggle}
              disabled={mut.isPending}
              className={
                flag.enabled_globally
                  ? "bg-rose-600 hover:bg-rose-700 text-white"
                  : "bg-emerald-600 hover:bg-emerald-700 text-white"
              }
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              {flag.enabled_globally ? "Kapat" : "Aç"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
