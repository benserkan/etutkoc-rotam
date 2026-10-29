"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Gauge, Loader2, Sparkles } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { adminKeys, getAdminQuota } from "@/lib/api/admin";
import { useSetQuotaOverride } from "@/lib/hooks/use-admin-mutations";
import type {
  AdminQuotaResponse,
  QuotaCell,
  QuotaInstitutionRow,
} from "@/lib/types/admin";

interface Props {
  initial: AdminQuotaResponse;
}

/**
 * Kurum limitleri — Jinja `quota_dashboard.html` feature parity.
 *
 * Kurum × quota_key tablosu (current/limit + progress + override badge) +
 * "Özel Limit Ver" dialog + plan default karşılaştırma tablosu.
 */
export function AdminQuotaClient({ initial }: Props) {
  const q = useQuery<AdminQuotaResponse>({
    queryKey: adminKeys.quota(),
    queryFn: () => getAdminQuota(),
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
          <Gauge className="size-6 text-indigo-700" aria-hidden />
          Kurum Limitleri
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          Hangi kurumda kaç öğretmen, öğrenci, yönetici olabilir? Mevcut sayılar
          + plana göre üst sınır. Bir kuruma özel sınır vermek için &ldquo;Özel
          Limit&rdquo; ekleyebilirsin.
        </p>
      </header>

      {data.rows.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center text-sm text-muted-foreground">
            Aktif kurum yok.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Kurum</th>
                  <th className="text-left px-4 py-2 font-medium">Plan</th>
                  {data.quota_keys.map((k) => (
                    <th key={k} className="text-left px-4 py-2 font-medium">
                      {data.quota_labels[k] ?? k}
                    </th>
                  ))}
                  <th className="text-right px-4 py-2 font-medium">İşlem</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.rows.map((r) => (
                  <QuotaRow
                    key={r.institution_id}
                    row={r}
                    quotaKeys={data.quota_keys}
                    quotaLabels={data.quota_labels}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <PlanDefaults
        plans={data.plans}
        quotaKeys={data.quota_keys}
        quotaLabels={data.quota_labels}
      />
    </div>
  );
}

function QuotaRow({
  row,
  quotaKeys,
  quotaLabels,
}: {
  row: QuotaInstitutionRow;
  quotaKeys: string[];
  quotaLabels: Record<string, string>;
}) {
  return (
    <tr>
      <td className="px-4 py-2">
        <Link
          href={`/admin/institutions/${row.institution_id}`}
          className="font-medium hover:text-indigo-600"
        >
          {row.name}
        </Link>
        <div className="text-[11px] text-muted-foreground font-mono">
          {row.slug}
        </div>
      </td>
      <td className="px-4 py-2">
        <span className="text-xs px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200">
          {row.plan}
        </span>
      </td>
      {row.cells.map((c) => (
        <td key={c.key} className="px-4 py-2 text-xs">
          <QuotaCellView cell={c} />
        </td>
      ))}
      <td className="px-4 py-2 text-right">
        <SetOverrideButton
          institutionId={row.institution_id}
          institutionName={row.name}
          quotaKeys={quotaKeys}
          quotaLabels={quotaLabels}
        />
      </td>
    </tr>
  );
}

function QuotaCellView({ cell }: { cell: QuotaCell }) {
  return (
    <div className="flex items-center gap-2">
      {cell.is_unlimited ? (
        <span className="font-mono text-foreground/80">
          {cell.current} / <strong>∞</strong>
        </span>
      ) : cell.limit === 0 ? (
        <span className="font-mono text-rose-700">
          {cell.current} / <strong>KAPALI</strong>
        </span>
      ) : (
        <>
          <span
            className={cn(
              "font-mono",
              cell.is_at_limit
                ? "text-rose-700 font-bold"
                : cell.pct >= 80
                  ? "text-amber-700 font-semibold"
                  : "text-foreground/80",
            )}
          >
            {cell.current} / {cell.limit}
          </span>
          <div className="w-12 h-1 bg-muted rounded">
            <div
              className={cn(
                "h-full",
                cell.is_at_limit
                  ? "bg-rose-500"
                  : cell.pct >= 80
                    ? "bg-amber-500"
                    : "bg-emerald-500",
              )}
              style={{ width: `${Math.min(100, cell.pct)}%` }}
            />
          </div>
        </>
      )}
      {cell.has_override && (
        <span
          className="text-[9px] px-1 rounded bg-violet-50 text-violet-700 border border-violet-200"
          title={cell.note ?? "Bu kuruma özel limit verilmiş"}
        >
          özel
        </span>
      )}
    </div>
  );
}

function SetOverrideButton({
  institutionId,
  institutionName,
  quotaKeys,
  quotaLabels,
}: {
  institutionId: number;
  institutionName: string;
  quotaKeys: string[];
  quotaLabels: Record<string, string>;
}) {
  const mut = useSetQuotaOverride(institutionId);
  const [open, setOpen] = React.useState(false);
  const [quotaKey, setQuotaKey] = React.useState(quotaKeys[0] ?? "");
  const [value, setValue] = React.useState("");
  const [note, setNote] = React.useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const n = Number(value);
    if (!Number.isFinite(n)) return;
    mut.mutate(
      { quota_key: quotaKey, override_value: n, note: note.trim() || null },
      {
        onSuccess: () => {
          setValue("");
          setNote("");
          setOpen(false);
        },
      },
    );
  }

  return (
    <>
      <Button
        size="sm"
        variant="outline"
        onClick={() => setOpen(true)}
        className="text-xs border-violet-200 text-violet-700 hover:bg-violet-50"
      >
        <Sparkles className="size-3" aria-hidden />
        Özel Limit
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{institutionName} — Özel Limit</DialogTitle>
          </DialogHeader>
          <form onSubmit={onSubmit} className="space-y-3">
            <div>
              <label className="text-xs font-medium block mb-1">
                Kuota türü
              </label>
              <select
                value={quotaKey}
                onChange={(e) => setQuotaKey(e.target.value)}
                className="w-full px-3 py-2 border border-input rounded text-sm bg-card"
              >
                {quotaKeys.map((k) => (
                  <option key={k} value={k}>
                    {quotaLabels[k] ?? k}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium block mb-1">
                Limit değeri
              </label>
              <Input
                type="number"
                min={-1}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="örn 50"
                required
              />
              <p className="text-[10px] text-muted-foreground mt-1">
                <strong>50</strong>: en fazla 50. <strong>-1</strong>: sınırsız.{" "}
                <strong>0</strong>: hiç eklenemez.
              </p>
            </div>
            <div>
              <label className="text-xs font-medium block mb-1">
                Not (opsiyonel)
              </label>
              <Input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="örn: pilot dönem"
                maxLength={255}
              />
            </div>
            <DialogFooter className="gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setOpen(false)}
                disabled={mut.isPending}
              >
                Vazgeç
              </Button>
              <Button
                type="submit"
                disabled={mut.isPending || value === ""}
                className="bg-violet-600 hover:bg-violet-700 text-white"
              >
                {mut.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : null}
                Kaydet
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function PlanDefaults({
  plans,
  quotaKeys,
  quotaLabels,
}: {
  plans: AdminQuotaResponse["plans"];
  quotaKeys: string[];
  quotaLabels: Record<string, string>;
}) {
  function valueFor(plan: AdminQuotaResponse["plans"][number], key: string) {
    const v = plan[key as keyof typeof plan];
    if (typeof v !== "number") return "—";
    if (v === -1) return "∞";
    if (v === 0) return "—";
    return String(v);
  }
  return (
    <Card className="bg-muted/30">
      <CardContent className="p-4">
        <div className="text-xs font-medium mb-2">
          Plana göre standart limitler (özel ayar yoksa geçerli):
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="text-muted-foreground">
              <th className="text-left py-1">Plan</th>
              {quotaKeys.map((k) => (
                <th key={k} className="text-right py-1">
                  {quotaLabels[k] ?? k}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {plans.map((p) => (
              <tr key={p.plan} className="border-t border-border">
                <td className="py-1 font-mono capitalize">{p.plan}</td>
                {quotaKeys.map((k) => (
                  <td key={k} className="py-1 text-right font-mono">
                    {valueFor(p, k)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
