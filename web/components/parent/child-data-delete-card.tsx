"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, ShieldAlert, Trash2, Undo2 } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ParentChildLink } from "@/lib/types/parent";
import type { StudentDataDeleteStatus } from "@/lib/types/teacher";

const statusKey = (sid: number) => ["parent", "students", String(sid), "data-delete"] as const;

function trDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" });
}

function errText(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message || fallback : fallback;
}

/** KVKK: veli, çocuğunun kişisel verilerinin silinmesini isteyebilir (30 gün sonra uygulanır). */
export function ChildDataDeleteCard({ childLinks }: { childLinks: ParentChildLink[] }) {
  return (
    <Card>
      <div className="px-5 py-3 border-b border-border">
        <h2 className="font-semibold inline-flex items-center gap-1.5">
          <ShieldAlert className="size-4 text-rose-700" aria-hidden />
          Çocuğumun verilerinin silinmesi
        </h2>
        <p className="text-xs text-muted-foreground mt-0.5">
          KVKK kapsamında çocuğunuzun kişisel verilerinin silinmesini isteyebilirsiniz.
          Talep 30 gün sonra uygulanır; bu süre içinde iptal edebilirsiniz.
        </p>
      </div>
      <ul className="divide-y divide-border">
        {childLinks.map((c) => (
          <ChildDeleteRow key={c.student_id} child={c} />
        ))}
      </ul>
    </Card>
  );
}

function ChildDeleteRow({ child }: { child: ParentChildLink }) {
  const qc = useQueryClient();
  const [open, setOpen] = React.useState(false);
  const q = useQuery<StudentDataDeleteStatus>({
    queryKey: statusKey(child.student_id),
    queryFn: () => api<StudentDataDeleteStatus>(`/api/v2/parent/students/${child.student_id}/data-delete`),
    staleTime: 30_000,
  });
  const create = useMutation<{ data: StudentDataDeleteStatus }, ApiError, void>({
    mutationFn: () =>
      api(`/api/v2/parent/students/${child.student_id}/data-delete`, {
        method: "POST",
        body: JSON.stringify({ confirm: true }),
      }),
    onSuccess: (res) => {
      qc.setQueryData(statusKey(child.student_id), res.data);
      qc.invalidateQueries({ queryKey: statusKey(child.student_id) });
      setOpen(false);
      toast.success("Silme talebiniz alındı", {
        description: "Veriler 30 gün sonra silinecek; bu süre içinde iptal edebilirsiniz.",
      });
    },
    onError: (err) => toast.error(errText(err, "Talep oluşturulamadı")),
  });
  const cancel = useMutation<{ data: StudentDataDeleteStatus }, ApiError, void>({
    mutationFn: () =>
      api(`/api/v2/parent/students/${child.student_id}/data-delete/cancel`, { method: "POST" }),
    onSuccess: (res) => {
      qc.setQueryData(statusKey(child.student_id), res.data);
      qc.invalidateQueries({ queryKey: statusKey(child.student_id) });
      toast.success("Silme talebi iptal edildi");
    },
    onError: (err) => toast.error(errText(err, "İptal edilemedi")),
  });

  const st = q.data;
  const pendingReq = st?.request_id != null;

  return (
    <li className="px-5 py-3 flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0">
        <div className="text-sm font-medium break-words">{child.full_name}</div>
        {st?.scheduled_at ? (
          <div className="text-xs font-semibold text-rose-800 mt-0.5">
            {pendingReq
              ? `Silme talebi var · ${trDate(st.scheduled_at)} tarihinde silinecek`
              : `Koçluk sona erdiği için veriler ${trDate(st.scheduled_at)} tarihinde silinecek`}
          </div>
        ) : null}
      </div>
      {pendingReq ? (
        st?.can_cancel ? (
          <Button size="sm" variant="outline" disabled={cancel.isPending} onClick={() => cancel.mutate()}>
            {cancel.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Undo2 className="size-4" aria-hidden />}
            Talebi iptal et
          </Button>
        ) : null
      ) : (
        <Button size="sm" variant="outline" onClick={() => setOpen(true)} disabled={q.isLoading}>
          <Trash2 className="size-4 text-rose-700" aria-hidden />
          Verilerin silinmesini iste
        </Button>
      )}

      <Dialog open={open} onOpenChange={(o) => { if (!create.isPending) setOpen(o); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{child.full_name} — verilerin silinmesi</DialogTitle>
            <DialogDescription>
              Talep 30 gün sonra uygulanır. O tarihte çocuğunuzun adı, e-postası, telefonu,
              notları, deneme karneleri ve fotoğrafları kalıcı olarak silinir; hesabı kapanır ve
              koçluk sona erer. Bu süre içinde talebi iptal edebilirsiniz. Koçunuza bilgi verilir.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} disabled={create.isPending}>Vazgeç</Button>
            <Button
              className="bg-rose-700 text-white hover:bg-rose-800"
              disabled={create.isPending}
              onClick={() => create.mutate()}
            >
              {create.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Trash2 className="size-4" aria-hidden />}
              Silme talebini gönder
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </li>
  );
}
