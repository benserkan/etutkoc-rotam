"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Check, Copy, Loader2, Plus, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getInstitutionInvitations,
  institutionKeys,
} from "@/lib/api/institution";
import {
  useCreateInstitutionInvitation,
  useRevokeInstitutionInvitation,
} from "@/lib/hooks/use-institution-mutations";
import type {
  InvitationItem,
  InvitationListResponse,
  InvitationStatus,
} from "@/lib/types/institution";

interface Props {
  initial: InvitationListResponse;
}

/**
 * Davetiye yönetimi — Jinja `invitations.html` ile birebir.
 *
 * Akış:
 *   - "+ Yeni Davetiye" dialog (ad+email opsiyonel)
 *   - Tablo: durum rozetleri, copy link, iptal et
 *   - Güvenlik notu (violet) sabit
 *   - Pending olmayan satırlar silikleştirilir
 *   - 7 gün geçerlilik notu modal'da ve header'da
 */
export function InvitationsClient({ initial }: Props) {
  const q = useQuery<InvitationListResponse>({
    queryKey: institutionKeys.invitations(),
    queryFn: () => getInstitutionInvitations(),
    initialData: initial,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
  const data = q.data ?? initial;
  const { institution, items } = data;
  const [createOpen, setCreateOpen] = React.useState(false);
  const [revokeTarget, setRevokeTarget] =
    React.useState<InvitationItem | null>(null);

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
          <h1 className="text-2xl font-semibold tracking-tight font-display mt-1">
            Davetiyeler
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {institution.name} — kurumuna öğretmen davet et. Link{" "}
            <strong>7 gün</strong> geçerli ve tek seferlik.
          </p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" aria-hidden />
          Yeni Davetiye
        </Button>
      </header>

      <SecurityNote />

      {items.length === 0 ? (
        <Card>
          <div className="p-12 text-center text-sm text-muted-foreground">
            Henüz davetiye yok. Sağ üstten oluştur.
          </div>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Alıcı</th>
                  <th className="text-left px-4 py-2 font-medium">Durum</th>
                  <th className="text-left px-4 py-2 font-medium">
                    Oluşturuldu
                  </th>
                  <th className="text-left px-4 py-2 font-medium">
                    Geçerlilik
                  </th>
                  <th className="text-left px-4 py-2 font-medium">Link</th>
                  <th className="text-right px-4 py-2 font-medium">
                    <span className="sr-only">Eylem</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((inv) => (
                  <InvitationRow
                    key={inv.id}
                    inv={inv}
                    onRevoke={() => setRevokeTarget(inv)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <NewInvitationDialog open={createOpen} onOpenChange={setCreateOpen} />

      <RevokeConfirmDialog
        target={revokeTarget}
        onClose={() => setRevokeTarget(null)}
      />
    </div>
  );
}

function SecurityNote() {
  return (
    <div className="rounded-md border border-violet-200 bg-violet-50 text-violet-900 px-3 py-2.5 text-xs flex items-start gap-2">
      <ShieldAlert className="size-4 shrink-0 mt-0.5" aria-hidden />
      <div>
        <strong>🔐 Güvenlik:</strong> Davetiye linki paylaşmadan önce alıcının
        doğru kişi olduğundan emin ol. Linki olan herkes hesap oluşturabilir;
        e-posta belirtildiyse o adres kilitlenir. Yanlış paylaşımda{" "}
        <strong>iptal et</strong> butonunu kullan.
      </div>
    </div>
  );
}

function InvitationRow({
  inv,
  onRevoke,
}: {
  inv: InvitationItem;
  onRevoke: () => void;
}) {
  const isPending = inv.status === "pending";
  return (
    <tr className={cn(!isPending && "bg-muted/30 text-muted-foreground")}>
      <td className="px-4 py-2">
        {inv.full_name ? (
          <div className="font-medium">{inv.full_name}</div>
        ) : null}
        {inv.email ? (
          <div className="text-[11px] text-muted-foreground font-mono">
            {inv.email}
          </div>
        ) : (
          <span className="text-[11px] text-muted-foreground italic">
            açık davetiye
          </span>
        )}
      </td>
      <td className="px-4 py-2">
        <StatusBadge status={inv.status} />
      </td>
      <td className="px-4 py-2 text-xs text-muted-foreground">
        {formatDate(inv.created_at)}
      </td>
      <td className="px-4 py-2 text-xs text-muted-foreground">
        {formatDate(inv.expires_at)}
      </td>
      <td className="px-4 py-2">
        {isPending ? (
          <LinkCopyControl url={inv.signup_url} />
        ) : (
          <span className="text-[11px] text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-2 text-right whitespace-nowrap">
        {isPending && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRevoke}
            className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
          >
            İptal et
          </Button>
        )}
      </td>
    </tr>
  );
}

function StatusBadge({ status }: { status: InvitationStatus }) {
  const cfg: Record<
    InvitationStatus,
    { label: string; cls: string; icon: string }
  > = {
    pending: {
      label: "bekliyor",
      cls: "bg-amber-100 text-amber-800 border-amber-200",
      icon: "⏳",
    },
    consumed: {
      label: "kullanıldı",
      cls: "bg-emerald-100 text-emerald-800 border-emerald-200",
      icon: "✓",
    },
    expired: {
      label: "süresi geçti",
      cls: "bg-muted text-foreground/70 border-border",
      icon: "",
    },
    revoked: {
      label: "iptal",
      cls: "bg-rose-100 text-rose-800 border-rose-200",
      icon: "",
    },
  };
  const c = cfg[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded border font-medium",
        c.cls,
      )}
    >
      {c.icon ? <span aria-hidden>{c.icon}</span> : null}
      {c.label}
    </span>
  );
}

function LinkCopyControl({ url }: { url: string }) {
  const [copied, setCopied] = React.useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success("Davetiye linki kopyalandı.");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Kopyalama başarısız", {
        description: "Linki manuel olarak seçip kopyalayın.",
      });
    }
  }

  return (
    <div className="flex items-center gap-1">
      <input
        type="text"
        readOnly
        value={url}
        onClick={(e) => (e.currentTarget as HTMLInputElement).select()}
        className="text-[11px] font-mono px-2 py-1 border border-border rounded bg-muted/40 w-64 truncate"
      />
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={copy}
        aria-label="Linki kopyala"
      >
        {copied ? (
          <Check className="size-3.5 text-emerald-600" aria-hidden />
        ) : (
          <Copy className="size-3.5" aria-hidden />
        )}
        {copied ? "Kopyalandı" : "Kopyala"}
      </Button>
    </div>
  );
}

function NewInvitationDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const mut = useCreateInstitutionInvitation();
  const [fullName, setFullName] = React.useState("");
  const [email, setEmail] = React.useState("");

  React.useEffect(() => {
    if (!open) {
      const t = setTimeout(() => {
        setFullName("");
        setEmail("");
        mut.reset();
      }, 200);
      return () => clearTimeout(t);
    }
  }, [open, mut]);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    mut.mutate(
      {
        full_name: fullName.trim() || null,
        email: email.trim().toLowerCase() || null,
      },
      {
        onSuccess: () => onOpenChange(false),
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Yeni Öğretmen Davetiyesi</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="inv-name">Ad Soyad</Label>
            <Input
              id="inv-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Öğretmenin tam adı (opsiyonel)"
              autoFocus
            />
            <p className="text-[11px] text-muted-foreground">
              Opsiyonel — formda ön-doldurulur, kullanıcı düzenleyebilir.
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="inv-email">E-posta</Label>
            <Input
              id="inv-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="ornek@okul.tr (opsiyonel)"
            />
            <p className="text-[11px] text-muted-foreground">
              Doluysa kayıt sırasında değiştirilemez. Boş bırakırsan link
              &ldquo;açık davetiye&rdquo; olur — alıcı kendi e-postasıyla
              kayıt olur.
            </p>
          </div>
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs text-amber-900">
            <strong>📨 Davetiye linki:</strong> oluşturulduktan sonra tabloda
            görünür. Linki <strong>kendin alıcıya iletmelisin</strong> —
            sistem henüz e-posta göndermiyor. Link <strong>7 gün</strong>{" "}
            geçerli, tek seferlik.
          </div>
          <DialogFooter className="gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={mut.isPending}
            >
              İptal
            </Button>
            <Button type="submit" disabled={mut.isPending}>
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : null}
              Oluştur
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RevokeConfirmDialog({
  target,
  onClose,
}: {
  target: InvitationItem | null;
  onClose: () => void;
}) {
  const mut = useRevokeInstitutionInvitation();
  const open = target !== null;

  function confirm() {
    if (!target) return;
    mut.mutate(target.id, {
      onSuccess: () => onClose(),
      onError: () => onClose(),
    });
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Davetiyeyi iptal et</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Davetiye iptal edilsin mi? Link kullanılamaz hale gelir.
        </p>
        {target?.email ? (
          <div className="text-xs text-muted-foreground font-mono">
            {target.email}
          </div>
        ) : null}
        <DialogFooter className="gap-2 pt-2">
          <Button
            variant="ghost"
            onClick={onClose}
            disabled={mut.isPending}
          >
            Vazgeç
          </Button>
          <Button
            variant="destructive"
            onClick={confirm}
            disabled={mut.isPending}
          >
            {mut.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            İptal et
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}
