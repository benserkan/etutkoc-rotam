"use client";

import * as React from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";

interface ActionResult {
  ok: boolean;
  status: string;
  message: string;
}

export function OfferActions({ token }: { token: string }) {
  const [busy, setBusy] = React.useState<"accept" | "decline" | null>(null);
  const [done, setDone] = React.useState<{ ok: boolean; message: string } | null>(null);
  const [showDecline, setShowDecline] = React.useState(false);
  const [reason, setReason] = React.useState("");

  async function act(kind: "accept" | "decline") {
    setBusy(kind);
    try {
      const res = await api<ActionResult>(`/api/v2/offers/${token}/${kind}`, {
        method: "POST",
        ...(kind === "decline" ? { body: JSON.stringify({ reason }) } : {}),
      });
      setDone({ ok: res.ok, message: res.message });
    } catch (e) {
      setDone({
        ok: false,
        message: e instanceof ApiError ? e.detail?.message ?? "İşlem yapılamadı." : "Sunucuya ulaşılamadı.",
      });
    } finally {
      setBusy(null);
    }
  }

  if (done) {
    return (
      <div className="flex flex-col items-center gap-2 py-2 text-center">
        {done.ok ? (
          <CheckCircle2 className="size-9 text-emerald-600" aria-hidden />
        ) : (
          <XCircle className="size-9 text-rose-600" aria-hidden />
        )}
        <p className="text-sm text-muted-foreground">{done.message}</p>
      </div>
    );
  }

  if (showDecline) {
    return (
      <div className="space-y-3">
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={2}
          maxLength={500}
          placeholder="Geri bildiriminiz (opsiyonel)"
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <div className="flex gap-2">
          <Button variant="destructive" disabled={busy !== null} onClick={() => act("decline")} className="flex-1">
            {busy === "decline" ? <Loader2 className="animate-spin" /> : null}
            Reddet
          </Button>
          <Button variant="ghost" disabled={busy !== null} onClick={() => setShowDecline(false)}>
            Geri
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <Button disabled={busy !== null} onClick={() => act("accept")} className="w-full">
        {busy === "accept" ? <Loader2 className="animate-spin" /> : null}
        Teklifi kabul et
      </Button>
      <Button variant="outline" disabled={busy !== null} onClick={() => setShowDecline(true)} className="w-full">
        Reddet
      </Button>
    </div>
  );
}
