"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Building2,
  Clock,
  Loader2,
  ShieldOff,
  UserCircle2,
  Wallet,
} from "lucide-react";

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
import { adminKeys, getAdminUsage } from "@/lib/api/admin";
import {
  useAddBonus,
  useHardBlockToggle,
} from "@/lib/hooks/use-admin-mutations";
import type {
  AdminUsageResponse,
  UsageAccountInfo,
  UsageIndependentRow,
  UsageInstitutionRow,
} from "@/lib/types/admin";

interface Props {
  initial: AdminUsageResponse;
  initialTab: "institutions" | "independents";
}

/**
 * Sistem kullanımı — Jinja `usage_dashboard.html` feature parity.
 *
 * 4 özet kart + 2 sekme (kurumlar / bağımsız öğretmenler) + hard-block toggle
 * (sadece kurum) + bonus kredi ekleme (her ikisi).
 */
export function AdminUsageClient({ initial, initialTab }: Props) {
  const q = useQuery<AdminUsageResponse>({
    queryKey: adminKeys.usage(),
    queryFn: () => getAdminUsage(),
    initialData: initial,
    staleTime: 15_000,
  });
  const data = q.data ?? initial;
  const [tab, setTab] = React.useState(initialTab);

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
          <Wallet className="size-6 text-indigo-700" aria-hidden />
          Kredi Kullanımı — Sistem Geneli
        </h1>
        <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
          <span className="font-mono">{data.period}</span> ayı boyunca her kurum
          ve bağımsız öğretmenin yapay zeka, e-posta ve WhatsApp kullanımı.
        </p>
      </header>

      {/* Özet kartlar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard
          label="Toplam Kullanım"
          used={data.totals.grand_used}
          alloc={data.totals.grand_alloc}
          tone="default"
        />
        <SummaryCard
          label="Kurum Kullanımı"
          used={data.totals.inst_used}
          alloc={data.totals.inst_alloc}
          sub={`${data.inst_rows.length} kurum`}
          tone="indigo"
        />
        <SummaryCard
          label="Bağımsız Kullanım"
          used={data.totals.indep_used}
          alloc={data.totals.indep_alloc}
          sub={`${data.indep_rows.length} öğretmen`}
          tone="violet"
        />
        <Card>
          <CardContent className="p-4">
            <div className="text-[11px] text-muted-foreground uppercase tracking-wider">
              Her İşlem Kaç Kredi?
            </div>
            <div className="text-[11px] text-foreground/80 mt-1 leading-relaxed">
              {data.kind_costs.map((kc) => (
                <div key={kc.kind}>
                  {kc.label}: <strong>{kc.cost} kredi</strong>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-border">
        <button
          type="button"
          onClick={() => setTab("institutions")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 inline-flex items-center gap-1.5",
            tab === "institutions"
              ? "border-indigo-500 text-indigo-700"
              : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          <Building2 className="size-4" aria-hidden />
          Kurumlar ({data.inst_rows.length})
        </button>
        <button
          type="button"
          onClick={() => setTab("independents")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 inline-flex items-center gap-1.5",
            tab === "independents"
              ? "border-indigo-500 text-indigo-700"
              : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          <UserCircle2 className="size-4" aria-hidden />
          Bağımsız Öğretmenler ({data.indep_rows.length})
        </button>
      </div>

      {tab === "institutions" ? (
        <InstitutionsTable rows={data.inst_rows} />
      ) : (
        <IndependentsTable rows={data.indep_rows} />
      )}

      <div className="rounded-md border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
        💡 <strong>Tam durdurma</strong> yalnızca kurumlar için ve elle açıp
        kapatılır — kredi bittiğinde bile sistem çalışır. <strong>Bağımsız
        öğretmenler</strong> krediyi bitirince otomatik 5 saat cooldown&apos;a girer.
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  used,
  alloc,
  sub,
  tone,
}: {
  label: string;
  used: number;
  alloc: number;
  sub?: string;
  tone: "default" | "indigo" | "violet";
}) {
  const borderMap = {
    default: "border-border",
    indigo: "border-indigo-200",
    violet: "border-violet-200",
  };
  const textMap = {
    default: "text-foreground",
    indigo: "text-indigo-700",
    violet: "text-violet-700",
  };
  return (
    <Card className={cn("border", borderMap[tone])}>
      <CardContent className="p-4">
        <div className="text-[11px] text-muted-foreground uppercase tracking-wider">
          {label}
        </div>
        <div className={cn("text-2xl font-semibold tabular-nums mt-1", textMap[tone])}>
          {used}
        </div>
        <div className="text-[11px] text-muted-foreground mt-0.5">
          / {alloc} kredi{sub ? ` · ${sub}` : ""}
        </div>
      </CardContent>
    </Card>
  );
}

function UsageBar({ account }: { account: UsageAccountInfo }) {
  const pct = account.usage_pct;
  const barColor =
    pct >= 100 ? "bg-rose-500" : pct >= 80 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div>
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={cn("h-full", barColor)}
            style={{ width: `${Math.min(100, pct)}%` }}
          />
        </div>
        <span className="text-xs font-mono w-10 text-right tabular-nums">
          %{pct}
        </span>
      </div>
      <div className="text-[10px] text-muted-foreground mt-0.5">
        {account.used_credits} / {account.total_allocated}
        {account.bonus_credits > 0 && (
          <span className="text-violet-600"> (+{account.bonus_credits} bonus)</span>
        )}
      </div>
    </div>
  );
}

function RemainingCell({ account }: { account: UsageAccountInfo }) {
  const tone =
    account.usage_pct >= 100
      ? "text-rose-700 font-semibold"
      : account.usage_pct >= 80
        ? "text-amber-700 font-semibold"
        : "text-foreground/80";
  return <span className={cn("tabular-nums", tone)}>{account.remaining_credits}</span>;
}

function InstitutionsTable({ rows }: { rows: UsageInstitutionRow[] }) {
  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="p-12 text-center text-sm text-muted-foreground">
          Aktif kurum yok.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Kurum</th>
              <th className="text-left px-4 py-2 font-medium">Plan</th>
              <th className="text-left px-4 py-2 font-medium">Kullanım</th>
              <th className="text-right px-4 py-2 font-medium">Kalan</th>
              <th className="text-left px-4 py-2 font-medium">Tam Durdurma</th>
              <th className="text-right px-4 py-2 font-medium">İşlem</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <InstRow key={r.institution_id} row={r} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function InstRow({ row }: { row: UsageInstitutionRow }) {
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
        <span className="text-xs px-2 py-0.5 rounded bg-sky-50 text-sky-700 border border-sky-200 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200">
          {row.account.plan_code}
        </span>
      </td>
      <td className="px-4 py-2 w-48">
        <UsageBar account={row.account} />
      </td>
      <td className="px-4 py-2 text-right">
        <RemainingCell account={row.account} />
      </td>
      <td className="px-4 py-2">
        {row.account.hard_block_enabled ? (
          <span className="text-xs px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200 font-medium inline-flex items-center gap-0.5 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200">
            <ShieldOff className="size-3" aria-hidden />
            Erişim Kapalı
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">kapalı</span>
        )}
      </td>
      <td className="px-4 py-2 text-right">
        <InstActions
          institutionId={row.institution_id}
          hardBlocked={row.account.hard_block_enabled}
        />
      </td>
    </tr>
  );
}

function InstActions({
  institutionId,
  hardBlocked,
}: {
  institutionId: number;
  hardBlocked: boolean;
}) {
  const [blockOpen, setBlockOpen] = React.useState(false);
  const [bonusOpen, setBonusOpen] = React.useState(false);
  const blockMut = useHardBlockToggle(institutionId);
  const bonusMut = useAddBonus("institution", institutionId);
  const [bonus, setBonus] = React.useState("");

  function doBlock() {
    blockMut.mutate(undefined, { onSettled: () => setBlockOpen(false) });
  }
  function doBonus(e: React.FormEvent) {
    e.preventDefault();
    const n = Number(bonus);
    if (!Number.isFinite(n) || n <= 0) return;
    bonusMut.mutate(
      { bonus_amount: n },
      {
        onSuccess: () => {
          setBonus("");
          setBonusOpen(false);
        },
      },
    );
  }

  return (
    <div className="inline-flex items-center gap-1">
      <Button
        size="sm"
        variant="outline"
        onClick={() => setBlockOpen(true)}
        className={cn(
          "text-xs",
          hardBlocked
            ? "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
            : "border-rose-200 text-rose-700 hover:bg-rose-50",
        )}
      >
        {hardBlocked ? "Aç" : "Durdur"}
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => setBonusOpen(true)}
        className="text-xs border-violet-200 text-violet-700 hover:bg-violet-50"
      >
        +Bonus
      </Button>

      <Dialog open={blockOpen} onOpenChange={setBlockOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {hardBlocked ? "Erişimi Tekrar Aç" : "Erişimi Tamamen Durdur"}
            </DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {hardBlocked
              ? "Bu kurumun yapay zeka/e-posta/WhatsApp erişimi tekrar açılsın mı?"
              : "Bu kurumun yapay zeka, e-posta ve WhatsApp özellikleri tamamen durdurulsun mu? (Krediden bağımsız, sen tekrar açana kadar kapalı kalır.)"}
          </p>
          <DialogFooter className="gap-2 pt-2">
            <Button
              variant="ghost"
              onClick={() => setBlockOpen(false)}
              disabled={blockMut.isPending}
            >
              Vazgeç
            </Button>
            <Button
              onClick={doBlock}
              disabled={blockMut.isPending}
              className={
                hardBlocked
                  ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                  : "bg-rose-600 hover:bg-rose-700 text-white"
              }
            >
              {blockMut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              {hardBlocked ? "Aç" : "Durdur"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={bonusOpen} onOpenChange={setBonusOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bonus Kredi Ekle</DialogTitle>
          </DialogHeader>
          <form onSubmit={doBonus} className="space-y-3">
            <Input
              type="number"
              min={1}
              max={100000}
              value={bonus}
              onChange={(e) => setBonus(e.target.value)}
              placeholder="kredi miktarı (1-100000)"
              autoFocus
            />
            <DialogFooter className="gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setBonusOpen(false)}
                disabled={bonusMut.isPending}
              >
                Vazgeç
              </Button>
              <Button
                type="submit"
                disabled={bonusMut.isPending || !bonus}
                className="bg-violet-600 hover:bg-violet-700 text-white"
              >
                {bonusMut.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : null}
                Ekle
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function IndependentsTable({ rows }: { rows: UsageIndependentRow[] }) {
  if (rows.length === 0) {
    return (
      <Card>
        <CardContent className="p-12 text-center text-sm text-muted-foreground">
          Aktif bağımsız öğretmen yok.
        </CardContent>
      </Card>
    );
  }
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Öğretmen</th>
              <th className="text-left px-4 py-2 font-medium">Plan</th>
              <th className="text-left px-4 py-2 font-medium">Kullanım</th>
              <th className="text-right px-4 py-2 font-medium">Kalan</th>
              <th className="text-left px-4 py-2 font-medium">Bekleme</th>
              <th className="text-right px-4 py-2 font-medium">İşlem</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <IndepRow key={r.user_id} row={r} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function IndepRow({ row }: { row: UsageIndependentRow }) {
  return (
    <tr>
      <td className="px-4 py-2">
        <Link
          href={`/admin/users/${row.user_id}`}
          className="font-medium hover:text-indigo-600"
        >
          {row.full_name}
        </Link>
        <div className="text-[11px] text-muted-foreground font-mono">
          {row.email}
        </div>
      </td>
      <td className="px-4 py-2">
        <span className="text-xs px-2 py-0.5 rounded bg-violet-50 text-violet-700 border border-violet-200 dark:bg-violet-500/10 dark:border-violet-500/30 dark:text-violet-200">
          {row.account.plan_code}
        </span>
      </td>
      <td className="px-4 py-2 w-48">
        <UsageBar account={row.account} />
      </td>
      <td className="px-4 py-2 text-right">
        <RemainingCell account={row.account} />
      </td>
      <td className="px-4 py-2 text-xs">
        {row.account.blocked_until ? (
          <span className="text-rose-700 font-medium inline-flex items-center gap-0.5">
            <Clock className="size-3" aria-hidden />
            {formatDateTime(row.account.blocked_until)}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-2 text-right">
        <IndepBonus userId={row.user_id} />
      </td>
    </tr>
  );
}

function IndepBonus({ userId }: { userId: number }) {
  const mut = useAddBonus("user", userId);
  const [open, setOpen] = React.useState(false);
  const [bonus, setBonus] = React.useState("");

  function doBonus(e: React.FormEvent) {
    e.preventDefault();
    const n = Number(bonus);
    if (!Number.isFinite(n) || n <= 0) return;
    mut.mutate(
      { bonus_amount: n },
      {
        onSuccess: () => {
          setBonus("");
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
        +Bonus
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bonus Kredi Ekle</DialogTitle>
          </DialogHeader>
          <form onSubmit={doBonus} className="space-y-3">
            <Input
              type="number"
              min={1}
              max={100000}
              value={bonus}
              onChange={(e) => setBonus(e.target.value)}
              placeholder="kredi miktarı (1-100000)"
              autoFocus
            />
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
                disabled={mut.isPending || !bonus}
                className="bg-violet-600 hover:bg-violet-700 text-white"
              >
                {mut.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : null}
                Ekle
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm} ${hh}:${mn}'e kadar`;
}
