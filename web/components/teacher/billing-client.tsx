"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Loader2, Wallet } from "lucide-react";

import { getTeacherBilling, getTeacherStudentSessions, teacherKeys } from "@/lib/api/teacher";
import { useSetRate, useCreatePayment } from "@/lib/hooks/use-teacher-mutations";
import type {
  BillingMonthResponse,
  BillingStatus,
  BillingStudentRow,
} from "@/lib/types/teacher";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { DemoHint } from "@/components/demos/demo-hint";

const MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];

function monthLabel(m: string): string {
  const [y, mo] = m.split("-").map(Number);
  if (!y || !mo) return m;
  return `${MONTHS_TR[mo - 1]} ${y}`;
}
function addMonth(m: string, delta: number): string {
  const [y, mo] = m.split("-").map(Number);
  const d = new Date(y, mo - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function lira(n: number): string {
  return `₺${n.toLocaleString("tr-TR")}`;
}

const STATUS_META: Record<BillingStatus, { label: string; cls: string }> = {
  paid: { label: "Ödendi", cls: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200" },
  partial: { label: "Kısmi", cls: "border-amber-200 bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200" },
  pending: { label: "Bekliyor", cls: "border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200" },
  no_rate: { label: "Ücret yok", cls: "border-slate-200 bg-slate-50 text-slate-600 dark:bg-slate-500/10 dark:border-slate-500/30" },
};

export function BillingClient({
  initialMonth,
  initial,
}: {
  initialMonth: string;
  initial: BillingMonthResponse;
}) {
  const [month, setMonth] = React.useState(initialMonth);
  const q = useQuery<BillingMonthResponse>({
    queryKey: teacherKeys.billing(month),
    queryFn: () => getTeacherBilling(month),
    initialData: month === initialMonth ? initial : undefined,
    staleTime: 15_000,
  });
  const [rateFor, setRateFor] = React.useState<BillingStudentRow | null>(null);
  const [payFor, setPayFor] = React.useState<{ row: BillingStudentRow; preset: number } | null>(null);
  const [seansFor, setSeansFor] = React.useState<BillingStudentRow | null>(null);

  const d = q.data;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="inline-flex items-center gap-2 font-display text-2xl font-semibold tracking-tight">
            <Wallet className="size-6 text-cyan-700" aria-hidden /> Tahsilat
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Yapılan seans × ücret − ödenen = kalan alacak. Ertelenen/iptal seans sayılmaz.
          </p>
          <DemoHint contextKey="billing" role="teacher" className="mt-1.5" />
        </div>
        <div className="inline-flex items-center gap-1 rounded-lg border border-border bg-card p-1">
          <Button variant="ghost" size="icon" onClick={() => setMonth(addMonth(month, -1))} aria-label="Önceki ay">
            <ChevronLeft className="size-4" aria-hidden />
          </Button>
          <span className="min-w-[120px] text-center text-sm font-semibold">{monthLabel(month)}</span>
          <Button variant="ghost" size="icon" onClick={() => setMonth(addMonth(month, 1))} aria-label="Sonraki ay">
            <ChevronRight className="size-4" aria-hidden />
          </Button>
        </div>
      </header>

      {d ? (
        <section className="grid grid-cols-3 gap-3">
          <Stat label="Bu ay tahakkuk" value={lira(d.totals.accrued)} />
          <Stat label="Tahsil edilen" value={lira(d.totals.paid)} tone="good" />
          <Stat label="Kalan alacak" value={lira(d.totals.balance)} tone={d.totals.balance > 0 ? "warn" : undefined} />
        </section>
      ) : null}

      <Card className="overflow-hidden">
        {q.isLoading && !d ? (
          <p className="p-6 text-sm text-muted-foreground">Yükleniyor…</p>
        ) : !d || d.rows.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Aktif öğrenci yok.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-[11px] uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Öğrenci</th>
                  <th className="px-3 py-2 text-right">Seans</th>
                  <th className="px-3 py-2 text-right">Ücret</th>
                  <th className="px-3 py-2 text-right">Tahakkuk</th>
                  <th className="px-3 py-2 text-right">Ödenen</th>
                  <th className="px-3 py-2 text-right">Kalan</th>
                  <th className="px-3 py-2 text-left">Durum</th>
                  <th className="px-3 py-2 text-right">İşlem</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.rows.map((r) => (
                  <tr key={r.student_id} className="hover:bg-muted/30">
                    <td className="px-3 py-2 font-medium">
                      {r.student_name}
                      {r.is_active === false && (
                        <span className="ml-1.5 inline-flex rounded border border-slate-300 bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-300">
                          pasif
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      <button
                        type="button"
                        onClick={() => setSeansFor(r)}
                        className="rounded px-1.5 py-0.5 hover:bg-muted underline-offset-2 hover:underline"
                        title="Yapılan seans günlerini gör"
                      >
                        {r.done_sessions}
                      </button>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      <button
                        type="button"
                        onClick={() => setRateFor(r)}
                        className={cn("rounded px-1.5 py-0.5 hover:bg-muted", r.session_fee == null && "text-cyan-700 underline underline-offset-2")}
                      >
                        {r.session_fee != null ? lira(r.session_fee) : "Ücret belirle"}
                      </button>
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{r.accrued != null ? lira(r.accrued) : "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-emerald-700">{r.paid > 0 ? lira(r.paid) : "—"}</td>
                    <td className={cn("px-3 py-2 text-right font-semibold tabular-nums", r.balance && r.balance > 0 ? "text-rose-700" : "")}>
                      {r.balance != null ? lira(r.balance) : "—"}
                    </td>
                    <td className="px-3 py-2">
                      <span className={cn("inline-flex rounded border px-1.5 py-0.5 text-[10px] font-bold", STATUS_META[r.status].cls)}>
                        {STATUS_META[r.status].label}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      {r.session_fee == null ? (
                        <Button variant="ghost" size="sm" className="text-xs" onClick={() => setRateFor(r)}>Ücret</Button>
                      ) : (
                        <div className="inline-flex gap-1">
                          <Button variant="ghost" size="sm" className="text-xs" onClick={() => setPayFor({ row: r, preset: 0 })}>Ödeme</Button>
                          {r.balance != null && r.balance > 0 ? (
                            <Button variant="outline" size="sm" className="text-xs" onClick={() => setPayFor({ row: r, preset: r.balance ?? 0 })}>Ayı kapat</Button>
                          ) : null}
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="text-[11px] leading-relaxed text-muted-foreground">
        Tahsilat kayıtları yalnızca size özeldir. Ödeme genelde elden/nakit alınır; burada
        yalnız kayıt + hatırlatma tutulur (online tahsilat yok).
      </p>

      {rateFor ? (
        <RateDialog row={rateFor} onClose={() => setRateFor(null)} />
      ) : null}
      {payFor ? (
        <PaymentDialog row={payFor.row} preset={payFor.preset} month={month} onClose={() => setPayFor(null)} />
      ) : null}
      {seansFor ? (
        <SessionDetailDialog row={seansFor} month={month} onClose={() => setSeansFor(null)} />
      ) : null}
    </div>
  );
}

const SESSION_TONE: Record<string, string> = {
  done: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:border-emerald-500/30 dark:text-emerald-200",
  postponed: "border-amber-200 bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:border-amber-500/30 dark:text-amber-200",
  cancelled: "border-slate-200 bg-slate-100 text-slate-600 dark:bg-slate-500/10 dark:border-slate-500/30 dark:text-slate-300",
  no_show: "border-rose-200 bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:border-rose-500/30 dark:text-rose-200",
};

function fmtDate(iso: string): string {
  const [y, m, dd] = iso.split("-").map(Number);
  if (!y) return iso;
  return `${String(dd).padStart(2, "0")}.${String(m).padStart(2, "0")}.${y}`;
}

function SessionDetailDialog({ row, month, onClose }: { row: BillingStudentRow; month: string; onClose: () => void }) {
  const q = useQuery({
    queryKey: teacherKeys.studentSessions(row.student_id),
    queryFn: () => getTeacherStudentSessions(row.student_id),
    staleTime: 15_000,
  });
  const all = q.data?.rows ?? [];
  const monthRows = all
    .filter((s) => s.session_date.startsWith(month))
    .sort((a, b) => a.session_date.localeCompare(b.session_date));
  const doneCount = monthRows.filter((s) => s.status === "done").length;

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{row.student_name} — {monthLabel(month)} seansları</DialogTitle>
        </DialogHeader>
        {q.isLoading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> Yükleniyor…
          </div>
        ) : monthRows.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Bu ay kayıtlı seans yok.</p>
        ) : (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              <b className="text-emerald-700 dark:text-emerald-300">{doneCount}</b> yapılan seans tahakkuka sayılır
              {row.session_fee != null ? ` (${doneCount} × ${lira(row.session_fee)} = ${lira(doneCount * row.session_fee)})` : ""}.
            </p>
            <ul className="divide-y divide-border rounded-lg border border-border">
              {monthRows.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                  <div className="min-w-0">
                    <span className="font-medium tabular-nums">{fmtDate(s.session_date)}</span>
                    {s.channel_label ? <span className="ml-2 text-xs text-muted-foreground">{s.channel_label}</span> : null}
                    {s.duration_min ? <span className="ml-1 text-xs text-muted-foreground">· {s.duration_min} dk</span> : null}
                    {s.agenda ? <span className="block truncate text-xs text-muted-foreground">{s.agenda}</span> : null}
                  </div>
                  <span className={cn("shrink-0 inline-flex rounded border px-1.5 py-0.5 text-[10px] font-bold", SESSION_TONE[s.status] ?? SESSION_TONE.cancelled)}>
                    {s.status_label}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" }) {
  return (
    <Card>
      <CardContent className="space-y-1 p-4">
        <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={cn("text-2xl font-bold tabular-nums", tone === "good" && "text-emerald-600", tone === "warn" && "text-rose-600")}>{value}</p>
      </CardContent>
    </Card>
  );
}

function RateDialog({ row, onClose }: { row: BillingStudentRow; onClose: () => void }) {
  const mut = useSetRate(row.student_id);
  const [fee, setFee] = React.useState(row.session_fee != null ? String(row.session_fee) : "");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = Number(fee);
    if (!Number.isFinite(v) || v < 0) return;
    mut.mutate({ sessionFee: v }, { onSuccess: () => onClose() });
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{row.student_name} — seans ücreti</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="fee">Seans başına ücret (₺)</Label>
            <Input id="fee" type="number" min={0} value={fee} onChange={(e) => setFee(e.target.value)} placeholder="örn. 2500" autoFocus />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={onClose} disabled={mut.isPending}>İptal</Button>
            <Button type="submit" disabled={mut.isPending || fee === ""}>
              {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null} Kaydet
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PaymentDialog({
  row,
  preset,
  month,
  onClose,
}: {
  row: BillingStudentRow;
  preset: number;
  month: string;
  onClose: () => void;
}) {
  const mut = useCreatePayment(row.student_id);
  const [amount, setAmount] = React.useState(preset > 0 ? String(preset) : "");
  const [paidAt, setPaidAt] = React.useState(new Date().toISOString().slice(0, 10));
  const [method, setMethod] = React.useState<"cash" | "transfer" | "other">("cash");
  const [note, setNote] = React.useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const v = Number(amount);
    if (!Number.isFinite(v) || v <= 0) return;
    mut.mutate(
      { body: { amount: v, paid_at: paidAt, method, period_month: month, note: note.trim() || null } },
      { onSuccess: () => onClose() },
    );
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{row.student_name} — ödeme gir ({monthLabel(month)})</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="amt">Tutar (₺)</Label>
              <Input id="amt" type="number" min={1} value={amount} onChange={(e) => setAmount(e.target.value)} autoFocus />
            </div>
            <div className="space-y-1">
              <Label htmlFor="pdate">Tarih</Label>
              <Input id="pdate" type="date" value={paidAt} onChange={(e) => setPaidAt(e.target.value)} />
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="pmethod">Yöntem</Label>
            <select id="pmethod" value={method} onChange={(e) => setMethod(e.target.value as "cash" | "transfer" | "other")}
              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <option value="cash">Nakit / elden</option>
              <option value="transfer">Havale / EFT</option>
              <option value="other">Diğer</option>
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="pnote">Not (ops.)</Label>
            <Input id="pnote" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          {row.balance != null && row.balance > 0 ? (
            <p className="text-xs text-muted-foreground">Bu ay kalan: <b className="text-rose-700">{lira(row.balance)}</b></p>
          ) : null}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" onClick={onClose} disabled={mut.isPending}>İptal</Button>
            <Button type="submit" disabled={mut.isPending || amount === ""}>
              {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null} Kaydet
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
