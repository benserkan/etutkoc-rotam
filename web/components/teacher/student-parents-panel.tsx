"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Mail, Plus, Send, Trash2 } from "lucide-react";

import { getTeacherStudentParents, teacherKeys } from "@/lib/api/teacher";
import {
  useInviteParent,
  useSendParentNote,
  useUnlinkParent,
} from "@/lib/hooks/use-teacher-mutations";
import type {
  ParentLinkItem,
  ParentRelation,
  PendingParentInvitation,
  StudentParentsResponse,
} from "@/lib/types/teacher";
import { PARENT_RELATION_LABELS_TR } from "@/lib/types/teacher";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

const RELATION_OPTIONS: Array<{ value: ParentRelation; label: string }> = [
  { value: "anne", label: "Anne" },
  { value: "baba", label: "Baba" },
  { value: "vasi", label: "Vasi" },
  { value: "diger", label: "Diğer" },
];

interface Props {
  studentId: number;
}

export function StudentParentsPanel({ studentId }: Props) {
  const parentsQ = useQuery<StudentParentsResponse>({
    queryKey: teacherKeys.studentParents(studentId),
    queryFn: () => getTeacherStudentParents(studentId),
    staleTime: 30_000,
  });
  const [inviteOpen, setInviteOpen] = React.useState(false);
  const data = parentsQ.data;

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-medium">Bağlı veliler</h3>
            <Button size="sm" onClick={() => setInviteOpen(true)}>
              <Plus className="size-4" aria-hidden />
              Veli davet et
            </Button>
          </div>
          {parentsQ.isLoading && !data ? (
            <p className="text-sm text-muted-foreground">Yükleniyor…</p>
          ) : !data || data.links.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Henüz bağlı veli yok.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {data.links.map((l) => (
                <ParentLinkRow key={l.link_id} link={l} studentId={studentId} />
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {data && data.pending_invitations.length > 0 ? (
        <Card>
          <CardContent className="p-4 space-y-2">
            <h3 className="text-base font-medium">Bekleyen davetler</h3>
            <ul className="divide-y divide-border text-sm">
              {data.pending_invitations.map((p) => (
                <PendingInviteRow key={p.invitation_id} inv={p} />
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      {data && data.links.length > 0 ? (
        <ParentNoteCard
          studentId={studentId}
          parentCount={data.links.length}
        />
      ) : null}

      <p className="text-[11px] text-muted-foreground leading-relaxed">
        Veli sadece <b>tamamlama oranı, görev tipi dağılımı, streak ve
        projeksiyon</b> gibi özet metrikleri görür. Deneme net sayıları ve konu
        bazında doğru-yanlış oranları paylaşılmaz.
      </p>

      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Veli davet et</DialogTitle>
          </DialogHeader>
          <InviteForm
            studentId={studentId}
            onDone={() => setInviteOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ParentLinkRow({
  link,
  studentId,
}: {
  link: ParentLinkItem;
  studentId: number;
}) {
  const mut = useUnlinkParent(studentId);
  function onRemove() {
    if (
      !window.confirm(
        `${link.parent_full_name} (${link.parent_email}) bağlantısını kaldırmak istiyor musunuz? Veli hesabı silinmez.`,
      )
    ) {
      return;
    }
    mut.mutate({ linkId: link.link_id });
  }
  return (
    <li className="flex items-center gap-3 py-2 text-sm">
      <span className="flex-1 min-w-0">
        <span className="font-medium truncate block">
          {link.parent_full_name}
        </span>
        <span className="text-xs text-muted-foreground truncate block">
          {link.parent_email} · {PARENT_RELATION_LABELS_TR[link.relation]}
          {link.is_primary ? " · birincil" : ""}
          {link.muted ? " · sessiz" : ""}
        </span>
      </span>
      <Button
        variant="ghost"
        size="sm"
        onClick={onRemove}
        disabled={mut.isPending}
        aria-label="Bağlantıyı kaldır"
      >
        {mut.isPending ? (
          <Loader2 className="size-4 animate-spin" aria-hidden />
        ) : (
          <Trash2 className="size-4" aria-hidden />
        )}
      </Button>
    </li>
  );
}

function PendingInviteRow({ inv }: { inv: PendingParentInvitation }) {
  return (
    <li className="py-2 grid grid-cols-12 gap-2 items-center">
      <span className="col-span-7 truncate">{inv.invited_email}</span>
      <span className="col-span-2 text-xs text-muted-foreground">
        {PARENT_RELATION_LABELS_TR[inv.relation]}
      </span>
      <span className="col-span-3 text-xs text-muted-foreground tabular-nums text-right">
        son: {inv.expires_at.slice(0, 10)}
      </span>
    </li>
  );
}

function InviteForm({
  studentId,
  onDone,
}: {
  studentId: number;
  onDone: () => void;
}) {
  const mut = useInviteParent(studentId);
  const [email, setEmail] = React.useState("");
  const [relation, setRelation] = React.useState<ParentRelation>("diger");
  const [isPrimary, setIsPrimary] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const em = email.trim().toLowerCase();
    if (!em.includes("@")) {
      setError("Geçerli bir e-posta girin.");
      return;
    }
    mut.mutate(
      {
        body: {
          parent_email: em,
          relation,
          is_primary: isPrimary,
        },
      },
      { onSuccess: () => onDone() },
    );
  }
  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor="iv-email">E-posta</Label>
        <Input
          id="iv-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="iv-relation">İlişki</Label>
          <select
            id="iv-relation"
            value={relation}
            onChange={(e) => setRelation(e.target.value as ParentRelation)}
            className={cn(
              "h-9 w-full rounded-md border border-input bg-background px-2 text-sm",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            {RELATION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm h-9 mt-6">
          <input
            type="checkbox"
            checked={isPrimary}
            onChange={(e) => setIsPrimary(e.target.checked)}
          />
          Birincil veli
        </label>
      </div>
      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
      <div className="flex items-center justify-end gap-2 pt-2">
        <Button type="button" variant="ghost" onClick={onDone} disabled={mut.isPending}>
          İptal
        </Button>
        <Button type="submit" disabled={mut.isPending}>
          {mut.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : null}
          Davet gönder
        </Button>
      </div>
    </form>
  );
}

function ParentNoteCard({
  studentId,
  parentCount,
}: {
  studentId: number;
  parentCount: number;
}) {
  const [text, setText] = React.useState("");
  const mut = useSendParentNote(studentId);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (trimmed.length < 10) return;
    if (
      !window.confirm(
        `Notu ${parentCount} veliye göndermek istediğinizden emin misiniz?`,
      )
    ) {
      return;
    }
    mut.mutate(
      { body: { body: trimmed } },
      {
        onSuccess: () => {
          setText("");
        },
      },
    );
  }

  const remaining = 2000 - text.length;
  const tooShort = text.trim().length > 0 && text.trim().length < 10;

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-start gap-3">
          <Mail
            className="size-5 text-indigo-500 flex-shrink-0 mt-0.5"
            aria-hidden
          />
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold">Veliye Not Gönder</h3>
            <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
              Yazdığınız not, bağlı tüm velilere e-posta + (varsa) WhatsApp ile
              iletilir. Öğrenci bu notu görmez.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-2">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            minLength={10}
            maxLength={2000}
            rows={4}
            placeholder="Velilere özel not (10–2000 karakter)..."
            className="w-full px-3 py-2 border border-border rounded-md text-sm bg-background focus:outline-none focus:ring-2 focus:ring-ring/30 focus:border-ring resize-y"
          />
          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span className="italic">
              Not bu öğretmen-veli ekseninde kalır; öğrenci tarafına sızdırılmaz.
            </span>
            <span
              className={cn(
                "tabular-nums",
                tooShort && "text-rose-500",
                remaining < 100 && remaining >= 0 && "text-amber-500",
              )}
            >
              {tooShort ? "en az 10 karakter · " : ""}
              {text.length} / 2000
            </span>
          </div>
          <div className="flex justify-end pt-1">
            <Button
              type="submit"
              disabled={mut.isPending || text.trim().length < 10}
            >
              {mut.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Send className="size-4" aria-hidden />
              )}
              {parentCount === 1
                ? "1 veliye gönder"
                : `${parentCount} veliye gönder`}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
