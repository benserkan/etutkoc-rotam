"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Info,
  Loader2,
  Mail,
  Send,
  SkipForward,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  getInstitutionAdminDigests,
  institutionKeys,
} from "@/lib/api/institution";
import { useSendAdminDigestNow } from "@/lib/hooks/use-institution-mutations";
import type {
  AdminDigestListResponse,
  AdminDigestStatus,
  AdminDigestSummary,
} from "@/lib/types/institution";

interface Props {
  initial: AdminDigestListResponse;
}

/**
 * Admin haftalık özet arşivi — Jinja `admin_digest_list.html` ile birebir.
 *
 * "Şimdi gönder" force=True tetikler (mevcut hafta için yeniden gönderim).
 * Otomatik gönderim Pazartesi 12:00 TR; bu sayfada açıklanır.
 */
export function AdminDigestListClient({ initial }: Props) {
  const q = useQuery<AdminDigestListResponse>({
    queryKey: institutionKeys.adminDigests(),
    queryFn: () => getInstitutionAdminDigests(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const { institution, items } = data;
  const [confirmOpen, setConfirmOpen] = React.useState(false);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link
            href="/institution"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Panel
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1 flex items-center gap-2">
            <Mail className="size-6 text-emerald-700" aria-hidden />
            Haftalık Yönetici Özeti
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            {institution.name} kurumunda her hafta öğretmen ve öğrenci
            performans özeti otomatik olarak yöneticilere e-posta ile
            gönderilir. Aşağıda son 12 haftanın arşivi var.
          </p>
        </div>
        <Button onClick={() => setConfirmOpen(true)}>
          <Send className="size-4" aria-hidden />
          Şimdi Gönder
        </Button>
      </header>

      <AutoSendNote />

      {items.length === 0 ? <EmptyState /> : <DigestTable items={items} />}

      <SendNowConfirm
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
      />
    </div>
  );
}

function AutoSendNote() {
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50 text-sky-900 px-3 py-2.5 text-xs flex items-start gap-2 dark:bg-sky-500/10 dark:border-sky-500/30 dark:text-sky-200">
      <Info className="size-4 shrink-0 mt-0.5" aria-hidden />
      <div>
        <strong>Otomatik gönderim:</strong> Her Pazartesi öğlen saat 12:00&apos;de
        (Türkiye saatiyle) tüm aktif yöneticilere e-posta gönderilir. Aynı
        haftaya tekrar otomatik gönderim yapılmaz; ama &ldquo;Şimdi
        Gönder&rdquo; tuşuyla sen tekrar tetikleyebilirsin. Eğer e-posta
        servisi devre dışıysa, özet kayıt edilir ama e-posta atılmaz — bu
        sayfada &ldquo;log-only&rdquo; olarak görünür.
      </div>
    </div>
  );
}

function DigestTable({ items }: { items: AdminDigestSummary[] }) {
  return (
    <Card>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-2 font-medium">Hafta</th>
              <th className="text-left px-4 py-2 font-medium">Durum</th>
              <th className="text-right px-4 py-2 font-medium">Alıcı</th>
              <th className="text-left px-4 py-2 font-medium">
                Gönderim Zamanı
              </th>
              <th className="text-right px-4 py-2 font-medium">
                <span className="sr-only">Detay</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((d) => (
              <DigestRow key={d.id} digest={d} />
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function DigestRow({ digest }: { digest: AdminDigestSummary }) {
  return (
    <tr>
      <td className="px-4 py-2">
        <div className="font-medium">
          {formatRange(digest.week_start_date, digest.week_end_date)}
        </div>
      </td>
      <td className="px-4 py-2">
        <SendStatusLabel status={digest.send_status} />
        {digest.error_message ? (
          <div
            className="text-[10px] text-muted-foreground mt-0.5 truncate max-w-[260px]"
            title={digest.error_message}
          >
            {digest.error_message.slice(0, 80)}
          </div>
        ) : null}
      </td>
      <td className="px-4 py-2 text-right tabular-nums">
        {digest.recipient_count}
      </td>
      <td className="px-4 py-2 text-xs text-muted-foreground">
        {digest.sent_at ? formatDateTime(digest.sent_at) : "—"}
      </td>
      <td className="px-4 py-2 text-right whitespace-nowrap">
        <Link
          href={`/institution/admin-digest/${digest.id}`}
          className="text-xs text-accent hover:underline"
        >
          Detay →
        </Link>
      </td>
    </tr>
  );
}

export function SendStatusLabel({ status }: { status: AdminDigestStatus }) {
  switch (status) {
    case "sent":
      return (
        <span className="text-emerald-700 font-medium inline-flex items-center gap-1">
          <CheckCircle2 className="size-3.5" aria-hidden />
          Gönderildi
        </span>
      );
    case "log_only":
      return (
        <span
          className="text-muted-foreground inline-flex items-center gap-1"
          title="E-posta servisi kapalı olduğu için sadece kayıt tutuldu"
        >
          <FileText className="size-3.5" aria-hidden />
          Sadece kayıt
        </span>
      );
    case "failed":
      return (
        <span className="text-rose-700 font-medium inline-flex items-center gap-1">
          <AlertTriangle className="size-3.5" aria-hidden />
          Gönderilemedi
        </span>
      );
    case "skipped_no_admin":
      return (
        <span
          className="text-amber-700 inline-flex items-center gap-1"
          title="Bu kurumda alıcı yönetici yok"
        >
          <SkipForward className="size-3.5" aria-hidden />
          Yönetici tanımsız
        </span>
      );
    default:
      return <span className="text-muted-foreground">{status}</span>;
  }
}

function EmptyState() {
  return (
    <Card>
      <div className="p-12 text-center">
        <Mail
          className="size-12 mx-auto text-muted-foreground mb-3"
          aria-hidden
        />
        <h2 className="text-lg font-semibold mb-1">Henüz özet üretilmedi</h2>
        <p className="text-sm text-muted-foreground">
          İlk özet bir sonraki Pazartesi otomatik gelecek; ya da &ldquo;Şimdi
          Gönder&rdquo; ile şimdiden tetikleyebilirsin.
        </p>
      </div>
    </Card>
  );
}

function SendNowConfirm({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const mut = useSendAdminDigestNow();
  function confirm() {
    mut.mutate(undefined, {
      onSuccess: () => onOpenChange(false),
      onError: () => onOpenChange(false),
    });
  }
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Haftalık özeti şimdi gönder</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Bu haftaki özet hemen yöneticilere e-posta ile gönderilsin mi? (Daha
          önce gönderildiyse yeniden gönderilir.)
        </p>
        <DialogFooter className="gap-2 pt-2">
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={mut.isPending}
          >
            Vazgeç
          </Button>
          <Button onClick={confirm} disabled={mut.isPending}>
            {mut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : (
              <Send className="size-4" aria-hidden />
            )}
            Şimdi Gönder
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function formatDayShort(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}.${mm}`;
}

export function formatDayFull(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

export function formatRange(startIso: string, endIso: string): string {
  return `${formatDayShort(startIso)} – ${formatDayFull(endIso)}`;
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  const hh = String(d.getHours()).padStart(2, "0");
  const mn = String(d.getMinutes()).padStart(2, "0");
  return `${dd}.${mm}.${yyyy} ${hh}:${mn}`;
}
