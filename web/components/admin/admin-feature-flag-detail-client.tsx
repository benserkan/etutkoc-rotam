"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Plus } from "lucide-react";

import { cn } from "@/lib/utils";
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
import { adminKeys, getAdminFeatureFlag } from "@/lib/api/admin";
import {
  useAddFeatureFlagOverride,
  useRemoveFeatureFlagOverride,
  useToggleFeatureFlag,
} from "@/lib/hooks/use-admin-mutations";
import type {
  FeatureFlagDetailResponse,
  FeatureFlagOverrideItem,
} from "@/lib/types/admin";

interface Props {
  initial: FeatureFlagDetailResponse;
  flagId: number;
}

/**
 * Flag detayı — Jinja `feature_flag_detail.html` feature parity.
 *
 * Global toggle kartı + override tablosu (sil) + override ekleme formu.
 */
export function AdminFeatureFlagDetailClient({ initial, flagId }: Props) {
  const q = useQuery<FeatureFlagDetailResponse>({
    queryKey: adminKeys.featureFlag(flagId),
    queryFn: () => getAdminFeatureFlag(flagId),
    initialData: initial,
    staleTime: 30_000,
  });
  const data = q.data ?? initial;

  return (
    <div className="space-y-5">
      <header>
        <Link
          href="/admin/feature-flags"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Özellik Anahtarları
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 font-mono">
          {data.key}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">{data.description}</p>
      </header>

      <GlobalToggleCard
        flagId={flagId}
        enabledGlobally={data.enabled_globally}
      />

      <OverridesCard overrides={data.overrides} />

      {data.available_institutions.length > 0 ? (
        <AddOverrideForm
          flagId={flagId}
          institutions={data.available_institutions}
        />
      ) : (
        <Card className="bg-muted/30">
          <CardContent className="p-4 text-sm text-muted-foreground italic text-center">
            Tüm kurumlar için zaten özel ayar mevcut. Yenisini eklemek için önce
            birini kaldır.
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function GlobalToggleCard({
  flagId,
  enabledGlobally,
}: {
  flagId: number;
  enabledGlobally: boolean;
}) {
  const router = useRouter();
  const mut = useToggleFeatureFlag(flagId);

  function doToggle() {
    mut.mutate(undefined, { onSuccess: () => router.refresh() });
  }

  return (
    <Card>
      <CardContent className="p-5 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-sm font-medium">Genel Durum (tüm kurumlar)</h2>
          <p className="text-xs text-muted-foreground mt-1">
            Bir kuruma özel ayar verilmediği sürece tüm kurumlar bunu kullanır.
          </p>
        </div>
        <Button
          onClick={doToggle}
          disabled={mut.isPending}
          className={cn(
            "font-medium border",
            enabledGlobally
              ? "bg-emerald-100 text-emerald-700 border-emerald-300 hover:bg-emerald-200"
              : "bg-rose-100 text-rose-700 border-rose-300 hover:bg-rose-200",
          )}
        >
          {mut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          {enabledGlobally
            ? "● Genel olarak AÇIK — kapatmak için tıkla"
            : "○ Genel olarak KAPALI — açmak için tıkla"}
        </Button>
      </CardContent>
    </Card>
  );
}

function OverridesCard({
  overrides,
}: {
  overrides: FeatureFlagOverrideItem[];
}) {
  return (
    <Card>
      <div className="px-4 py-3 border-b border-border bg-muted/40">
        <h2 className="text-sm font-medium">Kuruma Özel Ayarlar</h2>
      </div>
      {overrides.length === 0 ? (
        <p className="p-6 text-center text-sm text-muted-foreground italic">
          Henüz kuruma özel ayar yok. Tüm kurumlar yukarıdaki genel durumu
          kullanıyor.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/30 text-muted-foreground text-xs">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Kurum</th>
                <th className="text-left px-4 py-2 font-medium">Bu Kurumda</th>
                <th className="text-left px-4 py-2 font-medium">Not</th>
                <th className="text-right px-4 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {overrides.map((o) => (
                <OverrideRow key={o.id} override={o} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function OverrideRow({ override }: { override: FeatureFlagOverrideItem }) {
  const router = useRouter();
  const mut = useRemoveFeatureFlagOverride(override.id);
  const [open, setOpen] = React.useState(false);

  function doRemove() {
    mut.mutate(undefined, {
      onSuccess: () => {
        setOpen(false);
        router.refresh();
      },
    });
  }

  return (
    <tr>
      <td className="px-4 py-2">
        <Link
          href={`/admin/institutions/${override.institution_id}`}
          className="font-medium hover:text-indigo-600"
        >
          {override.institution_name}
        </Link>
      </td>
      <td className="px-4 py-2">
        {override.enabled ? (
          <span className="text-xs px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200">
            ● Açık
          </span>
        ) : (
          <span className="text-xs px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200 font-medium dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200">
            ○ Kapalı
          </span>
        )}
      </td>
      <td className="px-4 py-2 text-xs text-muted-foreground">
        {override.note ?? "—"}
      </td>
      <td className="px-4 py-2 text-right">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="text-xs text-rose-600 hover:text-rose-800"
        >
          Kaldır
        </button>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Özel Ayarı Kaldır</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              Bu kuruma özel ayar kaldırılsın mı?{" "}
              <strong>{override.institution_name}</strong> bundan sonra genel
              durumu kullanır.
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
                onClick={doRemove}
                disabled={mut.isPending}
                className="bg-rose-600 hover:bg-rose-700 text-white"
              >
                {mut.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : null}
                Kaldır
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </td>
    </tr>
  );
}

function AddOverrideForm({
  flagId,
  institutions,
}: {
  flagId: number;
  institutions: FeatureFlagDetailResponse["available_institutions"];
}) {
  const router = useRouter();
  const mut = useAddFeatureFlagOverride(flagId);
  const [instId, setInstId] = React.useState("");
  const [enabled, setEnabled] = React.useState("on");
  const [note, setNote] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!instId) return;
    mut.mutate(
      {
        institution_id: Number(instId),
        enabled: enabled === "on",
        note: note.trim() || null,
      },
      {
        onSuccess: () => {
          setInstId("");
          setNote("");
          setEnabled("on");
          router.refresh();
        },
      },
    );
  }

  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="text-sm font-medium mb-3 inline-flex items-center gap-1.5">
          <Plus className="size-4 text-indigo-700" aria-hidden />
          Bir Kuruma Özel Ayar Ver
        </h2>
        <form
          onSubmit={onSubmit}
          className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end"
        >
          <div>
            <Label htmlFor="ff-inst" className="text-xs uppercase tracking-wide">
              Kurum
            </Label>
            <select
              id="ff-inst"
              value={instId}
              onChange={(e) => setInstId(e.target.value)}
              required
              className="mt-1 w-full px-3 py-2 border border-input rounded text-sm bg-card"
            >
              <option value="">Seçin…</option>
              {institutions.map((i) => (
                <option key={i.id} value={String(i.id)}>
                  {i.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="ff-enabled" className="text-xs uppercase tracking-wide">
              Bu Kurumda Durum
            </Label>
            <select
              id="ff-enabled"
              value={enabled}
              onChange={(e) => setEnabled(e.target.value)}
              className="mt-1 w-full px-3 py-2 border border-input rounded text-sm bg-card"
            >
              <option value="on">Açık olsun</option>
              <option value="off">Kapalı olsun</option>
            </select>
          </div>
          <div>
            <Label htmlFor="ff-note" className="text-xs uppercase tracking-wide">
              Not (kendin için)
            </Label>
            <Input
              id="ff-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="örn: pilot deneme"
              className="mt-1"
            />
          </div>
          <Button
            type="submit"
            disabled={mut.isPending || !instId}
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
          >
            {mut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            Kaydet
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
