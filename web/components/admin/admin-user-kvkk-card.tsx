"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, ShieldAlert } from "lucide-react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import { applyInvalidate } from "@/lib/invalidate";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Result {
  data: { request_id: number; applied: boolean; process_after: string | null };
  invalidate: string[];
}

/**
 * KVKK: kullanıcı adına silme talebi (e-posta / telefonla gelen başvuru ya da
 * giriş yapamayan, koçluğu sonlandırılmış öğrenci için). Varsayılan 30 gün
 * bekleme; "hemen uygula" ile süre atlanır.
 */
export function AdminUserKvkkCard({ userId, targetName }: { userId: number; targetName: string }) {
  const qc = useQueryClient();
  const [reason, setReason] = React.useState("");
  const [immediate, setImmediate] = React.useState(false);
  const [confirming, setConfirming] = React.useState(false);

  const mut = useMutation<Result, ApiError, void>({
    mutationFn: () =>
      api<Result>(`/api/v2/admin/users/${userId}/data-delete`, {
        method: "POST",
        body: JSON.stringify({ reason, immediate }),
      }),
    onSuccess: (res) => {
      applyInvalidate(qc, res.invalidate);
      qc.invalidateQueries({ queryKey: ["admin"] });
      setConfirming(false);
      toast.success(
        res.data.applied ? "Kullanıcının verileri silindi" : "Silme talebi açıldı",
        { description: res.data.applied ? undefined : "30 gün sonra uygulanacak (KVKK sayfasından izlenir)." },
      );
    },
    onError: (err) => toast.error(err.message || "İşlem başarısız"),
  });

  return (
    <Card className="border-rose-300">
      <CardContent className="p-5 space-y-3">
        <h2 className="font-medium text-rose-900 inline-flex items-center gap-1.5">
          <ShieldAlert className="size-4" aria-hidden /> KVKK silme talebi
        </h2>
        <p className="text-xs text-slate-700 leading-relaxed">
          {targetName} adına kişisel veri silme talebi açar. Ad, e-posta, telefon, notlar,
          karneler ve fotoğraflar kalıcı olarak silinir; sayısal kayıtlar isimsiz kalır.
          Varsayılan: 30 gün sonra uygulanır.
        </p>
        <div className="space-y-1.5">
          <Label htmlFor="kvkk-reason" className="text-xs">Gerekçe (ör. &quot;Veli e-postayla istedi&quot;)</Label>
          <Input id="kvkk-reason" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-800 cursor-pointer">
          <input type="checkbox" className="size-4" checked={immediate} onChange={(e) => setImmediate(e.target.checked)} />
          30 gün beklemeden hemen uygula
        </label>
        <Button
          className={confirming ? "bg-rose-700 text-white hover:bg-rose-800" : "bg-slate-700 text-white hover:bg-slate-800"}
          disabled={mut.isPending}
          onClick={() => (confirming ? mut.mutate() : setConfirming(true))}
        >
          {mut.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {confirming ? (immediate ? "Eminim, şimdi sil" : "Eminim, talebi aç") : "Silme talebi aç"}
        </Button>
      </CardContent>
    </Card>
  );
}
